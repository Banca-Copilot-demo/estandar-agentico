"""Punto de entrada del validador: parsea argumentos, configura el logging y cablea los adaptadores.

Es el composition root (G5): el UNICO modulo que conoce implementaciones concretas y el UNICO que
convierte el resultado en un codigo de salida. Cualquier otra funcion del paquete es invocable
desde una prueba sin que el proceso muera (P3).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from validador_agentico.adaptadores import gh_skill, informe
from validador_agentico.aplicacion.ejecutar_gate import ejecutar

log = logging.getLogger(__name__)

SALIDA_CONFORME = 0
SALIDA_NO_CONFORME = 1
FORMATO_CI = "%(levelname)-8s %(name)s - %(message)s"
FORMATO_LOCAL = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"
FORMATO_HORA = "%H:%M:%S"


def _configurar_logging(verboso: bool) -> None:
    """El logging va a stderr; el informe a stdout (L8). En CI el formato es plano para que los
    logs sean parseables (L9). La deteccion del entorno ocurre aqui y en ningun modulo de libreria."""
    en_ci = os.getenv("CI") == "true"
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter(
        fmt=FORMATO_CI if en_ci else FORMATO_LOCAL, datefmt=FORMATO_HORA))
    raiz = logging.getLogger()
    raiz.setLevel(logging.DEBUG if verboso else logging.INFO)
    raiz.addHandler(manejador)


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validar-artefactos",
        description="Ejecuta el gate de conformidad: G1 estructura, G3 higiene y G4 gobierno, "
                    "mas la comprobacion oficial de la especificacion cuando hay skills. Es el "
                    "MISMO comando que corre CI, para que un pull request nazca en verde.")
    parser.add_argument("raiz", nargs="?", default=".", type=Path,
                        help="raiz del repositorio a validar (por defecto, el directorio actual)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="logging de diagnostico en stderr")
    parser.add_argument("--formato", choices=informe.FORMATOS, default=informe.FORMATO_TEXTO,
                        help="`texto` para leerlo; `json` para firmarlo como predicado")
    parser.add_argument("--sin-comprobacion-oficial", action="store_true",
                        help="no invoca `gh skill publish --dry-run`. La comprobacion se declara "
                             "`no aplica` con su motivo: nunca se da por buena en silencio")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argumentos = _parsear_argumentos(argv)
    _configurar_logging(argumentos.verbose)
    raiz = argumentos.raiz.resolve()
    if not raiz.is_dir():
        log.error("la raiz no existe o no es un directorio: %s", raiz)
        return SALIDA_NO_CONFORME
    # El composition root es el unico que conoce la implementacion concreta del puerto (G5).
    resultado = ejecutar(raiz, comprobador_oficial=gh_skill,
                         con_comprobacion_oficial=not argumentos.sin_comprobacion_oficial)
    informe.imprimir_gate(resultado, raiz.name, argumentos.formato)
    return SALIDA_CONFORME if resultado.conforme else SALIDA_NO_CONFORME


if __name__ == "__main__":
    sys.exit(main())
