"""Dos `instructions` distribuidas NO pueden aplicar al mismo archivo. Regla pura sobre el CONJUNTO.

POR QUE ES UNA REGLA DE PUBLICACION Y NO DE EJECUCION. Ni Copilot ni Claude Code garantizan el orden
en que aplican varias instructions al mismo archivo, y ninguno de los dos tiene semantica de
precedencia: `applyTo` y `paths` acotan DONDE aplican, no QUIEN gana. Asi que un conflicto entre dos
instructions que se solapan no se puede resolver en ejecucion -- no hay a quien preguntarle quien
manda --. Solo se puede PREVENIR: si nunca se publican dos que se solapen, el conflicto no existe.

POR QUE SE MIDE SOBRE EL REPOSITORIO Y NO SOBRE CADA PLUGIN. El solapamiento ocurre en el
repositorio DESTINO, donde las instructions acaban instaladas. Dos plugins del mismo repositorio de
dominio se instalan a menudo juntos, asi que comprobar cada plugin por separado dejaria pasar
exactamente el caso mas probable: dos plugins vecinos que declaran el mismo glob.

CONSERVADORA A PROPOSITO. Decidir si dos globs cualesquiera se intersecan no es practicable, y este
hallazgo BLOQUEA la publicacion: un falso positivo aqui para el trabajo de alguien por un conflicto
que no existe. Por eso solo se senala el solapamiento CIERTO -- glob identico, universal contra
cualquiera, y un `**` que contiene al otro por prefijo --. Lo que no se detecta queda documentado en
`_SOLAPAMIENTO_NO_DETECTADO`: se prefiere dejar pasar un conflicto dudoso a bloquear uno inexistente.
"""
from __future__ import annotations

from validador_agentico.dominio.hallazgo import Hallazgo, error

# Globs que aplican a TODO el arbol. Cualquiera de estos solapa con cualquier otro glob.
_GLOBS_UNIVERSALES = ("*", "**", "**/*", "./**")

_SOLAPAMIENTO_NO_DETECTADO = (
    "No se detectan: extensiones que coinciden por conjunto sin ser iguales (`*.{ts,js}` frente a "
    "`*.ts`), clases de caracteres (`[abc]`), ni dos prefijos distintos que resuelven al mismo "
    "arbol por enlaces simbolicos. Son casos raros y ambiguos; senalarlos costaria falsos positivos "
    "que bloquean publicaciones legitimas."
)

_SEPARADOR_DE_GLOBS = ","
_COMODIN_DE_ARBOL = "**"


def _globs_de(aplica_a: object) -> tuple[str, ...]:
    """Los globs declarados, ya sea como cadena separada por comas o como lista.

    `applyTo` es una CADENA separada por comas en Copilot y `paths` una LISTA en Claude Code. Se
    aceptan las dos formas porque el mismo artefacto se publica a los dos clientes.
    """
    if isinstance(aplica_a, str):
        crudos = aplica_a.split(_SEPARADOR_DE_GLOBS)
    elif isinstance(aplica_a, (list, tuple)):
        crudos = [str(elemento) for elemento in aplica_a]
    else:
        return ()
    return tuple(sorted({g.strip() for g in crudos if g.strip()}))


def _partir_en_arbol(glob: str) -> tuple[str, str] | None:
    """`(prefijo, sufijo)` de un glob `<prefijo>/**/<sufijo>`, o `None` si no es de esa forma.

    El prefijo es el directorio del que cuelga y el sufijo lo que se exige del nombre del archivo.
    Un sufijo VACIO significa «todo lo que haya debajo».
    """
    if _COMODIN_DE_ARBOL not in glob:
        return None
    antes, despues = glob.split(_COMODIN_DE_ARBOL, 1)
    return antes.strip("/"), despues.strip("/")


def _sufijos_compatibles(uno: str, otro: str) -> bool:
    """Si dos sufijos pueden alcanzar EL MISMO archivo.

    Un sufijo vacio abarca todo lo que hay bajo su prefijo, asi que es compatible con cualquiera.
    Dos sufijos concretos y distintos -- `*.java` frente a `*.py` -- no pueden coincidir nunca, y
    tratarlos como solapados era un FALSO POSITIVO que bloqueaba publicaciones legitimas: medido
    con `**/*.java` y `**/*.py`, que comparten el prefijo raiz y no comparten ni un archivo.
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
    """`declaradas` son pares `(donde, applies_to)` de TODAS las instructions del repositorio.

    Se compara cada par una sola vez y se reporta en el segundo de los dos por orden, para que el
    mensaje aparezca junto al archivo que llega despues y no en el que ya estaba.
    """
    hallazgos: list[Hallazgo] = []
    con_globs = [(donde, _globs_de(aplica_a)) for donde, aplica_a in declaradas]
    for indice, (donde, globs) in enumerate(con_globs):
        for donde_previo, globs_previos in con_globs[:indice]:
            colisiones = sorted({
                f"`{uno}` con `{otro}`"
                for uno in globs for otro in globs_previos if _se_solapan(uno, otro)
            })
            if colisiones:
                hallazgos.append(error(
                    donde,
                    f"su ambito se solapa con {donde_previo}: {', '.join(colisiones)}. El cliente NO "
                    f"garantiza cual de las dos gana, asi que el conflicto no se puede resolver al "
                    f"aplicarlas: se previene no publicandolas juntas. Acota los globs o unifica las "
                    f"dos instructions en una."))
    return hallazgos
