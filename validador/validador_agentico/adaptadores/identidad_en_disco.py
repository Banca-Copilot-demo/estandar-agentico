"""Adaptador que lee la identidad de una unidad del ARBOL DE TRABAJO.

Es la mitad de disco de `dominio.reglas_identidad`; la otra -- la que lee de la rama base -- vive en
`versiones_en_base`. Las dos comparten la regla, y lo unico que cambia entre ellas es de donde sale
el texto. Vive aqui, y no en el entry point que lo estrenó, porque tiene DOS consumidores: el listado
de plugins que alimenta al etiquetado, y el gate, que necesita la version actual para compararla con
la de la base. Dejarlo en el entry point habria obligado a la capa de aplicacion a importarlo, con la
flecha de dependencia apuntando hacia afuera (G5).
"""
from __future__ import annotations

import logging
from pathlib import Path

from validador_agentico.adaptadores.repositorio import RUTA_GOBIERNO
from validador_agentico.dominio import reglas_identidad
from validador_agentico.dominio.especificacion import RUTAS_MANIFIESTO

log = logging.getLogger(__name__)


def _lector_de_disco(unidad: Path) -> reglas_identidad.LectorDeTexto:
    def leer(relativa: str) -> str | None:
        archivo = unidad / relativa
        if not archivo.is_file():
            return None
        try:
            return archivo.read_text(encoding="utf-8")
        except OSError as fallo:
            log.error("no se pudo leer %s", archivo, exc_info=fallo)
            return None
    return leer


def identidad_de(unidad: Path, raiz: Path) -> reglas_identidad.Identidad | None:
    """La identidad declarada por `unidad`, o `None` si no declara nombre y version.

    El ORDEN de las fuentes -- manifiesto primero, gobierno solo para el conjunto suelto -- y por que
    ese orden y no el contrario vive en `reglas_identidad`.
    """
    identidad = reglas_identidad.identidad_de_unidad(
        _lector_de_disco(unidad), RUTAS_MANIFIESTO, RUTA_GOBIERNO,
        es_raiz=unidad == raiz, donde=str(unidad))
    if identidad is None:
        log.info("%s no declara nombre y version: no hay nada que publicar ahi", unidad)
    return identidad
