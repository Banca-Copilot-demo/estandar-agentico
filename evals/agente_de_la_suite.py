#!/usr/bin/env python3
"""El AGENTE que evalua una suite, deducido de donde vive. Vacio si la suite no es de un agente.

POR QUE HACE FALTA. Un skill y un agente NO se evaluan igual, y la diferencia no es de matiz:

  - de un SKILL se mide si el cliente lo ACTIVA cuando toca y que produce. Se invoca sin `--agent`,
    porque justamente se quiere comprobar que el cliente lo elige solo;
  - un AGENTE no se activa: se INVOCA. Sin `--agent` la suite no ejecuta al agente sino al asistente
    por defecto, asi que mide otra cosa y falla por una razon que no tiene nada que ver con el
    artefacto.

MEDIDO: la primera ejecucion del gate en CI corrio las dos suites igual y la del agente dio 1 de 3.
El informe acusaba al ARTEFACTO de un fallo de la HERRAMIENTA -- el mismo dano que ya costo caro al
montar el puente --.

DE DONDE SE DEDUCE. Una suite de promptfoo no declara a que artefacto evalua (el esquema con
`artifact` es el de las suites `*.eval.json`, que son otro formato). Lo que si es fiable es el LAYOUT:
una suite co-localizada con un agente vive en `<unidad>/agents/evals/`, con el `.agent.md` como
hermano. Se lee su `name` del frontmatter y no del nombre del archivo, porque el nombre de invocacion
es el que declara el artefacto.

SALIDA A STDOUT PORQUE LA CONSUME OTRO PROCESO; el logging va a stderr (L8).
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_DIRECTORIO_DE_AGENTES = "agents"
_SUFIJO_DE_AGENTE = "*.agent.md"
_NOMBRE_EN_FRONTMATTER = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)


def _nombre_declarado(definicion: Path) -> str | None:
    """El `name` del frontmatter, o `None` si no se puede leer.

    Se lee solo el frontmatter -- lo que va entre los dos `---` -- para no confundirse con un
    `name:` que aparezca en el cuerpo, por ejemplo dentro de un bloque de ejemplo.
    """
    try:
        texto = definicion.read_text(encoding="utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError) as fallo:
        log.error("no se pudo leer %s", definicion, exc_info=fallo)
        return None
    bloque = re.match(r"^---\n(.*?)\n---", texto, re.S)
    if not bloque:
        log.error("%s no tiene frontmatter: no se puede saber su nombre de invocacion", definicion)
        return None
    encontrado = _NOMBRE_EN_FRONTMATTER.search(bloque.group(1))
    return encontrado.group(1).strip().strip("\"'") if encontrado else None


def agente_de(suite: Path) -> str | None:
    """El nombre de invocacion del agente que esta suite evalua, o `None` si no evalua a uno.

    `None` NO es un error: la mayoria de las suites son de skills y no llevan agente. Quien llama
    distingue los dos casos por el valor, no por una excepcion.
    """
    directorio = suite.parent.parent
    if directorio.name != _DIRECTORIO_DE_AGENTES:
        return None
    definiciones = sorted(directorio.glob(_SUFIJO_DE_AGENTE))
    if not definiciones:
        log.warning("%s cuelga de `%s/` pero no hay ningun `.agent.md` al lado",
                    suite, _DIRECTORIO_DE_AGENTES)
        return None
    if len(definiciones) > 1:
        # Con varios no se puede adivinar cual, y elegir uno mediria el artefacto equivocado.
        log.error("%s tiene %d agentes hermanos: la suite no dice cual evalua",
                  suite, len(definiciones))
        return None
    return _nombre_declarado(definiciones[0])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("suite", type=Path, help="ruta a promptfooconfig.yaml")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Activa logging DEBUG (detalles internos de ejecucion).")
    argumentos = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if argumentos.verbose else logging.INFO,
                        stream=sys.stderr, format="%(levelname)-8s %(name)s — %(message)s")

    agente = agente_de(argumentos.suite)
    if agente:
        log.info("%s evalua al agente %s", argumentos.suite, agente)
    print(agente or "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
