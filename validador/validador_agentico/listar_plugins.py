#!/usr/bin/env python3
"""Entry point: imprime los PLUGINS del repositorio, uno por linea.

`<ruta relativa>TAB<nombre>TAB<version>`, con `.` cuando el plugin es la raiz del repositorio.

POR QUE EXISTE. Un repositorio de dominio puede alojar varios plugins bajo `plugins/<nombre>/`,
y entonces el etiquetado y el empaquetado necesitan saber cuales son y donde. Y necesitan
coincidir EXACTAMENTE con lo que el gate considera un plugin: si el etiquetado crea una etiqueta
para algo que el empaquetado no encuentra, la publicacion falla despues de haber creado una
etiqueta que -- con releases inmutables -- ya no se puede borrar.

De ahi que esto no reimplemente el descubrimiento: reutiliza `dominio.reglas_layout`, la misma
regla que usa el gate. Una sola implementacion, tres consumidores.

SALIDA A STDOUT PORQUE LA CONSUME OTRO PROCESO; el logging va a stderr (L8).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from validador_agentico.adaptadores import registro
from validador_agentico.adaptadores.repositorio import RUTA_GOBIERNO
from validador_agentico.dominio.especificacion import RUTAS_MANIFIESTO
from validador_agentico.dominio.reglas_layout import raices_de_plugin

log = logging.getLogger(__name__)

_SEPARADOR = "\t"


def _manifiesto_de(raiz: Path) -> Path | None:
    """El manifiesto del plugin, en cualquiera de las ubicaciones que los clientes leen."""
    for relativa in RUTAS_MANIFIESTO:
        candidato = raiz / relativa
        if candidato.is_file():
            return candidato
    return None


def _identidad(manifiesto: Path) -> tuple[str, str] | None:
    """`(nombre, version)` del manifiesto, o `None` si le falta alguno de los dos.

    Un plugin sin nombre no se puede resolver en el catalogo y uno sin version no se puede
    etiquetar: emitir una linea a medias haria que el llamador la tratara como valida.
    """
    try:
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    except json.JSONDecodeError as fallo:
        log.error("%s no es JSON valido", manifiesto, exc_info=fallo)
        return None
    except OSError as fallo:
        log.error("no se pudo leer %s", manifiesto, exc_info=fallo)
        return None
    nombre, version = datos.get("name"), datos.get("version")
    if not nombre or not version:
        log.error("%s sin `name` o sin `version`: se omite", manifiesto)
        return None
    return str(nombre), str(version)


def _identidad_del_gobierno(raiz: Path) -> tuple[str, str] | None:
    """`(id, version)` del `GOVERNANCE.json` de la raiz, para un repositorio de artefactos SUELTOS.

    POR QUE EXISTE. Aqui se rompia la cadena del artefacto suelto: cuando no habia manifiesto esta
    funcion no existia y el descubrimiento hacia `continue`, asi que no se etiquetaba nada -- y sin
    etiqueta no hay release, ni paquete, ni atestacion, ni ficha en el catalogo --. El comentario de
    `etiquetar.yml` ya decia que un repositorio de sueltos declara su version en el `GOVERNANCE.json`;
    el campo NO existia en el esquema y esta funcion tampoco. El resultado era que el lineamiento
    prometia que un suelto aparece en el catalogo y se puede atestar, y ninguna de las dos cosas pasaba.

    `None` cuando no hay gobierno legible o le falta la `version`: sin ella no hay de donde derivar la
    etiqueta, y emitir una linea a medias haria que el llamador la tratara como valida.
    """
    gobierno = raiz / RUTA_GOBIERNO
    if not gobierno.is_file():
        return None
    try:
        datos = json.loads(gobierno.read_text(encoding="utf-8"))
    except json.JSONDecodeError as fallo:
        log.error("%s no es JSON valido", gobierno, exc_info=fallo)
        return None
    except OSError as fallo:
        log.error("no se pudo leer %s", gobierno, exc_info=fallo)
        return None
    identificador, version = datos.get("id"), datos.get("version")
    if not identificador or not version:
        log.info("%s no declara `id` y `version`: nada que etiquetar como paquete suelto", gobierno)
        return None
    return str(identificador), str(version)


def listar(raiz: Path) -> list[tuple[str, str, str]]:
    """Las unidades publicables del repositorio como `(ruta, nombre, version)`.

    Son los PLUGINS cuando los hay, y el REPOSITORIO ENTERO cuando no: un repositorio de artefactos
    sueltos es su propia unidad de publicacion, con la version declarada en su `GOVERNANCE.json`. En
    los dos casos el consumidor recibe lo mismo -- una ruta, un nombre y una version -- porque lo que
    el etiquetado y el empaquetado necesitan saber no cambia.
    """
    encontrados = []
    for raiz_plugin in raices_de_plugin(raiz, RUTAS_MANIFIESTO):
        manifiesto = _manifiesto_de(raiz_plugin)
        if manifiesto is None:
            continue
        identidad = _identidad(manifiesto)
        if identidad is None:
            continue
        relativa = raiz_plugin.relative_to(raiz).as_posix() or "."
        encontrados.append((relativa, *identidad))

    if encontrados:
        return encontrados

    # SIN NINGUN PLUGIN, el repositorio entero es la unidad. Se pregunta DESPUES de recorrer los
    # plugins y no antes: un repositorio con plugins tiene su propio `GOVERNANCE.json` en cada uno, y
    # preguntar primero por la raiz habria hecho que un repositorio multiplugin se etiquetara ademas
    # como si fuera un suelto -- dos etiquetas para el mismo commit, y con releases inmutables no se
    # borran.
    del_gobierno = _identidad_del_gobierno(raiz)
    if del_gobierno is None:
        log.info("%s no tiene plugin ni gobierno con version: no hay nada que publicar", raiz)
        return []
    log.info("sin plugin: se publica el repositorio como paquete suelto %s v%s", *del_gobierno)
    return [(".", *del_gobierno)]


def _parsear_argumentos() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", nargs="?", default=".", type=Path)
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Activa logging DEBUG (detalles internos de ejecucion).")
    return ap.parse_args()


def main() -> int:
    argumentos = _parsear_argumentos()
    registro.configurar(verboso=argumentos.verbose)
    for fila in listar(argumentos.raiz):
        print(_SEPARADOR.join(fila))
    return 0


if __name__ == "__main__":
    sys.exit(main())
