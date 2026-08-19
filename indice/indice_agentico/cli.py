"""Punto de entrada del generador del indice: parsea, configura el logging y cablea los adaptadores.

Composition root (G5). Es tambien el unico modulo que decide el codigo de salida, y decide una cosa
que conviene leer despacio: **un rechazo NO es un fallo**. Un dominio que publico sin sellar tiene
que quedarse fuera del indice sin tumbar la generacion de los demas; si esto fallara, un solo
dominio mal publicado congelaria el indice de todos.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from indice_agentico.adaptadores import catalogo
from indice_agentico.aplicacion.generar import generar

log = logging.getLogger(__name__)

SALIDA_OK = 0
SALIDA_ERROR = 1
TOPICO_POR_DEFECTO = "agent-skills"
FORMATO_CI = "%(levelname)-8s %(name)s - %(message)s"
FORMATO_LOCAL = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"
FORMATO_HORA = "%H:%M:%S"


def _configurar_logging(verboso: bool) -> None:
    """A stderr; el catalogo generado va a stdout o a un archivo (L8)."""
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter(
        fmt=FORMATO_CI if os.getenv("CI") == "true" else FORMATO_LOCAL, datefmt=FORMATO_HORA))
    raiz = logging.getLogger()
    raiz.setLevel(logging.DEBUG if verboso else logging.INFO)
    raiz.addHandler(manejador)


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generar-indice",
        description="Genera marketplace.json con los plugins que tienen atestacion verificada.")
    parser.add_argument("organizacion", help="organizacion de GitHub donde viven los dominios")
    parser.add_argument("--topico", default=TOPICO_POR_DEFECTO,
                        help="topico que marca un repositorio de dominio")
    parser.add_argument("--nombre", default="agentico", help="`name` del catalogo")
    parser.add_argument("--equipo", default="Plataforma Agentica (demo)")
    parser.add_argument("--contacto", default="plataforma-agentica@ejemplo.dev")
    parser.add_argument("--version", default="0.1.0", help="version del catalogo")
    parser.add_argument("--salida", type=Path,
                        help="archivo donde escribir; por defecto, stdout")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def _informar_rechazos(indice) -> None:
    for rechazo in indice.rechazos:
        log.warning("FUERA DEL INDICE %s: %s", rechazo.repositorio, rechazo.motivo.value)


def main(argv: list[str] | None = None) -> int:
    argumentos = _parsear_argumentos(argv)
    _configurar_logging(argumentos.verbose)

    indice = generar(argumentos.organizacion, argumentos.topico)
    _informar_rechazos(indice)

    propietario = {"name": argumentos.equipo, "email": argumentos.contacto}
    contenido = catalogo.render(indice, argumentos.nombre, propietario, argumentos.version)

    if argumentos.salida is None:
        print(contenido, end="")
        return SALIDA_OK

    if not indice.entradas:
        # Un indice vacio sobreescribiendo uno que funcionaba desinstalaria todo de golpe. Si no
        # hay NADA que indexar es un fallo de credenciales o de red, no un catalogo legitimo.
        log.error("ningun plugin paso las comprobaciones: no se sobreescribe %s",
                  argumentos.salida)
        return SALIDA_ERROR

    argumentos.salida.parent.mkdir(parents=True, exist_ok=True)
    argumentos.salida.write_text(contenido, encoding="utf-8")
    log.info("escrito %s con %d plugin(s)", argumentos.salida, len(indice.entradas))
    return SALIDA_OK


if __name__ == "__main__":
    sys.exit(main())
