"""Configuracion del logging, en UN solo sitio para los cuatro entry points.

POR QUE EXISTE ESTE MODULO. Los cuatro CLI del paquete tenian su propia `_configurar_logging`, y la
duplicacion YA HABIA DIVERGIDO: solo `cli.py` respetaba L9 --formato plano en CI, con hora en local--
y los otros tres fijaban un formato a mano, dos de ellos distinto entre si. Un mismo comando producia
logs con nombre de modulo o sin el segun por que entry point se entrara, que es exactamente el fallo
que G2 predice: lo duplicado no se mantiene sincronizado, se olvida.

ES UN ADAPTADOR y no dominio porque toca el exterior: escribe en stderr y lee `CI` del entorno.

L4 SIGUE VIGENTE: esto NO se llama al importar. Lo invoca `main()` de cada entry point, una vez, y
ningun modulo de libreria lo toca.
"""
from __future__ import annotations

import logging
import os
import sys

# El nombre del modulo se incluye SIEMPRE: con cuatro entry points y tres capas, un mensaje sin decir
# de donde sale obliga a buscarlo por texto en todo el paquete.
FORMATO_CI = "%(levelname)-8s %(name)s - %(message)s"
FORMATO_LOCAL = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"
FORMATO_HORA = "%H:%M:%S"

# GitHub Actions define `CI=true`. Fuera de CI se añade la hora, que en local sirve para ver cuanto
# tarda cada fase; en CI la quita porque el propio runner ya sella cada linea con su timestamp.
_VARIABLE_CI = "CI"
_VALOR_CI = "true"


def configurar(verboso: bool) -> None:
    """Deja el logging listo: DEBUG si `verboso`, INFO si no. Idempotente.

    Idempotente a proposito: si dos entry points se encadenan en el mismo proceso -- o una prueba lo
    llama dos veces -- duplicar el handler haria que cada mensaje saliera dos veces, y un log que
    repite todo se deja de leer.
    """
    raiz = logging.getLogger()
    raiz.setLevel(logging.DEBUG if verboso else logging.INFO)
    if any(getattr(h, "_es_del_track_agentico", False) for h in raiz.handlers):
        return
    raiz.addHandler(_manejador())


def _manejador() -> logging.Handler:
    """El handler a stderr. A stderr y no a stdout porque la salida estructurada -- el informe, el
    JSON -- va a stdout y las dos streams no se mezclan (L8)."""
    en_ci = os.getenv(_VARIABLE_CI) == _VALOR_CI
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter(
        fmt=FORMATO_CI if en_ci else FORMATO_LOCAL, datefmt=FORMATO_HORA))
    manejador._es_del_track_agentico = True
    return manejador
