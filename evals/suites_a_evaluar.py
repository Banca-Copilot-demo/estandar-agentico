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

# LA PERTENENCIA DE UN ARCHIVO A UNA UNIDAD NO SE DEFINE AQUI. Vivio en este modulo mientras fue su
# unico consumidor; al necesitarla tambien el gate -- para exigirle a toda unidad que cambia que suba
# su version -- mantener dos copias habria significado que un archivo pudiera pertenecer a una unidad
# para la seleccion de suites y a otra para el versionado: se evaluaria una y se publicaria otra.
# Vive en `reglas_layout`, junto a la regla que dice cuales son las unidades.
#
# La suite de una unidad vive DENTRO de ella, a cualquier profundidad: la de un skill en
# `<unidad>/evals/`, la de un agente en `<unidad>/agents/evals/`. Por eso basta con comparar prefijos.
from validador_agentico.dominio.reglas_layout import unidad_de as _unidad_de

log = logging.getLogger(__name__)


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
