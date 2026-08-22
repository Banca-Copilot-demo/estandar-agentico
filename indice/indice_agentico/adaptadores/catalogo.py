"""Adaptador de salida: renderiza el indice como `marketplace.json`.

La forma del archivo NO es nuestra: es la que consumen los clientes. `source` se emite como OBJETO
-- no como la cadena abreviada -- porque la forma abreviada no admite `sha`, y sin `sha` el puntero
seria movil: la etiqueta se puede reescribir si el repositorio no tiene releases inmutables.

DOS PROYECCIONES DEL MISMO INDICE, NO DOS INDICES. Un solo barrido produce los dos archivos, asi
que no pueden divergir. Se diferencian SOLO en como se direcciona un plugin, porque los dos
clientes NO aceptan lo mismo -- y esta MEDIDO: Copilot rechaza la fuente `git-subdir`, y Claude
Code acepta `github` con `path` pero IGNORA el `path` e instala el repositorio entero, sin dar
error. Mientras el indice solo liste plugins en la raiz de su repositorio, las dos proyecciones
salen identicas; la distincion existe para el dia en que liste uno anidado, y para que ese dia no
haya que acordarse de nada.
"""
from __future__ import annotations

import json
from enum import Enum

from indice_agentico.dominio.candidato import Entrada, Indice

_SANGRIA = 2
_AVISO = "GENERADO por el workflow del indice: no editar a mano."


class Proyeccion(Enum):
    """Para que cliente se renderiza.

    Cada miembro lleva las DOS cosas que lo identifican -- donde lee ese cliente su indice y contra
    que subesquema se valida -- porque mantenerlas en un mapeo aparte permitiria anadir una
    proyeccion y olvidar su validacion, y entonces se publicaria sin comprobar.
    """

    CLAUDE_CODE = ("claudeCode", ".claude-plugin/marketplace.json")
    COPILOT = ("copilot", ".github/plugin/marketplace.json")

    @property
    def subesquema(self) -> str:
        """Clave dentro de `proyecciones` en `marketplace.schema.json`."""
        return self.value[0]

    @property
    def ruta(self) -> str:
        """Ruta del archivo, relativa a la raiz del repositorio del indice."""
        return self.value[1]


def _fuente(entrada: Entrada) -> dict:
    """El puntero de instalacion. Hoy solo hay plugins en la raiz de su repositorio: los anidados
    los RECHAZA `reglas_indice` porque falta su subruta, asi que aqui no puede llegar ninguno."""
    return {
        "source": "github",
        "repo": entrada.repositorio,
        "ref": entrada.etiqueta,
        "sha": entrada.sha,
    }


def _como_plugin(entrada: Entrada) -> dict:
    return {
        "name": entrada.name,
        "description": entrada.description,
        "version": entrada.version,
        "source": _fuente(entrada),
    }


def render(indice: Indice, nombre: str, propietario: dict[str, str], version: str) -> str:
    """El contenido del indice, IGUAL para las dos proyecciones.

    No lleva parametro de proyeccion a proposito: hoy no habria nada que hacer con el, porque los
    plugins anidados -- lo unico que se direcciona distinto en cada cliente -- se rechazan antes de
    llegar aqui. Un parametro que no cambia nada insinuaria una diferencia inexistente. Cuando el
    indice sepa resolver la subruta, la diferencia entra por `_fuente` y ahi si hara falta.

    Ordenado por `name` para que el diff del commit muestre solo lo que cambio de verdad.
    """
    catalogo = {
        "name": nombre,
        "owner": propietario,
        "metadata": {"description": _AVISO, "version": version},
        "plugins": [_como_plugin(e) for e in sorted(indice.entradas, key=lambda e: e.name)],
    }
    return json.dumps(catalogo, indent=_SANGRIA, ensure_ascii=False) + "\n"
