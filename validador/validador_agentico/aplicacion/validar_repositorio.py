"""Caso de uso: validar un repositorio y devolver el veredicto.

Orquesta el dominio con lo que el adaptador de repositorio le entrega. No hace I/O propio y no
imprime nada: DEVUELVE un `Veredicto` y quien lo llame decide que hacer con el (G4 — los efectos
secundarios son explicitos).

Los adaptadores llegan como argumentos con un default sobreescribible, de modo que una prueba
pueda inyectar dobles sin tocar disco.

────────────────────────────────────────────────────────────────────────────────────────────────
POR QUE ESTE MODULO PASA DE ~300 LINEAS SIN DIVIDIRSE (tripwire de G1)

El umbral es un disparador de revision, no un limite, y la regla real es la cohesion. Aplicados los
dos tests que el estandar exige:

TEST DE LA CONJUNCION. Describir este archivo NO necesita «y»: aplica las reglas del dominio al
contenido leido y agrega los hallazgos. Eso es una sola frase. Lo que parece una lista de
responsabilidades -- revisa el plugin, el gobierno, los skills, los prompts... -- es la lista de
REGLAS, y las reglas viven cada una en su modulo de `dominio/`. Aqui no hay ni una decision de
negocio: cada `_revisar_*` traduce la forma de `ContenidoRepositorio` a la firma que su regla espera
y devuelve lo que esta responde.

TEST DE GRUPOS TEMATICOS. Las 19 funciones caen en UN grupo -- despacho de reglas -- salvo dos
ayudantes de tres lineas (`_prefijar`, `_hallazgo_de_formato`) que solo sirven a ese despacho.

Y YA SE EXTRAJO LO QUE SI ERA OTRA COSA: la proyeccion del contenido hacia el inventario, las fichas
y la custodia se fue a `aplicacion/proyeccion.py` cuando el modulo cruzo el umbral la primera vez.
Ese si era un segundo grupo. Lo que queda es el despacho, y partirlo por familias de regla --
«validar_artefactos.py», «validar_configuracion.py» -- seria dividir por la METRICA y no por el
significado, que es lo que G3 advierte: obligaria a que `validar()` llamara a dos orquestadores para
recomponer un unico veredicto, y el orden de agregacion -- que es lo unico que este modulo decide de
verdad -- quedaria repartido en tres sitios.

LO QUE SI JUSTIFICARIA DIVIDIRLO, para quien lo lea despues: que alguna de estas funciones deje de
ser un despacho y empiece a decidir algo. Ahi habria una regla mal colocada, y su sitio es
`dominio/`, no un modulo nuevo aqui.
────────────────────────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from validador_agentico.adaptadores import esquema
from validador_agentico.adaptadores import identidad_en_disco
from validador_agentico.adaptadores import frontmatter as adaptador_frontmatter
from validador_agentico.adaptadores import repositorio as adaptador_repositorio
from validador_agentico.adaptadores.repositorio import (
    DIRECTORIO_AGENTES,
    DIRECTORIO_PROMPTS,
    DIRECTORIO_SKILLS,
    RUTA_GOBIERNO,
    RUTA_MCP,
    ArchivoJson,
    ContenidoRepositorio,
)
from validador_agentico.aplicacion import proyeccion
from validador_agentico.dominio import reglas_agente, reglas_aprobacion
from validador_agentico.dominio import reglas_credenciales, reglas_evals, reglas_layout, reglas_mcp
from validador_agentico.dominio import reglas_recursos, reglas_version
from validador_agentico.dominio import reglas_higiene, reglas_hooks, reglas_huerfanos
from validador_agentico.dominio import scripts_de_hooks
from validador_agentico.dominio import reglas_artefacto, reglas_plugin
from validador_agentico.dominio import ensamblado, forma_frontmatter
from validador_agentico.dominio.especificacion import RUTAS_MANIFIESTO
from validador_agentico.dominio.hallazgo import (
    Hallazgo,
    Inventario,
    Veredicto,
    error,
)

log = logging.getLogger(__name__)

# Donde viven los artefactos dentro de una unidad. Se nombran aqui, en el composition root del caso de
# uso, y se pasan como dato a las reglas de dominio: `reglas_layout` y `reglas_huerfanos` deciden
# COSAS sobre artefactos sin tener que saber como se llaman sus directorios en disco (G5).
_DIRECTORIOS_DE_ARTEFACTOS = (DIRECTORIO_SKILLS, DIRECTORIO_AGENTES, DIRECTORIO_PROMPTS)
_ARCHIVOS_DE_ARTEFACTOS = (RUTA_MCP,)


def validar(raiz: Path, *, lector=adaptador_frontmatter,
            repositorio=adaptador_repositorio,
            equipos_conocidos: frozenset[str] | None = None,
            archivos_cambiados: tuple[str, ...] | None = None,
            versiones_en_base: dict[str, str | None] | None = None,
            directorio_de_esquemas: Path | None = None) -> Veredicto:
    """`equipos_conocidos`, `archivos_cambiados` y `versiones_en_base` llegan como DATOS y no como
    adaptadores: son contexto que el composition root resuelve una sola vez. Los tres admiten
    `None`, que significa «no se pudo averiguar» y produce un aviso -- nunca un pase silencioso."""
    raices = reglas_layout.unidades_publicables(
        raiz, RUTAS_MANIFIESTO,
        directorios_de_artefactos=_DIRECTORIOS_DE_ARTEFACTOS,
        archivos_de_artefactos=_ARCHIVOS_DE_ARTEFACTOS)
    varios = reglas_layout.es_multiunidad(raices, raiz)
    if varios:
        log.info("el repositorio publica %d unidad(es): %s", len(raices),
                 ", ".join(r.name if r != raiz else "(conjunto suelto)" for r in raices))

    # UN veredicto para todo el repositorio, aunque se revise plugin a plugin: la regla de un solo
    # gate y un solo veredicto no cambia porque el layout tenga niveles.
    hallazgos: list[Hallazgo] = []
    inventario = Inventario()
    artefactos: list = []
    plugins: list = []
    custodia: dict = {}
    for raiz_plugin in raices:
        contenido = repositorio.leer(raiz_plugin, lector)
        prefijo = _prefijo_de(raiz_plugin, raiz, varios)
        parcial = proyeccion.construir_inventario(contenido)
        inventario = proyeccion.sumar_inventarios(inventario, parcial)
        hallazgos += _prefijar(prefijo, [
            *_revisar_plugin(contenido),
            *_revisar_gobierno(contenido, parcial, _nombre_de_unidad(raiz_plugin, raiz)),
            *_revisar_skills(contenido),
            *_revisar_prompts(contenido),
            *_revisar_agentes(contenido),
            *_revisar_hooks(contenido, raiz_plugin),
            *_revisar_mcp(contenido),
            *_revisar_evals(contenido, raiz_plugin, directorio_de_esquemas),
            *_revisar_yaml(contenido),
            *_revisar_recursos(contenido),
            *_revisar_duenos(contenido, equipos_conocidos),
            *_revisar_forma_contra_esquemas(contenido, directorio_de_esquemas),
        ])
        # EL MISMO `prefijo` que ya se usa para los hallazgos: la ficha publica la ruta relativa al
        # REPOSITORIO, que es como la resuelven sus consumidores -- la pista de verificacion descarga
        # `<repo>/<ruta>` fijado al sha --. Sin el, un plugin anidado publicaba rutas que no existen
        # desde la raiz, y dos plugins con `.mcp.json` publicaban la MISMA ruta.
        artefactos += proyeccion.listar_artefactos(contenido, raiz_plugin, prefijo)
        publicado = proyeccion.plugin_publicado(contenido, raiz_plugin, raiz)
        if publicado is not None:
            plugins.append(publicado)
        custodia = {**custodia, **proyeccion.custodia_declarada(contenido)}

    # Estas TRES son del REPOSITORIO, no de cada plugin: la higiene se revisa sobre el arbol completo
    # -- un secreto no deja de serlo por estar fuera de un plugin --, la mezcla de firmantes se juzga
    # sobre el pull request entero, y los HUERFANOS solo se ven desde arriba: son artefactos que no
    # caen dentro de ninguna raiz de plugin, asi que por construccion ningun recorrido por plugin los
    # encuentra.
    del_repositorio = repositorio.leer(raiz, lector)
    hallazgos += [*_revisar_higiene(del_repositorio), *_revisar_mezcla(archivos_cambiados),
                  *_revisar_sin_unidad(raiz, del_repositorio),
                  *_revisar_subida_de_version(raiz, raices, archivos_cambiados, versiones_en_base)]

    log.info("%d hallazgo(s) en %s", len(hallazgos), raiz.name)
    return Veredicto(hallazgos=tuple(hallazgos), inventario=inventario,
                     artefactos=tuple(artefactos), plugins=tuple(plugins),
                     credencial_ownership=custodia)


def _prefijo_de(unidad: Path, raiz: Path, varios: bool) -> str:
    """La subruta de la unidad dentro del repositorio, o vacio si la unidad ES la raiz.

    EL CASO DE LA RAIZ SE TRATA APARTE, y es un defecto MEDIDO al instalar de verdad. La expresion era
    `f"{unidad.relative_to(raiz).as_posix()}/"`, y para la raiz `relative_to` devuelve `.`, asi que el
    prefijo salia `./` y el conjunto suelto de un repositorio MIXTO firmaba rutas como
    `./skills/revisar-jql/SKILL.md`. La API de GitHub tolera ese `./` -- se comprobo -- pero el mismo
    archivo pasaba a tener DOS rutas canonicas segun el layout: `skills/x` en un repositorio de puros
    sueltos y `./skills/x` en uno mixto. Cualquier comparacion de rutas -- deduplicar fichas, cruzar
    una ruta contra el diff de un pull request -- falla con eso, y encima queda escrito en un registro
    FIRMADO, que es donde menos se puede corregir despues.
    """
    if not varios or unidad == raiz:
        return ""
    return f"{unidad.relative_to(raiz).as_posix()}/"


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


def _nombre_de_unidad(unidad: Path, raiz: Path) -> str:
    """Como se nombra la unidad en un mensaje. `.` cuando la unidad ES el repositorio, que es el
    mismo nombre con el que `listar_plugins` la emite."""
    if unidad == raiz:
        return reglas_layout.RAIZ_DEL_REPOSITORIO
    return unidad.relative_to(raiz).as_posix()


def _lo_que_publica(inventario: Inventario) -> str:
    """Que hay dentro de la unidad, para que el mensaje de gobierno ausente diga POR QUE le toca
    declararlo. Sin esto el hallazgo obliga a ir a mirar el arbol para entender de que unidad habla.
    """
    if inventario.tiene_plugin:
        return f"plugin `{inventario.nombre_plugin}`"
    piezas = [f"{cuenta} {tipo}" for tipo, cuenta in inventario.como_declarado().items() if cuenta]
    return ", ".join(piezas)


def _revisar_gobierno(contenido: ContenidoRepositorio, inventario: Inventario,
                      unidad: str) -> list[Hallazgo]:
    if contenido.gobierno is None:
        # SOLO SE RECLAMA A QUIEN PUBLICA ALGO. `unidades_publicables` devuelve `(raiz,)` tambien
        # para un repositorio vacio o de puros documentos -- es lo que lo mantiene revisable -- y
        # exigirle gobierno a un repositorio que no publica ningun artefacto seria pedir un dueno
        # para nada. En cuanto aparece un plugin o un artefacto, la unidad publica y declara.
        que_publica = _lo_que_publica(inventario)
        if not que_publica:
            return []
        return reglas_plugin.revisar_gobierno_ausente(unidad, que_publica)
    if not contenido.gobierno.es_legible:
        return _hallazgo_de_formato(contenido.gobierno)
    manifiesto = contenido.manifiesto.contenido if inventario.tiene_plugin else None
    return [*reglas_plugin.revisar_gobierno(contenido.gobierno.contenido, manifiesto),
            *reglas_plugin.revisar_inventario(
                (contenido.gobierno.contenido.get("artifacts") or {}), inventario)]


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


def _revisar_hooks(contenido: ContenidoRepositorio, raiz_unidad: Path) -> list[Hallazgo]:
    if contenido.hooks is None:
        return []
    if not contenido.hooks.es_legible:
        return _hallazgo_de_formato(contenido.hooks)
    declarado = ((contenido.gobierno.contenido if contenido.gobierno
                  and contenido.gobierno.es_legible else {}).get("artifacts") or {})
    # QUE SCRIPTS EXISTEN se resuelve aqui, no en la regla: la regla es de dominio y comprueba que lo
    # referenciado este presente, pero mirar el disco es I/O y le toca a esta capa. Se comprueba
    # justo lo referenciado en vez de listar el arbol entero: un `scripts/` con veinte archivos de los
    # que el hook usa dos no tiene por que declararlos todos.
    # UNOS HOOKS VAN DENTRO DE UN PLUGIN, por el mismo motivo que el `mcp` y con mas fuerza: los hooks
    # se SUMAN entre capas de ajustes, asi que uno suelto no lo quita ninguna capa superior.
    hallazgos = reglas_hooks.revisar_que_esta_en_un_plugin(
        contenido.hooks.ruta_relativa,
        hay_manifiesto=contenido.manifiesto is not None and contenido.manifiesto.es_legible)
    presentes = frozenset(
        ruta for ruta in scripts_de_hooks.referencias_propias(contenido.hooks.contenido)
        if (raiz_unidad / ruta).is_file())
    return hallazgos + reglas_hooks.revisar_hooks(
        contenido.hooks.ruta_relativa, contenido.hooks.contenido, declarado,
        scripts_presentes=presentes)


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
                      + contenido.agentes_leidos):
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


def _revisar_subida_de_version(raiz: Path, raices: tuple[Path, ...],
                               archivos_cambiados: tuple[str, ...] | None,
                               versiones_en_base: dict[str, str | None] | None) -> list[Hallazgo]:
    """G5 — lo que cambia se declara: si una unidad cambio, su version tambien.

    Sin lista de cambios o sin rama base la regla NO APLICA y no se avisa, por la misma razon que en
    la mezcla de aprobadores: fuera de un pull request no hay contra que comparar, y un aviso en cada
    validacion local ensenaria a ignorarlo. En CI las dos llegan siempre, y cuando la base existe pero
    no se puede leer es `versiones_en_base` -- no esta funcion -- quien avisa.
    """
    if archivos_cambiados is None or versiones_en_base is None:
        return []
    unidades = []
    for unidad in raices:
        ruta = unidad.relative_to(raiz).as_posix() or reglas_layout.RAIZ_DEL_REPOSITORIO
        identidad = identidad_en_disco.identidad_de(unidad, raiz)
        if identidad is None:
            # Sin version declarada no hay nada que subir, y el gate ya lo reprocha por otra via:
            # una unidad sin `version` no se puede etiquetar y eso se dice donde se valida el
            # manifiesto. Repetirlo aqui daria dos errores para un solo defecto.
            continue
        unidades.append(reglas_version.VersionDeUnidad(
            ruta=ruta, nombre=identidad.nombre, version=identidad.version,
            version_en_base=versiones_en_base.get(ruta)))
    return reglas_version.revisar_subida_de_version(tuple(unidades), archivos_cambiados)


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

    # UN `mcp` VA DENTRO DE UN PLUGIN. Se comprueba aqui porque hace falta saber si esta unidad
    # tiene manifiesto, que es un dato del contenido y no del archivo de configuracion.
    hallazgos = reglas_mcp.revisar_que_esta_en_un_plugin(
        contenido.mcp.ruta_relativa,
        hay_manifiesto=contenido.manifiesto is not None and contenido.manifiesto.es_legible)
    hallazgos += reglas_mcp.revisar_servidores(
        contenido.mcp.ruta_relativa, contenido.mcp.contenido)
    # EL COTEJO GOBIERNO <-> CONFIGURACION. Necesita los dos archivos, asi que se despacha aqui.
    hallazgos += reglas_mcp.revisar_declaracion(
        contenido.mcp.ruta_relativa, contenido.mcp.contenido,
        (_gobierno_del_mcp(contenido) or {}).get("servers"))

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


def _revisar_sin_unidad(raiz: Path, contenido_de_la_raiz: ContenidoRepositorio) -> list[Hallazgo]:
    """Artefactos en la raiz que nadie publica, porque la raiz no declara con que version.

    Se resuelve aqui si el conjunto suelto se publica -- leyendo el gobierno de la raiz -- y se le
    pasa a la regla como un booleano: el dominio no tiene que saber en que archivo vive ese dato.
    """
    gobierno = contenido_de_la_raiz.gobierno
    publica = bool(
        gobierno is not None and gobierno.es_legible and gobierno.contenido.get("version"))
    rutas = reglas_huerfanos.artefactos_sin_unidad(
        raiz,
        hay_plugins=bool(reglas_layout.raices_de_plugin(raiz, RUTAS_MANIFIESTO)),
        publica_el_conjunto_suelto=publica,
        directorios=_DIRECTORIOS_DE_ARTEFACTOS,
        archivos=_ARCHIVOS_DE_ARTEFACTOS,
        rutas_manifiesto=RUTAS_MANIFIESTO)
    return reglas_huerfanos.revisar_sin_unidad(rutas)


# Que esquema valida cada coleccion de artefactos, y con que `kind` se ensambla.
_ESQUEMA_POR_COLECCION = (
    ("skills", "skill", "skill.schema.json"),
    ("prompts", "prompt", "prompt.schema.json"),
    ("agentes_leidos", "agent", "agent.schema.json"),
)

# Los documentos que se validan COMPLETOS contra su esquema, a diferencia de los artefactos, donde lo
# que se valida es el objeto ensamblado a partir del frontmatter.
#
# EL GOBIERNO FALTABA, y era el mismo defecto que la propia existencia de esta capa vino a cerrar: un
# esquema publicado como parte del entregable que NINGUN codigo ejecutaba. Se midio auditando el
# repositorio: `plugins/asistente-autoria/GOVERNANCE.json` declaraba `artifacts.instructions`, que su
# propio esquema PROHIBE -- `additionalProperties: false`, y la clave no esta entre las seis
# admitidas --, y el gate lo daba por CONFORME. El esquema decia una cosa, el repositorio otra, y no
# habia nada que lo notara.
#
# Y CABLEAR ESTE ESQUEMA EJECUTA TAMBIEN EL DEL `mcp`: `plugin-governance.schema.json` lo alcanza con
# tres `$ref` -- `aprobacion`, `credenciales`, `servidorGobernado` --. `mcp.schema.json` no es un
# esquema de documento suelto y no se valida por separado: es la caja de piezas que el gobierno
# referencia, que es el motivo por el que no aparecia en ninguna llamada.
_ESQUEMA_POR_DOCUMENTO = (
    ("gobierno", "plugin-governance.schema.json"),
)

# Las suites no van en `_ESQUEMA_POR_DOCUMENTO` porque son VARIAS por unidad, no una: ese recorrido
# resuelve un atributo con un documento, y las suites necesitan ademas la regla que las coteja contra
# el arbol. Van por `_revisar_evals`.
_ESQUEMA_DE_LA_SUITE = "eval-suite.schema.json"


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
    for atributo, nombre_esquema in _ESQUEMA_POR_DOCUMENTO:
        documento = getattr(contenido, atributo)
        if documento is None or not documento.es_legible:
            # Ausente e ilegible ya los senalan sus propias reglas -- una con el aviso de que no hay
            # gobierno, la otra con el error de formato --, y aqui no hay objeto que validar.
            continue
        try:
            defectos = esquema.incumplimientos(documento.contenido, nombre_esquema, directorio)
        except esquema.EsquemasNoDisponiblesError as fallo:
            return [error(str(directorio), f"no se pudo comprobar la forma: {fallo}")]
        hallazgos += [error(documento.ruta_relativa, f"forma invalida — {defecto}")
                      for defecto in defectos]

    for coleccion, kind, nombre_esquema in _ESQUEMA_POR_COLECCION:
        for artefacto in getattr(contenido, coleccion):
            if artefacto.frontmatter is None:
                # La ausencia de frontmatter ya la senala la regla del tipo; aqui no hay objeto que
                # ensamblar y repetirlo daria dos hallazgos por el mismo defecto.
                continue
            objeto = ensamblado.ensamblar(
                forma_frontmatter.solo_lo_declarado(artefacto.frontmatter), None, kind)
            try:
                defectos = esquema.incumplimientos(objeto, nombre_esquema, directorio)
            except esquema.EsquemasNoDisponiblesError as fallo:
                return [error(str(directorio), f"no se pudo comprobar la forma: {fallo}")]
            hallazgos += [error(artefacto.ruta_relativa, f"forma invalida — {defecto}")
                          for defecto in defectos]
    return hallazgos


def _revisar_evals(contenido: ContenidoRepositorio, raiz_plugin: Path,
                   directorio_de_esquemas: Path | None) -> list[Hallazgo]:
    """G5: las suites de evals de la unidad, contra su esquema y contra el arbol.

    LAS DOS COMPROBACIONES SON DISTINTAS Y LAS DOS HACEN FALTA. El esquema valida la forma -- que
    `eval_type` sea uno de los cuatro, que haya tres casos, que al menos uno sea `negative` --; la
    regla valida contra el arbol que el `artifact` de la suite exista de verdad, que es lo que ningun
    esquema puede saber.

    UNA SUITE MAL FORMADA ES ERROR Y NO AVISO. Podria parecer que una suite defectuosa solo degrada la
    evaluacion, pero hace algo peor: su presencia se lee como cobertura. Una suite que apunta a un id
    inexistente corre, no falla y no evalua nada -- y el artefacto figura como evaluado --.

    QUE NO HACE ESTA FUNCION: ejecutar la suite. Correrla consume modelo y sale a la red, asi que es un
    paso propio con su propio comando; el gate comprueba que la suite es VALIDA, no que pasa.
    """
    if not contenido.suites_de_evals:
        return []
    ids_publicados = frozenset(
        ficha.id for ficha in proyeccion.listar_artefactos(contenido, raiz_plugin))
    hallazgos: list[Hallazgo] = []
    for suite in contenido.suites_de_evals:
        if not suite.es_legible:
            hallazgos += _hallazgo_de_formato(suite)
            continue
        hallazgos += reglas_evals.revisar_suite(suite.ruta_relativa, suite.contenido, ids_publicados)
        if directorio_de_esquemas is None:
            continue
        try:
            defectos = esquema.incumplimientos(
                suite.contenido, _ESQUEMA_DE_LA_SUITE, directorio_de_esquemas)
        except esquema.EsquemasNoDisponiblesError as fallo:
            return [error(str(directorio_de_esquemas), f"no se pudo comprobar la forma: {fallo}")]
        hallazgos += [error(suite.ruta_relativa, f"forma invalida — {defecto}")
                      for defecto in defectos]
    return hallazgos


def _revisar_yaml(contenido: ContenidoRepositorio) -> list[Hallazgo]:
    """Un frontmatter que no es YAML valido hace que el cliente SALTE el artefacto sin avisar.

    Es error y no aviso: el artefacto existe, pasa todas las demas reglas y no se carga nunca. Es
    exactamente el caso que G1 -- que el artefacto exista de forma comprobable -- tiene que atrapar.
    """
    todos = (*contenido.skills, *contenido.prompts, *contenido.agentes_leidos,
             )
    return [
        error(artefacto.ruta_relativa,
              f"el frontmatter no es YAML valido ({artefacto.yaml_invalido}): el cliente se salta "
              "el artefacto sin avisar. Suele ser un `:` o un `#` sin entrecomillar")
        for artefacto in todos if artefacto.yaml_invalido
    ]
