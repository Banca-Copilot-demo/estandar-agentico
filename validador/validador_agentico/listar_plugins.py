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
from validador_agentico.adaptadores.repositorio import (
    DIRECTORIO_AGENTES,
    DIRECTORIO_PROMPTS,
    DIRECTORIO_SKILLS,
    RUTA_GOBIERNO,
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
        identidad = _identidad_de(unidad, raiz)
        if identidad is None:
            continue
        identificadas.append((unidad.relative_to(raiz).as_posix() or ".", *identidad))

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


def _identidad_de(unidad: Path, raiz: Path) -> tuple[str, str] | None:
    """`(nombre, version)` de una unidad: del MANIFIESTO si lo tiene, del gobierno si es el suelto.

    EL ORDEN DE LAS FUENTES ES LO QUE EVITA ETIQUETAR DOS VECES EL MISMO CONTENIDO, y se aprendio
    rompiendolo: al preguntar primero por el gobierno, un repositorio de UN plugin en la raiz se
    etiquetaba con la version del `GOVERNANCE.json` -- 1.0.0 -- en vez de la del `plugin.json` --
    3.0.0 --, porque en ese layout los dos archivos describen el MISMO paquete (el gate exige que su
    `id` coincida con el `name`). Con el manifiesto primero, cada unidad tiene una sola identidad y la
    del gobierno solo se usa cuando no hay manifiesto, que es exactamente el conjunto suelto.
    """
    manifiesto = _manifiesto_de(unidad)
    if manifiesto is not None:
        return _identidad(manifiesto)
    if unidad != raiz:
        # Una unidad anidada sin manifiesto no deberia existir -- se descubren POR el manifiesto --
        # pero si apareciera, no se inventa su identidad.
        return None
    del_gobierno = _identidad_del_gobierno(raiz)
    if del_gobierno is not None:
        log.info("el conjunto suelto se publica como %s v%s", *del_gobierno)
    return del_gobierno


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
