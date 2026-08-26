#!/usr/bin/env python3
"""Que suites hay que ejecutar, dados los archivos que cambia una solicitud de cambio.

EL PROBLEMA QUE RESUELVE, y es de escala, no de comodidad. Ejecutar TODAS las suites del repositorio
en cada solicitud tiene dos costes que crecen con el inventario:

  - TIEMPO Y CUOTA. Las suites corren en secuencia y cada una tarda minutos. En un repositorio con
    decenas de artefactos, cambiar un skill obligaria a evaluarlos todos.
  - ACOPLAMIENTO, que es peor. Una suite en rojo bloquea a TODO el que toque el repositorio, aunque
    no sea suya y no pueda arreglarla. MEDIDO: un cambio de cableado quedo bloqueado por la suite de
    un agente ajeno.

LA REGLA: se evalua la unidad que el cambio TOCA. Una unidad es lo que el estandar publica por
separado -- un plugin anidado o un artefacto suelto con manifiesto propio --, y NO se redefine aqui:
se recibe ya resuelta por `listar_plugins`, que es la misma regla que usan el gate, el etiquetado y el
empaquetado. Inventar una segunda definicion de «unidad» es exactamente como divergen las cosas.

SIN ARCHIVOS CAMBIADOS SE DEVUELVEN TODAS. Es el caso de la publicacion y del disparo manual: ahi no
hay «lo que cambia», hay un estado que evaluar entero.

SALIDA A STDOUT PORQUE LA CONSUME OTRO PROCESO; el logging va a stderr (L8).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import PurePosixPath

log = logging.getLogger(__name__)

# La suite de una unidad vive DENTRO de ella, a cualquier profundidad: la de un skill en
# `<unidad>/evals/`, la de un agente en `<unidad>/agents/evals/`. Por eso basta con comparar prefijos.
_RAIZ_DEL_REPOSITORIO = "."


def _unidad_de(ruta: str, unidades: list[str]) -> str | None:
    """La unidad a la que pertenece una ruta, o `None` si no cuelga de ninguna.

    Gana la unidad MAS ESPECIFICA cuando hay varias candidatas -- un suelto dentro de un repositorio
    que tambien publica su conjunto --, por la misma razon que en el resto del estandar: un plugin
    anidado manda sobre el que lo contiene.
    """
    candidatas = [u for u in unidades
                  if u != _RAIZ_DEL_REPOSITORIO and _cuelga_de(ruta, u)]
    if candidatas:
        return max(candidatas, key=len)
    return _RAIZ_DEL_REPOSITORIO if _RAIZ_DEL_REPOSITORIO in unidades else None


def _cuelga_de(ruta: str, unidad: str) -> bool:
    """Comparacion por SEGMENTOS y no por texto: `plugins/referencia-vieja` NO esta dentro de
    `plugins/referencia`, y sin esto una coincidencia de prefijo los daria por el mismo."""
    partes_unidad = PurePosixPath(unidad).parts
    return PurePosixPath(ruta).parts[:len(partes_unidad)] == partes_unidad


def suites_a_evaluar(suites: list[str], unidades: list[str],
                     cambiados: list[str]) -> list[str]:
    """Las suites que corresponde ejecutar. Todas si `cambiados` esta vacio."""
    if not cambiados:
        log.info("sin lista de archivos cambiados: se evaluan las %d suite(s)", len(suites))
        return suites

    tocadas = {u for u in (_unidad_de(c, unidades) for c in cambiados) if u}
    log.info("unidades tocadas por el cambio: %s", ", ".join(sorted(tocadas)) or "ninguna")

    elegidas = [s for s in suites if _unidad_de(s, unidades) in tocadas]
    omitidas = len(suites) - len(elegidas)
    if omitidas:
        # SE DICE CUANTAS SE OMITEN. Una cobertura que se acota en silencio se lee como cobertura
        # completa, y es justo lo que hace que nadie note que dejo de comprobarse algo.
        log.info("%d suite(s) omitida(s): su unidad no la toca este cambio", omitidas)
    return elegidas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suites", required=True, type=argparse.FileType(encoding="utf-8"),
                        help="archivo con una ruta de suite por linea")
    parser.add_argument("--unidades", required=True, type=argparse.FileType(encoding="utf-8"),
                        help="archivo con una subruta de unidad por linea, de `listar_plugins`")
    parser.add_argument("--cambiados", type=argparse.FileType(encoding="utf-8"),
                        help="archivo con los archivos cambiados. Sin el, se evaluan todas")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Activa logging DEBUG (detalles internos de ejecucion).")
    argumentos = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if argumentos.verbose else logging.INFO,
                        stream=sys.stderr, format="%(levelname)-8s %(name)s — %(message)s")

    def _lineas(archivo) -> list[str]:
        return [l.strip().removeprefix("./") for l in archivo if l.strip()] if archivo else []

    for suite in suites_a_evaluar(_lineas(argumentos.suites), _lineas(argumentos.unidades),
                                  _lineas(argumentos.cambiados)):
        print(suite)
    return 0


if __name__ == "__main__":
    sys.exit(main())
