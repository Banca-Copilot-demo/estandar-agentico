"""Caso de uso: validar un repositorio y devolver el veredicto.

Orquesta el dominio con lo que el adaptador de repositorio le entrega. No hace I/O propio y no
imprime nada: DEVUELVE un `Veredicto` y quien lo llame decide que hacer con el (G4 — los efectos
secundarios son explicitos).

Los adaptadores llegan como argumentos con un default sobreescribible, de modo que una prueba
pueda inyectar dobles sin tocar disco.
"""
from __future__ import annotations

import logging
from pathlib import Path

from validador_agentico.adaptadores import frontmatter as adaptador_frontmatter
from validador_agentico.adaptadores import repositorio as adaptador_repositorio
from validador_agentico.adaptadores.repositorio import ArchivoJson, ContenidoRepositorio
from validador_agentico.dominio import reglas_higiene, reglas_hooks, reglas_plugin
from validador_agentico.dominio import reglas_artefacto
from validador_agentico.dominio.hallazgo import Hallazgo, Inventario, Veredicto, error

log = logging.getLogger(__name__)


def validar(raiz: Path, *, lector=adaptador_frontmatter,
            repositorio=adaptador_repositorio) -> Veredicto:
    contenido = repositorio.leer(raiz, lector)
    inventario = _construir_inventario(contenido)
    hallazgos = [
        *_revisar_plugin(contenido),
        *_revisar_gobierno(contenido, inventario),
        *_revisar_skills(contenido),
        *_revisar_prompts(contenido),
        *_revisar_hooks(contenido),
        *_revisar_higiene(contenido),
    ]
    log.info("%d hallazgo(s) en %s", len(hallazgos), raiz.name)
    return Veredicto(hallazgos=tuple(hallazgos), inventario=inventario)


def _construir_inventario(contenido: ContenidoRepositorio) -> Inventario:
    return Inventario(
        skills=len(contenido.skills),
        agentes=contenido.agentes,
        prompts=len(contenido.prompts),
        mcps=contenido.mcps,
        hooks=1 if contenido.hooks else 0,
        tiene_plugin=contenido.manifiesto is not None and contenido.manifiesto.es_legible,
    )


def _hallazgo_de_formato(archivo: ArchivoJson) -> list[Hallazgo]:
    return [error(archivo.ruta_relativa, f"JSON invalido: {archivo.error_de_formato}")]


def _revisar_plugin(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    if contenido.manifiesto is None:
        return reglas_plugin.revisar_ausencia_de_plugin()
    if not contenido.manifiesto.es_legible:
        return _hallazgo_de_formato(contenido.manifiesto)
    return reglas_plugin.revisar_manifiesto(contenido.manifiesto.ruta_relativa,
                                            contenido.manifiesto.contenido)


def _revisar_gobierno(contenido: ContenidoRepositorio, inventario: Inventario) -> list[Hallazgo]:
    if contenido.gobierno is None:
        return reglas_plugin.revisar_gobierno_ausente() if inventario.tiene_plugin else []
    if not contenido.gobierno.es_legible:
        return _hallazgo_de_formato(contenido.gobierno)
    manifiesto = contenido.manifiesto.contenido if inventario.tiene_plugin else None
    return [
        *reglas_plugin.revisar_gobierno(contenido.gobierno.contenido, manifiesto),
        *reglas_plugin.revisar_inventario(
            (contenido.gobierno.contenido.get("artifacts") or {}), inventario),
    ]


def _revisar_skills(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for skill in contenido.skills:
        if skill.frontmatter is None:
            hallazgos.append(error(skill.ruta_relativa,
                                   "sin frontmatter: el artefacto es indescubrible"))
            continue
        hallazgos += reglas_artefacto.revisar_skill(
            skill.ruta_relativa, skill.nombre_directorio, skill.frontmatter, skill.lineas)
    return hallazgos


def _revisar_prompts(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for prompt in contenido.prompts:
        if prompt.frontmatter is None:
            hallazgos.append(error(prompt.ruta_relativa, "sin frontmatter"))
            continue
        hallazgos += reglas_artefacto.revisar_prompt(prompt.ruta_relativa, prompt.frontmatter)
    return hallazgos


def _revisar_hooks(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    if contenido.hooks is None:
        return []
    if not contenido.hooks.es_legible:
        return _hallazgo_de_formato(contenido.hooks)
    declarado = ((contenido.gobierno.contenido if contenido.gobierno
                  and contenido.gobierno.es_legible else {}).get("artifacts") or {})
    return reglas_hooks.revisar_hooks(contenido.hooks.ruta_relativa,
                                      contenido.hooks.contenido, declarado)


def _revisar_higiene(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for ruta_relativa, texto in contenido.archivos_escaneables:
        hallazgos += reglas_higiene.revisar_higiene(ruta_relativa, texto)
    return hallazgos
