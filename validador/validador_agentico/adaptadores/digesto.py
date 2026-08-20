"""Calcula el sha256 de un archivo del repositorio.

POR QUE ENTRA EN EL PREDICADO FIRMADO. La atestacion sella el PAQUETE. Un `prompt` o unas
`instructions` no viajan dentro de un plugin: se distribuyen copiando el archivo al repositorio del
consumidor, y en ese momento el archivo PIERDE el vinculo con el sello -- el consumidor tiene un
archivo y ninguna forma de comprobar que es el que se aprobo.

Con el digesto de cada archivo dentro del predicado, cualquiera puede calcular el sha256 de lo que
tiene y compararlo contra lo firmado, sin bajar el paquete entero. Y el flujo de obsolescencia puede
detectar que una copia en un repositorio consumidor ya no coincide con lo aprobado.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_TAMANO_BLOQUE = 65536


def sha256_de(ruta: Path) -> str:
    """Devuelve el sha256 en hexadecimal, o cadena vacia si el archivo no se puede leer.

    Cadena vacia y no excepcion: el gate ya habra reportado un archivo ilegible con su propio
    hallazgo, y perder el digesto de un artefacto no debe tumbar la validacion de los demas.
    """
    resumen = hashlib.sha256()
    try:
        with ruta.open("rb") as binario:
            for bloque in iter(lambda: binario.read(_TAMANO_BLOQUE), b""):
                resumen.update(bloque)
    except OSError as fallo:
        log.warning("no se pudo calcular el digesto de %s: %s", ruta, fallo)
        return ""
    return resumen.hexdigest()
