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
from dataclasses import dataclass
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


@dataclass(frozen=True)
class LecturaManifiesto:
    """AUSENTE e ILEGIBLE son resultados distintos y el consumidor necesita separarlos: un paquete
    sin plugin es correcto -- se omite del marketplace --, y uno con plugin roto es un defecto que
    hay que rechazar. Devolver `None` para las dos cosas mezclaba un caso esperado con un fallo."""

    presente: bool
    contenido: dict | None = None


def leer_manifiesto(ruta: Path) -> LecturaManifiesto:
    try:
        with tarfile.open(ruta, "r:gz") as paquete:
            try:
                miembro = paquete.extractfile(RUTA_MANIFIESTO)
            except KeyError:
                miembro = None
            if miembro is None:
                log.info("el paquete %s no lleva plugin (%s): no va al marketplace",
                         ruta.name, RUTA_MANIFIESTO)
                return LecturaManifiesto(presente=False)
            return LecturaManifiesto(presente=True,
                                     contenido=json.loads(miembro.read().decode("utf-8")))
    except (tarfile.TarError, json.JSONDecodeError, UnicodeDecodeError) as error:
        log.warning("%s lleva %s pero no se pudo leer: %s", ruta.name, RUTA_MANIFIESTO, error)
        return LecturaManifiesto(presente=True)
