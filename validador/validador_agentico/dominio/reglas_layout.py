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

from collections.abc import Sequence
from pathlib import Path, PurePosixPath

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


def raices_de_artefacto_individual(raiz: Path, rutas_manifiesto: tuple[str, ...],
                                    directorios_de_artefactos: tuple[str, ...]) -> tuple[Path, ...]:
    """Los artefactos SUELTOS que traen manifiesto propio: `skills/<n>/`, `commands/<n>/`, ...

    POR QUE EXISTEN. Un artefacto suelto sin manifiesto NO se puede distribuir por el catalogo, y esta
    MEDIDO contra los dos clientes: con el contenido en otro repositorio -- que es la topologia real,
    catalogo aparte y artefactos en repos de dominio -- la instalacion falla con «No plugin.json found
    in repository». `strict: false` solo exime del manifiesto cuando el contenido vive DENTRO del
    propio catalogo, que no es nuestro caso. Sin entrada en el catalogo, un suelto no queda sujeto al
    estado: se instala igual este certificado, conforme o suspendido.

    Con manifiesto propio, cada suelto es su propia unidad publicable: version propia, digesto propio y
    entrada propia en el catalogo. Antes compartian los tres con todos los sueltos del repositorio, asi
    que tocar un prompt cambiaba el digesto del skill que nadie habia tocado.

    SE RECONOCEN POR EL MANIFIESTO, igual que los plugins anidados. La diferencia es DONDE se busca:
    un plugin cuelga de `plugins/`, y un artefacto individual de su directorio por tipo. Un directorio
    de artefacto SIN manifiesto no aparece aqui -- sigue siendo parte del conjunto suelto --, asi que
    esta regla no cambia el comportamiento de un repositorio que no la use.
    """
    individuales = []
    for contenedor in directorios_de_artefactos:
        directorio = raiz / contenedor
        if not directorio.is_dir():
            continue
        for candidato in sorted(p for p in directorio.iterdir() if p.is_dir()):
            if any((candidato / ruta).is_file() for ruta in rutas_manifiesto):
                individuales.append(candidato)
    return tuple(individuales)


def tiene_artefactos_propios(raiz: Path, directorios: tuple[str, ...],
                              archivos: tuple[str, ...],
                              rutas_manifiesto: tuple[str, ...]) -> bool:
    """Si en la raiz hay artefactos fuera de todo plugin, o sea si existe un conjunto suelto.

    Las rutas llegan como DATO, no importadas del adaptador: asi esta regla se prueba sin saber como
    se llaman los directorios en disco (G5).

    NO CUENTAN LOS ARTEFACTOS CON MANIFIESTO PROPIO, que son unidades por si mismos. Si contaran, un
    repositorio donde TODOS los sueltos tienen manifiesto seguiria declarando un conjunto suelto -- y
    ese conjunto volveria a empaquetar los mismos artefactos, asi que cada uno viajaria en dos
    paquetes con dos digestos.

    `rutas_manifiesto` NO TIENE DEFECTO A PROPOSITO. Lo tuvo, y era una trampa: quien lo olvidara
    obtenia el comportamiento antiguo -- contar como suelto algo que ya es unidad -- sin ningun aviso.
    Esta MEDIDO que ese olvido ocurre: `artefactos_sin_unidad` no lo pasaba y acusaba de huerfano al
    artefacto mejor publicado del repositorio. Un parametro obligatorio convierte ese olvido en un
    error de arranque en vez de en un hallazgo falso.
    """
    for nombre in directorios:
        directorio = raiz / nombre
        if not directorio.is_dir():
            continue
        for entrada in directorio.iterdir():
            if entrada.is_dir() and any((entrada / ruta).is_file() for ruta in rutas_manifiesto):
                continue
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
    individuales = raices_de_artefacto_individual(raiz, rutas_manifiesto, directorios_de_artefactos)
    publicables = (*anidadas, *individuales)
    if not publicables:
        return (raiz,)
    if tiene_artefactos_propios(raiz, directorios_de_artefactos, archivos_de_artefactos,
                                rutas_manifiesto):
        return (*publicables, raiz)
    return publicables


def es_multiunidad(unidades: tuple[Path, ...], raiz: Path) -> bool:
    """Si el repositorio publica mas de una cosa. Cambia lo que el gate exige: con varias, el
    inventario de cada `GOVERNANCE.json` se compara contra el arbol de SU unidad y no del
    repositorio, o un plugin que declara un skill fallaria por los artefactos de su vecino."""
    return unidades != (raiz,)


# La ruta con la que se nombra la unidad que ocupa el repositorio ENTERO -- el conjunto suelto, o el
# plugin unico de la raiz --. Es la forma en que `listar_plugins` la emite, y lo que hace que
# `unidad_de` pueda responder por un archivo que no cuelga de ninguna unidad anidada.
RAIZ_DEL_REPOSITORIO = "."


def _cuelga_de(ruta: str, unidad: str) -> bool:
    """Comparacion por SEGMENTOS y no por texto: `plugins/referencia-vieja` NO esta dentro de
    `plugins/referencia`, aunque una comparacion de prefijos de cadena diga que si."""
    partes_unidad = PurePosixPath(unidad).parts
    return PurePosixPath(ruta).parts[:len(partes_unidad)] == partes_unidad


def unidad_de(ruta: str, unidades: Sequence[str]) -> str | None:
    """La unidad a la que pertenece `ruta`, o `None` si no cuelga de ninguna.

    GANA LA UNIDAD MAS ESPECIFICA cuando hay varias candidatas: con un plugin anidado dentro de
    otro, atribuir el archivo al de fuera lo asignaria al paquete que no lo publica.

    ESTA ES LA UNICA DEFINICION DE PERTENENCIA del repositorio, y esa unicidad es el punto. La usan
    el gate -- para exigir la subida de version de lo que cambio -- y la seleccion de suites a
    evaluar. Con dos definiciones, un archivo podria pertenecer a una unidad para una y a otra para
    la otra, y entonces se evaluaria una unidad y se versionaria otra.
    """
    candidatas = [u for u in unidades if u != RAIZ_DEL_REPOSITORIO and _cuelga_de(ruta, u)]
    if candidatas:
        return max(candidatas, key=len)
    return RAIZ_DEL_REPOSITORIO if RAIZ_DEL_REPOSITORIO in unidades else None
