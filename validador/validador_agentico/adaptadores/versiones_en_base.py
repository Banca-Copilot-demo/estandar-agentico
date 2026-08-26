"""Adaptador que lee, de la RAMA BASE, la version que cada unidad declaraba alli.

POR QUE NO SE RELEE EL ARBOL DE TRABAJO. La regla de subida de version compara dos estados, y el
arbol de trabajo solo tiene uno. El otro esta en git y solo en git: `git show <base>:<ruta>` da el
contenido del archivo TAL Y COMO ESTABA en la base, sin sacar un segundo checkout ni tocar el arbol.

POR QUE NO REIMPLEMENTA EL ORDEN DE FUENTES. Cual archivo manda -- manifiesto primero, gobierno solo
para el conjunto suelto -- es una regla de dominio con su propia historia de fallos, y vive en
`reglas_identidad`. Aqui solo se le da un lector distinto: en vez de leer del disco, lee de un blob.

`None` -- el diccionario entero -- cuando la base no esta disponible: no es un repositorio git, o el
checkout fue superficial y el commit base no esta. Igual que con los archivos cambiados, `None` no es
un diccionario vacio: el vacio diria «ninguna unidad existia en la base» y eximiria a todas de subir
version, callando en vez de avisar.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from validador_agentico.adaptadores.repositorio import RUTA_GOBIERNO
from validador_agentico.dominio.especificacion import RUTAS_MANIFIESTO
from validador_agentico.dominio.reglas_identidad import identidad_de_unidad
from validador_agentico.dominio.reglas_layout import RAIZ_DEL_REPOSITORIO

log = logging.getLogger(__name__)

_TIEMPO_LIMITE_S = 60


def _existe_la_base(raiz: Path, base: str) -> bool:
    orden = ("git", "-C", str(raiz), "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    try:
        return subprocess.run(orden, capture_output=True, text=True,
                              timeout=_TIEMPO_LIMITE_S, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired) as fallo:
        log.warning("no se pudo resolver la rama base %s: %s", base, fallo)
        return False


def _leer_de_la_base(raiz: Path, base: str, ruta: str) -> str | None:
    """El contenido de `ruta` en la base, o `None` si alli no existia."""
    orden = ("git", "-C", str(raiz), "show", f"{base}:{ruta}")
    try:
        salida = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8",
                                timeout=_TIEMPO_LIMITE_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as fallo:
        log.warning("no se pudo leer %s en %s: %s", ruta, base, fallo)
        return None
    # Un codigo distinto de cero aqui significa «ese archivo no esta en ese commit», que es
    # informacion legitima y no un fallo: es como se reconoce una unidad nueva.
    return salida.stdout if salida.returncode == 0 else None


def versiones_en_base(raiz: Path, base: str,
                      unidades: tuple[str, ...]) -> dict[str, str | None] | None:
    """Por cada unidad, la version que declaraba en `base`, o `None` si alli no existia."""
    if not _existe_la_base(raiz, base):
        log.warning("la rama base %s no esta disponible: no se puede comprobar la subida de "
                    "version", base)
        return None
    declaradas: dict[str, str | None] = {}
    for unidad in unidades:
        prefijo = "" if unidad == RAIZ_DEL_REPOSITORIO else f"{unidad}/"
        identidad = identidad_de_unidad(
            lambda relativa, prefijo=prefijo: _leer_de_la_base(raiz, base, f"{prefijo}{relativa}"),
            RUTAS_MANIFIESTO, RUTA_GOBIERNO,
            es_raiz=unidad == RAIZ_DEL_REPOSITORIO,
            donde=f"{base}:{unidad}")
        declaradas[unidad] = identidad.version if identidad is not None else None
    log.debug("versiones en %s: %s", base, declaradas)
    return declaradas
