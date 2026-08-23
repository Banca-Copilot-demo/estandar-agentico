"""Artefactos que quedan FUERA de toda unidad publicable: ni en un plugin, ni en el paquete suelto.

EL DEFECTO QUE CIERRA, y se descubrio preguntando «un repositorio que tiene plugins no va a aceptar
nunca artefactos sueltos?». La respuesta era que no, y ademas EN SILENCIO.

Como se construyo el recorrido: el lector del repositorio se invoca UNA VEZ POR RAIZ DE PLUGIN, y
cuando hay plugins la raiz del repositorio deja de ser una de esas raices. Consecuencia: un
`skills/x/SKILL.md` en la raiz de un repositorio que tiene `plugins/` NO SE LEE como artefacto. No
entra al inventario, no recibe ficha, no se etiqueta -- y nada lo dice --. Medido: en un repositorio
con un plugin y un skill en la raiz, el skill de la raiz desaparecia por completo del veredicto.

POR QUE ES UN ERROR Y NO UN AVISO. El estandar existe para que no haya artefactos sin gobierno, y un
artefacto que el catalogo ignora es indistinguible de uno que no existe. Perderlo en silencio es
peor que rechazarlo: quien lo escribio cree que esta publicado.

QUE NO DECIDE ESTA REGLA. No prohibe que un repositorio tenga plugins y sueltos a la vez como
decision de arquitectura; lo que dice es que HOY el pipeline no publica los segundos, asi que hay que
elegir: mover el artefacto dentro de un plugin, o sacarlo a un repositorio de sueltos. El dia que el
empaquetado sepa producir un paquete suelto que EXCLUYA `plugins/`, esta regla es el sitio donde se
cambia el error por la publicacion de los dos.
"""
from __future__ import annotations

from pathlib import Path

from validador_agentico.dominio.hallazgo import Hallazgo, error


def artefactos_huerfanos(raiz: Path, raices_de_plugin: tuple[Path, ...],
                          directorios: tuple[str, ...],
                          archivos: tuple[str, ...]) -> tuple[str, ...]:
    """Las rutas de artefacto que estan en la raiz del repositorio teniendo plugins anidados.

    `directorios` son los que contienen artefactos (`skills`, `agents`, `commands`) y `archivos` los
    que son un artefacto por si mismos (`.mcp.json`). Llegan como DATO y no importados del adaptador:
    asi esta regla se prueba sin conocer como se llama nada en disco (G5).

    Vacio cuando el repositorio no tiene plugins anidados: entonces la raiz ES la unidad publicable y
    sus artefactos no son huerfanos, son el paquete.
    """
    if raices_de_plugin == (raiz,):
        return ()

    huerfanos: list[str] = []
    for nombre in directorios:
        directorio = raiz / nombre
        if directorio.is_dir() and any(directorio.iterdir()):
            huerfanos.append(f"{nombre}/")
    for nombre in archivos:
        if (raiz / nombre).is_file():
            huerfanos.append(nombre)
    return tuple(sorted(huerfanos))


def revisar_huerfanos(huerfanos: tuple[str, ...]) -> list[Hallazgo]:
    """Un error por cada ruta huerfana, diciendo las DOS salidas posibles.

    Un error que solo dice «esto esta mal» obliga a adivinar; aqui las dos salidas son distintas de
    verdad -- una cambia el paquete al que pertenece el artefacto, la otra lo saca a otro repositorio
    -- y quien lo lee tiene que poder elegir.
    """
    return [
        error(ruta,
              "esta en la raiz de un repositorio que aloja plugins, asi que NO pertenece a ninguna "
              "unidad publicable: no se empaqueta, no se sella y no recibe ficha en el catalogo. "
              "Muevelo dentro del plugin que le corresponda, o saca los artefactos sueltos a su "
              "propio repositorio -- que si se publica, con su `version` en el GOVERNANCE.json --")
        for ruta in huerfanos
    ]
