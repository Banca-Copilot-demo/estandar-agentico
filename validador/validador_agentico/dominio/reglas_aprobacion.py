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
    """Quien tiene que firmar, por tipo de artefacto. Son las tres clases del estandar y no una
    lista de nombres: los nombres concretos viven en CODEOWNERS, que es lo que GitHub exige."""

    SEGURIDAD = "seguridad"
    ARQUITECTURA = "arquitectura"
    DOMINIO = "dominio"


# Cada prefijo o nombre de archivo con la clase que su cambio EXIGE. El orden importa: se toma la
# primera coincidencia, asi que lo mas especifico va primero.
_CLASE_POR_RUTA = (
    (".mcp.json", ClaseAprobador.SEGURIDAD),
    ("hooks.json", ClaseAprobador.SEGURIDAD),
    ("hooks/", ClaseAprobador.SEGURIDAD),
    (".instructions.md", ClaseAprobador.ARQUITECTURA),
    ("instructions/", ClaseAprobador.ARQUITECTURA),
    ("skills/", ClaseAprobador.DOMINIO),
    ("agents/", ClaseAprobador.DOMINIO),
    ("commands/", ClaseAprobador.DOMINIO),
)


def clase_de(ruta: str) -> ClaseAprobador | None:
    """La clase de aprobador que exige cambiar esa ruta, o `None` si no exige ninguna -- un README,
    un `.gitignore`: cambiarlos no requiere un firmante especifico."""
    for patron, clase in _CLASE_POR_RUTA:
        if ruta.endswith(patron) or patron in ruta:
            return clase
    return None


def revisar_mezcla_de_aprobadores(archivos_cambiados: tuple[str, ...]) -> list[Hallazgo]:
    """Un pull request no mezcla tipos que exigen firmantes distintos.

    `mcp`, `hooks` e `instructions` van SOLOS. No es una regla de comodidad: es lo unico que
    mantiene la aprobacion atribuible a lo que se aprobo.
    """
    clases = {}
    for ruta in archivos_cambiados:
        clase = clase_de(ruta)
        if clase is not None:
            clases.setdefault(clase, []).append(ruta)

    if len(clases) < 2:
        return []

    detalle = " | ".join(
        f"{clase.value}: {', '.join(sorted(rutas)[:3])}" for clase, rutas in sorted(clases.items())
    )
    return [error(
        "el pull request",
        "mezcla artefactos que exigen firmantes DISTINTOS, asi que la aprobacion no seria "
        f"atribuible a lo que se aprobo. Sepáralo en varios pull requests -- {detalle}")]


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
