"""Adaptador de entrada: valida una proyeccion del indice contra `marketplace.schema.json`.

POR QUE ANTES DE ESCRIBIR Y NO DESPUES. El catalogo que se escribe es el que los clientes instalan;
validarlo despues solo documentaria que se publico algo malo. Si una proyeccion no cumple, no se
escribe NINGUNA -- las dos avanzan juntas o ninguna, o los usuarios de un cliente veran un catalogo
mas viejo sin que nada lo indique.

POR QUE UN SUBESQUEMA POR PROYECCION. La validez depende de a que cliente va dirigido el archivo:
Copilot rechaza la fuente `git-subdir`, y Claude Code acepta `github` con `path` pero IGNORA el
`path` e instala el repositorio entero sin dar error. Son restricciones OPUESTAS sobre la misma
forma, asi que no hay un unico esquema valido para «un marketplace». La raiz del archivo de esquema
rechaza todo a proposito, para que apuntarle un validador por error falle en vez de pasar en vacio.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator

# El esquema vive en el repositorio del estandar, no dentro del paquete del indice: es el contrato
# publicado, y tener una copia aqui la dejaria derivar del original (G2).
NOMBRE_DEL_ESQUEMA = "marketplace.schema.json"
_CLAVE_DE_PROYECCIONES = "proyecciones"
_CLAVE_DE_DEFINICIONES = "$defs"


class EsquemaNoDisponibleError(FileNotFoundError):
    """No se encontro `marketplace.schema.json`. Es un error y no una degradacion: sin el esquema
    no se comprueba nada, y publicar sin comprobar es justo lo que esto viene a impedir."""


def _cargar(directorio_de_esquemas: Path) -> dict:
    ruta = directorio_de_esquemas / NOMBRE_DEL_ESQUEMA
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except OSError as fallo:
        raise EsquemaNoDisponibleError(f"no se pudo leer {ruta}: {fallo}") from fallo


def _validador_de(esquema: dict, proyeccion: str) -> Draft202012Validator:
    """El subesquema de una proyeccion, con las definiciones compartidas injertadas.

    Se injertan porque los `$ref` del subesquema apuntan a `#/$defs/...` -- relativos a la RAIZ del
    archivo --, y al validar contra el subesquema suelto esa raiz ya no es la misma.
    """
    subesquema = copy.deepcopy(esquema[_CLAVE_DE_PROYECCIONES][proyeccion])
    subesquema[_CLAVE_DE_DEFINICIONES] = esquema[_CLAVE_DE_DEFINICIONES]
    return Draft202012Validator(subesquema)


# Como se escribe la ruta de un defecto dentro del documento. UN PUNTO, igual que en el validador: era
# `/` aqui y `.` alli, o sea el mismo concepto con dos notaciones segun que paquete emitiera el
# mensaje. No es un defecto -- las dos se leen -- pero `metadata/id` en una anotacion de pull request
# se confunde con una ruta de archivo, que es justo lo que el campo de al lado ya contiene.
_SEPARADOR_DE_RUTA = "."
_RUTA_RAIZ = "(raiz)"


def incumplimientos(contenido: str, proyeccion: str,
                    directorio_de_esquemas: Path) -> list[str]:
    """Los defectos de una proyeccion, ya legibles. Lista vacia = conforme."""
    validador = _validador_de(_cargar(directorio_de_esquemas), proyeccion)
    documento = json.loads(contenido)
    return [
        f"{_SEPARADOR_DE_RUTA.join(str(t) for t in fallo.path) or _RUTA_RAIZ}: {fallo.message}"
        for fallo in sorted(validador.iter_errors(documento), key=lambda f: list(f.path))
    ]
