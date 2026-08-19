"""Adaptador que resuelve los equipos reales de una organizacion de GitHub.

Devuelve `None` -- y no un conjunto vacio -- cuando no se puede consultar. La diferencia es todo el
punto: un conjunto vacio diria «esta organizacion no tiene equipos» y haria que TODO dueno declarado
se marcara como inexistente; `None` dice «no lo se», y la regla lo convierte en un aviso.

Es el permiso `members: read` de la App. Con el `GITHUB_TOKEN` del repositorio esta consulta NO
funciona: esta acotado a su repositorio y no ve los equipos de la organizacion.
"""
from __future__ import annotations

import json
import logging
import subprocess

log = logging.getLogger(__name__)

_LIMITE_EQUIPOS = 200
_TIEMPO_LIMITE_S = 60


def equipos(organizacion: str) -> frozenset[str] | None:
    """Los `slug` de los equipos de la organizacion, o `None` si no se pudo consultar."""
    orden = ("gh", "api", f"orgs/{organizacion}/teams?per_page={_LIMITE_EQUIPOS}",
             "--jq", "[.[].slug]")
    log.debug("consultando los equipos de %s", organizacion)
    try:
        salida = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8",
                                timeout=_TIEMPO_LIMITE_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as fallo:
        log.warning("no se pudo consultar los equipos de %s: %s", organizacion, fallo)
        return None
    if salida.returncode != 0:
        log.warning("no se pudo consultar los equipos de %s: %s",
                    organizacion, salida.stderr.strip())
        return None
    try:
        return frozenset(json.loads(salida.stdout))
    except json.JSONDecodeError as fallo:
        log.warning("respuesta inesperada al pedir los equipos de %s: %s", organizacion, fallo)
        return None
