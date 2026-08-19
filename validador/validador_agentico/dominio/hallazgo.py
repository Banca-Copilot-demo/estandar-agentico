"""Tipos de dominio del veredicto: severidad, hallazgo y veredicto agregado.

Puro: sin I/O y sin imports del proyecto fuera de `dominio/`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severidad(str, Enum):
    """Severidad de un hallazgo. Enum de dominio y no strings sueltos (P6): un typo en
    `"eror"` seria un bug silencioso que ninguna comprobacion detectaria."""

    ERROR = "error"
    AVISO = "aviso"


@dataclass(frozen=True)
class Hallazgo:
    """Un hallazgo del validador. Dataclass y no `tuple[str, str, str]` (OO1): con la tupla,
    el significado de cada elemento dependia del orden y no se veia en ninguna firma."""

    severidad: Severidad
    donde: str
    """Ruta relativa del archivo, con `:linea` cuando la comprobacion la conoce."""
    mensaje: str
    """Que esta mal Y por que importa. Un hallazgo que solo dice que algo esta mal obliga
    al desarrollador a investigar desde cero."""

    @property
    def bloquea(self) -> bool:
        return self.severidad is Severidad.ERROR


def error(donde: str, mensaje: str) -> Hallazgo:
    return Hallazgo(Severidad.ERROR, donde, mensaje)


def aviso(donde: str, mensaje: str) -> Hallazgo:
    return Hallazgo(Severidad.AVISO, donde, mensaje)


@dataclass(frozen=True)
class Inventario:
    """Cuantos artefactos de cada tipo encontro el validador en el arbol real, y si hay plugin.

    Se compara contra lo DECLARADO en `GOVERNANCE.json`: un catalogo que publica un inventario
    que no existe es peor que no tener catalogo.
    """

    skills: int = 0
    agentes: int = 0
    prompts: int = 0
    mcps: int = 0
    hooks: int = 0
    tiene_plugin: bool = False

    def como_declarado(self) -> dict[str, int]:
        """Las claves con las que el inventario se declara en `GOVERNANCE.json`."""
        return {"skills": self.skills, "agents": self.agentes, "prompts": self.prompts}


@dataclass(frozen=True)
class ArtefactoPublicado:
    """Lo que el catalogo necesita saber de UN artefacto. Sale del envelope, que el gate ya valido."""

    id: str
    tipo: str
    ruta: str
    owner_team: str
    owner_contact: str
    version: str
    data_classification: str
    standard_version: str


@dataclass(frozen=True)
class Veredicto:
    """Resultado de validar un repositorio. Inmutable: se construye una vez, al final.

    Sustituye a la lista global que las comprobaciones mutaban (P5): con estado global, dos
    validaciones seguidas en el mismo proceso acumulaban los hallazgos de la primera, y el
    efecto secundario no aparecia en ninguna firma (G4).
    """

    hallazgos: tuple[Hallazgo, ...]
    inventario: Inventario
    artefactos: tuple[ArtefactoPublicado, ...] = ()

    @property
    def errores(self) -> tuple[Hallazgo, ...]:
        return tuple(h for h in self.hallazgos if h.bloquea)

    @property
    def avisos(self) -> tuple[Hallazgo, ...]:
        return tuple(h for h in self.hallazgos if not h.bloquea)

    @property
    def conforme(self) -> bool:
        """Los avisos NO bloquean: senalan lo que conviene mirar, no lo que impide publicar."""
        return not self.errores
