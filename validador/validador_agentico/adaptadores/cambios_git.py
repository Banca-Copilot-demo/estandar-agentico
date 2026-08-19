"""Adaptador que lista los archivos cambiados frente a la rama base.

Devuelve `None` cuando no se puede determinar -- no es un repositorio git, o la base no esta
disponible porque el checkout fue superficial --. Igual que con los equipos, `None` no es una tupla
vacia: una tupla vacia diria «este pull request no cambia nada» y la regla de mezcla no encontraria
nada que objetar, callando en vez de avisar.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

_TIEMPO_LIMITE_S = 60


def archivos_cambiados(raiz: Path, base: str) -> tuple[str, ...] | None:
    """Rutas relativas cambiadas entre `base` y el estado actual, con `/` como separador."""
    orden = ("git", "-C", str(raiz), "diff", "--name-only", f"{base}...HEAD")
    log.debug("listando cambios frente a %s", base)
    try:
        salida = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8",
                                timeout=_TIEMPO_LIMITE_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as fallo:
        log.warning("no se pudieron listar los cambios: %s", fallo)
        return None
    if salida.returncode != 0:
        log.warning("no se pudieron listar los cambios frente a %s: %s",
                    base, salida.stderr.strip())
        return None
    return tuple(linea.strip() for linea in salida.stdout.splitlines() if linea.strip())
