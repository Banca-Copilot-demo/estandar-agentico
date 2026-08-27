"""Artefactos que NADIE publica: existen en el arbol y no pertenecen a ninguna unidad publicable.

QUE PROBLEMA RESUELVE, y se descubrio preguntando «un repositorio que tiene plugins no va a aceptar
nunca artefactos sueltos?». Resulto que no los aceptaba, y ademas EN SILENCIO: el lector se invoca una
vez por unidad, la raiz no era una unidad cuando habia plugins, y un `skills/x/SKILL.md` de la raiz
DESAPARECIA del veredicto -- sin ficha, sin error y sin aviso --.

QUE CAMBIO DESPUES. Un repositorio de dominio SI puede tener plugins y sueltos a la vez, y es el caso
normal: el estandar recomienda repositorios por DOMINIO, no repositorios separados segun se empaquete
o no. Asi que la raiz paso a ser una unidad publicable mas -- el CONJUNTO SUELTO -- y esta regla dejo
de ser «hay artefactos fuera de los plugins» para ser lo unico que de verdad importa:

    hay artefactos en la raiz Y la raiz no declara con que version publicarlos.

Sin esa version no hay de donde derivar la etiqueta, asi que no hay paquete, ni atestacion, ni ficha,
y el artefacto queda igual de invisible que antes -- solo que ahora se dice --.

POR QUE ES UN ERROR Y NO UN AVISO. El estandar existe para que no haya artefactos sin gobierno, y uno
que Port ignora es indistinguible de uno que no existe. Perderlo callando es peor que
rechazarlo: quien lo escribio cree que esta publicado.
"""
from __future__ import annotations

from pathlib import Path

from validador_agentico.dominio.hallazgo import Hallazgo, error
from validador_agentico.dominio.reglas_layout import tiene_artefactos_propios


def artefactos_sin_unidad(raiz: Path, hay_plugins: bool, publica_el_conjunto_suelto: bool,
                           directorios: tuple[str, ...], archivos: tuple[str, ...],
                           rutas_manifiesto: tuple[str, ...]) -> tuple[str, ...]:
    """Las rutas de artefacto de la raiz que no las publica nadie.

    `publica_el_conjunto_suelto` es si la raiz declara `version` en su gobierno. Llega como dato
    resuelto y no se lee aqui: esta regla es de dominio y no toca disco mas que para mirar que rutas
    EXISTEN, que es lo que no se puede saber de otra forma.

    Vacio en los dos casos en que si hay quien publique: cuando la raiz declara su version, y cuando
    no hay plugins -- ahi el repositorio entero es la unidad y sus artefactos SON el paquete --.

    UN ARTEFACTO CON MANIFIESTO PROPIO NO ES HUERFANO: es su propia unidad publicable, con version,
    digesto y entrada de marketplace propios. `rutas_manifiesto` es lo que permite distinguirlo, y sin
    ese dato esta regla acusaba de huerfano justo al artefacto mejor publicado del repositorio.
    MEDIDO: con un plugin anidado, un skill suelto CON manifiesto y una raiz que no declara version,
    reportaba `skills/`. No salio antes porque el repositorio de prueba SI declaraba version, asi que
    la regla salia por la primera condicion -- otro control que pasaba por coincidencia --.
    """
    if not hay_plugins or publica_el_conjunto_suelto:
        return ()
    if not tiene_artefactos_propios(raiz, directorios, archivos, rutas_manifiesto):
        return ()

    sin_unidad: list[str] = []
    for nombre in directorios:
        directorio = raiz / nombre
        if not directorio.is_dir():
            continue
        huerfanos = [hijo for hijo in directorio.iterdir()
                     if not (hijo.is_dir()
                             and any((hijo / ruta).is_file() for ruta in rutas_manifiesto))]
        if huerfanos:
            sin_unidad.append(f"{nombre}/")
    sin_unidad += [nombre for nombre in archivos if (raiz / nombre).is_file()]
    return tuple(sorted(sin_unidad))


def revisar_sin_unidad(rutas: tuple[str, ...]) -> list[Hallazgo]:
    """Un error por ruta, diciendo QUE falta y no solo que algo esta mal.

    Lo que falta es una linea en un archivo, asi que el mensaje la nombra: sin ella el autor sabe que
    hay un problema y no sabe que escribir.
    """
    return [
        error(ruta,
              "hay artefactos aqui, en la raiz de un repositorio que tambien aloja plugins, y el "
              "GOVERNANCE.json de la raiz no declara `version`: sin ella no hay de donde derivar la "
              "etiqueta del conjunto suelto, asi que estos artefactos NO se empaquetan, no se sellan "
              "y no reciben ficha en Port. Declara `version` en el GOVERNANCE.json de la raiz "
              "para publicarlos, o muevelos dentro del plugin que les corresponda")
        for ruta in rutas
    ]
