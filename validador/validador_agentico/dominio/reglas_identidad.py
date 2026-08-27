"""Como se lee la IDENTIDAD -- nombre y version -- de una unidad publicable.

POR QUE ES UNA REGLA Y NO UNA FUNCION DEL LISTADO. Vivia dentro de `listar_plugins`, atada a leer
del disco, y ahi bastaba mientras la unica pregunta fuera «que version publica el arbol de trabajo».
La regla de subida de version hace la MISMA pregunta sobre la RAMA BASE, donde no hay arbol que leer
sino blobs de git. Copiar el orden de fuentes en el adaptador lo habria duplicado (G2), y la copia
habria divergido en el primer cambio -- que es justo el fallo que este modulo previene: si el gate y
el etiquetado difieren sobre que version declara una unidad, el gate aprueba una cosa y se etiqueta
otra --.

De ahi la forma: la regla no sabe de donde sale el texto. Recibe un LECTOR -- `ruta relativa a la
unidad` -> `contenido o None` -- y el llamador decide si eso es el disco o `git show`.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)

# `ruta relativa a la unidad` -> contenido del archivo, o `None` si no existe o no se pudo leer.
LectorDeTexto = Callable[[str], str | None]


@dataclass(frozen=True)
class Identidad:
    """Lo que hace publicable a una unidad: como se llama y que version publica.

    Dataclass y no `tuple[str, str]` (OO1): con la tupla, cual de los dos era cual dependia del
    orden y no aparecia en ninguna firma.
    """

    nombre: str
    version: str


def _identidad_declarada(texto: str, campo_nombre: str, donde: str) -> Identidad | None:
    """La identidad de un JSON ya leido, o `None` si no es JSON o le falta alguno de los dos campos.

    Una unidad sin nombre no se puede resolver en el marketplace y una sin version no se puede
    etiquetar: devolver una identidad a medias haria que el llamador la tratara como valida.
    """
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as fallo:
        log.error("%s no es JSON valido", donde, exc_info=fallo)
        return None
    nombre, version = datos.get(campo_nombre), datos.get("version")
    if not nombre or not version:
        log.debug("%s sin `%s` o sin `version`", donde, campo_nombre)
        return None
    return Identidad(str(nombre), str(version))


def identidad_de_unidad(leer: LectorDeTexto, rutas_manifiesto: tuple[str, ...],
                        ruta_gobierno: str, *, es_raiz: bool,
                        donde: str) -> Identidad | None:
    """La identidad de una unidad: de su MANIFIESTO si lo tiene, del gobierno si es el conjunto suelto.

    EL ORDEN DE LAS FUENTES ES LO QUE EVITA ETIQUETAR DOS VECES EL MISMO CONTENIDO, y se aprendio
    rompiendolo: al preguntar primero por el gobierno, un repositorio de UN plugin en la raiz se
    etiquetaba con la version del `GOVERNANCE.json` -- 1.0.0 -- en vez de la del `plugin.json` --
    3.0.0 --, porque en ese layout los dos archivos describen el MISMO paquete (el gate exige que su
    `id` coincida con el `name`). Con el manifiesto primero, cada unidad tiene una sola identidad y la
    del gobierno solo se usa cuando no hay manifiesto, que es exactamente el conjunto suelto.

    Una unidad ANIDADA sin manifiesto no deberia existir -- se descubren POR el manifiesto -- pero si
    apareciera, no se inventa su identidad cayendo al gobierno de la raiz.
    """
    for relativa in rutas_manifiesto:
        texto = leer(relativa)
        if texto is not None:
            return _identidad_declarada(texto, "name", f"{donde}/{relativa}")
    if not es_raiz:
        return None
    texto = leer(ruta_gobierno)
    if texto is None:
        return None
    return _identidad_declarada(texto, "id", f"{donde}/{ruta_gobierno}")
