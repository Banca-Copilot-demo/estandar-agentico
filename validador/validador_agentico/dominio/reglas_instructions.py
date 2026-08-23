"""Lo que se OBSERVA de unas `instructions`, que no son un tipo gobernado. Reglas puras.

POR QUE NO SE GOBIERNAN, y esta comprobado en fuente primaria: no hay canal para distribuirlas. La
referencia de plugins de Claude Code dice que un `CLAUDE.md` en la raiz de un plugin NO se carga como
contexto y que un plugin aporta contexto «a traves de skills, agents y hooks»; el conjunto de
componentes de un plugin de Copilot -- agents, skills, commands, hooks, extensions, mcpServers,
lspServers -- no incluye `instructions`, y los plugins se instalan FUERA del repositorio. Sin canal,
darles version, dueno y deprecacion seria gobierno de papel: prometeria un mantenimiento que ningun
workflow puede hacer.

Y AUN ASI EL GATE LAS MIRA, porque el riesgo no es su contenido sino su INVISIBILIDAD. Es el unico
archivo del repositorio que cambia el comportamiento del agente sin que nadie lo elija: se aplica solo
a lo que casa con su `applyTo` y su tamano se paga en cada peticion. Un repositorio donde nadie sabe
que existe ese archivo es peor que uno donde existe y consta.

TODO AVISO, NINGUN ERROR. Tener unas `instructions` locales es legitimo -- es como funciona el
cliente, y un equipo puede querer una guia para su propio codigo --, asi que bloquear seria imponer
una regla que la herramienta no impone. Lo que se hace es dejar constancia.

Y NO SE RECOMIENDA QUE USAR EN SU LUGAR: el gate no puede saber la intencion, y decirle «usa un
prompt» a quien escribio una guia local legitima es el tipo de consejo que ensena a ignorar los
avisos. La eleccion entre prompt, skill e instructions se explica en el lineamiento, que se lee ANTES
de escribir el archivo.
"""
from __future__ import annotations

import re

from validador_agentico.dominio.hallazgo import Hallazgo, aviso

# Un `applyTo` de `**` aplica a todo el repositorio: deja de ser una regla acotada y se paga en cada
# peticion sobre cualquier archivo.
GLOBS_DE_TODO_EL_REPOSITORIO = frozenset({"**", "**/*", "*", "/", "./**"})

# A partir de aqui el tamano se nota, porque el cuerpo esta activo en todas las peticiones que casen.
# Es un umbral de AVISO y no un limite: no hay ninguno documentado por la plataforma -- se comprobo --
# asi que imponer un numero seria inventarselo, pero no decir nada deja crecer el coste sin que nadie
# lo note.
LIMITE_LINEAS_SIN_TECHO = 200

_CLAVES_DE_AMBITO = ("applyTo", "applies_to")

# Etiquetas moviles y comodines: ver `reglas_mcp` para el mismo problema en otro contexto.
_SEPARADOR_DE_GLOBS = ","
_COMODIN_DE_ARBOL = "**"


def ambito_de(frontmatter: dict) -> object:
    """El `applyTo` declarado, en cualquiera de las dos ortografias que conviven.

    `applyTo` es la de Copilot y `applies_to` aparece en artefactos reales; se aceptan las dos porque
    lo que se mide es el AMBITO, no la ortografia -- y el gate no es quien decide cual lee el cliente.
    """
    for clave in _CLAVES_DE_AMBITO:
        if frontmatter.get(clave):
            return frontmatter[clave]
    return None


def revisar_instructions(donde: str, frontmatter: dict, lineas: int) -> list[Hallazgo]:
    """Deja constancia de que existe y de su alcance. Nunca bloquea."""
    hallazgos: list[Hallazgo] = []
    ambito = ambito_de(frontmatter)

    if not ambito:
        # Sin `applyTo` el archivo es INERTE: VS Code lo documenta -- «si no se especifica, las
        # instrucciones no se aplican automaticamente» --, aunque GitHub lo redacte como obligatorio.
        # Las dos fuentes oficiales se contradicen, asi que se informa en vez de decidir por ellas.
        hallazgos.append(aviso(
            donde, "sin `applyTo`: segun la documentacion de VS Code el archivo NO se aplica "
                   "automaticamente, asi que queda inerte salvo que alguien lo adjunte a mano. La "
                   "documentacion de GitHub lo redacta como obligatorio: las dos fuentes oficiales "
                   "se contradicen"))
    elif str(ambito).strip() in GLOBS_DE_TODO_EL_REPOSITORIO:
        hallazgos.append(aviso(
            donde, f"`applyTo` es {ambito!r}: aplica a TODO el repositorio, asi que su cuerpo se "
                   "paga en cualquier peticion sobre cualquier archivo"))
    else:
        hallazgos.append(aviso(
            donde, f"aplica automaticamente a {ambito!r} en cada peticion, y queda FUERA del ciclo "
                   "de vida: sin dueno declarado, sin version y sin entrada en el catalogo"))

    if lineas > LIMITE_LINEAS_SIN_TECHO:
        hallazgos.append(aviso(
            donde, f"{lineas} lineas SIEMPRE activas: su tamano se paga en todas las peticiones que "
                   f"casen con su ambito. No hay limite documentado por la plataforma, asi que "
                   f"{LIMITE_LINEAS_SIN_TECHO} es un umbral nuestro"))
    return hallazgos


# ── el solapamiento entre varias, que el cliente NO desempata ────────────────────────────────
_GLOBS_UNIVERSALES = tuple(GLOBS_DE_TODO_EL_REPOSITORIO)


def _globs_de(ambito: object) -> tuple[str, ...]:
    """Los globs declarados, como cadena separada por comas o como lista.

    `applyTo` es una CADENA separada por comas en Copilot y `paths` una LISTA en Claude Code: el mismo
    archivo puede escribirse de las dos formas.
    """
    if isinstance(ambito, str):
        crudos = ambito.split(_SEPARADOR_DE_GLOBS)
    elif isinstance(ambito, (list, tuple)):
        crudos = [str(elemento) for elemento in ambito]
    else:
        return ()
    return tuple(sorted({g.strip() for g in crudos if g.strip()}))


def _partir_en_arbol(glob: str) -> tuple[str, str] | None:
    """`(prefijo, sufijo)` de un glob `<prefijo>/**/<sufijo>`, o `None` si no es de esa forma."""
    if _COMODIN_DE_ARBOL not in glob:
        return None
    antes, despues = glob.split(_COMODIN_DE_ARBOL, 1)
    return antes.strip("/"), despues.strip("/")


def _sufijos_compatibles(uno: str, otro: str) -> bool:
    """Si dos sufijos pueden alcanzar EL MISMO archivo.

    Un sufijo vacio abarca todo lo que hay bajo su prefijo. Dos sufijos concretos y distintos --
    `*.java` frente a `*.py` -- no coinciden nunca, y tratarlos como solapados era un FALSO POSITIVO:
    medido con `**/*.java` y `**/*.py`, que comparten el prefijo raiz y no comparten ni un archivo.
    """
    if not uno or not otro:
        return True
    return uno == otro


def _se_solapan(uno: str, otro: str) -> bool:
    if uno == otro:
        return True
    if uno in _GLOBS_UNIVERSALES or otro in _GLOBS_UNIVERSALES:
        return True
    partes_uno, partes_otro = _partir_en_arbol(uno), _partir_en_arbol(otro)
    if partes_uno is None or partes_otro is None:
        return False
    (prefijo_uno, sufijo_uno), (prefijo_otro, sufijo_otro) = partes_uno, partes_otro
    if not _sufijos_compatibles(sufijo_uno, sufijo_otro):
        return False
    # Un `**` cuyo prefijo contiene al del otro abarca todo lo que el otro abarca: `src/**` incluye
    # cuanto cubre `src/api/**`. El prefijo vacio es la raiz, y contiene a cualquiera.
    corto, largo = sorted((prefijo_uno, prefijo_otro), key=len)
    return largo == corto or largo.startswith(corto + "/") or corto == ""


def revisar_solapamiento(declaradas: list[tuple[str, object]]) -> list[Hallazgo]:
    """`declaradas` son pares `(donde, ambito)` de TODAS las instructions del repositorio.

    POR QUE IMPORTA AUNQUE NO SE GOBIERNEN. La documentacion oficial dice que «all sets of relevant
    instructions are provided» -- se COMBINAN -- y no define orden entre dos archivos que casen con el
    mismo. O sea que el conflicto no lo desempata nadie: no se resuelve al aplicarlas, y lo unico que
    se puede hacer es que quien las escribio lo sepa.

    ES UN AVISO. Antes bloqueaba, cuando `instructions` era un tipo gobernado con ciclo de vida; sin
    gobierno, impedir un merge por esto seria imponer una regla que la herramienta no impone. Se
    informa, que es lo que permite decidir.

    CONSERVADORA a proposito: solo se senala el solapamiento CIERTO -- glob identico, universal contra
    cualquiera, y un `**` que contiene al otro por prefijo con sufijos compatibles --. Decidir si dos
    globs cualesquiera se intersecan no es practicable, y un aviso por un conflicto inexistente
    ensena a ignorar los avisos.
    """
    hallazgos: list[Hallazgo] = []
    con_globs = [(donde, _globs_de(ambito)) for donde, ambito in declaradas]
    for indice, (donde, globs) in enumerate(con_globs):
        for donde_previo, globs_previos in con_globs[:indice]:
            colisiones = sorted({
                f"`{uno}` con `{otro}`"
                for uno in globs for otro in globs_previos if _se_solapan(uno, otro)
            })
            if colisiones:
                hallazgos.append(aviso(
                    donde,
                    f"su ambito se solapa con {donde_previo}: {', '.join(colisiones)}. El cliente NO "
                    f"garantiza cual de las dos gana -- las combina sin orden definido --, asi que el "
                    f"conflicto no se resuelve al aplicarlas"))
    return hallazgos
