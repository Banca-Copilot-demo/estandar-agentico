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
# LOS DOS NOMBRES QUE LOS PLUGINS REALES USAN, y buscar solo el primero era un fallo ABIERTO.
# Medido sobre los catalogos publicos: 16 archivos se llaman `.mcp.json` y 5 `mcp.json` -- estos
# ultimos en `github/awesome-copilot`, tres de ellos DENTRO de `plugins/` --. El gate solo miraba el
# primero, asi que un plugin que declarara su MCP a la manera de Copilot quedaba INVISIBLE: inventario
# 0, ninguna ficha, ningun error y veredicto CONFORME. Se comprobo con un servidor fijado a `@latest`,
# que es justo el defecto que la regla del rug pull existe para cazar.
#
# El orden importa: si por lo que sea aparecieran los dos, manda `.mcp.json`, que es el que la
# especificacion de plugins documenta.
RUTAS_MCP = (".mcp.json", "mcp.json")
DIRECTORIO_VALIDADOR = "validador"

# Las suites de evals van CO-LOCALIZADAS con lo que evaluan -- `<lo-que-sea>/evals/*.eval.json` -- y no
# en un directorio central del repositorio. El motivo es el mismo por el que el gobierno del `mcp` vive
# en el plugin: una suite lejos de su artefacto se queda atras cuando el artefacto cambia, y nadie lo
# nota porque el archivo sigue ahi y sigue pasando.
DIRECTORIO_EVALS = "evals"
SUFIJO_EVAL = "*.eval.json"


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
    # Motivo por el que el frontmatter NO es YAML valido, o None si lo es. Un artefacto con YAML
    # roto lo SALTAN los clientes sin avisar, asi que el gate tiene que verlo.
    yaml_invalido: str | None = None
    # El texto tras el frontmatter. G2 revisa las rutas que referencia.
    cuerpo: str = ""


@dataclass(frozen=True)
class ContenidoRepositorio:
    """Todo lo que el validador necesita del repositorio, leido una sola vez."""

    manifiesto: ArchivoJson | None = None
    gobierno: ArchivoJson | None = None
    gobierno_heredado: bool = False
    """El gobierno no es de esta unidad sino del repositorio que la aloja. Pasa con un ARTEFACTO
    SUELTO publicado por separado, que no declara gobierno propio.

    IMPORTA PARA LAS REGLAS DE IDENTIDAD: un gobierno heredado describe el REPOSITORIO, asi que su
    `id` y su `version` no son los de esta unidad y compararlos con el manifiesto da un error falso
    -- medido: «`id` (demo.sdlc.sueltos) no coincide con `name` (demo.sdlc.revisar-jql)», que es
    exactamente lo que debe pasar y no un defecto --. Lo que si se hereda y si aplica es el DUENO,
    el dominio y la clasificacion del dato."""
    hooks: ArchivoJson | None = None
    # El `.mcp.json` LEIDO, no solo contado: hay reglas que se aplican sobre lo que declara -- que
    # sus referencias esten FIJADAS a una version, por ejemplo -- y para eso hace falta su contenido.
    mcp: ArchivoJson | None = None
    suites_de_evals: tuple[ArchivoJson, ...] = ()
    """Las suites `evals/*.eval.json` de la unidad, LEIDAS. Son varias -- una por artefacto y tipo de
    evaluacion -- a diferencia del gobierno o el mcp, que son uno por unidad."""
    skills: tuple[Artefacto, ...] = ()
    prompts: tuple[Artefacto, ...] = ()
    # Se LEEN, no solo se cuentan: sin frontmatter no hay gate que aplicarles.
    agentes_leidos: tuple[Artefacto, ...] = ()
    agentes: int = 0
    mcps: int = 0
    archivos_escaneables: tuple[tuple[str, str], ...] = field(default=())
    """Pares (ruta relativa, contenido) para el gate de higiene."""
    rutas: frozenset[str] = field(default=frozenset())
    """TODAS las rutas del arbol, para resolver las referencias a recursos de G2. Son todas y no
    solo las escaneables: un `.png` de `assets/` no se escanea y aun asi tiene que existir."""


def _archivo_mcp(raiz: Path) -> Path | None:
    """El archivo de configuracion MCP de esta unidad, con cualquiera de los dos nombres en uso.

    `None` si no hay ninguno. Se busca en el orden de `RUTAS_MCP`, o sea `.mcp.json` primero.
    """
    for relativa in RUTAS_MCP:
        candidato = raiz / relativa
        if candidato.is_file():
            return candidato
    return None


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


def _leer_skill_en_la_raiz(raiz: Path, lector) -> tuple[Artefacto, ...]:
    """El skill cuando la unidad ES el skill: `SKILL.md` en la raiz de la unidad, sin `skills/`.

    ES LA FORMA QUE LOS CLIENTES YA ESPERAN, y esta medido instalando en los dos: un plugin que
    entrega exactamente un skill puede llevar su `SKILL.md` en la raiz, y entonces el nombre de
    invocacion sale del frontmatter -- sin prefijo de plugin --. Asi, publicar un skill suelto por
    separado NO obliga a reestructurar nada: basta anadirle el manifiesto donde ya vive.

    La ruta se emite RELATIVA A LA UNIDAD -- `SKILL.md` a secas -- porque quien compone el veredicto
    le antepone la subruta de su unidad. Emitirla completa la duplicaria.
    """
    definicion = raiz / ARCHIVO_SKILL
    if not definicion.is_file():
        return ()
    return (Artefacto(
        ruta_relativa=ARCHIVO_SKILL,
        nombre_directorio=raiz.name,
        frontmatter=lector.leer(definicion),
        yaml_invalido=lector.es_yaml_valido(definicion),
        lineas=lector.contar_lineas(definicion),
        cuerpo=lector.leer_cuerpo(definicion),
    ),)


def _leer_artefactos_por_directorio(raiz: Path, lector) -> tuple[Artefacto, ...]:
    en_la_raiz = _leer_skill_en_la_raiz(raiz, lector)
    if en_la_raiz:
        return en_la_raiz
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
            yaml_invalido=lector.es_yaml_valido(definicion) if definicion.exists() else None,
            lineas=lector.contar_lineas(definicion) if definicion.exists() else 0,
            cuerpo=lector.leer_cuerpo(definicion) if definicion.exists() else "",
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
            yaml_invalido=lector.es_yaml_valido(archivo),
            lineas=lector.contar_lineas(archivo),
            cuerpo=lector.leer_cuerpo(archivo),
        )
        for archivo in sorted(directorio.glob(SUFIJO_PROMPT))
    )


def _leer_agentes(raiz: Path, lector) -> tuple[Artefacto, ...]:
    directorio = raiz / DIRECTORIO_AGENTES
    if not directorio.is_dir():
        return ()
    return tuple(
        Artefacto(
            ruta_relativa=f"{DIRECTORIO_AGENTES}/{archivo.name}",
            # El nombre esperado es el del archivo sin `.agent.md`, no `Path.stem`, que solo quita
            # la ultima extension y dejaria `migrador.agent`.
            nombre_directorio=archivo.name.removesuffix(".agent.md"),
            frontmatter=lector.leer(archivo),
            yaml_invalido=lector.es_yaml_valido(archivo),
            lineas=lector.contar_lineas(archivo),
            cuerpo=lector.leer_cuerpo(archivo),
        )
        for archivo in sorted(directorio.glob(SUFIJO_AGENTE))
    )


def _leer_suites_de_evals(raiz: Path) -> tuple[ArchivoJson, ...]:
    """Las suites `*/evals/*.eval.json` de la unidad, a cualquier profundidad.

    A CUALQUIER PROFUNDIDAD, y no en un directorio fijo, porque una suite va co-localizada con lo que
    evalua: la de un skill esta en `skills/<nombre>/evals/`, y la de un `mcp` -- que es uno por unidad y
    no tiene carpeta propia -- en `evals/` de la raiz. Un unico patron cubre los dos.

    SE EXCLUYEN LAS SUITES DE PLUGINS ANIDADOS, y la primera version no lo hacia porque razone que
    «cada unidad se lee con su propia raiz, asi que aqui no hay ninguno debajo». ES FALSO para el
    CONJUNTO SUELTO de un repositorio mixto: su raiz es la del repositorio, y `plugins/` cuelga de ahi.
    El sintoma al ejecutarlo fue inequivoco -- la suite del `mcp` aparecio DOS veces, una en su unidad
    y otra en la del suelto, y en la segunda el cotejo decia «esa unidad no publica ningun artefacto
    con ese id» listando los ids de la RAIZ --. O sea que una suite correcta producia un error falso, y
    ademas se contaba dos veces.
    """
    encontradas = sorted(
        archivo for archivo in raiz.rglob(f"{DIRECTORIO_EVALS}/{SUFIJO_EVAL}")
        if archivo.is_file() and ".git" not in archivo.parts
        and not _bajo_un_plugin_anidado(raiz, archivo)
    )
    return tuple(_leer_json(raiz, archivo) for archivo in encontradas)


def _bajo_un_plugin_anidado(raiz: Path, archivo: Path) -> bool:
    """Si el archivo cuelga de un directorio -- distinto de `raiz` -- que es raiz de otro plugin.

    Se resuelve por la presencia de un manifiesto y no por el nombre `plugins/`, que es solo una
    convencion: un plugin anidado se reconoce por tener `plugin.json`, no por donde este.
    """
    for antepasado in archivo.parents:
        if antepasado == raiz:
            return False
        if any((antepasado / relativa).is_file() for relativa in RUTAS_MANIFIESTO):
            return True
    return False


def _leer_rutas(raiz: Path) -> frozenset[str]:
    """Todas las rutas versionables del arbol, en POSIX y relativas a la raiz."""
    return frozenset(
        archivo.relative_to(raiz).as_posix()
        for archivo in raiz.rglob("*")
        if archivo.is_file() and ".git" not in archivo.parts
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


def leer(raiz: Path, lector, gobierno_de_respaldo: Path | None = None) -> ContenidoRepositorio:
    """Lee el repositorio completo una sola vez. `lector` es el adaptador de frontmatter.

    `gobierno_de_respaldo` es el `GOVERNANCE.json` que se usa cuando la unidad no trae el suyo. Solo
    lo pasa el composition root, y solo para un ARTEFACTO SUELTO publicado por separado: ese artefacto
    vive en el repositorio del dominio, cuyo gobierno de la raiz ya declara dueno, dominio y
    clasificacion. Exigirle uno propio obligaria a escribir un archivo de gobierno por cada skill del
    inventario -- decenas -- para repetir los mismos tres campos. Un PLUGIN si declara el suyo: agrupa
    varios artefactos y puede tener dueno distinto del repositorio que lo aloja.
    """
    log.debug("leyendo el repositorio %s", raiz)
    manifiesto = _primera_existente(raiz, RUTAS_MANIFIESTO)
    gobierno = raiz / RUTA_GOBIERNO
    # La BASE del gobierno se lleva aparte porque un gobierno heredado NO cuelga de la unidad, y
    # `_leer_json` calcula su ruta relativa contra la base que se le da.
    base_del_gobierno = raiz
    if not gobierno.exists() and gobierno_de_respaldo is not None and gobierno_de_respaldo.exists():
        log.debug("%s hereda el gobierno de %s", raiz, gobierno_de_respaldo)
        gobierno = gobierno_de_respaldo
        base_del_gobierno = gobierno_de_respaldo.parent
    hooks = _primera_existente(raiz, RUTAS_HOOKS)
    agentes_leidos = _leer_agentes(raiz, lector)
    return ContenidoRepositorio(
        manifiesto=_leer_json(raiz, manifiesto) if manifiesto else None,
        gobierno=_leer_json(base_del_gobierno, gobierno) if gobierno.exists() else None,
        gobierno_heredado=base_del_gobierno != raiz,
        hooks=_leer_json(raiz, hooks) if hooks else None,
        mcp=_leer_json(raiz, _archivo_mcp(raiz)) if _archivo_mcp(raiz) else None,
        suites_de_evals=_leer_suites_de_evals(raiz),
        skills=_leer_artefactos_por_directorio(raiz, lector),
        prompts=_leer_prompts(raiz, lector),
        agentes=len(agentes_leidos),
        agentes_leidos=agentes_leidos,
        mcps=1 if _archivo_mcp(raiz) else 0,
        archivos_escaneables=_leer_archivos_escaneables(raiz),
        rutas=_leer_rutas(raiz),
    )
