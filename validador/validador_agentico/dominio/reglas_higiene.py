"""G3 · higiene de contenido: que el paquete no lleve dentro nada que no deba salir del banco.

Hoy el unico control de seguridad vigente en el estandar es el escaneo de secretos, asi que este gate no
compite con nada: es el primer control real que se suma.

LIMITE HONESTO DEL GATE: escanea el PAQUETE PROPIO, no lo que un servidor remoto devuelve en
ejecucion. Para `mcp` eso deja fuera la superficie de inyeccion real —la `description` de una
herramienta es texto de terceros que el modelo lee— y ese hueco lo cierra otra comprobacion, no
esta.

PURA (G5): recibe el texto ya leido y devuelve hallazgos.
"""
from __future__ import annotations

import re

from validador_agentico.dominio.especificacion import (
    PATRON_REFERENCIA_SEGURA,
    PATRONES_HIGIENE,
    VENTANA_CONTEXTO_REFERENCIA,
)
from validador_agentico.dominio.hallazgo import Hallazgo, error

_referencia_segura = re.compile(PATRON_REFERENCIA_SEGURA)


def revisar_higiene(ruta_relativa: str, contenido: str) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for patron, que_es in PATRONES_HIGIENE:
        for coincidencia in re.finditer(patron, contenido):
            if _es_referencia(contenido, coincidencia.start(), coincidencia.end()):
                continue
            linea = contenido[: coincidencia.start()].count("\n") + 1
            hallazgos.append(error(f"{ruta_relativa}:{linea}", f"posible {que_es}"))
    return hallazgos


def _es_referencia(contenido: str, inicio: int, fin: int) -> bool:
    """Una referencia NO es un secreto: el archivo solo dice COMO obtener la credencial.

    `${input:...}`, `${env:...}` y el bloque `oauth` son las formas correctas; lo que el gate busca
    es el valor escrito literalmente.
    """
    desde = max(0, inicio - VENTANA_CONTEXTO_REFERENCIA)
    return bool(_referencia_segura.search(contenido[desde:fin + 10]))
