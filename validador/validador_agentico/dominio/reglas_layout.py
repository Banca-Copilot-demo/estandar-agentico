"""Donde estan las RAICES DE PLUGIN de un repositorio. Regla pura: recibe rutas, devuelve rutas.

EL DEFECTO QUE CIERRA, medido: un repositorio con la estructura `plugins/<nombre>/` -- la que usan
los catalogos publicos para alojar varios plugins en un repo -- daba CONFORME con «0 skills, 0
agentes, plugin: no». El gate buscaba los artefactos en rutas fijas desde la raiz del repositorio,
no los encontraba, y un repositorio con tres artefactos era indistinguible de uno vacio. Es la peor
forma de fallar: en verde.

POR QUE ESTO ES UNA REGLA Y NO UN AJUSTE DEL LECTOR. El lector del repositorio ya funciona bien
sobre la raiz de UN plugin; lo unico que estaba mal era a que ruta se le apuntaba. Asi que en vez de
ensenarle a bajar niveles -- que lo obligaria a distinguir el plugin de cada artefacto -- se
descubren las raices y se le llama UNA VEZ POR RAIZ. El lector no cambia.

UN PLUGIN SE RECONOCE POR SU MANIFIESTO, no por su carpeta. `plugins/` es la convencion habitual,
pero lo que hace que un directorio sea la raiz de un plugin es tener el manifiesto dentro. Buscar por
manifiesto y no por nombre de carpeta evita inventar una convencion que los clientes no imponen.
"""
from __future__ import annotations

from pathlib import Path

# Donde se buscan raices de plugin anidadas. Es una convencion observada en los catalogos publicos,
# no un requisito de ninguna especificacion: por eso la lista es corta y explicita.
DIRECTORIOS_DE_PLUGINS = ("plugins",)


def raices_de_plugin(raiz: Path, rutas_manifiesto: tuple[str, ...]) -> tuple[Path, ...]:
    """Las raices de plugin del repositorio, en orden estable.

    Devuelve `(raiz,)` cuando el repositorio es de un solo plugin -- el caso normal -- o cuando no
    hay ningun manifiesto: un repositorio de artefactos SUELTOS sigue siendo una unidad de
    validacion, y devolver una tupla vacia lo dejaria sin revisar.
    """
    anidadas = []
    for contenedor in DIRECTORIOS_DE_PLUGINS:
        directorio = raiz / contenedor
        if not directorio.is_dir():
            continue
        for candidato in sorted(p for p in directorio.iterdir() if p.is_dir()):
            if any((candidato / ruta).is_file() for ruta in rutas_manifiesto):
                anidadas.append(candidato)
    return tuple(anidadas) if anidadas else (raiz,)


def es_multiplugin(raices: tuple[Path, ...], raiz: Path) -> bool:
    """Si el repositorio aloja varios plugins. Cambia lo que el gate exige: con varios, el
    inventario de cada `GOVERNANCE.json` se compara contra el arbol de SU plugin y no del
    repositorio, o un plugin que declara un skill fallaria por los artefactos de su vecino."""
    return raices != (raiz,)
