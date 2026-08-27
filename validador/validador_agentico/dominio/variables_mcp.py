"""Que credenciales pide de verdad un `.mcp.json`, leidas de sus `${VAR}`.

POR QUE EXISTE. El gobierno declaraba la credencial con un solo campo -- `{"mechanism": "none"}` --
y eso NO SE PODIA COMPROBAR CONTRA NADA: era una afirmacion del autor, y el gate la creia. Un
servidor que declaraba `none` y traia una cabecera `Authorization: ${API_TOKEN}` pasaba en verde, y
esa es exactamente la situacion en la que alguien aprueba «un servidor publico sin credencial» y lo
que se instala pide un token del banco.

LA FORMA NUEVA ES VERIFICABLE, y sigue el patron del registro oficial de MCP -- `environmentVariables`
y `headers` con `isRequired` / `isSecret` --: una LISTA de credenciales con nombre y sitio.

    "credentials": [
      { "name": "GITHUB_PERSONAL_ACCESS_TOKEN", "kind": "env",
        "is_secret": true, "is_required": true }
    ]

Y este modulo es la otra mitad: saca del `.mcp.json` los `${VAR}` que el servidor realmente usa, con
el sitio en que aparecen, para que la regla pueda contrastar las dos listas. Declarar cero
credenciales y traer un `Authorization` deja de ser una afirmacion y pasa a ser una CONTRADICCION
comprobable.

DONDE SE MIRA, y por que solo ahi. En `env` -- variables de entorno del proceso, el mecanismo de un
`stdio` -- y en `headers` -- cabeceras HTTP, el mecanismo de un remoto --. NO se miran los `args`: ahi
una `${VAR}` es casi siempre una ruta (`${CLAUDE_PLUGIN_ROOT}`), no una credencial, y tratarla como
tal produciria un error por cada servidor bien escrito. Un gate que se equivoca en el caso normal se
desactiva.

PURO (G5): recibe la configuracion ya parseada y devuelve datos.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class SitioDeLaCredencial(str, Enum):
    """Donde viaja la credencial. Enum de dominio y no strings sueltos (P6).

    Los dos valores son los mismos que admite el campo `kind` del gobierno, para que la regla compare
    lo declarado con lo observado sin traducir nada por el camino.
    """

    ENTORNO = "env"
    CABECERA = "header"


# Las claves del `.mcp.json` donde vive cada sitio. `headers` es la forma de un remoto; `env` la de un
# `stdio`. Un mismo servidor puede llevar las dos.
_CLAVE_POR_SITIO = ((SitioDeLaCredencial.ENTORNO, "env"),
                    (SitioDeLaCredencial.CABECERA, "headers"))

# `${VAR}` y `${input:VAR}` / `${env:VAR}`: los tres estilos que aparecen en los archivos reales. El
# prefijo opcional se descarta -- lo que identifica la credencial es su NOMBRE, y el prefijo dice de
# donde la saca el cliente, que es cosa suya y no del gobierno.
_VARIABLE = re.compile(r"\$\{(?:(?:input|env|secrets|localEnv):)?([A-Za-z_][A-Za-z0-9_]*)\}")

# Variables del propio cliente: son RUTAS que el cliente sustituye, nunca credenciales. Declararlas
# como credencial seria pedir custodia de algo que no es un secreto.
VARIABLES_DEL_CLIENTE = frozenset({
    "CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_DATA", "workspaceFolder",
})


@dataclass(frozen=True)
class CredencialObservada:
    """Una `${VAR}` encontrada en la configuracion, con donde apareció."""

    nombre: str
    sitio: SitioDeLaCredencial
    servidor: str


def observadas(servidores: dict) -> tuple[CredencialObservada, ...]:
    """Las credenciales que la configuracion pide de verdad, ordenadas para que el mensaje sea estable.

    `servidores` es el mapa `nombre -> definicion` que resuelve `forma_mcp`, no el archivo entero: la
    forma del archivo la conoce ese modulo y repetirlo aqui seria la duplicacion que G2 prohibe.
    """
    encontradas: list[CredencialObservada] = []
    for nombre_servidor, definicion in sorted(servidores.items()):
        if not isinstance(definicion, dict):
            continue
        for sitio, clave in _CLAVE_POR_SITIO:
            valores = definicion.get(clave)
            if not isinstance(valores, dict):
                continue
            for texto in valores.values():
                encontradas += [
                    CredencialObservada(nombre=variable, sitio=sitio, servidor=str(nombre_servidor))
                    for variable in _VARIABLE.findall(str(texto))
                    if variable not in VARIABLES_DEL_CLIENTE
                ]
    return tuple(sorted(encontradas, key=lambda c: (c.servidor, c.sitio.value, c.nombre)))
