"""Adaptador de lectura de frontmatter YAML.

Es un ADAPTADOR y no dominio porque hace I/O: lee el archivo. Devuelve un dict plano con lo que
las reglas necesitan, para que el dominio siga siendo puro y verificable sin disco.

LA EXTRACCION es por expresiones regulares y no por un parser completo: solo se saca lo que las
reglas usan —claves de primer nivel, el bloque `metadata` y tres formas mal escritas que hay que
detectar—. Con YAML retorcido (anclas, multilinea, listas anidadas) ese parseo se queda corto.

LA VALIDEZ SINTACTICA, en cambio, SI se comprueba con un parser de verdad, y esto se decidio con un
defecto medido delante: un `description` con dos puntos sin entrecomillar hacia el frontmatter
ilegible para cualquier cliente -- que se SALTA el skill sin avisar -- y nuestro gate lo daba por
CONFORME, porque una expresion regular no ve un error de sintaxis. Un artefacto que ningun cliente
puede cargar es justo lo que G1 existe para impedir.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from validador_agentico.dominio.forma_frontmatter import (
    CLAVE_METADATA,
    CLAVE_OBSERVACIONES,
    OBSERVACION_ALLOWED_TOOLS_LISTA,
    OBSERVACION_MODEL_ARRAY,
    OBSERVACION_SKILLS_REFERENCE,
    observar,
)

log = logging.getLogger(__name__)

_DELIMITADO = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)
_CLAVE_ANIDADA = re.compile(r"^\s+\S")
_ALLOWED_TOOLS_VACIO = re.compile(r"^allowed-tools:\s*$", re.M)
_ELEMENTO_DE_LISTA = re.compile(r"^\s+-\s", re.M)
_MODEL_ARRAY = re.compile(r"^model:\s*\[", re.M)
_SKILLS_REFERENCE = re.compile(r"^skillsReference:", re.M)


def _texto(ruta: Path) -> str:
    """El contenido del archivo, o cadena vacia si no se puede leer.

    UN SOLO LECTOR PARA LAS CUATRO FUNCIONES PUBLICAS DEL MODULO, y no lo habia: `leer_cuerpo` degradaba
    con este mismo `except` y `leer`, `es_yaml_valido` y `contar_lineas` leian a pelo. Consecuencia
    MEDIDA con un `SKILL.md` de bytes que no son UTF-8: el gate ABORTABA con `UnicodeDecodeError` en vez
    de reportar el artefacto. Un gate que revienta no dice «no conforme», no dice nada, y en CI se lee
    como fallo de infraestructura.

    Una auditoria habia señalado solo `contar_lineas`; al ejecutar la prueba de regresion aparecieron
    las otras dos. Es la diferencia entre leer el codigo y correrlo.

    DEGRADA EN VEZ DE LANZAR porque perder un artefacto ilegible no debe tumbar la validacion de los
    otros cincuenta, y el artefacto no se cuela: sin contenido no hay frontmatter, y un artefacto sin
    frontmatter ya lo bloquea su propia regla -- «indescubrible» --. Se registra en WARNING para que el
    motivo real no quede escondido detras de ese mensaje.
    """
    try:
        return ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as fallo:
        log.warning("no se pudo leer %s: %s", ruta, fallo)
        return ""


def es_yaml_valido(ruta: Path) -> str | None:
    """Devuelve el motivo si el frontmatter NO es YAML valido, o `None` si lo es.

    Se comprueba aparte de `leer` a proposito: `leer` extrae lo que las reglas necesitan y tiene que
    seguir funcionando aunque el YAML sea imperfecto; esto responde una sola pregunta, la que decide
    si un cliente podra cargar el artefacto.
    """
    contenido = _texto(ruta)
    delimitado = _DELIMITADO.match(contenido)
    if delimitado is None:
        return None
    try:
        yaml.safe_load(delimitado.group(1))
    except yaml.YAMLError as fallo:
        primera_linea = str(fallo).splitlines()[0]
        return primera_linea
    return None


# LAS OBSERVACIONES DE FORMA y la clave `metadata` viven en `dominio/forma_frontmatter`, no aqui, y el
# motivo es la regla de dependencia: dos modulos de `dominio/` las necesitan, y si viven en este
# adaptador el dominio tiene que importar hacia fuera -- lo que G5 prohibe --. Este modulo las importa
# hacia dentro, que es la direccion correcta, y se limita a lo suyo: leer el archivo y parsear.


def leer(ruta: Path) -> dict | None:
    """Extrae el frontmatter. Devuelve None si el archivo no lo tiene — ausencia, no error (P7)."""
    contenido = _texto(ruta)
    delimitado = _DELIMITADO.match(contenido)
    if delimitado is None:
        log.debug("%s no tiene frontmatter delimitado", ruta.name)
        return None
    bloque = delimitado.group(1)

    # SE PARSEA CON EL PARSER DE VERDAD, y solo se cae a las expresiones regulares si el YAML es
    # invalido -- caso en el que el artefacto YA esta bloqueado por `es_yaml_valido`, asi que lo que
    # se extraiga solo alimenta mensajes --.
    #
    # DEFECTO MEDIDO que obligo a esto: la extraccion era SIEMPRE por expresiones regulares, asi que
    # una lista YAML -- `tools:` con guiones debajo -- llegaba como cadena VACIA. Al validar el primer
    # agente real contra su esquema, `tools` y `handoffs` fallaban con «'' is not of type 'array'».
    # Teniamos el parser delante, usado solo para comprobar sintaxis.
    analizado = _analizar(bloque)
    if analizado is None:
        return {
            **_claves_planas(bloque),
            CLAVE_METADATA: _bloque_metadata(bloque),
            CLAVE_OBSERVACIONES: _observaciones_por_regex(bloque),
        }

    metadata = analizado.get(CLAVE_METADATA)
    return {
        **{c: v for c, v in analizado.items() if c != CLAVE_METADATA},
        CLAVE_METADATA: metadata if isinstance(metadata, dict) else {},
        CLAVE_OBSERVACIONES: observar(analizado),
    }


def leer_cuerpo(ruta: Path) -> str:
    """El texto DESPUES del frontmatter. Es donde el artefacto referencia sus recursos, y por eso
    G2 lo necesita: el frontmatter no declara los archivos de apoyo -- ningun estandar tiene campo
    para eso -- asi que la unica pista de que existen son las rutas del cuerpo."""
    contenido = _texto(ruta)
    delimitado = _DELIMITADO.match(contenido)
    return contenido[delimitado.end():] if delimitado else contenido


def contar_lineas(ruta: Path) -> int:
    """Las lineas del archivo, o 0 si no se puede leer. Ver `_texto` para el por que de la guarda."""
    return _texto(ruta).count("\n")


def _analizar(bloque: str) -> dict | None:
    """El frontmatter como estructura, o `None` si el YAML no es valido o no es un mapa.

    No es un mapa cuando alguien escribe una lista o un escalar en el frontmatter: es un artefacto
    roto, y devolver `None` lo manda a la extraccion degradada en vez de reventar aqui.
    """
    try:
        analizado = yaml.safe_load(bloque)
    except yaml.YAMLError as fallo:
        log.debug("frontmatter con YAML invalido, se extrae de forma degradada: %s", fallo)
        return None
    return analizado if isinstance(analizado, dict) else None


def _observaciones_por_regex(bloque: str) -> dict[str, bool]:
    """La version degradada, para cuando el YAML no se puede parsear. El artefacto ya esta bloqueado
    por la regla de sintaxis; esto solo evita que los mensajes salgan vacios."""
    return {
        OBSERVACION_ALLOWED_TOOLS_LISTA: _es_lista_yaml(bloque),
        OBSERVACION_MODEL_ARRAY: bool(_MODEL_ARRAY.search(bloque)),
        OBSERVACION_SKILLS_REFERENCE: bool(_SKILLS_REFERENCE.search(bloque)),
    }


def _claves_planas(bloque: str) -> dict[str, str]:
    claves: dict[str, str] = {}
    for linea in bloque.splitlines():
        if _CLAVE_ANIDADA.match(linea) or ":" not in linea:
            continue
        clave, valor = linea.split(":", 1)
        claves[clave.strip()] = valor.strip().strip("\"'")
    return claves


def _bloque_metadata(bloque: str) -> dict[str, str]:
    """El campo `metadata` de la especificacion: mapa string->string. Ahi vive el envelope de
    gobierno del estandar, y `gh skill install` lo preserva al instalar."""
    metadata: dict[str, str] = {}
    dentro = False
    for linea in bloque.splitlines():
        if re.match(r"^metadata:\s*$", linea):
            dentro = True
            continue
        if not _CLAVE_ANIDADA.match(linea):
            dentro = False
            continue
        if dentro and ":" in linea:
            clave, valor = linea.split(":", 1)
            metadata[clave.strip()] = valor.strip().strip("\"'")
    return metadata


def _es_lista_yaml(bloque: str) -> bool:
    """`allowed-tools` escrito como lista YAML. Es la forma natural de escribirlo y la
    especificacion exige una CADENA separada por espacios: el cliente no lo carga."""
    return bool(_ALLOWED_TOOLS_VACIO.search(bloque) and _ELEMENTO_DE_LISTA.search(bloque))
