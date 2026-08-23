"""Dos reglas que protegen el RASTRO DE APROBACION. Ninguna mira el contenido del artefacto: miran
quien tiene que firmarlo y quien dice ser su dueno.

POR QUE HACEN FALTA, medido en un repositorio de prueba con tres artefactos: el gate daba CONFORME
con tres equipos duenos distintos -- `squad-a`, `squad-b`, `squad-c` -- y ninguno existia. Y un mismo
pull request podia mezclar un skill trivial con un `mcp`, con dos consecuencias en direcciones
opuestas:

  - el skill arrastra a seguridad a revisar algo que no lo necesita, y
  - el revisor de seguridad APRUEBA UN PR QUE CONTIENE COSAS QUE NO EXAMINO.

La segunda es la grave: la aprobacion se registra por pull request, asi que la firma deja de decir de
que responde. Y eso no se arregla despues -- una aprobacion mal atribuida ya esta dada.
"""
from __future__ import annotations

from enum import Enum

from validador_agentico.dominio.hallazgo import Hallazgo, aviso, error


class ClaseAprobador(str, Enum):
    """Quien tiene que firmar, por tipo de artefacto. Son las clases del estandar y no una lista de
    nombres: los nombres concretos viven en CODEOWNERS, que es lo que GitHub exige.

    ARQUITECTURA se quedo SIN NINGUNA RUTA que la exija cuando `instructions` dejo de ser un tipo
    gobernado. Se conserva el miembro porque la matriz de aprobadores del estandar la sigue nombrando
    y borrarla obligaria a reintroducirla en cuanto haya un tipo que la necesite; lo que se quito es
    la ruta que la disparaba.
    """

    SEGURIDAD = "seguridad"
    ARQUITECTURA = "arquitectura"
    DOMINIO = "dominio"


# Cada nombre de archivo o SEGMENTO de directorio con la clase que su cambio EXIGE. El orden importa:
# se toma la primera coincidencia, asi que lo mas especifico va primero.
#
# `instructions` YA NO ESTA, y es una correccion medida: seguia mapeada a ARQUITECTURA despues de que
# el estandar dejara de gobernarla, asi que un pull request que tocara un skill y un archivo de
# instrucciones se BLOQUEABA con un error -- «mezcla firmantes distintos» -- por un tipo que
# deliberadamente decidimos no gobernar. Un gate que bloquea por algo que el estandar no exige es peor
# que uno que no comprueba: manda a la gente a partir pull requests sin motivo.
_CLASE_POR_ARCHIVO = (
    (".mcp.json", ClaseAprobador.SEGURIDAD),
    ("hooks.json", ClaseAprobador.SEGURIDAD),
)
_CLASE_POR_DIRECTORIO = (
    ("hooks", ClaseAprobador.SEGURIDAD),
    ("skills", ClaseAprobador.DOMINIO),
    ("agents", ClaseAprobador.DOMINIO),
    ("commands", ClaseAprobador.DOMINIO),
)

_SEPARADOR_DE_RUTA = "/"

# Cuantas rutas de ejemplo se muestran por clase en el mensaje. Es un tope de LEGIBILIDAD, no de
# analisis: la regla mira todas. Cuando se recorta, el mensaje DICE cuantas quedan -- un «y 4 mas» --
# porque una lista truncada en silencio se lee como la lista completa.
_MAX_RUTAS_EN_EL_MENSAJE = 3
_MIN_CLASES_PARA_MEZCLA = 2


def clase_de(ruta: str) -> ClaseAprobador | None:
    """La clase de aprobador que exige cambiar esa ruta, o `None` si no exige ninguna -- un README,
    un `.gitignore`: cambiarlos no requiere un firmante especifico.

    LOS DIRECTORIOS SE COMPARAN POR SEGMENTO, no por subcadena, y esto es un defecto MEDIDO: con
    `patron in ruta` y el patron `hooks/`, la ruta `plugins/mis-hooks/skills/x/SKILL.md` daba
    SEGURIDAD -- porque `mis-hooks/` contiene `hooks/` --. Consecuencia real: cualquier plugin cuyo
    nombre acabe en `-hooks` exigia firma de seguridad para TODOS sus skills, y arrastraba a seguridad
    a revisar lo que no le toca. Partir la ruta en segmentos lo resuelve sin excepciones.
    """
    segmentos = ruta.split(_SEPARADOR_DE_RUTA)
    nombre = segmentos[-1]
    for sufijo, clase in _CLASE_POR_ARCHIVO:
        if nombre.endswith(sufijo):
            return clase
    directorios = set(segmentos[:-1])
    for directorio, clase in _CLASE_POR_DIRECTORIO:
        if directorio in directorios:
            return clase
    return None


def revisar_mezcla_de_aprobadores(archivos_cambiados: tuple[str, ...]) -> list[Hallazgo]:
    """Un pull request no mezcla tipos que exigen firmantes distintos.

    `mcp` y `hooks` van SOLOS. No es una regla de comodidad: es lo unico que mantiene la aprobacion
    atribuible a lo que se aprobo.
    """
    clases: dict[ClaseAprobador, list[str]] = {}
    for ruta in archivos_cambiados:
        clase = clase_de(ruta)
        if clase is not None:
            clases.setdefault(clase, []).append(ruta)

    if len(clases) < _MIN_CLASES_PARA_MEZCLA:
        return []

    detalle = " | ".join(f"{clase.value}: {_muestra(rutas)}"
                         for clase, rutas in sorted(clases.items()))
    return [error(
        "el pull request",
        "mezcla artefactos que exigen firmantes DISTINTOS, asi que la aprobacion no seria "
        f"atribuible a lo que se aprobo. Sepáralo en varios pull requests -- {detalle}")]


def _muestra(rutas: list[str]) -> str:
    """Hasta `_MAX_RUTAS_EN_EL_MENSAJE` rutas, diciendo cuantas se dejaron fuera."""
    ordenadas = sorted(rutas)
    visibles = ", ".join(ordenadas[:_MAX_RUTAS_EN_EL_MENSAJE])
    restantes = len(ordenadas) - _MAX_RUTAS_EN_EL_MENSAJE
    return f"{visibles} y {restantes} mas" if restantes > 0 else visibles


def revisar_equipo_resoluble(donde: str, equipo: str | None,
                             equipos_conocidos: frozenset[str] | None) -> list[Hallazgo]:
    """El dueno declarado tiene que EXISTIR en la organizacion.

    `equipos_conocidos=None` significa que no se pudo consultar -- sin token, o fuera de una
    organizacion --. En ese caso se AVISA en vez de dar por bueno: un gate que no puede comprobar
    algo y calla es indistinguible de uno que lo comprobo.
    """
    if not equipo:
        return []
    if equipos_conocidos is None:
        return [aviso(donde, f"no se pudo resolver el equipo `{equipo}`: sin acceso a los equipos "
                             "de la organizacion, `owner_team` queda como texto libre")]
    if equipo not in equipos_conocidos:
        return [error(donde, f"el equipo `{equipo}` NO existe en la organizacion: sin dueno "
                             "resoluble no hay a quien avisar cuando este artefacto falle")]
    return []
