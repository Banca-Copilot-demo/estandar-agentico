"""Adaptador de lectura del paquete publicado.

Lee el manifiesto de DENTRO del .tar.gz y no del repositorio a proposito: los bytes del paquete son
los que estan sellados por la atestacion. Leer el repositorio dejaria un hueco -- el paquete podria
declarar una cosa y el repositorio otra --.
"""
from __future__ import annotations

import hashlib
import json
import logging
import tarfile
from pathlib import Path

log = logging.getLogger(__name__)

RUTA_MANIFIESTO = ".claude-plugin/plugin.json"
_TAMANO_BLOQUE = 65536


def digest(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with ruta.open("rb") as binario:
        for bloque in iter(lambda: binario.read(_TAMANO_BLOQUE), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def leer_manifiesto(ruta: Path) -> dict | None:
    """Devuelve el manifiesto, o `None` si el paquete no lo trae o no es JSON valido."""
    try:
        with tarfile.open(ruta, "r:gz") as paquete:
            miembro = paquete.extractfile(RUTA_MANIFIESTO)
            if miembro is None:
                log.warning("el paquete %s no contiene %s", ruta.name, RUTA_MANIFIESTO)
                return None
            return json.loads(miembro.read().decode("utf-8"))
    except (KeyError, tarfile.TarError, json.JSONDecodeError, UnicodeDecodeError) as error:
        log.warning("no se pudo leer %s de %s: %s", RUTA_MANIFIESTO, ruta.name, error)
        return None
