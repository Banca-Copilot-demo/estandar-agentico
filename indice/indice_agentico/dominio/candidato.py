"""Tipos del dominio del indice. Inmutables y sin dependencias: describen QUE se indexa y POR QUE
se rechaza, sin saber de donde salio la informacion.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Motivo(str, Enum):
    """Por que un candidato NO entra al indice. Es un enum y no una cadena libre porque el motivo
    se muestra al equipo del dominio y se cuenta en el resumen: tiene que ser un valor cerrado."""

    SIN_RELEASE = "no tiene ningun release publicado"
    SIN_PAQUETE = "el release no trae el paquete .tar.gz"
    SIN_MANIFIESTO = "el paquete no contiene .claude-plugin/plugin.json"
    SIN_ATESTACION = "no hay atestacion verificable para el digest del paquete"
    SIN_VEREDICTO = "no hay atestacion del veredicto de conformidad del estandar"
    NO_CONFORME = "el veredicto atestado dice que no es conforme"
    VERSION_DISCREPANTE = "la version del manifiesto no coincide con la etiqueta"


@dataclass(frozen=True)
class Candidato:
    """Lo que se sabe de un repositorio de dominio antes de decidir si se indexa."""

    repositorio: str
    etiqueta: str
    sha: str
    digest: str | None = None
    manifiesto: dict | None = None
    atestacion_verificada: bool = False
    veredicto: dict | None = None


@dataclass(frozen=True)
class Entrada:
    """Una entrada del indice: es lo unico que un cliente necesita para instalar."""

    name: str
    description: str
    version: str
    repositorio: str
    etiqueta: str
    sha: str


@dataclass(frozen=True)
class Rechazo:
    repositorio: str
    motivo: Motivo


@dataclass(frozen=True)
class Indice:
    entradas: tuple[Entrada, ...]
    rechazos: tuple[Rechazo, ...]
