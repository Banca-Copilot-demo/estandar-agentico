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

from validador_agentico.adaptadores import esquema
from validador_agentico.adaptadores import frontmatter as adaptador_frontmatter
from validador_agentico.adaptadores import repositorio as adaptador_repositorio
from validador_agentico.adaptadores.repositorio import (
    RUTA_GOBIERNO,
    ArchivoJson,
    ContenidoRepositorio,
)
from validador_agentico.aplicacion import proyeccion
from validador_agentico.dominio import reglas_agente, reglas_aprobacion
from validador_agentico.dominio import reglas_credenciales, reglas_layout, reglas_mcp
from validador_agentico.dominio import reglas_instructions, reglas_recursos
from validador_agentico.dominio import reglas_higiene, reglas_hooks
from validador_agentico.dominio import reglas_artefacto, reglas_plugin
from validador_agentico.dominio import ensamblado
from validador_agentico.dominio.especificacion import RUTAS_MANIFIESTO
from validador_agentico.dominio.hallazgo import (
    Hallazgo,
    Inventario,
    Veredicto,
    error,
)

log = logging.getLogger(__name__)


def validar(raiz: Path, *, lector=adaptador_frontmatter,
            repositorio=adaptador_repositorio,
            equipos_conocidos: frozenset[str] | None = None,
            archivos_cambiados: tuple[str, ...] | None = None,
            directorio_de_esquemas: Path | None = None) -> Veredicto:
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
    plugins: list = []
    custodia: dict = {}
    for raiz_plugin in raices:
        contenido = repositorio.leer(raiz_plugin, lector)
        prefijo = f"{raiz_plugin.relative_to(raiz).as_posix()}/" if varios else ""
        parcial = proyeccion.construir_inventario(contenido)
        inventario = proyeccion.sumar_inventarios(inventario, parcial)
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
            *_revisar_forma_contra_esquemas(contenido, directorio_de_esquemas),
        ])
        artefactos += proyeccion.listar_artefactos(contenido, raiz_plugin)
        publicado = proyeccion.plugin_publicado(contenido, raiz_plugin, raiz)
        if publicado is not None:
            plugins.append(publicado)
        custodia = {**custodia, **proyeccion.custodia_declarada(contenido)}

    # Estas TRES son del REPOSITORIO, no de cada plugin: la higiene se revisa sobre el arbol
    # completo -- un secreto no deja de serlo por estar fuera de un plugin --, la mezcla de
    # firmantes se juzga sobre el pull request entero, y el solapamiento de instructions se mide
    # entre TODAS las del repositorio: dos plugins vecinos se instalan juntos en el repositorio
    # destino, asi que comprobar cada plugin por separado dejaria pasar el caso mas probable.
    del_repositorio = repositorio.leer(raiz, lector)
    hallazgos += [*_revisar_higiene(del_repositorio), *_revisar_mezcla(archivos_cambiados),
                  *_revisar_solapamiento_de_instructions(del_repositorio)]

    log.info("%d hallazgo(s) en %s", len(hallazgos), raiz.name)
    return Veredicto(hallazgos=tuple(hallazgos), inventario=inventario,
                     artefactos=tuple(artefactos), plugins=tuple(plugins),
                     credencial_ownership=custodia)


def _prefijar(prefijo: str, hallazgos: list[Hallazgo]) -> list[Hallazgo]:
    """Anade la ruta del plugin al `donde` de cada hallazgo. Sin esto, dos plugins con el mismo
    defecto en el mismo archivo producirian dos mensajes identicos y nadie sabria cual arreglar."""
    if not prefijo:
        return hallazgos
    return [replace(h, donde=f"{prefijo}{h.donde}") for h in hallazgos]


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
    for donde, equipo in proyeccion.equipos_declarados(contenido):
        hallazgos += reglas_aprobacion.revisar_equipo_resoluble(donde, equipo, equipos_conocidos)
    return hallazgos


def _revisar_mezcla(archivos_cambiados: tuple[str, ...] | None) -> list[Hallazgo]:
    """Sin la lista de cambios no se puede comprobar la mezcla. No se avisa aqui: fuera de un pull
    request -- una validacion local del arbol completo -- la regla NO APLICA, y un aviso en cada
    ejecucion local ensenaria a ignorarlo."""
    if archivos_cambiados is None:
        return []
    return reglas_aprobacion.revisar_mezcla_de_aprobadores(archivos_cambiados)


def _revisar_mcp(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    """El `mcp`, que se gobierna con DOS archivos y hay que revisar los dos.

    El `.mcp.json` es la configuracion que lee el CLIENTE: de ahi sale si sus referencias estan
    fijadas a una version, y NO se le añade ninguna clave nuestra -- los plugins reales lo llevan con
    una sola, `mcpServers`, y meter mas nos haria depender de lo estricto que sea cada cliente --.

    El gobierno vive en `GOVERNANCE.json`, bajo la clave `mcp`. Un `mcp` es UNO POR PLUGIN, igual que
    el manifiesto y el gobierno, asi que no necesita archivo propio: los skills son muchos y por eso
    ellos si llevan hermano en su carpeta.
    """
    if contenido.mcp is None:
        return []
    if not contenido.mcp.es_legible:
        return _hallazgo_de_formato(contenido.mcp)

    hallazgos = reglas_mcp.revisar_servidores(
        contenido.mcp.ruta_relativa, contenido.mcp.contenido.get("mcpServers"))

    gobierno_del_mcp = _gobierno_del_mcp(contenido)
    if gobierno_del_mcp is None:
        return [*hallazgos, error(RUTA_GOBIERNO,
                                 "hay un `.mcp.json` pero el gobierno no declara `mcp`: sin eso el "
                                 "servidor no tiene dueno de la credencial ni aprobacion, y el "
                                 "`.mcp.json` no puede llevarlos porque lo consume el cliente")]

    return [*hallazgos, *reglas_credenciales.revisar_credenciales(
        RUTA_GOBIERNO, gobierno_del_mcp.get("credentials"))]


def _gobierno_del_mcp(contenido: ContenidoRepositorio) -> dict | None:
    """El bloque `mcp` del gobierno del plugin, o `None` si no lo declara."""
    if contenido.gobierno is None or not contenido.gobierno.es_legible:
        return None
    bloque = contenido.gobierno.contenido.get("mcp")
    return bloque if isinstance(bloque, dict) else None


def _revisar_agentes(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for agente in contenido.agentes_leidos:
        if agente.frontmatter is None:
            hallazgos.append(error(agente.ruta_relativa,
                                   "sin frontmatter: el agente es indescubrible"))
            continue
        hallazgos += reglas_agente.revisar_agente(
            agente.ruta_relativa, agente.nombre_directorio, agente.frontmatter)
        hallazgos += reglas_artefacto.revisar_envelope(
            agente.ruta_relativa, agente.frontmatter.get("metadata") or {})
    return hallazgos


def _revisar_instructions(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    """NO se les aplica el envelope: `instructions` dejo de ser un tipo gobernado -- no hay canal para
    distribuirlas, comprobado en la referencia de plugins de los dos clientes --. Lo que queda es
    higiene: dejar constancia de que existen y de su alcance, porque son el unico archivo que cambia
    el comportamiento del agente sin que nadie lo elija.

    Un archivo sin frontmatter tampoco es un error aqui: sin gobierno no hay campos obligatorios que
    exigir, y lo unico que se pierde es el `applyTo` -- que ya se avisa como tal --.
    """
    hallazgos: list[Hallazgo] = []
    for instruccion in contenido.instructions:
        hallazgos += reglas_instructions.revisar_instructions(
            instruccion.ruta_relativa, instruccion.frontmatter or {}, instruccion.lineas)
    return hallazgos


def _revisar_solapamiento_de_instructions(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    """Se pasan las que TIENEN ambito: la falta de `applyTo` ya la senala la regla por archivo, y
    volver a nombrarla aqui daria dos hallazgos por el mismo hecho."""
    declaradas = [
        (instruccion.ruta_relativa,
         reglas_instructions.ambito_de(instruccion.frontmatter or {}))
        for instruccion in contenido.instructions
    ]
    return reglas_instructions.revisar_solapamiento(
        [(donde, ambito) for donde, ambito in declaradas if ambito])


# Que esquema valida cada coleccion de artefactos, y con que `kind` se ensambla.
_ESQUEMA_POR_COLECCION = (
    ("skills", "skill", "skill.schema.json"),
    ("prompts", "prompt", "prompt.schema.json"),
    ("agentes_leidos", "agent", "agent.schema.json"),
)


def _revisar_forma_contra_esquemas(contenido: ContenidoRepositorio,
                                   directorio: Path | None) -> list[Hallazgo]:
    """G1 sobre los ESQUEMAS: que cada artefacto tenga la forma que su tipo declara.

    POR QUE ESTO Y LAS REGLAS A LA VEZ, sin duplicarse. El esquema valida la FORMA -- que los campos
    esten, que sean del tipo correcto, que los enums tengan un valor admitido, que no haya claves
    inventadas -- y es declarativo. Las reglas validan lo que un esquema NO PUEDE: que una fecha no
    haya vencido, que un equipo resuelva contra la organizacion, que una ruta exista en el arbol. Son
    comprobaciones contra el MUNDO, no contra la forma.

    POR QUE HACIA FALTA. Los esquemas eran documentos que ningun codigo ejecutaba, asi que decian una
    cosa y las reglas otra. Al ejecutarlos por primera vez aparecieron tres divergencias en los
    artefactos REALES de la demo: el esquema del prompt pedia `model` como array y la regla trata el
    array como error; exigia un `produces` que ningun prompt tenia; y el del skill rechazaba
    `license`, que es uno de los SEIS campos oficiales de la especificacion.

    SIN ESQUEMAS ES ERROR, no silencio: un gate que no puede comprobar y calla es indistinguible de
    uno que comprobo y aprobo. `directorio=None` significa «no se pidio esta comprobacion» -- para que
    una prueba de otra cosa no tenga que llevarse los esquemas detras --, y eso si es legitimo.
    """
    if directorio is None:
        return []

    hallazgos: list[Hallazgo] = []
    for coleccion, kind, nombre_esquema in _ESQUEMA_POR_COLECCION:
        for artefacto in getattr(contenido, coleccion):
            if artefacto.frontmatter is None:
                # La ausencia de frontmatter ya la senala la regla del tipo; aqui no hay objeto que
                # ensamblar y repetirlo daria dos hallazgos por el mismo defecto.
                continue
            objeto = ensamblado.ensamblar(
                adaptador_frontmatter.solo_lo_declarado(artefacto.frontmatter), None, kind)
            try:
                defectos = esquema.incumplimientos(objeto, nombre_esquema, directorio)
            except esquema.EsquemasNoDisponiblesError as fallo:
                return [error(str(directorio), f"no se pudo comprobar la forma: {fallo}")]
            hallazgos += [error(artefacto.ruta_relativa, f"forma invalida — {defecto}")
                          for defecto in defectos]
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
