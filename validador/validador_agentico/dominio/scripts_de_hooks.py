"""Los SCRIPTS que un `hooks.json` manda ejecutar: cuales son, donde viven, y su digesto conjunto.

POR QUE HACE FALTA. `hooks` era el unico de los cinco tipos sin ficha ni digesto propio: su integridad
la cubria solo el digesto del paquete completo. O sea que EL TIPO QUE EJECUTA CODIGO era el unico cuyo
contenido no se podia verificar archivo a archivo, que es justo al reves de lo deseable. Y el
`hooks.json` por si solo no basta: el JSON DECLARA comandos, y los scripts son los que hacen algo.
Firmar el JSON y no los scripts es firmar el indice de un libro.

LA FORMA DEL DIGESTO ES DE DOS NIVELES, y no es una invencion: es lo que hace la industria cuando un
manifiesto apunta a archivos. Un wheel de Python lleva un `RECORD` con el sha256 de cada archivo y se
firma sobre el RECORD; un JAR firmado lleva un `SHA-256-Digest` por entrada en su `MANIFEST.MF` y una
firma sobre el manifiesto; una imagen OCI tiene el digesto de cada capa y el del manifiesto. La razon
es practica y la medimos hoy en carne propia: el digesto del CONJUNTO dice que algo cambio, y los
digestos POR ARCHIVO dicen QUE cambio. Con solo el primero, una deriva manda a buscar a mano -- que es
exactamente lo que paso con «el sha256 del prompt no coincide» cuando el problema era una ruta --.

DONDE PUEDE VIVIR UN SCRIPT, y aqui esta el riesgo de gobierno:

  ${CLAUDE_PLUGIN_ROOT}/scripts/x.sh    DENTRO del artefacto -> viaja en el paquete y se firma
  ${CLAUDE_PROJECT_DIR}/.claude/hooks/  en el repositorio del CONSUMIDOR -> NO se puede firmar

El segundo caso es el que hay que impedir: un hook aprobado y sellado que invoca un script que vive en
la maquina de otro y que nadie reviso. El `hooks.json` pasaria cualquier verificacion, y lo que se
ejecuta no existia cuando se firmo. La firma diria mucho menos de lo que aparenta.

TODO EN ESTE MODULO ES PURO: recibe la configuracion ya leida, devuelve datos. Sin I/O.
"""
from __future__ import annotations

import hashlib
import re

# Las variables que un `hooks.json` puede usar para localizar un script. Las define el cliente y por
# eso se nombran aqui tal cual: no son convencion nuestra.
VARIABLE_RAIZ_DEL_ARTEFACTO = "${CLAUDE_PLUGIN_ROOT}"
VARIABLE_RAIZ_DEL_CONSUMIDOR = "${CLAUDE_PROJECT_DIR}"

# `command` es el ejecutable o la linea de shell; `args` sus argumentos cuando se invoca en forma exec.
_CLAVE_COMANDO = "command"
_CLAVE_ARGUMENTOS = "args"
_CLAVE_TIPO = "type"
_TIPO_COMANDO = "command"
_CLAVE_HOOKS = "hooks"

# Que parece una referencia a un archivo del propio artefacto. Se busca la variable y se toma lo que
# viene detras hasta el primer espacio o comilla: basta para localizar el archivo, y no se intenta
# interpretar la linea de shell entera -- eso seria escribir un parser de shell, y un parser
# incompleto daria falsos negativos justo en los casos retorcidos, que son los que importan --.
_REFERENCIA_PROPIA = re.compile(
    re.escape(VARIABLE_RAIZ_DEL_ARTEFACTO) + r"/([^\s\"';|&)]+)")


def referencias_propias(configuracion: dict) -> tuple[str, ...]:
    """Las rutas de script DENTRO del artefacto, relativas a su raiz, sin repetir y en orden.

    Orden estable y sin duplicados porque de esto sale un digesto: si el mismo script apareciera dos
    veces o en orden distinto, el digesto cambiaria sin que cambiara nada.
    """
    encontradas = {
        coincidencia
        for texto in _textos_de_comando(configuracion)
        for coincidencia in _REFERENCIA_PROPIA.findall(texto)
    }
    return tuple(sorted(encontradas))


def referencias_externas(configuracion: dict) -> tuple[str, ...]:
    """Los comandos que apuntan FUERA del artefacto, tal cual se escribieron.

    Se devuelven completos y no solo la ruta: quien lea el hallazgo necesita ver la linea entera para
    entender que se ejecuta.
    """
    externas = {
        texto for texto in _textos_de_comando(configuracion)
        if VARIABLE_RAIZ_DEL_CONSUMIDOR in texto
    }
    return tuple(sorted(externas))


def forma_canonica(digestos_por_ruta: dict[str, str]) -> str:
    """El texto sobre el que se calcula el digesto conjunto: `ruta<TAB>sha256`, una linea por archivo.

    Se expone para poder DIFERENCIAR dos conjuntos cuando sus digestos no coinciden. Sin esto, una
    deriva solo dice que algo cambio; con esto se ve que archivo.
    """
    return "\n".join(f"{ruta}\t{digestos_por_ruta[ruta]}"
                     for ruta in sorted(digestos_por_ruta))


def digest_del_conjunto(digestos_por_ruta: dict[str, str]) -> str:
    """El digesto de SEGUNDO NIVEL: uno solo que cubre el `hooks.json` y todos sus scripts.

    Es lo que permite responder «¿cambio algo?» con una comparacion, mientras los digestos por archivo
    responden «¿que cambio?». Mismo patron que el `tools_digest` del `mcp`, que tambien concatena y
    vuelve a hashear.
    """
    return hashlib.sha256(forma_canonica(digestos_por_ruta).encode("utf-8")).hexdigest()



def _textos_de_comando(configuracion: dict) -> list[str]:
    """Todo lo que un manejador de tipo `command` ejecuta: su `command` y sus `args`.

    Se recorren los dos porque la especificacion admite las dos formas: en forma de shell la ruta esta
    en `command`, y en forma exec el ejecutable esta en `command` y el script en `args`. Mirar solo uno
    dejaria pasar la mitad de los casos.
    """
    textos: list[str] = []
    for manejador in _manejadores(configuracion):
        if manejador.get(_CLAVE_TIPO) != _TIPO_COMANDO:
            continue
        comando = manejador.get(_CLAVE_COMANDO)
        if isinstance(comando, str):
            textos.append(comando)
        argumentos = manejador.get(_CLAVE_ARGUMENTOS)
        if isinstance(argumentos, list):
            textos += [a for a in argumentos if isinstance(a, str)]
    return textos


def _manejadores(configuracion: dict) -> list[dict]:
    """Los manejadores de todos los eventos, aplanados.

    LA ESTRUCTURA TIENE `hooks` DOS VECES y conviene decirlo: el archivo tiene un `hooks` de primer
    nivel con un array por EVENTO, y cada entrada de ese array tiene su propio `hooks` con los
    manejadores. Confundirlos daba cero manejadores sin error.
    """
    por_evento = configuracion.get(_CLAVE_HOOKS)
    if not isinstance(por_evento, dict):
        return []
    manejadores: list[dict] = []
    for entradas in por_evento.values():
        if not isinstance(entradas, list):
            continue
        for entrada in entradas:
            if not isinstance(entrada, dict):
                continue
            internos = entrada.get(_CLAVE_HOOKS)
            if isinstance(internos, list):
                manejadores += [m for m in internos if isinstance(m, dict)]
    return manejadores
