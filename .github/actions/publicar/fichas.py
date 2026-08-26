"""Publica en Port una ficha por artefacto, construida del PREDICADO FIRMADO.

POR QUE ES UN SCRIPT Y NO BASH. Hay que leer un JSON, derivar campos por artefacto y hacer una
llamada por cada uno. En bash serian varias invocaciones a `python3 -c` con el JSON interpolado en
la linea de comandos: el patron fragil que ya nos rompio dos veces.

POR QUE SE LEE DEL PREDICADO Y NO DEL REPOSITORIO. El predicado es lo que se firmo. Si la ficha se
construyera releyendo los archivos, podria decir algo distinto de lo sellado y habria dos fuentes de
verdad sobre el mismo artefacto -- el problema que el sello existe para eliminar.

UN FALLO AQUI NO DESHACE LA PUBLICACION. El release y las atestaciones ya existen y son
inmutables; la ficha es la vitrina. Si Port no responde, se avisa y se sigue: el artefacto YA es
instalable y el catalogo se pone al dia en la siguiente publicacion.

LA FICHA SE VALIDA CONTRA EL BLUEPRINT ANTES DE ENVIARLA, y esto corrige una asimetria de nuestro
propio diseno: las dos proyecciones del marketplace se validan contra su esquema ANTES de escribirse
-- «publicar un indice que algun cliente no sabra instalar es peor que no publicar» -- y la ficha, en
cambio, se enviaba a ciegas. Un payload malformado lo descubria la API de Port, con un HTTP 4xx en el
ultimo paso de la publicacion y un mensaje escrito por un tercero. Validar aqui convierte eso en un
fallo nuestro, dicho en nuestros terminos, antes de la llamada.

Y NO HACE FALTA UN ESQUEMA NUEVO: el blueprint YA lleva dentro el fragmento que describe las
propiedades, en vocabulario de JSON Schema. Escribir un segundo esquema para lo mismo seria la
duplicacion que G2 prohibe, y divergiria del blueprint en la primera modificacion.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path

from jsonschema import Draft202012Validator

# El logging se configura con el registro del validador, que este job ya tiene instalado -- la accion
# hace `pip install` del paquete antes de llegar aqui --. Era la SEXTA copia de la misma funcion en el
# repositorio: cuatro dentro del validador (ya unificadas), una en el indice y esta.
from validador_agentico.adaptadores import registro
from validador_agentico.dominio import ficha
from validador_agentico.dominio.politica import ESTADO_AL_PUBLICAR, promocion_declarada

# Reexportado a proposito: `plugin_que_contiene` era una regla pura viviendo en este adaptador, y
# ahora la comparte con la pieza que fija el estado en transiciones posteriores.
plugin_que_contiene = ficha.plugin_que_contiene
CATALOGO = ficha.CATALOGO

log = logging.getLogger(__name__)

# El blueprint vive en el repositorio del estandar, tres niveles por encima de esta accion. Es la misma
# forma de referencia que usa el `pip install` de la accion, asi que la topologia ya es parte del
# contrato de este directorio y no se introduce nada nuevo.
_BLUEPRINT_DEL_CATALOGO = Path(__file__).resolve().parents[3] / "port" / \
    "blueprint-artefacto-agentico.json"

# Cuanto se cita del cuerpo de una respuesta de error: lo justo para diagnosticar sin volcar
# una pagina de HTML al log.
_MAX_CUERPO_ERROR_CHARS = 200

API_PORT = "https://api.port.io"
BLUEPRINT = "artefacto_agentico"
# Quien FIRMA las atestaciones: el workflow reutilizable del estandar, no el repo del dominio.
SIGNER = "Banca-Copilot-demo/estandar-agentico"
_TIEMPO_LIMITE_S = 30
# `upsert` actualiza si ya existe, y `merge` conserva las propiedades que este payload no trae.
_RUTA_ENTIDADES = f"/v1/blueprints/{BLUEPRINT}/entities?upsert=true&merge=true"

def _pista_de_verificacion(artefacto: dict, viaja_en_un_paquete: bool, repositorio: str,
                           paquete_o_archivo: str) -> str:
    """Como comprobar el sello ANTES de confiar en lo instalado.

    MEDIDO: ni `copilot plugin install` ni `gh skill install` documentan verificacion de
    atestaciones, y el `--help` de `gh skill install` no la menciona. Asi que verificar es un paso
    EXPLICITO, y la ficha tiene que decir como -- incluido el `--signer-repo`, sin el cual la
    verificacion falla con un mensaje que no menciona al firmante.

    LA CONDICION ES SI EL CONSUMIDOR ACABA CON UN PAQUETE, no si el artefacto se distribuye. Son
    cosas distintas desde que publicar y distribuir se separaron: un artefacto Conforme dentro de un
    plugin NO esta en el catalogo y aun asi se entrega empaquetado -- descargando el release --, asi
    que lo que tiene que verificar es la atestacion y no un sha256 suelto.
    """
    if viaja_en_un_paquete or artefacto["tipo"] == ficha.TIPO_SKILL:
        return (f"gh attestation verify <paquete>.tar.gz --repo {repositorio} "
                f"--signer-repo {SIGNER}")
    # Un archivo copiado fuera del paquete no se verifica contra la atestacion: se compara su sha256
    # contra el que quedo firmado en el predicado.
    return f"sha256sum {paquete_o_archivo}  # debe dar {artefacto.get('sha256', '')}"


def _entidad(artefacto: dict, veredicto: dict, argumentos: argparse.Namespace) -> dict:
    # EL PLUGIN DE ESTE ARTEFACTO, no el del repositorio. `tiene_plugin` es del repositorio entero, y
    # usarlo aqui daba por instalable-por-catalogo a un artefacto suelto SIN plugin solo porque un
    # vecino si lo tenia -- y entonces la pista salia como `plugin install @agentico`, con el nombre
    # vacio: un comando que no resuelve. Con la publicacion por artefacto suelto individual el caso
    # deja de ser teorico, porque en un mismo repositorio conviven sueltos con manifiesto y sin el.
    plugin_del_artefacto = plugin_que_contiene(artefacto["ruta"], veredicto.get("plugins") or [])

    # DISTRIBUIDO NO ES LO MISMO QUE «ES COMPONENTE DE UN PLUGIN», y confundirlos hacia que la ficha
    # de un artefacto Conforme prometiera un `plugin install` que no resuelve. Lo decide el ESTADO
    # combinado con la politica, y la regla vive en el dominio porque la comparte con la pieza que
    # fija el estado en las transiciones posteriores.
    en_marketplace = ficha.esta_distribuido(
        ESTADO_AL_PUBLICAR, argumentos.promocion, bool(plugin_del_artefacto), artefacto["tipo"])
    return {
        "identifier": artefacto["id"],
        "title": f"{artefacto['id']} ({artefacto['tipo']})",
        "properties": {
            "tipo": artefacto["tipo"],
            # `conformant` y no `certified`: la promocion la decide G5, despues, y no este paso.
            "status": ESTADO_AL_PUBLICAR,
            "owner_team": artefacto["owner_team"],
            "owner_contact": artefacto["owner_contact"],
            "data_classification": artefacto["data_classification"],
            "standard_version": artefacto["standard_version"],
            "repo": argumentos.repositorio,
            # La necesita la pieza que fija el estado despues: sin ella una transicion no puede
            # reconstruir la pista de instalacion y la dejaria en la del estado anterior.
            "ruta": artefacto["ruta"],
            "ref": argumentos.etiqueta,
            "sha": argumentos.sha,
            "digest": argumentos.digest,
            "install_hint": ficha.pista_de_instalacion(
                artefacto["tipo"], artefacto["ruta"], en_marketplace, argumentos.repositorio,
                argumentos.sha, argumentos.etiqueta, plugin_del_artefacto),
            "verify_hint": _pista_de_verificacion(
                artefacto, bool(plugin_del_artefacto), argumentos.repositorio, artefacto["ruta"]),
            "sha256_archivo": artefacto.get("sha256", ""),
            # Solo lo trae un `mcp`, y solo cuando su credencial exige que alguien la conceda. Va en
            # la ficha porque ningun cliente lo muestra: es un campo propio sin convencion, y su
            # consumidor es el catalogo y el instalador.
            **_custodia_de_la_credencial(veredicto),
            "en_marketplace": en_marketplace,
        },
    }


def _custodia_de_la_credencial(veredicto: dict) -> dict:
    """Quien concede el acceso, si el artefacto declara una credencial que alguien tiene que dar.

    El `owner_team` del artefacto es quien lo PUBLICO. El token del servicio lo da quien ADMINISTRA
    ese servicio, y sin ese dato el consumidor acaba ante un prompt del cliente sin saber a quien
    escribir. Con `oauth` no aplica: se autentica con su propia identidad.
    """
    propiedad = veredicto.get("credencial_ownership") or {}
    if not propiedad:
        return {}
    return {"credential_owner": propiedad.get("credential_owner", ""),
            "access_request_url": propiedad.get("access_request_url", "")}


def _validador_del_blueprint() -> Draft202012Validator | None:
    """El validador de las propiedades de una ficha, sacado del propio blueprint.

    `None` si el blueprint no se puede leer. Es degradacion deliberada y NO un error: este script
    corre despues de que el release y las atestaciones ya existan, asi que abortar aqui no protegeria
    nada -- el artefacto ya es instalable -- y dejaria el catalogo desactualizado por un problema de
    lectura de archivo. Se avisa, que es lo que hace el resto del modulo ante un fallo de vitrina.
    """
    try:
        blueprint = json.loads(_BLUEPRINT_DEL_CATALOGO.read_text(encoding="utf-8"))
    except OSError as fallo:
        log.warning("no se pudo leer el blueprint (%s): las fichas se envian sin validar", fallo)
        return None
    except json.JSONDecodeError as fallo:
        log.warning("el blueprint no es JSON valido (%s): las fichas se envian sin validar", fallo)
        return None
    return Draft202012Validator(blueprint["schema"])


def _defectos_de_forma(entidad: dict, validador: Draft202012Validator | None) -> list[str]:
    """Los defectos de las propiedades de la ficha, ya legibles. Lista vacia = conforme."""
    if validador is None:
        return []
    return [f"{'.'.join(str(t) for t in fallo.path) or '(raiz)'}: {fallo.message}"
            for fallo in sorted(validador.iter_errors(entidad["properties"]),
                                key=lambda f: list(f.path))]


def _publicar(entidad: dict, token: str) -> str:
    peticion = urllib.request.Request(
        API_PORT + _RUTA_ENTIDADES,
        data=json.dumps(entidad).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=_TIEMPO_LIMITE_S) as respuesta:
            return f"HTTP {respuesta.status}"
    except urllib.error.HTTPError as fallo:
        return f"HTTP {fallo.code}: {fallo.read()[:_MAX_CUERPO_ERROR_CHARS].decode('utf-8', 'replace')}"
    except (urllib.error.URLError, TimeoutError) as fallo:
        return f"sin respuesta: {fallo}"


def _parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publica las fichas del catalogo en Port.")
    parser.add_argument("--veredicto", type=Path, required=True,
                        help="predicado firmado del que se construye la ficha")
    parser.add_argument("--repositorio", required=True)
    parser.add_argument("--etiqueta", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--subruta", required=True,
                        help="subruta de la unidad que ESTA publicacion sella; `.` es el "
                             "repositorio entero o su conjunto suelto")
    parser.add_argument("--promocion", required=True,
                        help="politica de promocion al catalogo ya resuelta por la accion")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Activa logging DEBUG (detalles internos de ejecucion).")
    argumentos = parser.parse_args()
    # Se convierte aqui y no en cada uso: `promocion_declarada` degrada a la politica MAS
    # RESTRICTIVA ante un valor que no reconoce, asi que un fallo de cableado deja de distribuir en
    # vez de distribuir de mas.
    argumentos.promocion = promocion_declarada({"promocion_al_catalogo": argumentos.promocion})
    return argumentos


def main() -> int:
    argumentos = _parsear_argumentos()
    registro.configurar(verboso=argumentos.verbose)
    veredicto = json.loads(argumentos.veredicto.read_text(encoding="utf-8"))
    unidades = veredicto.get("plugins") or []

    # SOLO LOS ARTEFACTOS DE LA UNIDAD QUE SE PUBLICA. El predicado firmado es del REPOSITORIO
    # entero -- lo valida entero, por diseno --, asi que iterarlo tal cual reescribia la ficha de
    # todos los vecinos con la etiqueta, el sha y el digesto de una version que no es la suya.
    todos = veredicto.get("artefactos") or []
    artefactos = [a for a in todos if ficha.es_de_la_unidad(a["ruta"], argumentos.subruta, unidades)]
    if len(artefactos) != len(todos):
        log.info("la publicacion sella la unidad %s: %d de %d artefactos del predicado",
                 argumentos.subruta, len(artefactos), len(todos))

    if not artefactos:
        log.info("la unidad %s no declara artefactos: no hay ficha que publicar", argumentos.subruta)
        return 0

    validador = _validador_del_blueprint()
    fallos = 0
    for artefacto in artefactos:
        entidad = _entidad(artefacto, veredicto, argumentos)
        defectos = _defectos_de_forma(entidad, validador)
        if defectos:
            # NO se envia: Port lo rechazaria igual, y el mensaje vendria de su API en vez de decir
            # que campo de NUESTRA ficha esta mal.
            for defecto in defectos:
                log.error("ficha %s no cumple el blueprint — %s", artefacto["id"], defecto)
            fallos += 1
            continue
        resultado = _publicar(entidad, argumentos.token)
        log.info("ficha %-50s %s", artefacto["id"], resultado)
        if not resultado.startswith("HTTP 2"):
            fallos += 1

    if fallos:
        # Aviso y no error: el release y las atestaciones ya son inmutables, y el artefacto YA es
        # instalable. La ficha se pone al dia en la siguiente publicacion.
        print(f"::warning::{fallos} ficha(s) no se pudieron publicar en el catalogo. "
              "El artefacto ya es instalable: la vitrina se pone al dia despues.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
