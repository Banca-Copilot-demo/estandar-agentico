"""Comparar lo ATESTADO con lo que un servidor MCP declara hoy. Regla pura: recibe datos, no red.

TRES RESULTADOS Y NO DOS, y la distincion es lo que hace util esta comprobacion:

  CONFORME       el digest de hoy coincide con el atestado
  DERIVA         difieren: la superficie cambio sin pasar por revision
  SIN_COMPROBAR  no se pudo consultar el servidor -- sin credencial, sin red, sin respuesta

El tercero existe porque su ausencia es el peor fallo posible aqui. Si «no se pudo comprobar» se
tratara como «esta en orden», un servidor sin vigilancia pasaria por vigilado indefinidamente, y nadie
lo notaria precisamente porque no hay alarma. Un MCP sin comprobar NO es un MCP en orden.

Y CONFORME exige que haya linea base. Un servidor sin `tools_digest` atestado no se puede comparar
contra nada: no es conforme, es SIN_COMPROBAR con otro motivo. Es el caso de un `mcp` aprobado antes
de que existiera este control.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Resultado(str, Enum):
    CONFORME = "conforme"
    DERIVA = "deriva"
    SIN_COMPROBAR = "sin_comprobar"


@dataclass(frozen=True)
class Comprobacion:
    """El resultado para UN `mcp`, listo para reportar.

    NO lleva las descripciones de las herramientas a proposito. Las controla un tercero, y volcarlas
    en un issue las convertiria en un vector de inyeccion dirigido a quien lo lea -- o a un agente que
    revise issues --. Se reportan los digests y los NOMBRES, que basta para investigar.
    """

    artefacto: str
    resultado: Resultado
    digest_atestado: str = ""
    digest_actual: str = ""
    motivo: str = ""
    herramientas_nuevas: tuple[str, ...] = ()
    herramientas_retiradas: tuple[str, ...] = ()

    @property
    def exige_atencion(self) -> bool:
        return self.resultado is not Resultado.CONFORME


def comparar(artefacto: str, digest_atestado: str, digest_actual: str | None,
             nombres_atestados: tuple[str, ...] = (),
             nombres_actuales: tuple[str, ...] = (),
             motivo_de_fallo: str = "") -> Comprobacion:
    """`digest_actual = None` significa que no se pudo consultar al servidor."""
    if not digest_atestado:
        return Comprobacion(
            artefacto=artefacto, resultado=Resultado.SIN_COMPROBAR,
            motivo="el predicado firmado no declara `tools_digest`: no hay linea base contra la que "
                   "comparar. Se aprobo antes de que existiera este control, o se aprobo sin el")

    if digest_actual is None:
        return Comprobacion(
            artefacto=artefacto, resultado=Resultado.SIN_COMPROBAR,
            digest_atestado=digest_atestado,
            motivo=motivo_de_fallo or "no se pudo consultar el servidor")

    if digest_actual == digest_atestado:
        return Comprobacion(artefacto=artefacto, resultado=Resultado.CONFORME,
                            digest_atestado=digest_atestado, digest_actual=digest_actual)

    atestados, actuales = set(nombres_atestados), set(nombres_actuales)
    return Comprobacion(
        artefacto=artefacto, resultado=Resultado.DERIVA,
        digest_atestado=digest_atestado, digest_actual=digest_actual,
        # Los nombres SI se reportan: son un identificador, no texto libre del proveedor, y sin ellos
        # el issue diria «algo cambio» sin decir donde mirar.
        herramientas_nuevas=tuple(sorted(actuales - atestados)),
        herramientas_retiradas=tuple(sorted(atestados - actuales)),
        motivo="las herramientas que el servidor declara no son las que se atestaron")


def resumir(comprobaciones: list[Comprobacion]) -> str:
    """Una linea por `mcp`, para el resumen del run. Sin texto del proveedor."""
    if not comprobaciones:
        return "No hay ningun `mcp` que comprobar."
    filas = [
        "| Artefacto | Resultado | Detalle |",
        "|---|---|---|",
    ]
    for c in sorted(comprobaciones, key=lambda c: (not c.exige_atencion, c.artefacto)):
        detalle = c.motivo or "sin cambios"
        if c.resultado is Resultado.DERIVA:
            cambios = []
            if c.herramientas_nuevas:
                cambios.append(f"nuevas: {', '.join(c.herramientas_nuevas)}")
            if c.herramientas_retiradas:
                cambios.append(f"retiradas: {', '.join(c.herramientas_retiradas)}")
            # Sin nombres nuevos ni retirados, lo que cambio fue una DESCRIPCION o un esquema: el
            # caso mas peligroso, porque el conjunto de herramientas parece intacto.
            detalle = "; ".join(cambios) or "misma lista, cambio una descripcion o un esquema"
        filas.append(f"| `{c.artefacto}` | {c.resultado.value} | {detalle} |")
    return "\n".join(filas)
