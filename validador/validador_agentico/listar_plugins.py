#!/usr/bin/env python3
"""Entry point: imprime los PLUGINS del repositorio, uno por linea.

`<ruta relativa>TAB<nombre>TAB<version>TAB<etiqueta>`, con `.` de ruta cuando la unidad es la
raiz del repositorio. La ETIQUETA se emite calculada -- no la construye el consumidor -- porque su
forma depende de si el repositorio publica una unidad o varias, y eso solo se sabe aqui.

POR QUE EXISTE. Un repositorio de dominio puede alojar varios plugins bajo `plugins/<nombre>/`,
y entonces el etiquetado y el empaquetado necesitan saber cuales son y donde. Y necesitan
coincidir EXACTAMENTE con lo que el gate considera un plugin: si el etiquetado crea una etiqueta
para algo que el empaquetado no encuentra, la publicacion falla despues de haber creado una
etiqueta que -- con releases inmutables -- ya no se puede borrar.

De ahi que esto no reimplemente el descubrimiento: reutiliza `dominio.reglas_layout`, la misma
regla que usa el gate, ni la lectura de la identidad: `dominio.reglas_identidad`, la misma que el
gate usa para preguntarle a la rama base que version declaraba alli. Una sola implementacion.

SALIDA A STDOUT PORQUE LA CONSUME OTRO PROCESO; el logging va a stderr (L8).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from validador_agentico.adaptadores import registro
from validador_agentico.adaptadores.identidad_en_disco import identidad_de
from validador_agentico.adaptadores.repositorio import (
    DIRECTORIO_AGENTES,
    DIRECTORIO_PROMPTS,
    DIRECTORIO_SKILLS,
    RUTA_MCP,
)
from validador_agentico.dominio import reglas_etiquetas
from validador_agentico.dominio.especificacion import RUTAS_MANIFIESTO
from validador_agentico.dominio.reglas_layout import unidades_publicables

log = logging.getLogger(__name__)

_SEPARADOR = "\t"

# Donde viven los artefactos dentro de una unidad. Se pasan como dato a la regla de layout, que es de
# dominio y no tiene que saber como se llaman los directorios en disco (G5).
_DIRECTORIOS_DE_ARTEFACTOS = (DIRECTORIO_SKILLS, DIRECTORIO_AGENTES, DIRECTORIO_PROMPTS)
_ARCHIVOS_DE_ARTEFACTOS = (RUTA_MCP,)


def listar(raiz: Path) -> list[tuple[str, str, str, str]]:
    """Las unidades publicables del repositorio como `(ruta, nombre, version, etiqueta)`.

    LAS DOS CLASES DE UNIDAD, y un repositorio de dominio puede tener las dos a la vez:

      - cada PLUGIN anidado, con su nombre y version del manifiesto;
      - el CONJUNTO SUELTO -- los artefactos de la raiz, fuera de todo plugin -- con el `id` y la
        `version` del `GOVERNANCE.json` de la raiz.

    El conjunto suelto se emite con `.` como ruta y CON NOMBRE, igual que un plugin, para que su
    etiqueta diga QUE publica. La alternativa era reservarle la forma corta `vX.Y.Z`, y se descarto:
    en un repositorio mixto esa etiqueta significaria «todo excepto los plugins», una definicion por
    resta que nadie deduce leyendola. Con nombre, todas las etiquetas del repositorio se leen igual.

    El caso de UN SOLO plugin en la raiz sigue dando `.` sin nombre propio: ahi el repositorio entero
    ES el plugin y su manifiesto ya lo nombra.
    """
    identificadas = []
    for unidad in unidades_publicables(raiz, RUTAS_MANIFIESTO,
                                       _DIRECTORIOS_DE_ARTEFACTOS, _ARCHIVOS_DE_ARTEFACTOS):
        identidad = identidad_de(unidad, raiz)
        if identidad is None:
            continue
        identificadas.append((unidad.relative_to(raiz).as_posix() or ".",
                              identidad.nombre, identidad.version))

    if not identificadas:
        log.info("%s no tiene plugin ni gobierno con version: no hay nada que publicar", raiz)
        return []

    # LA ETIQUETA SE CALCULA AQUI Y SE EMITE, en vez de dejar que el etiquetado la construya. Estaba
    # en tres lineas de bash dentro del workflow, donde ninguna prueba la alcanzaba, y se equivoco al
    # aparecer el repositorio mixto: la condicion era «subruta `.` -> forma corta», y en un repo con
    # plugins eso produjo un `v1.0.0` que significaba «todo excepto los plugins». Con la etiqueta como
    # columna, el consumidor no decide nada y la regla tiene pruebas.
    unica = len(identificadas) == 1
    return [(ruta, nombre, version, reglas_etiquetas.etiqueta_de(nombre, version, unica))
            for ruta, nombre, version in identificadas]


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
