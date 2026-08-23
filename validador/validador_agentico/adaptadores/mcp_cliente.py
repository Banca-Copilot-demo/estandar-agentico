"""Adaptador de salida: le pregunta a un servidor MCP que herramientas declara.

SOLO `tools/list`, nunca `tools/call`. La comprobacion de deriva no invoca ninguna herramienta: solo
mira la superficie declarada. Eso permite pedirle al dueño de la credencial una que SOLO PUEDA
LISTAR, y con eso una fuga pasa de «se puede hacer lo que las herramientas hacen» a «se conocen sus
nombres». Custodiar bien una credencial demasiado amplia no arregla que sea demasiado amplia.

MCP habla JSON-RPC 2.0. Sobre transporte `http` es un POST y se resuelve con la libreria estandar; no
se añade una dependencia para esto. El transporte `stdio` lanza un proceso local y NO se implementa
aqui a proposito: exige descargar y EJECUTAR el paquete del servidor en el runner de la comprobacion,
que es superficie de ejecucion nueva para un trabajo que solo necesita leer. Un servidor `stdio` esta
fijado por `version_pin` -- ese paquete exacto es inmutable --, asi que su riesgo de deriva ya esta
cubierto por otra via; el remoto, que es el que no se puede fijar, es justo el que si se consulta.

LO QUE DEVUELVE ES DATO HOSTIL. Las descripciones las escribe un tercero. Aqui se devuelven tal cual
para poder calcular el digest, y quien las use tiene que saberlo: el reporte nunca las imprime.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

_VERSION_JSONRPC = "2.0"
_METODO_LISTAR = "tools/list"
_TIEMPO_LIMITE_S = 30
# Un servidor que devuelve mas de esto no es un servidor de herramientas: es una respuesta que no
# queremos cargar en memoria ni hashear.
_MAX_RESPUESTA_BYTES = 2_000_000
_CABECERA_AUTORIZACION = "Authorization"
_CLAVE_HERRAMIENTAS = "tools"


class ServidorInalcanzableError(RuntimeError):
    """No se pudo obtener la lista de herramientas. Se distingue de «la lista esta vacia»: lo primero
    es SIN_COMPROBAR y lo segundo es un dato legitimo."""


def _peticion(endpoint: str, credencial: str | None) -> urllib.request.Request:
    cuerpo = json.dumps({
        "jsonrpc": _VERSION_JSONRPC,
        "id": 1,
        "method": _METODO_LISTAR,
        "params": {},
    }).encode("utf-8")
    cabeceras = {"Content-Type": "application/json", "Accept": "application/json"}
    if credencial:
        cabeceras[_CABECERA_AUTORIZACION] = f"Bearer {credencial}"
    return urllib.request.Request(endpoint, data=cuerpo, headers=cabeceras, method="POST")


def listar_herramientas(endpoint: str, credencial: str | None = None) -> list[dict]:
    """Las herramientas que el servidor declara. Lanza `ServidorInalcanzableError` si no se pudo."""
    try:
        with urllib.request.urlopen(_peticion(endpoint, credencial),
                                    timeout=_TIEMPO_LIMITE_S) as respuesta:
            crudo = respuesta.read(_MAX_RESPUESTA_BYTES + 1)
    except urllib.error.HTTPError as fallo:
        raise ServidorInalcanzableError(f"HTTP {fallo.code} al pedir {_METODO_LISTAR}") from fallo
    except (urllib.error.URLError, TimeoutError) as fallo:
        raise ServidorInalcanzableError(f"no se pudo conectar: {fallo}") from fallo

    if len(crudo) > _MAX_RESPUESTA_BYTES:
        raise ServidorInalcanzableError(
            f"la respuesta supera {_MAX_RESPUESTA_BYTES} bytes: no se procesa")

    try:
        respuesta_json = json.loads(crudo)
    except json.JSONDecodeError as fallo:
        raise ServidorInalcanzableError(f"la respuesta no es JSON: {fallo}") from fallo

    if "error" in respuesta_json:
        # El mensaje del servidor NO se propaga: lo escribe un tercero y acabaria en un issue.
        codigo = (respuesta_json.get("error") or {}).get("code", "sin codigo")
        raise ServidorInalcanzableError(f"el servidor respondio un error JSON-RPC ({codigo})")

    herramientas = (respuesta_json.get("result") or {}).get(_CLAVE_HERRAMIENTAS)
    if not isinstance(herramientas, list):
        raise ServidorInalcanzableError(
            f"la respuesta no trae `result.{_CLAVE_HERRAMIENTAS}` como lista")
    log.debug("%s declara %d herramienta(s)", endpoint, len(herramientas))
    return herramientas
