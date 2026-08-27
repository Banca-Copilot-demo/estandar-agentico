"""Que dice una ETIQUETA de release, y cual de ellas queda vigente. Reglas puras sobre cadenas.

Modulo aparte porque es un grupo tematico propio: interpretar etiquetas no es decidir el destino de
un candidato (G1). Lo usan dos consumidores distintos -- la decision de indexar, para comparar la
version, y el caso de uso, para saber que releases merece la pena descargar --, y ninguno de los dos
necesita al otro.

DOS FORMAS DE ETIQUETA, y toda la complejidad de aqui viene de eso: `vX.Y.Z` cuando el repositorio
es un solo plugin en su raiz, y `<nombre>--vX.Y.Z` cuando aloja varios y hay que decir de cual es.
Las dos conviven a proposito: las etiquetas publicadas no se reescriben.
"""
from __future__ import annotations

# Separador de la etiqueta por plugin: `<nombre>--vX.Y.Z`. Un repositorio de dominio que aloja
# varios plugins publica una etiqueta por plugin, porque un solo `vX.Y.Z` no dice de cual es.
_SEPARADOR_DE_ETIQUETA_POR_PLUGIN = "--v"
_PREFIJO_DE_VERSION = "v"


def version_de_la_etiqueta(etiqueta: str) -> str:
    """La version que una etiqueta declara, en sus DOS formas.

    `vX.Y.Z` cuando el repositorio es un solo plugin en la raiz, y `<nombre>--vX.Y.Z` cuando aloja
    varios. Sin esto, la etiqueta por plugin se comparaba entera contra la version del manifiesto y
    el candidato se rechazaba por VERSION_DISCREPANTE -- un mensaje que manda al equipo del dominio
    a buscar un desajuste de version que no existe.
    """
    if _SEPARADOR_DE_ETIQUETA_POR_PLUGIN in etiqueta:
        return etiqueta.rsplit(_SEPARADOR_DE_ETIQUETA_POR_PLUGIN, 1)[1]
    return etiqueta.removeprefix(_PREFIJO_DE_VERSION)


def es_etiqueta_por_plugin(etiqueta: str) -> bool:
    """Si la etiqueta identifica UN plugin dentro de un repositorio que aloja varios."""
    return _SEPARADOR_DE_ETIQUETA_POR_PLUGIN in etiqueta


def _plugin_de_la_etiqueta(etiqueta: str) -> str:
    """Que plugin nombra la etiqueta. Cadena vacia = el plugin de la RAIZ del repositorio.

    Es el nombre que el equipo puso en la etiqueta, no el del manifiesto: sirve para AGRUPAR
    releases sin descargar ninguno, que es lo que evita bajar y verificar el historial completo.
    """
    if not es_etiqueta_por_plugin(etiqueta):
        return ""
    return etiqueta.rsplit(_SEPARADOR_DE_ETIQUETA_POR_PLUGIN, 1)[0]


def etiquetas_vigentes(etiquetas_de_mas_nueva_a_mas_vieja: tuple[str, ...]) -> tuple[str, ...]:
    """Una etiqueta por plugin: la mas nueva de cada uno, en el orden recibido.

    POR QUE HACE FALTA. El indice preguntaba por EL ultimo release, en singular, y eso bastaba
    cuando un repositorio era un plugin. Con una etiqueta por plugin, el repositorio tiene varios
    releases y «el ultimo» es solo uno: los demas no se rechazaban ni se omitian -- no se MIRABAN,
    sin dejar rastro en ningun log. Medido en la organizacion real: cinco releases publicados y el
    indice evaluaba uno.

    Y no se devuelven TODAS: de un mismo plugin hay varias versiones publicadas -- las etiquetas no
    se reescriben -- y el marketplace lista la version vigente de cada plugin, no su historial.
    """
    vigentes: list[str] = []
    vistos: set[str] = set()
    for etiqueta in etiquetas_de_mas_nueva_a_mas_vieja:
        plugin = _plugin_de_la_etiqueta(etiqueta)
        if plugin in vistos:
            continue
        vistos.add(plugin)
        vigentes.append(etiqueta)
    return tuple(vigentes)
