"""Que el gobierno declare EXACTAMENTE los servidores que la configuracion ejecuta.

EL DEFECTO QUE CIERRA, medido. Un servidor presente en el `.mcp.json` y ausente del `GOVERNANCE.json`
pasaba el gate en verde si estaba fijado a una version. O sea que la aprobacion podia cubrir un
subconjunto de lo que se ejecuta, y nadie lo notaba: se probo con un gobierno que declaraba un servidor
de documentacion de solo lectura y una configuracion que ademas traia uno apuntando a un host interno
de produccion. Veredicto: CONFORME, y el segundo servidor no aparecia en ningun hallazgo.

SE COTEJA EN LAS DOS DIRECCIONES, y la segunda importa tanto como la primera:

  - un servidor CONFIGURADO y no declarado se ejecuta sin aprobacion;
  - un servidor DECLARADO y no configurado significa que la aprobacion cubre un fantasma. Suele ser el
    sintoma de un renombrado a medias, y deja al aprobador creyendo que reviso algo que no esta ahi.

POR QUE NO SE COTEJA POR EL NOMBRE, que es lo que se hacia implicitamente. La documentacion de la
plataforma es explicita: «un `serverName` NO ES UN CONTROL DE SEGURIDAD. El nombre es la etiqueta que
asigna el usuario, no el servidor subyacente, asi que un usuario puede llamar `github` a cualquier
servidor». Y sus propios allowlists lo aplican: emparejan por `serverUrl` o por `serverCommand`, y
aceptan `serverName` solo cuando no hay ninguna entrada de las otras dos.

Asi que la identidad de un servidor es LO QUE SE EJECUTA:

  remoto (http/sse)   la URL
  stdio               la referencia del paquete con su version, `paquete@1.2.3`

El nombre se sigue usando en los MENSAJES, porque es lo que la persona reconoce. Pero no decide nada.

TODO ES PURO: recibe los dos objetos ya leidos y devuelve datos.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

_CLAVE_URL = "url"
_CLAVE_COMANDO = "command"
_CLAVE_ARGUMENTOS = "args"
_CLAVE_ENDPOINT = "endpoint"
_CLAVE_FUENTE = "source"
_CLAVE_REFERENCIA = "ref"
_CLAVE_VERSION = "version_pin"
_CLAVE_NOMBRE = "name"

# La version que declara «este servidor es remoto y no hay nada que fijar». No forma parte de la
# identidad: la identidad de un remoto es su URL.
_SIN_VERSION = "sin-version"


def identidad_configurada(definicion: dict) -> str | None:
    """Lo que identifica al servidor tal como se va a EJECUTAR, o `None` si no se reconoce.

    `None` y no una cadena vacia: no poder identificar un servidor es distinto de identificarlo como
    algo vacio, y el llamador da mensajes distintos.
    """
    url = definicion.get(_CLAVE_URL)
    if isinstance(url, str) and url:
        return _url_normalizada(url)
    return _referencia_de_los_argumentos(definicion)


def identidad_declarada(servidor: dict) -> str | None:
    """Lo que identifica al servidor tal como el gobierno lo DECLARA."""
    endpoint = servidor.get(_CLAVE_ENDPOINT)
    if isinstance(endpoint, str) and endpoint:
        return _url_normalizada(endpoint)
    fuente = servidor.get(_CLAVE_FUENTE)
    if not isinstance(fuente, dict):
        return None
    referencia = fuente.get(_CLAVE_REFERENCIA)
    if not isinstance(referencia, str) or not referencia:
        return None
    version = fuente.get(_CLAVE_VERSION)
    if referencia.startswith(("http://", "https://")):
        return _url_normalizada(referencia)
    if not isinstance(version, str) or not version or version == _SIN_VERSION:
        return referencia
    return f"{referencia}@{version}"


def _referencia_de_los_argumentos(definicion: dict) -> str | None:
    """La referencia del paquete dentro de los `args`, que es lo que identifica a un `stdio`.

    Se mira en los argumentos y NO en el `command`: el comando es el lanzador -- `uvx`, `npx`, `docker`
    -- y lo que dice QUE servidor se ejecuta va detras. Mismo criterio que la regla de fijado.
    """
    argumentos = definicion.get(_CLAVE_ARGUMENTOS)
    if not isinstance(argumentos, (list, tuple)):
        return None
    for argumento in argumentos:
        texto = str(argumento)
        if "@" in texto and not texto.startswith("-"):
            return texto
    return None


def _url_normalizada(url: str) -> str:
    """La URL en forma comparable: host en minusculas, sin barra final, ruta intacta.

    EL HOST EN MINUSCULAS Y LA RUTA NO, y no es un capricho: la plataforma documenta que el
    emparejamiento de host es insensible a mayusculas y que «las rutas siguen siendo sensibles». Y sin
    quitar la barra final, `https://x/mcp` y `https://x/mcp/` serian dos servidores distintos y el
    cotejo bloquearia artefactos correctos.
    """
    partes = urlsplit(url.strip())
    ruta = partes.path.rstrip("/")
    return urlunsplit((partes.scheme.lower(), partes.netloc.lower(), ruta,
                       partes.query, partes.fragment))


def cotejar(configurados: dict, declarados: list) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """`(sin_declarar, sin_configurar)`, cada uno con etiquetas legibles para el mensaje.

    Se devuelven las dos listas y no un booleano: los dos casos necesitan mensajes distintos, y quien
    lee un hallazgo necesita saber DE QUE servidor se habla.
    """
    por_identidad_declarada = {}
    for servidor in declarados:
        if not isinstance(servidor, dict):
            continue
        identidad = identidad_declarada(servidor)
        if identidad is not None:
            por_identidad_declarada[identidad] = str(servidor.get(_CLAVE_NOMBRE, "?"))

    sin_declarar = []
    identidades_configuradas = set()
    for nombre, definicion in configurados.items():
        if not isinstance(definicion, dict):
            continue
        identidad = identidad_configurada(definicion)
        if identidad is None:
            # No se puede afirmar que no este declarado si no se sabe que es. La regla de fijado ya
            # avisa de que su referencia no se reconoce.
            continue
        identidades_configuradas.add(identidad)
        if identidad not in por_identidad_declarada:
            sin_declarar.append(f"`{nombre}` ({identidad})")

    sin_configurar = [f"`{nombre}` ({identidad})"
                      for identidad, nombre in sorted(por_identidad_declarada.items())
                      if identidad not in identidades_configuradas]
    return tuple(sorted(sin_declarar)), tuple(sin_configurar)
