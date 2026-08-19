"""La regla que decide si G1 esta superado cuando lo forman varias comprobaciones.

POR QUE ESTO ES DOMINIO Y NO UN PASO DE CI. Antes esta regla vivia en un `if` de bash dentro de una
accion compuesta:

    if [ "$ESTANDAR" = "success" ] && { [ "$ESPEC" = "success" ] || [ "$ESPEC" = "no aplica" ]; }

Eso es una regla de negocio -- «esta conforme cuando ninguna comprobacion aplicable falla» -- en el
unico sitio donde no se puede probar ni ejecutar en local. Aqui es una funcion pura con sus casos
cubiertos, y el mismo comando decide igual en la maquina del autor y en CI.

LOS TRES RESULTADOS, y por que hacen falta tres y no dos. `NO_APLICA` no es un `NO_CONFORME` suave:
significa que la comprobacion NO TENIA NADA QUE MIRAR. La comprobacion oficial es exclusiva de
skills y falla con «no skills found» en un repositorio que solo tiene prompts; con dos estados, ese
dominio quedaria rechazado por el motivo equivocado.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from validador_agentico.dominio.hallazgo import Veredicto


class Resultado(str, Enum):
    CONFORME = "conforme"
    NO_CONFORME = "no conforme"
    NO_APLICA = "no aplica"


@dataclass(frozen=True)
class Comprobacion:
    """Una comprobacion del gate. `detalle` explica SIEMPRE el resultado -- tambien cuando es
    `NO_APLICA` --: un «no aplica» sin motivo es indistinguible de una comprobacion que se olvido."""

    nombre: str
    resultado: Resultado
    detalle: str

    @property
    def bloquea(self) -> bool:
        return self.resultado is Resultado.NO_CONFORME


def agrega_conforme(comprobaciones: tuple[Comprobacion, ...]) -> bool:
    """Conforme cuando NINGUNA comprobacion aplicable falla.

    Se evaluan TODAS y se agrega al final, en vez de cortar en la primera que falla. Medido: con las
    comprobaciones en serie, la oficial encontro 3 errores, aborto, y la higiene y el inventario
    nunca corrieron -- el autor veia 3 de 5 defectos y no se enteraba del token literal que llevaba
    dentro. Un gate que oculta la mitad de los defectos obliga a tres rondas de PR en vez de una.
    """
    return not any(comprobacion.bloquea for comprobacion in comprobaciones)


@dataclass(frozen=True)
class ResultadoGate:
    """Lo que sale del gate completo.

    Lleva el veredicto detallado Y las comprobaciones agregadas porque el informe necesita las dos
    cosas: el detalle para que el autor corrija, y el resumen para que la proteccion de rama tenga
    algo que exigir.
    """

    veredicto: Veredicto
    comprobaciones: tuple[Comprobacion, ...]

    @property
    def conforme(self) -> bool:
        return agrega_conforme(self.comprobaciones)
