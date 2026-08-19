"""Adaptador de lectura de frontmatter YAML.

Es un ADAPTADOR y no dominio porque hace I/O: lee el archivo. Devuelve un dict plano con lo que
las reglas necesitan, para que el dominio siga siendo puro y verificable sin disco.

POR QUE NO PyYAML: el validador corre en cada pull request de cada dominio y no debe arrastrar
dependencias que alguien tenga que instalar. Solo se extrae lo que las reglas usan —claves de
primer nivel, el bloque `metadata` y tres formas mal escritas que hay que detectar—, no YAML
completo. LIMITACION CONOCIDA: con YAML retorcido (anclas, multilinea, listas anidadas) este
parseo se queda corto; si el estandar llega a necesitarlo, aqui es donde se cambia.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

_DELIMITADO = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)
_CLAVE_ANIDADA = re.compile(r"^\s+\S")
_ALLOWED_TOOLS_VACIO = re.compile(r"^allowed-tools:\s*$", re.M)
_ELEMENTO_DE_LISTA = re.compile(r"^\s+-\s", re.M)
_MODEL_ARRAY = re.compile(r"^model:\s*\[", re.M)
_SKILLS_REFERENCE = re.compile(r"^skillsReference:", re.M)


def leer(ruta: Path) -> dict | None:
    """Extrae el frontmatter. Devuelve None si el archivo no lo tiene — ausencia, no error (P7)."""
    contenido = ruta.read_text(encoding="utf-8")
    delimitado = _DELIMITADO.match(contenido)
    if delimitado is None:
        log.debug("%s no tiene frontmatter delimitado", ruta.name)
        return None
    bloque = delimitado.group(1)
    return {
        **_claves_planas(bloque),
        "metadata": _bloque_metadata(bloque),
        "allowed_tools_es_lista": _es_lista_yaml(bloque),
        "model_es_array": bool(_MODEL_ARRAY.search(bloque)),
        "tiene_skills_reference": bool(_SKILLS_REFERENCE.search(bloque)),
    }


def contar_lineas(ruta: Path) -> int:
    return ruta.read_text(encoding="utf-8").count("\n")


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
