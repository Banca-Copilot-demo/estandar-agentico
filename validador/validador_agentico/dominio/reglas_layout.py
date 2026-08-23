"""Cuales son las UNIDADES PUBLICABLES de un repositorio. Regla pura: recibe rutas, devuelve rutas.

UNA UNIDAD PUBLICABLE es lo que recibe una etiqueta, un paquete y una atestacion. Hay dos clases:

  - un PLUGIN, reconocido por su manifiesto, y
  - el CONJUNTO SUELTO: los artefactos que viven en la raiz del repositorio, fuera de todo plugin.

Un repositorio de dominio puede tener las dos cosas a la vez, y ESO ES EL CASO NORMAL y no una
excepcion: el estandar recomienda repositorios por DOMINIO, no repositorios separados para plugins y
para sueltos. Quien escribe un artefacto no deberia tener que abrir un repositorio nuevo para decidir
si lo empaqueta.

EL DEFECTO QUE CIERRA ESTA VERSION, medido. La funcion devolvia «o los plugins anidados O la raiz»,
nunca las dos. Consecuencia: en un repositorio con plugins, un `skills/x/SKILL.md` de la raiz no se
leia como artefacto -- el lector se invoca una vez por unidad, y la raiz no era una -- asi que
DESAPARECIA del veredicto sin ficha, sin error y sin aviso. Quien lo escribio creia que estaba
publicado.

POR QUE SE PUEDEN DEVOLVER LAS DOS SIN CONTAR NADA DOS VECES, y esto se comprobo antes de cambiarlo:
el lector de artefactos NO es recursivo. Busca `skills/*/SKILL.md`, `agents/*.agent.md` y
`commands/*.prompt.md` un nivel por debajo de la raiz que se le da, asi que apuntarlo a la raiz del
repositorio coge SOLO los artefactos de la raiz y nunca los de `plugins/<nombre>/`.

EL DEFECTO ORIGINAL QUE CERRO LA PRIMERA VERSION sigue cubierto: un repositorio con la estructura
`plugins/<nombre>/` daba CONFORME con «0 skills, 0 agentes, plugin: no», porque el gate buscaba en
rutas fijas desde la raiz. Es la peor forma de fallar: en verde.

UN PLUGIN SE RECONOCE POR SU MANIFIESTO, no por su carpeta. `plugins/` es la convencion habitual,
pero lo que hace que un directorio sea la raiz de un plugin es tener el manifiesto dentro.
"""
from __future__ import annotations

from pathlib import Path

# Donde se buscan raices de plugin anidadas. Es una convencion observada en los catalogos publicos,
# no un requisito de ninguna especificacion: por eso la lista es corta y explicita.
DIRECTORIOS_DE_PLUGINS = ("plugins",)


def raices_de_plugin(raiz: Path, rutas_manifiesto: tuple[str, ...]) -> tuple[Path, ...]:
    """Solo las raices de PLUGIN anidadas, en orden estable. Vacio si no hay ninguna.

    Se expone aparte de `unidades_publicables` porque hay dos preguntas distintas: «que plugins hay»
    -- que es lo que el marketplace necesita -- y «que se publica», que incluye el conjunto suelto.
    """
    anidadas = []
    for contenedor in DIRECTORIOS_DE_PLUGINS:
        directorio = raiz / contenedor
        if not directorio.is_dir():
            continue
        for candidato in sorted(p for p in directorio.iterdir() if p.is_dir()):
            if any((candidato / ruta).is_file() for ruta in rutas_manifiesto):
                anidadas.append(candidato)
    return tuple(anidadas)


def tiene_artefactos_propios(raiz: Path, directorios: tuple[str, ...],
                              archivos: tuple[str, ...]) -> bool:
    """Si en la raiz hay artefactos fuera de todo plugin, o sea si existe un conjunto suelto.

    Las rutas llegan como DATO, no importadas del adaptador: asi esta regla se prueba sin saber como
    se llaman los directorios en disco (G5).
    """
    for nombre in directorios:
        directorio = raiz / nombre
        if directorio.is_dir() and any(directorio.iterdir()):
            return True
    return any((raiz / nombre).is_file() for nombre in archivos)


def unidades_publicables(raiz: Path, rutas_manifiesto: tuple[str, ...],
                          directorios_de_artefactos: tuple[str, ...],
                          archivos_de_artefactos: tuple[str, ...]) -> tuple[Path, ...]:
    """Todo lo que el repositorio publica: sus plugins anidados y, si los hay, su conjunto suelto.

    EL ORDEN ES DELIBERADO -- plugins primero y la raiz al final -- porque es el que produce los
    mensajes mas utiles: los hallazgos de cada plugin salen agrupados y los de la raiz al cierre, en
    vez de intercalados.

    Devuelve `(raiz,)` cuando no hay ningun plugin: entonces el repositorio ENTERO es la unidad, y es
    tambien lo que mantiene revisable un repositorio vacio o de puros documentos -- devolver una tupla
    vacia lo dejaria sin gate --.
    """
    anidadas = raices_de_plugin(raiz, rutas_manifiesto)
    if not anidadas:
        return (raiz,)
    if tiene_artefactos_propios(raiz, directorios_de_artefactos, archivos_de_artefactos):
        return (*anidadas, raiz)
    return anidadas


def es_multiunidad(unidades: tuple[Path, ...], raiz: Path) -> bool:
    """Si el repositorio publica mas de una cosa. Cambia lo que el gate exige: con varias, el
    inventario de cada `GOVERNANCE.json` se compara contra el arbol de SU unidad y no del
    repositorio, o un plugin que declara un skill fallaria por los artefactos de su vecino."""
    return unidades != (raiz,)
