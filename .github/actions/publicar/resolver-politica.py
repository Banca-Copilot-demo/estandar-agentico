#!/usr/bin/env python3
"""Imprime la bandera de `gh release create` que corresponde a la politica de promocion.

SALIDA A STDOUT PORQUE LA CONSUME OTRO PROCESO: `--prerelease` o vacio. El logging va a stderr (L8).

POR QUE ES UN SCRIPT Y NO TRES LINEAS EN EL WORKFLOW. Estuvo en el workflow y rompio el YAML: un
bloque `run:` no admite codigo a columna cero. Pero la razon de fondo es otra y vale para las dos
formas -- la decision de si algo se distribuye no deberia vivir donde ninguna prueba la alcanza.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from validador_agentico.adaptadores import registro
from validador_agentico.dominio.politica import Promocion, promocion_declarada

log = logging.getLogger(__name__)

_BANDERA_PRELANZAMIENTO = "--prerelease"


def bandera_de(promocion: Promocion) -> str:
    """La bandera que hace que el release NAZCA fuera del marketplace, o vacio si entra al publicar."""
    return "" if promocion is Promocion.AL_PUBLICAR else _BANDERA_PRELANZAMIENTO


def respuesta_de(promocion: Promocion) -> str:
    """Lo que se imprime: SIEMPRE un valor, nunca vacio.

    POR QUE NO SE IMPRIME LA BANDERA DIRECTAMENTE. Con `al_publicar` la bandera correcta es la cadena
    VACIA, y entonces el llamador no puede distinguir «la politica dice que no hace falta bandera» de
    «el resolutor fallo y no imprimio nada». Esa ambiguedad es exactamente la que dejo entrar al
    marketplace un artefacto sin certificar: el shell leyo un vacio de FALLO como un vacio de
    POLITICA. Imprimiendo el nombre de la politica, un vacio solo puede significar un fallo.
    """
    return promocion.value


def _politica_leida(ruta: Path) -> dict | None:
    """El contenido de la politica, o `None` si no se puede leer.

    NO SE PROPAGA EL FALLO, y es deliberado: `promocion_declarada` ya trata la ausencia como «la
    politica mas restrictiva», que es la degradacion correcta. Abortar la publicacion porque falte un
    archivo de politica seria peor que publicar sin distribuir.
    """
    if not ruta.is_file():
        log.warning("no hay %s: se aplica la politica mas restrictiva", ruta)
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as fallo:
        log.error("%s no es JSON valido; se aplica la politica mas restrictiva", ruta, exc_info=fallo)
        return None
    except OSError as fallo:
        log.error("no se pudo leer %s; se aplica la politica mas restrictiva", ruta, exc_info=fallo)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("politica", type=Path, help="ruta a POLITICA.json")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Activa logging DEBUG (detalles internos de ejecucion).")
    argumentos = parser.parse_args()
    registro.configurar(verboso=argumentos.verbose)

    promocion = promocion_declarada(_politica_leida(argumentos.politica))
    log.info("politica de promocion: %s", promocion.value)
    print(respuesta_de(promocion))
    return 0


if __name__ == "__main__":
    sys.exit(main())
