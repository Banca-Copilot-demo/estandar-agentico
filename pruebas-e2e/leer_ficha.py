"""Lee una ficha del catalogo y la emite como variables de entorno.

Es el paso 1 del camino de instalacion hecho por un programa: NO inventa ningun dato ni relee el
repositorio, lee exactamente lo que el catalogo publica -- que es lo que vera el desarrollador.

Las credenciales llegan por entorno, no por argumento: un `clientSecret` en la linea de comandos
queda en el historial del shell y en la tabla de procesos.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import urllib.request

log = logging.getLogger(__name__)

API_POR_DEFECTO = "https://api.port.io"
BLUEPRINT = "artefacto_agentico"
_TIEMPO_LIMITE_S = 30

# Cuantos `/` hay que saltarse en la pista de instalacion de un prompt para llegar a la ruta del
# artefacto. Son los de `curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/<sha>/<ruta>`:
# `https:`, el vacio de `//`, el host, el owner, el repo y el sha.
#
# ES UN ACOPLE CON `dominio/ficha.py`, y por eso lleva nombre en vez de ir suelto en la expresion
# (P11): quien cambie ahi la forma de la URL tiene que cambiar este numero, y con un `6` incrustado
# a mitad de un `split` no hay forma de que se entere -- esto no falla, devuelve otra ruta --.
_SEGMENTOS_ANTES_DE_LA_RUTA = 6


def _token(api: str) -> str:
    peticion = urllib.request.Request(
        f"{api}/v1/auth/access_token",
        data=json.dumps({"clientId": os.environ["PORT_CLIENT_ID"],
                         "clientSecret": os.environ["PORT_CLIENT_SECRET"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(peticion, timeout=_TIEMPO_LIMITE_S) as respuesta:
        return json.load(respuesta)["accessToken"]


def _ruta_del_prompt(pista: str) -> str:
    """La ruta del artefacto no es un campo de la ficha: viene dentro del comando de instalacion de
    un prompt, que es el unico tipo cuyo canal la necesita."""
    if " -o " not in pista:
        return ""
    return pista.split("/", _SEGMENTOS_ANTES_DE_LA_RUTA)[-1].split(" -o ")[0]


def _configurar_logging(verboso: bool) -> None:
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
    logging.getLogger().setLevel(logging.DEBUG if verboso else logging.INFO)
    logging.getLogger().addHandler(manejador)


def _parsear_argumentos() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("identificador", help="`id` del artefacto cuya ficha se lee")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Activa logging DEBUG (detalles internos de ejecucion).")
    return ap.parse_args()


def main() -> int:
    argumentos = _parsear_argumentos()
    _configurar_logging(verboso=argumentos.verbose)

    api = os.environ.get("PORT_API", API_POR_DEFECTO)
    log.debug("consultando %s para el artefacto %s", api, argumentos.identificador)
    peticion = urllib.request.Request(
        f"{api}/v1/blueprints/{BLUEPRINT}/entities/{argumentos.identificador}",
        headers={"Authorization": f"Bearer {_token(api)}"})
    with urllib.request.urlopen(peticion, timeout=_TIEMPO_LIMITE_S) as respuesta:
        propiedades = json.load(respuesta)["entity"]["properties"]

    campos = {
        "FICHA_STATUS": propiedades.get("status", ""),
        "FICHA_TIPO": propiedades.get("tipo", ""),
        "FICHA_REPO": propiedades.get("repo", ""),
        "FICHA_REF": propiedades.get("ref", ""),
        "FICHA_SHA": propiedades.get("sha", ""),
        "FICHA_SHA256": propiedades.get("sha256_archivo", ""),
        "FICHA_MARKETPLACE": str(propiedades.get("en_marketplace", "")),
        "FICHA_RUTA": _ruta_del_prompt(propiedades.get("install_hint", "")),
    }
    for clave, valor in campos.items():
        print(f'{clave}="{valor}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
