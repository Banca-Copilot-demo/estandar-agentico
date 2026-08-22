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
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

# Cuanto se cita del cuerpo de una respuesta de error: lo justo para diagnosticar sin volcar
# una pagina de HTML al log.
_MAX_CUERPO_ERROR_CHARS = 200
# El `tipo` con el que el predicado firmado marca un skill.
_TIPO_SKILL = "skill"

API_PORT = "https://api.port.io"
BLUEPRINT = "artefacto_agentico"
# Quien FIRMA las atestaciones: el workflow reutilizable del estandar, no el repo del dominio.
SIGNER = "Banca-Copilot-demo/estandar-agentico"
# `name` del catalogo del marketplace, el que resuelve `<plugin>@<catalogo>`.
CATALOGO = "agentico"
# Donde espera cada cliente un prompt. `commands/` en el origen; en el destino cambia por cliente.
_DESTINO_PROMPT = ".github/prompts"
_TIEMPO_LIMITE_S = 30
# `upsert` actualiza si ya existe, y `merge` conserva las propiedades que este payload no trae.
_RUTA_ENTIDADES = f"/v1/blueprints/{BLUEPRINT}/entities?upsert=true&merge=true"

# Los tipos que un plugin TRANSPORTA. Agent Plugins v1 cubre skills y MCP; Copilot documenta
# cinco componentes -- agents, skills, hooks, .mcp.json, lsp.json --. NI `prompt` NI `instructions`
# estan en ninguna de las dos listas, asi que viajan por otro canal aunque vivan en el mismo
# repositorio y esten dentro del paquete sellado.
_TIPOS_EN_PLUGIN = frozenset({"skill", "agent", "mcp", "hooks"})


def _pista_de_instalacion(artefacto: dict, en_marketplace: bool, repositorio: str,
                          sha: str, etiqueta: str, nombre_plugin: str) -> str:
    """El COMANDO exacto que el consumidor ejecuta. Siempre un comando: una descripcion en prosa
    obliga al consumidor a averiguar como se instala, que es justo lo que la ficha evita."""
    if en_marketplace:
        # Se instala el PLUGIN, no el artefacto: un plugin se instala completo. Poner aqui el id del
        # artefacto daba un comando que no resuelve contra ninguna entrada del marketplace.
        return f"copilot plugin install {nombre_plugin}@{CATALOGO}"
    if artefacto["tipo"] == _TIPO_SKILL:
        # La forma es `gh skill install <repo> <skill[@version]>`, MEDIDO ejecutandolo: el nombre del
        # skill es un argumento aparte, no parte del repositorio. Concatenar la ruta al repositorio
        # -- como hacia la primera version -- produce un comando que falla con «must specify a skill
        # name». El nombre es el DIRECTORIO del skill, que la especificacion obliga a que coincida
        # con su `name`.
        nombre = artefacto["ruta"].rsplit("/", 2)[-2]
        return f"gh skill install {repositorio} {nombre}@{etiqueta}"

    # Un `prompt` no lo instala ninguna herramienta oficial: no es componente de plugin y `gh skill`
    # es exclusivo de skills. Se trae el archivo FIJADO AL SHA -- no a la etiqueta -- porque el sha
    # es lo que quedo sellado, y el nombre del destino lo fija el cliente, no nosotros.
    destino = f"{_DESTINO_PROMPT}/{artefacto['ruta'].rsplit('/', 1)[-1]}"
    return (f"curl -fsSL https://raw.githubusercontent.com/{repositorio}/{sha}/"
            f"{artefacto['ruta']} -o {destino}")


def _pista_de_verificacion(artefacto: dict, en_marketplace: bool, repositorio: str,
                           paquete_o_archivo: str) -> str:
    """Como comprobar el sello ANTES de confiar en lo instalado.

    MEDIDO: ni `copilot plugin install` ni `gh skill install` documentan verificacion de
    atestaciones, y el `--help` de `gh skill install` no la menciona. Asi que verificar es un paso
    EXPLICITO, y la ficha tiene que decir como -- incluido el `--signer-repo`, sin el cual la
    verificacion falla con un mensaje que no menciona al firmante.
    """
    if en_marketplace or artefacto["tipo"] == _TIPO_SKILL:
        return (f"gh attestation verify <paquete>.tar.gz --repo {repositorio} "
                f"--signer-repo {SIGNER}")
    # Un archivo copiado fuera del paquete no se verifica contra la atestacion: se compara su sha256
    # contra el que quedo firmado en el predicado.
    return f"sha256sum {paquete_o_archivo}  # debe dar {artefacto.get('sha256', '')}"


def _entidad(artefacto: dict, veredicto: dict, argumentos: argparse.Namespace) -> dict:
    en_marketplace = veredicto["inventario"]["tiene_plugin"] and \
        artefacto["tipo"] in _TIPOS_EN_PLUGIN
    return {
        "identifier": artefacto["id"],
        "title": f"{artefacto['id']} ({artefacto['tipo']})",
        "properties": {
            "tipo": artefacto["tipo"],
            # `conformant` y no `certified`: la promocion la decide G5, despues, y no este paso.
            "status": "conformant",
            "owner_team": artefacto["owner_team"],
            "owner_contact": artefacto["owner_contact"],
            "data_classification": artefacto["data_classification"],
            "standard_version": artefacto["standard_version"],
            "repo": argumentos.repositorio,
            "ref": argumentos.etiqueta,
            "sha": argumentos.sha,
            "digest": argumentos.digest,
            "install_hint": _pista_de_instalacion(
                artefacto, en_marketplace, argumentos.repositorio, argumentos.sha,
                argumentos.etiqueta, veredicto["inventario"].get("nombre_plugin", "")),
            "verify_hint": _pista_de_verificacion(
                artefacto, en_marketplace, argumentos.repositorio, artefacto["ruta"]),
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
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Activa logging DEBUG (detalles internos de ejecucion).")
    return parser.parse_args()


def _configurar_logging(verboso: bool) -> None:
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
    logging.getLogger().setLevel(logging.DEBUG if verboso else logging.INFO)
    logging.getLogger().addHandler(manejador)


def main() -> int:
    argumentos = _parsear_argumentos()
    _configurar_logging(verboso=argumentos.verbose)
    veredicto = json.loads(argumentos.veredicto.read_text(encoding="utf-8"))
    artefactos = veredicto.get("artefactos") or []

    if not artefactos:
        log.info("el predicado no declara artefactos: no hay ficha que publicar")
        return 0

    fallos = 0
    for artefacto in artefactos:
        resultado = _publicar(_entidad(artefacto, veredicto, argumentos), argumentos.token)
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
