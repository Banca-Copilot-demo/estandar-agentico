"""Reglas de un artefacto: envelope de gobierno, skill y prompt.

PURAS (G5): reciben datos ya parseados y DEVUELVEN hallazgos. No leen disco, no mutan nada y no
importan de `adaptadores/`. Eso las hace verificables sin repositorio de prueba.
"""
from __future__ import annotations

import re

from validador_agentico.dominio.forma_frontmatter import (
    OBSERVACION_ALLOWED_TOOLS_LISTA,
    OBSERVACION_MODEL_ARRAY,
    OBSERVACION_SKILLS_REFERENCE,
    observacion,
)
from validador_agentico.dominio.especificacion import (
    CAMPOS_ENVELOPE,
    ESTADO_EN_AUTORIA,
    MAX_CARACTERES_DESCRIPCION,
    MAX_LINEAS_SKILL,
    PATRON_SEMVER,
    Clasificacion,
    Estado,
)
from validador_agentico.dominio.hallazgo import Hallazgo, aviso, error

CAMPOS_SEMVER = ("version", "standard_version")


def revisar_envelope(donde: str, metadata: dict[str, str]) -> list[Hallazgo]:
    """El envelope de gobierno, dentro del campo `metadata` del propio artefacto.

    Es lo que hace al artefacto AUTODESCRIPTIVO: con esto puesto, se puede auditar aunque viaje
    suelto, sin plugin y sin catalogo.
    """
    hallazgos = [
        error(donde, f"`metadata.{campo}` falta: es parte del envelope de gobierno")
        for campo in sorted(CAMPOS_ENVELOPE - set(metadata))
    ]
    hallazgos += _revisar_estado(donde, metadata.get("status"))
    hallazgos += _revisar_clasificacion(donde, metadata.get("data_classification"))
    hallazgos += _revisar_semver(donde, metadata)
    hallazgos += _revisar_contacto(donde, metadata.get("owner_contact"))
    return hallazgos


def _revisar_estado(donde: str, estado: str | None) -> list[Hallazgo]:
    if estado is None:
        return []
    if estado not in {e.value for e in Estado}:
        return [error(donde, f"`status` invalido: {estado}")]
    if estado != ESTADO_EN_AUTORIA.value:
        return [aviso(donde, f"`status` es `{estado}`: el estado lo DERIVAN los gates, "
                             "no se declara a mano")]
    return []


def _revisar_clasificacion(donde: str, clasificacion: str | None) -> list[Hallazgo]:
    if clasificacion is None or clasificacion in {c.value for c in Clasificacion}:
        return []
    return [error(donde, f"`data_classification` invalida: {clasificacion}")]


def _revisar_semver(donde: str, metadata: dict[str, str]) -> list[Hallazgo]:
    return [
        error(donde, f"`{campo}` no es SemVer: {metadata[campo]}")
        for campo in CAMPOS_SEMVER
        if metadata.get(campo) and not re.fullmatch(PATRON_SEMVER, str(metadata[campo]))
    ]


def _revisar_contacto(donde: str, contacto: str | None) -> list[Hallazgo]:
    if contacto and "@" not in contacto:
        return [aviso(donde, "`owner_contact` no parece un correo ni un canal; conviene que sea "
                             "de EQUIPO y no de una persona: las personas rotan")]
    return []


def revisar_skill(donde: str, nombre_directorio: str, frontmatter: dict,
                  lineas_cuerpo: int) -> list[Hallazgo]:
    """Un skill: lo que la especificacion Agent Skills exige, mas el envelope del estandar."""
    hallazgos: list[Hallazgo] = []
    if observacion(frontmatter, OBSERVACION_ALLOWED_TOOLS_LISTA):
        hallazgos.append(error(donde, "`allowed-tools` es una lista YAML; la especificacion exige "
                                      "una CADENA separada por espacios"))
    hallazgos += _revisar_nombre(donde, frontmatter.get("name"), nombre_directorio)
    hallazgos += _revisar_descripcion(donde, frontmatter.get("description", ""))
    hallazgos += revisar_envelope(donde, frontmatter.get("metadata", {}))
    if lineas_cuerpo > MAX_LINEAS_SKILL:
        hallazgos.append(aviso(donde, f"{lineas_cuerpo} lineas: la especificacion recomienda menos "
                                      f"de {MAX_LINEAS_SKILL}. El cuerpo entero se carga cuando el "
                                      "skill se activa; mueve el material a references/"))
    return hallazgos


def _revisar_nombre(donde: str, nombre: str | None, nombre_directorio: str) -> list[Hallazgo]:
    if not nombre:
        return [error(donde, "falta `name`")]
    if nombre != nombre_directorio:
        return [error(donde, f"`name` ({nombre}) no coincide con el directorio "
                             f"({nombre_directorio}): el skill no cargara")]
    return []


def _revisar_descripcion(donde: str, descripcion: str) -> list[Hallazgo]:
    if not descripcion:
        return [error(donde, "falta `description`: es el mecanismo con el que el modelo decide "
                             "si usar el artefacto. Sin ella es codigo muerto que ademas ocupa "
                             "contexto en cada peticion")]
    if len(descripcion) > MAX_CARACTERES_DESCRIPCION:
        return [error(donde, f"`description` excede {MAX_CARACTERES_DESCRIPCION} caracteres "
                             f"({len(descripcion)})")]
    return []


def revisar_prompt(donde: str, frontmatter: dict) -> list[Hallazgo]:
    """Un prompt: punto de entrada con enrutamiento. Las dos primeras comprobaciones salen de
    defectos MEDIDOS en el activo del cliente (hallazgos 10 y 21)."""
    hallazgos: list[Hallazgo] = []
    if observacion(frontmatter, OBSERVACION_MODEL_ARRAY):
        hallazgos.append(error(donde, "`model` es un array de nombres fijos. Declara un modelo y "
                                      "deja la lista en el `model_allowlist` del plugin: si no, "
                                      "cada rotacion del catalogo obliga a tocar todos los archivos"))
    if observacion(frontmatter, OBSERVACION_SKILLS_REFERENCE):
        hallazgos.append(error(donde, "`skillsReference` no es un campo estandar. Usa "
                                      "`dependencies` por `id`: una ruta de sistema de archivos "
                                      "no resuelve en la maquina de otra persona"))
    hallazgos += _revisar_descripcion(donde, frontmatter.get("description", ""))
    hallazgos += revisar_envelope(donde, frontmatter.get("metadata", {}))
    return hallazgos
