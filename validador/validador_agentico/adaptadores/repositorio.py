"""Adaptador de lectura del repositorio evaluado: recorre el arbol y devuelve lo que hay.

Es un ADAPTADOR porque toda su razon de ser es el I/O. No decide si algo esta bien: eso lo hacen
las reglas del dominio con lo que este modulo les entrega.

RESOLUCION SIN SUPUESTOS DE TOPOLOGIA: el validador vive en el repositorio del estandar y corre
sobre el repositorio de un dominio, asi que la raiz llega siempre como argumento y nunca se
deduce de la ubicacion del propio codigo.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from validador_agentico.dominio.especificacion import (
    EXTENSIONES_ESCANEABLES,
    RUTAS_HOOKS,
    RUTAS_MANIFIESTO,
)

log = logging.getLogger(__name__)

RUTA_GOBIERNO = "GOVERNANCE.json"
DIRECTORIO_SKILLS = "skills"
DIRECTORIO_AGENTES = "agents"
DIRECTORIO_PROMPTS = "commands"
ARCHIVO_SKILL = "SKILL.md"
SUFIJO_AGENTE = "*.agent.md"
SUFIJO_PROMPT = "*.prompt.md"
RUTA_MCP = ".mcp.json"
DIRECTORIO_VALIDADOR = "validador"


@dataclass(frozen=True)
class ArchivoJson:
    """Un JSON del repositorio: su ruta relativa y su contenido, o el motivo por el que no se pudo
    leer. Dataclass y no `tuple[str, dict | None, str | None]` (OO1)."""

    ruta_relativa: str
    contenido: dict | None = None
    error_de_formato: str | None = None

    @property
    def es_legible(self) -> bool:
        return self.contenido is not None


@dataclass(frozen=True)
class Artefacto:
    """Un artefacto localizado en el arbol, listo para que las reglas lo revisen."""

    ruta_relativa: str
    nombre_directorio: str
    frontmatter: dict | None
    lineas: int = 0


@dataclass(frozen=True)
class ContenidoRepositorio:
    """Todo lo que el validador necesita del repositorio, leido una sola vez."""

    manifiesto: ArchivoJson | None = None
    gobierno: ArchivoJson | None = None
    hooks: ArchivoJson | None = None
    skills: tuple[Artefacto, ...] = ()
    prompts: tuple[Artefacto, ...] = ()
    agentes: int = 0
    mcps: int = 0
    archivos_escaneables: tuple[tuple[str, str], ...] = field(default=())
    """Pares (ruta relativa, contenido) para el gate de higiene."""


def _leer_json(raiz: Path, ruta: Path) -> ArchivoJson:
    relativa = ruta.relative_to(raiz).as_posix()
    try:
        return ArchivoJson(relativa, json.loads(ruta.read_text(encoding="utf-8")))
    except json.JSONDecodeError as excepcion:
        # Un JSON corrupto es un HALLAZGO que hay que reportar, no una excepcion que mate el
        # proceso: el desarrollador necesita ver el resto de los hallazgos en la misma corrida.
        return ArchivoJson(relativa, error_de_formato=str(excepcion))


def _primera_existente(raiz: Path, rutas: tuple[str, ...]) -> Path | None:
    return next((raiz / r for r in rutas if (raiz / r).exists()), None)


def _leer_artefactos_por_directorio(raiz: Path, lector) -> tuple[Artefacto, ...]:
    directorio = raiz / DIRECTORIO_SKILLS
    if not directorio.is_dir():
        return ()
    artefactos = []
    for hijo in sorted(p for p in directorio.iterdir() if p.is_dir()):
        definicion = hijo / ARCHIVO_SKILL
        artefactos.append(Artefacto(
            ruta_relativa=f"{DIRECTORIO_SKILLS}/{hijo.name}/{ARCHIVO_SKILL}",
            nombre_directorio=hijo.name,
            frontmatter=lector.leer(definicion) if definicion.exists() else None,
            lineas=lector.contar_lineas(definicion) if definicion.exists() else 0,
        ))
    return tuple(artefactos)


def _leer_prompts(raiz: Path, lector) -> tuple[Artefacto, ...]:
    directorio = raiz / DIRECTORIO_PROMPTS
    if not directorio.is_dir():
        return ()
    return tuple(
        Artefacto(
            ruta_relativa=f"{DIRECTORIO_PROMPTS}/{archivo.name}",
            nombre_directorio=archivo.stem,
            frontmatter=lector.leer(archivo),
            lineas=lector.contar_lineas(archivo),
        )
        for archivo in sorted(directorio.glob(SUFIJO_PROMPT))
    )


def _leer_archivos_escaneables(raiz: Path) -> tuple[tuple[str, str], ...]:
    """Los archivos que el gate de higiene revisa. Excluye el propio validador: contiene los
    patrones a proposito y se delataria a si mismo."""
    escaneables = []
    for archivo in sorted(raiz.rglob("*")):
        if not archivo.is_file() or ".git" in archivo.parts:
            continue
        if archivo.suffix.lower() not in EXTENSIONES_ESCANEABLES:
            continue
        relativa = archivo.relative_to(raiz).as_posix()
        if relativa.startswith(f"{DIRECTORIO_VALIDADOR}/"):
            continue
        try:
            escaneables.append((relativa, archivo.read_text(encoding="utf-8")))
        except (UnicodeDecodeError, PermissionError) as excepcion:
            log.debug("no se pudo leer %s: %s", relativa, excepcion)
    return tuple(escaneables)


def leer(raiz: Path, lector) -> ContenidoRepositorio:
    """Lee el repositorio completo una sola vez. `lector` es el adaptador de frontmatter."""
    log.debug("leyendo el repositorio %s", raiz)
    manifiesto = _primera_existente(raiz, RUTAS_MANIFIESTO)
    gobierno = raiz / RUTA_GOBIERNO
    hooks = _primera_existente(raiz, RUTAS_HOOKS)
    directorio_agentes = raiz / DIRECTORIO_AGENTES
    return ContenidoRepositorio(
        manifiesto=_leer_json(raiz, manifiesto) if manifiesto else None,
        gobierno=_leer_json(raiz, gobierno) if gobierno.exists() else None,
        hooks=_leer_json(raiz, hooks) if hooks else None,
        skills=_leer_artefactos_por_directorio(raiz, lector),
        prompts=_leer_prompts(raiz, lector),
        agentes=len(list(directorio_agentes.glob(SUFIJO_AGENTE))) if directorio_agentes.is_dir() else 0,
        mcps=1 if (raiz / RUTA_MCP).exists() else 0,
        archivos_escaneables=_leer_archivos_escaneables(raiz),
    )
