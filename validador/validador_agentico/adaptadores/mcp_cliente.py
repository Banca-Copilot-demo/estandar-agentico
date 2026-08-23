"""Adaptador de salida: le pregunta a un servidor MCP que herramientas declara.

SOLO `tools/list`, nunca `tools/call`. La comprobacion de deriva no invoca ninguna herramienta: solo
mira la superficie declarada. Eso permite pedirle al dueño de la credencial una que SOLO PUEDA
LISTAR, y con eso una fuga pasa de «se puede hacer lo que las herramientas hacen» a «se conocen sus
nombres». Custodiar bien una credencial demasiado amplia no arregla que sea demasiado amplia.

SE SIGUE EL SALUDO QUE EXIGE EL TRANSPORTE, y no se pide `tools/list` a pelo. La especificacion de
Streamable HTTP obliga a dos cosas que se descubrieron MIDIENDO contra servidores reales:

  1. La cabecera `Accept` DEBE anunciar `application/json` Y `text/event-stream`. Con solo el primero,
     un servidor estricto responde 400 -- medido contra el MCP de GitHub --. Un servidor permisivo lo
     acepta igual -- medido contra el de AWS --, y por eso la primera version parecia correcta.
  2. Antes de `tools/list` va `initialize`, cuya respuesta puede traer `Mcp-Session-Id`; si viene, hay
     que devolverlo en las peticiones siguientes junto con `MCP-Protocol-Version`.

Y LA RESPUESTA PUEDE LLEGAR COMO SSE aunque se pida JSON: el servidor elige. De ahi que se extraiga el
cuerpo de las lineas `data:` cuando el tipo de contenido es un flujo de eventos.

El transporte `stdio` NO se implementa a proposito: exige descargar y EJECUTAR el paquete del servidor
en el runner de la comprobacion, superficie de ejecucion nueva para un trabajo que solo necesita leer.
Un servidor `stdio` esta fijado por `version_pin` -- ese paquete exacto es inmutable --, asi que su
riesgo de deriva ya esta cubierto por otra via; el remoto, que es el que no se puede fijar, es justo
el que si se consulta.

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
_METODO_INICIAR = "initialize"
_METODO_LISTAR = "tools/list"
_NOTIFICACION_INICIADO = "notifications/initialized"
_TIEMPO_LIMITE_S = 30
# Un servidor que devuelve mas de esto no es un servidor de herramientas: es una respuesta que no
# queremos cargar en memoria ni hashear.
_MAX_RESPUESTA_BYTES = 2_000_000

# La especificacion del transporte EXIGE anunciar los dos tipos. Ver la cabecera del modulo.
_ACEPTA = "application/json, text/event-stream"
# Version del protocolo que se declara. Es una palanca de compatibilidad, asi que va nombrada.
VERSION_PROTOCOLO_MCP = "2025-06-18"
_NOMBRE_CLIENTE = "validador-agentico"
_VERSION_CLIENTE = "1.0.0"

_CABECERA_SESION = "Mcp-Session-Id"
_CABECERA_VERSION_PROTOCOLO = "MCP-Protocol-Version"
_PREFIJO_DATOS_SSE = "data:"
_TIPO_SSE = "text/event-stream"
_CLAVE_HERRAMIENTAS = "tools"


class ServidorInalcanzableError(RuntimeError):
    """No se pudo obtener la lista de herramientas. Se distingue de «la lista esta vacia»: lo primero
    es SIN_COMPROBAR y lo segundo es un dato legitimo."""


def _cabeceras(credencial: str | None, sesion: str | None) -> dict[str, str]:
    cabeceras = {
        "Content-Type": "application/json",
        "Accept": _ACEPTA,
        _CABECERA_VERSION_PROTOCOLO: VERSION_PROTOCOLO_MCP,
    }
    if credencial:
        cabeceras["Authorization"] = f"Bearer {credencial}"
    if sesion:
        cabeceras[_CABECERA_SESION] = sesion
    return cabeceras


def _cuerpo_de_la_respuesta(crudo: bytes, tipo_de_contenido: str) -> dict:
    """El JSON-RPC de la respuesta, venga como JSON o enmarcado en un flujo de eventos."""
    texto = crudo.decode("utf-8", errors="replace")
    if _TIPO_SSE in tipo_de_contenido:
        # En SSE el cuerpo va en lineas `data:`. Se toma la ULTIMA con contenido: es la respuesta al
        # metodo, y las anteriores pueden ser eventos de progreso.
        datos = [linea[len(_PREFIJO_DATOS_SSE):].strip()
                 for linea in texto.splitlines()
                 if linea.startswith(_PREFIJO_DATOS_SSE) and linea[len(_PREFIJO_DATOS_SSE):].strip()]
        if not datos:
            raise ServidorInalcanzableError("la respuesta SSE no trae ninguna linea `data:`")
        texto = datos[-1]
    try:
        return json.loads(texto)
    except json.JSONDecodeError as fallo:
        raise ServidorInalcanzableError(f"la respuesta no es JSON: {fallo}") from fallo


def _llamar(endpoint: str, credencial: str | None, sesion: str | None,
            metodo: str, parametros: dict, espera_respuesta: bool = True) -> tuple[dict, str | None]:
    """Una llamada JSON-RPC. Devuelve `(respuesta, id de sesion)`."""
    peticion_json = {"jsonrpc": _VERSION_JSONRPC, "method": metodo, "params": parametros}
    if espera_respuesta:
        peticion_json["id"] = 1
    peticion = urllib.request.Request(
        endpoint, data=json.dumps(peticion_json).encode("utf-8"),
        headers=_cabeceras(credencial, sesion), method="POST")

    try:
        with urllib.request.urlopen(peticion, timeout=_TIEMPO_LIMITE_S) as respuesta:
            crudo = respuesta.read(_MAX_RESPUESTA_BYTES + 1)
            tipo = respuesta.headers.get("Content-Type", "")
            sesion_devuelta = respuesta.headers.get(_CABECERA_SESION) or sesion
    except urllib.error.HTTPError as fallo:
        raise ServidorInalcanzableError(f"HTTP {fallo.code} al pedir {metodo}") from fallo
    except (urllib.error.URLError, TimeoutError) as fallo:
        raise ServidorInalcanzableError(f"no se pudo conectar para {metodo}: {fallo}") from fallo

    if len(crudo) > _MAX_RESPUESTA_BYTES:
        raise ServidorInalcanzableError(
            f"la respuesta a {metodo} supera {_MAX_RESPUESTA_BYTES} bytes: no se procesa")

    if not espera_respuesta:
        return {}, sesion_devuelta

    respuesta_json = _cuerpo_de_la_respuesta(crudo, tipo)
    if "error" in respuesta_json:
        # El mensaje del servidor NO se propaga: lo escribe un tercero y acabaria en un issue.
        codigo = (respuesta_json.get("error") or {}).get("code", "sin codigo")
        raise ServidorInalcanzableError(
            f"el servidor respondio un error JSON-RPC a {metodo} ({codigo})")
    return respuesta_json, sesion_devuelta


def listar_herramientas(endpoint: str, credencial: str | None = None) -> list[dict]:
    """Las herramientas que el servidor declara. Lanza `ServidorInalcanzableError` si no se pudo."""
    _, sesion = _llamar(endpoint, credencial, None, _METODO_INICIAR, {
        "protocolVersion": VERSION_PROTOCOLO_MCP,
        "capabilities": {},
        "clientInfo": {"name": _NOMBRE_CLIENTE, "version": _VERSION_CLIENTE},
    })

    # La notificacion no lleva `id` y el servidor no responde nada. Un servidor que no la espere la
    # ignora, asi que enviarla es seguro; no enviarla rompe con los que si la exigen.
    try:
        _llamar(endpoint, credencial, sesion, _NOTIFICACION_INICIADO, {}, espera_respuesta=False)
    except ServidorInalcanzableError as fallo:
        log.debug("el servidor no acepto la notificacion de inicio, se sigue: %s", fallo)

    respuesta, _ = _llamar(endpoint, credencial, sesion, _METODO_LISTAR, {})
    herramientas = (respuesta.get("result") or {}).get(_CLAVE_HERRAMIENTAS)
    if not isinstance(herramientas, list):
        raise ServidorInalcanzableError(
            f"la respuesta no trae `result.{_CLAVE_HERRAMIENTAS}` como lista")
    log.debug("%s declara %d herramienta(s)", endpoint, len(herramientas))
    return herramientas
