"""Lee una ficha del catalogo y la emite como variables de entorno.

Es el paso 1 del camino de instalacion hecho por un programa: NO inventa ningun dato ni relee el
repositorio, lee exactamente lo que el catalogo publica -- que es lo que vera el desarrollador.

Las credenciales llegan por entorno, no por argumento: un `clientSecret` en la linea de comandos
queda en el historial del shell y en la tabla de procesos.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

API_POR_DEFECTO = "https://api.port.io"
BLUEPRINT = "artefacto_agentico"
_TIEMPO_LIMITE_S = 30


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
    return pista.split("/", 6)[-1].split(" -o ")[0]


def main() -> int:
    if len(sys.argv) != 2:
        print("uso: leer_ficha.py <id-del-artefacto>", file=sys.stderr)
        return 2
    api = os.environ.get("PORT_API", API_POR_DEFECTO)
    peticion = urllib.request.Request(
        f"{api}/v1/blueprints/{BLUEPRINT}/entities/{sys.argv[1]}",
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
