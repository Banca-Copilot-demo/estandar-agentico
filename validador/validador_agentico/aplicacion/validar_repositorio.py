"""Caso de uso: validar un repositorio y devolver el veredicto.

Orquesta el dominio con lo que el adaptador de repositorio le entrega. No hace I/O propio y no
imprime nada: DEVUELVE un `Veredicto` y quien lo llame decide que hacer con el (G4 — los efectos
secundarios son explicitos).

Los adaptadores llegan como argumentos con un default sobreescribible, de modo que una prueba
pueda inyectar dobles sin tocar disco.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from validador_agentico.adaptadores import digesto
from validador_agentico.adaptadores import frontmatter as adaptador_frontmatter
from validador_agentico.adaptadores import repositorio as adaptador_repositorio
from validador_agentico.adaptadores.repositorio import ArchivoJson, ContenidoRepositorio
from validador_agentico.dominio import reglas_agente_instructions, reglas_aprobacion
from validador_agentico.dominio import reglas_credenciales, reglas_layout, reglas_recursos
from validador_agentico.dominio import reglas_higiene, reglas_hooks
from validador_agentico.dominio import reglas_artefacto, reglas_plugin
from validador_agentico.dominio.especificacion import RUTAS_MANIFIESTO
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
    raices = reglas_layout.raices_de_plugin(raiz, RUTAS_MANIFIESTO)
    varios = reglas_layout.es_multiplugin(raices, raiz)
    if varios:
        log.info("el repositorio aloja %d plugins: %s", len(raices),
                 ", ".join(r.name for r in raices))

    # UN veredicto para todo el repositorio, aunque se revise plugin a plugin: la regla de un solo
    # gate y un solo veredicto no cambia porque el layout tenga niveles.
    hallazgos: list[Hallazgo] = []
    inventario = Inventario()
    artefactos: list = []
    custodia: dict = {}
    for raiz_plugin in raices:
        contenido = repositorio.leer(raiz_plugin, lector)
        prefijo = f"{raiz_plugin.relative_to(raiz).as_posix()}/" if varios else ""
        parcial = _construir_inventario(contenido)
        inventario = _sumar_inventarios(inventario, parcial)
        hallazgos += _prefijar(prefijo, [
            *_revisar_plugin(contenido),
            *_revisar_gobierno(contenido, parcial),
            *_revisar_skills(contenido),
            *_revisar_prompts(contenido),
            *_revisar_agentes(contenido),
            *_revisar_instructions(contenido),
            *_revisar_hooks(contenido),
            *_revisar_mcp(contenido),
            *_revisar_yaml(contenido),
            *_revisar_recursos(contenido),
            *_revisar_duenos(contenido, equipos_conocidos),
        ])
        artefactos += _listar_artefactos(contenido, raiz_plugin)
        custodia = {**custodia, **_custodia_declarada(contenido)}

    # Estas dos son del REPOSITORIO, no de cada plugin: la higiene se revisa sobre el arbol
    # completo -- un secreto no deja de serlo por estar fuera de un plugin -- y la mezcla de
    # firmantes se juzga sobre el pull request entero.
    del_repositorio = repositorio.leer(raiz, lector)
    hallazgos += [*_revisar_higiene(del_repositorio), *_revisar_mezcla(archivos_cambiados)]

    log.info("%d hallazgo(s) en %s", len(hallazgos), raiz.name)
    return Veredicto(hallazgos=tuple(hallazgos), inventario=inventario,
                     artefactos=tuple(artefactos), credencial_ownership=custodia)


def _prefijar(prefijo: str, hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    """Anade la ruta del plugin al `donde` de cada hallazgo. Sin esto, dos plugins con el mismo
    defecto en el mismo archivo producirian dos mensajes identicos y nadie sabria cual arreglar."""
    if not prefijo:
        return hallazgos
    return [replace(h, donde=f"{prefijo}{h.donde}") for h in hallazgos]


def _sumar_inventarios(a: Inventario, b: Inventario) -> Inventario:
    """El inventario del repositorio es la suma del de sus plugins. `tiene_plugin` es un O: basta
    que uno lo tenga para que el repositorio publique al marketplace."""
    return Inventario(
        skills=a.skills + b.skills, agentes=a.agentes + b.agentes,
        prompts=a.prompts + b.prompts, mcps=a.mcps + b.mcps, hooks=a.hooks + b.hooks,
        tiene_plugin=a.tiene_plugin or b.tiene_plugin,
        nombre_plugin=a.nombre_plugin or b.nombre_plugin)


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


def _revisar_recursos(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    """G2 — los archivos que cada artefacto referencia tienen que existir. Se aplica a los cuatro
    tipos con cuerpo: un `.agent.md` que apunta a un script inexistente falla igual que un skill."""
    hallazgos: list[Hallazgo] = []
    for artefacto in (contenido.skills + contenido.prompts
                      + contenido.agentes_leidos + contenido.instructions):
        hallazgos += reglas_recursos.revisar_recursos_referenciados(
            artefacto.ruta_relativa, artefacto.cuerpo, contenido.rutas)
        hallazgos += reglas_recursos.revisar_recursos_no_referenciados(
            artefacto.ruta_relativa, artefacto.cuerpo, contenido.rutas)
    return hallazgos


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


def _artefacto_publicado(tipo: str, ruta: str, frontmatter: dict,
                         raiz: Path) -> ArtefactoPublicado | None:
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
        sha256=digesto.sha256_de(raiz / ruta),
    )


def _listar_artefactos(contenido: ContenidoRepositorio,
                       raiz: Path) -> tuple[ArtefactoPublicado, ...]:
    publicados: list[ArtefactoPublicado] = []
    for coleccion, tipo in _TIPO_POR_COLECCION:
        for artefacto in getattr(contenido, coleccion):
            if artefacto.frontmatter is None:
                continue
            publicado = _artefacto_publicado(tipo, artefacto.ruta_relativa,
                                             artefacto.frontmatter, raiz)
            if publicado is not None:
                publicados.append(publicado)
    return tuple(publicados)


def _revisar_mcp(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    """El `.mcp.json` del repositorio, si lo hay. La custodia de la credencial se revisa aqui y no en
    G3 porque no es higiene del contenido: es gobierno -- quien concede el acceso --."""
    if contenido.mcp is None:
        return []
    if not contenido.mcp.es_legible:
        return _hallazgo_de_formato(contenido.mcp)
    return reglas_credenciales.revisar_credenciales(
        contenido.mcp.ruta_relativa, contenido.mcp.contenido.get("credentials"))


def _custodia_declarada(contenido: ContenidoRepositorio) -> dict:
    """El bloque `ownership` del `.mcp.json`, si lo hay. Se propaga tal cual: la regla ya comprobo
    que este completo, y aqui solo se transporta hacia el predicado firmado."""
    if contenido.mcp is None or not contenido.mcp.es_legible:
        return {}
    return (contenido.mcp.contenido.get("credentials") or {}).get("ownership") or {}


def _revisar_agentes(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for agente in contenido.agentes_leidos:
        if agente.frontmatter is None:
            hallazgos.append(error(agente.ruta_relativa,
                                   "sin frontmatter: el agente es indescubrible"))
            continue
        hallazgos += reglas_agente_instructions.revisar_agente(
            agente.ruta_relativa, agente.nombre_directorio, agente.frontmatter)
        hallazgos += reglas_artefacto.revisar_envelope(
            agente.ruta_relativa, agente.frontmatter.get("metadata") or {})
    return hallazgos


def _revisar_instructions(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for instruccion in contenido.instructions:
        if instruccion.frontmatter is None:
            hallazgos.append(error(instruccion.ruta_relativa, "sin frontmatter"))
            continue
        hallazgos += reglas_agente_instructions.revisar_instructions(
            instruccion.ruta_relativa, instruccion.frontmatter, instruccion.lineas)
        hallazgos += reglas_artefacto.revisar_envelope(
            instruccion.ruta_relativa, instruccion.frontmatter.get("metadata") or {})
    return hallazgos


def _revisar_yaml(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    """Un frontmatter que no es YAML valido hace que el cliente SALTE el artefacto sin avisar.

    Es error y no aviso: el artefacto existe, pasa todas las demas reglas y no se carga nunca. Es
    exactamente el caso que G1 -- que el artefacto exista de forma comprobable -- tiene que atrapar.
    """
    todos = (*contenido.skills, *contenido.prompts, *contenido.agentes_leidos,
             *contenido.instructions)
    return [
        error(artefacto.ruta_relativa,
              f"el frontmatter no es YAML valido ({artefacto.yaml_invalido}): el cliente se salta "
              "el artefacto sin avisar. Suele ser un `:` o un `#` sin entrecomillar")
        for artefacto in todos if artefacto.yaml_invalido
    ]
