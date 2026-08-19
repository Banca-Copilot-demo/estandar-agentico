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
from validador_agentico.dominio import reglas_aprobacion, reglas_higiene, reglas_hooks
from validador_agentico.dominio import reglas_artefacto, reglas_plugin
from validador_agentico.dominio.hallazgo import (
    ArtefactoPublicado,
    Hallazgo,
    Inventario,
    Veredicto,
    error,
)

log = logging.getLogger(__name__)


def validar(raiz: Path, *, lector=adaptador_frontmatter,
            repositorio=adaptador_repositorio,
            equipos_conocidos: frozenset[str] | None = None,
            archivos_cambiados: tuple[str, ...] | None = None) -> Veredicto:
    """`equipos_conocidos` y `archivos_cambiados` llegan como DATOS y no como adaptadores: son
    contexto que el composition root resuelve una sola vez. Los dos admiten `None`, que significa
    «no se pudo averiguar» y produce un aviso -- nunca un pase silencioso."""
    contenido = repositorio.leer(raiz, lector)
    inventario = _construir_inventario(contenido)
    hallazgos = [
        *_revisar_plugin(contenido),
        *_revisar_gobierno(contenido, inventario),
        *_revisar_skills(contenido),
        *_revisar_prompts(contenido),
        *_revisar_hooks(contenido),
        *_revisar_higiene(contenido),
        *_revisar_duenos(contenido, equipos_conocidos),
        *_revisar_mezcla(archivos_cambiados),
    ]
    log.info("%d hallazgo(s) en %s", len(hallazgos), raiz.name)
    return Veredicto(hallazgos=tuple(hallazgos), inventario=inventario,
                     artefactos=_listar_artefactos(contenido))


def _construir_inventario(contenido: ContenidoRepositorio) -> Inventario:
    return Inventario(
        skills=len(contenido.skills),
        agentes=contenido.agentes,
        prompts=len(contenido.prompts),
        mcps=contenido.mcps,
        hooks=1 if contenido.hooks else 0,
        tiene_plugin=contenido.manifiesto is not None and contenido.manifiesto.es_legible,
        nombre_plugin=_nombre_del_plugin(contenido),
    )


def _nombre_del_plugin(contenido: ContenidoRepositorio) -> str:
    if contenido.manifiesto is None or not contenido.manifiesto.es_legible:
        return ""
    return contenido.manifiesto.contenido.get("name", "")


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


def _equipos_declarados(contenido: ContenidoRepositorio) -> list[tuple[str, str]]:
    """Todos los `owner_team` del repositorio, con donde se declaro cada uno."""
    declarados: list[tuple[str, str]] = []
    if contenido.gobierno is not None and contenido.gobierno.es_legible:
        equipo = (contenido.gobierno.contenido.get("owner") or {}).get("team")
        if equipo:
            declarados.append((contenido.gobierno.ruta_relativa, equipo))
    for artefacto in (*contenido.skills, *contenido.prompts):
        metadata = (artefacto.frontmatter or {}).get("metadata") or {}
        equipo = metadata.get("owner_team")
        if equipo:
            declarados.append((artefacto.ruta_relativa, equipo))
    return declarados


def _revisar_duenos(contenido: ContenidoRepositorio,
                    equipos_conocidos: frozenset[str] | None) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for donde, equipo in _equipos_declarados(contenido):
        hallazgos += reglas_aprobacion.revisar_equipo_resoluble(donde, equipo, equipos_conocidos)
    return hallazgos


def _revisar_mezcla(archivos_cambiados: tuple[str, ...] | None) -> list[Hallazgo]:
    """Sin la lista de cambios no se puede comprobar la mezcla. No se avisa aqui: fuera de un pull
    request -- una validacion local del arbol completo -- la regla NO APLICA, y un aviso en cada
    ejecucion local ensenaria a ignorarlo."""
    if archivos_cambiados is None:
        return []
    return reglas_aprobacion.revisar_mezcla_de_aprobadores(archivos_cambiados)


_TIPO_POR_COLECCION = (("skills", "skill"), ("prompts", "prompt"))


def _artefacto_publicado(tipo: str, ruta: str, frontmatter: dict) -> ArtefactoPublicado | None:
    """`None` cuando el envelope no esta completo: un artefacto sin gobierno no tiene ficha que
    publicar, y el gate ya lo habra marcado como error."""
    metadata = frontmatter.get("metadata") or {}
    identificador = metadata.get("id")
    if not identificador:
        return None
    return ArtefactoPublicado(
        id=identificador,
        tipo=tipo,
        ruta=ruta,
        owner_team=metadata.get("owner_team", ""),
        owner_contact=metadata.get("owner_contact", ""),
        version=str(metadata.get("version", "")),
        data_classification=metadata.get("data_classification", ""),
        standard_version=str(metadata.get("standard_version", "")),
    )


def _listar_artefactos(contenido: ContenidoRepositorio) -> tuple[ArtefactoPublicado, ...]:
    publicados: list[ArtefactoPublicado] = []
    for coleccion, tipo in _TIPO_POR_COLECCION:
        for artefacto in getattr(contenido, coleccion):
            if artefacto.frontmatter is None:
                continue
            publicado = _artefacto_publicado(tipo, artefacto.ruta_relativa, artefacto.frontmatter)
            if publicado is not None:
                publicados.append(publicado)
    return tuple(publicados)
