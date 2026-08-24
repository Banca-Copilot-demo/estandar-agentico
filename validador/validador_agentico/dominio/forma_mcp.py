"""Donde estan los servidores dentro de un archivo de configuracion MCP. Regla pura.

POR QUE HACE FALTA. El gate asumia UNA forma -- un objeto `mcpServers` -- y el comentario del codigo
decia que «los plugins reales lo llevan con una sola clave». Se midio sobre los catalogos publicos y
es FALSO: hay TRES variantes en uso, con dos nombres de archivo distintos.

  archivo       clave de primer nivel   observados
  .mcp.json     mcpServers              10
  .mcp.json     ninguna: los servidores en la RAIZ del objeto      10
  mcp.json      servers                  1  (y 4 mas con mcpServers)

Diez de los quince plugins del marketplace OFICIAL usan la forma sin clave -- entre ellos `github`,
`terraform`, `linear` y `playwright` --.

LOS DOS FALLOS QUE PRODUCIA, en direcciones opuestas:

  - CERRADO PERO EN FALSO: un `.mcp.json` con los servidores en la raiz se rechazaba con «no declara
    `mcpServers`». Habriamos rechazado la forma mayoritaria del catalogo oficial.

  - ABIERTO, y este es el grave: un `mcp.json` -- sin punto -- no se leia siquiera, asi que el
    inventario daba 0, no habia ficha, no habia error y el veredicto era CONFORME. Se comprobo con un
    servidor fijado a `@latest`: un MCP sin gobierno, sin aprobacion y sin digesto, en verde. Es lo
    contrario del principio que el resto de este codigo repite.

COMO SE DISTINGUE LA FORMA DESNUDA de un objeto cualquiera: por la pinta de sus valores. Una
definicion de servidor lleva `command` (stdio) o `url`/`type` (remoto). Se exige que TODOS los valores
la tengan, no solo alguno: con «alguno» un archivo con una clave suelta ademas de los servidores se
interpretaria mal, y aqui equivocarse significa gobernar el conjunto equivocado.
"""
from __future__ import annotations

# Las claves bajo las que un archivo puede envolver sus servidores, en orden de preferencia.
CLAVES_ENVOLTORIO = ("mcpServers", "servers")

# Que hace que un objeto parezca la definicion de un servidor y no otra cosa.
_MARCAS_DE_SERVIDOR = ("command", "url", "type")


def servidores_de(configuracion: object) -> dict | None:
    """El mapa `nombre -> definicion` de los servidores, sea cual sea la forma del archivo.

    `None` cuando no se reconoce ninguna forma con servidores dentro. Se distingue de un mapa VACIO a
    proposito: un `{"mcpServers": {}}` es un archivo que declara explicitamente que no hay servidores
    -- valido, y es como se desactiva MCP -- mientras que no reconocer la forma es no saber que hay.
    """
    if not isinstance(configuracion, dict):
        return None
    for clave in CLAVES_ENVOLTORIO:
        envuelto = configuracion.get(clave)
        if isinstance(envuelto, dict):
            return envuelto
    return _desnudos(configuracion)


def _desnudos(configuracion: dict) -> dict | None:
    """La forma sin envoltorio: los servidores como claves de primer nivel.

    Se exige que el objeto NO este vacio y que TODOS sus valores tengan pinta de servidor. Sin la
    segunda condicion, cualquier objeto JSON con un solo campo se leeria como un servidor.
    """
    if not configuracion:
        return None
    if all(isinstance(valor, dict) and any(m in valor for m in _MARCAS_DE_SERVIDOR)
           for valor in configuracion.values()):
        return configuracion
    return None
