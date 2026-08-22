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


def listar(raiz: Path) -> list[tuple[str, str, str]]:
    """Los plugins del repositorio como `(ruta, nombre, version)`. Funcion pura salvo la lectura."""
    encontrados = []
    for raiz_plugin in raices_de_plugin(raiz, RUTAS_MANIFIESTO):
        manifiesto = _manifiesto_de(raiz_plugin)
        if manifiesto is None:
            # Un repositorio de artefactos SUELTOS no tiene manifiesto y no hay nada que etiquetar.
            log.info("%s no tiene manifiesto: no hay plugin que publicar", raiz_plugin)
            continue
        identidad = _identidad(manifiesto)
        if identidad is None:
            continue
        relativa = raiz_plugin.relative_to(raiz).as_posix() or "."
        encontrados.append((relativa, *identidad))
    return encontrados


def _configurar_logging(verboso: bool) -> None:
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter("%(levelname)-8s %(name)s - %(message)s"))
    logging.getLogger().setLevel(logging.DEBUG if verboso else logging.INFO)
    logging.getLogger().addHandler(manejador)


def _parsear_argumentos() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raiz", nargs="?", default=".", type=Path)
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Activa logging DEBUG (detalles internos de ejecucion).")
    return ap.parse_args()


def main() -> int:
    argumentos = _parsear_argumentos()
    _configurar_logging(verboso=argumentos.verbose)
    for fila in listar(argumentos.raiz):
        print(_SEPARADOR.join(fila))
    return 0


if __name__ == "__main__":
    sys.exit(main())
