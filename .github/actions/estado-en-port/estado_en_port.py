"""Fija en el catalogo el ESTADO de los artefactos de una etiqueta, y solo lo que el estado cambia.

POR QUE ES UNA PIEZA APARTE Y NO MAS CODIGO DENTRO DE LA PUBLICACION. Publicar y cambiar de estado
son dos actos distintos: la publicacion escribe la ficha ENTERA -- identidad, propietario, sha,
digesto, etiqueta -- porque acaba de sellar el paquete; una transicion de estado no vuelve a sellar
nada y por tanto NO DEBE TOCAR ninguno de esos campos. Escribir la ficha entera en una promocion
seria reescribir con datos releidos lo que ya estaba firmado.

EL DEFECTO QUE CIERRA, medido en el catalogo real: promocionar quitaba la marca de prelanzamiento
del release -- con lo que el artefacto SI entraba al catalogo instalable -- y no tocaba Port. La
ficha se quedaba en `conformant` diciendo que el artefacto no se distribuye, mientras cualquiera ya
podia instalarlo por nombre. El catalogo de metadata contradecia al catalogo instalable, y quien
gobierna mirando fichas veia lo contrario de lo que pasaba.

QUE TOCA, EXACTAMENTE: `status` y los dos campos que SE DERIVAN de el -- `en_marketplace` y
`install_hint` --. No es una excepcion a «solo el estado»: una ficha que cambie de estado y conserve
la pista de instalacion del estado anterior vuelve a mentir, que es el defecto de arriba al reves.
Todo lo demas se conserva porque Port admite escritura POR FUSION.

QUE ARTEFACTOS ALCANZA: los que la publicacion dejo apuntando a esta ETIQUETA. Es el mismo criterio
de pertenencia que uso la publicacion -- ella escribio ese `ref` -- asi que las dos piezas coinciden
sin tener que repetir aqui la resolucion de unidades.

PARA QUE SIRVE MAS ALLA DE LA PROMOCION. Los flujos de suspension, reactivacion, obsolescencia y
retirada hacen exactamente esto mismo con otro estado, asi que reciben el estado como argumento en
vez de tenerlo escrito dentro.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.error
import urllib.parse
import urllib.request

from validador_agentico.adaptadores import registro
from validador_agentico.dominio import ficha
from validador_agentico.dominio.politica import Promocion, promocion_declarada

log = logging.getLogger(__name__)

API_PORT = "https://api.port.io"
BLUEPRINT = "artefacto_agentico"
_TIEMPO_LIMITE_S = 30
# `merge` conserva las propiedades que este payload no trae: es lo que permite tocar el estado sin
# reescribir la ficha entera.
_RUTA_ESCRITURA = f"/v1/blueprints/{BLUEPRINT}/entities?upsert=true&merge=true"
_RUTA_LECTURA = f"/v1/blueprints/{BLUEPRINT}/entities"
_MAX_CUERPO_ERROR_CHARS = 200


class FallaDePort(RuntimeError):
    """El catalogo no respondio o respondio un error. La decide `main()`, no las funciones."""


def _peticion(ruta: str, token: str, cuerpo: dict | None = None) -> dict:
    peticion = urllib.request.Request(
        API_PORT + ruta,
        data=None if cuerpo is None else json.dumps(cuerpo).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="GET" if cuerpo is None else "POST")
    try:
        with urllib.request.urlopen(peticion, timeout=_TIEMPO_LIMITE_S) as respuesta:
            return json.loads(respuesta.read() or b"{}")
    except urllib.error.HTTPError as fallo:
        detalle = fallo.read()[:_MAX_CUERPO_ERROR_CHARS].decode("utf-8", "replace")
        raise FallaDePort(f"HTTP {fallo.code}: {detalle}") from fallo
    except (urllib.error.URLError, TimeoutError) as fallo:
        raise FallaDePort(f"sin respuesta: {fallo}") from fallo
    except json.JSONDecodeError as fallo:
        raise FallaDePort(f"respuesta que no es JSON: {fallo}") from fallo


def fichas_de_la_etiqueta(entidades: list[dict], etiqueta: str) -> list[dict]:
    """Las fichas que apuntan a `etiqueta`. Regla pura: recibe las entidades ya leidas.

    El `ref` es lo que la publicacion escribio para decir DE QUE VERSION es esta ficha, asi que
    filtrar por el alcanza exactamente a los artefactos que esa publicacion sello -- ni los vecinos
    del repositorio ni las versiones anteriores del mismo artefacto --.
    """
    return [e for e in entidades if (e.get("properties") or {}).get("ref") == etiqueta]


def cambio_de_estado(entidad: dict, estado: str, promocion: Promocion, repositorio: str,
                     nombre_plugin: str) -> dict:
    """El payload de fusion que lleva la ficha al nuevo estado. Regla pura: no llama a nadie.

    `nombre_plugin` puede venir vacio -- una etiqueta corta `vX.Y.Z` no lo lleva dentro --. En ese
    caso el artefacto no puede pertenecer a ningun plugin resoluble desde aqui, y la pista cae en la
    rama sin catalogo, que es la conservadora: manda a verificar el paquete en vez de prometer un
    `plugin install` que quiza no resuelva.
    """
    propiedades = entidad.get("properties") or {}
    tipo = str(propiedades.get("tipo", ""))
    distribuido = ficha.esta_distribuido(estado, promocion, bool(nombre_plugin), tipo)
    return {
        "identifier": entidad["identifier"],
        "properties": {
            "status": estado,
            "en_marketplace": distribuido,
            "install_hint": ficha.pista_de_instalacion(
                tipo, str(propiedades.get("ruta", "")), distribuido, repositorio,
                str(propiedades.get("sha", "")), str(propiedades.get("ref", "")), nombre_plugin),
        },
    }


def _parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fija el estado en el catalogo de los artefactos de una etiqueta.")
    parser.add_argument("--etiqueta", required=True,
                        help="la etiqueta cuyas fichas cambian de estado")
    parser.add_argument("--estado", required=True,
                        help="el estado del ciclo de vida al que pasan")
    parser.add_argument("--repositorio", required=True)
    parser.add_argument("--nombre-plugin", default="",
                        help="el plugin al que pertenecen; vacio si la etiqueta no lo nombra")
    parser.add_argument("--promocion", required=True,
                        help="politica de promocion al catalogo")
    parser.add_argument("--token", required=True)
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Activa logging DEBUG (detalles internos de ejecucion).")
    return parser.parse_args()


def main() -> int:
    argumentos = _parsear_argumentos()
    registro.configurar(verboso=argumentos.verbose)
    promocion = promocion_declarada({"promocion_al_catalogo": argumentos.promocion})

    try:
        respuesta = _peticion(_RUTA_LECTURA, argumentos.token)
    except FallaDePort as fallo:
        log.error("no se pudieron leer las fichas del catalogo: %s", fallo)
        return 1

    objetivo = fichas_de_la_etiqueta(respuesta.get("entities") or [], argumentos.etiqueta)
    if not objetivo:
        log.warning("ninguna ficha del catalogo apunta a %s: no hay estado que fijar",
                    argumentos.etiqueta)
        return 0

    fallos = 0
    for entidad in objetivo:
        cambio = cambio_de_estado(entidad, argumentos.estado, promocion, argumentos.repositorio,
                                  argumentos.nombre_plugin)
        try:
            _peticion(_RUTA_ESCRITURA, argumentos.token, cambio)
        except FallaDePort as fallo:
            log.error("ficha %s no paso a %s: %s", entidad["identifier"], argumentos.estado, fallo)
            fallos += 1
            continue
        log.info("ficha %-50s -> %s (en_marketplace=%s)", entidad["identifier"], argumentos.estado,
                 cambio["properties"]["en_marketplace"])

    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
