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
from indice_agentico.dominio.reglas_indice import SUBRUTA_DEL_REPOSITORIO

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


_SUFIJO_DE_CLONADO = ".git"
_HOST = "https://github.com"


def _fuente(entrada: Entrada, proyeccion: Proyeccion) -> dict:
    """El puntero de instalacion, en la forma que ESTE cliente honra.

    Un plugin que ocupa su repositorio se direcciona igual en los dos. Uno ANIDADO no: Copilot lo
    entiende como `github` mas `path`, y Claude Code IGNORA ese `path` -- instala el repositorio
    entero sin dar error -- asi que ahi hay que usar `git-subdir`. Es la unica diferencia entre las
    dos proyecciones, y esta medida contra los dos clientes.
    """
    comun = {"ref": entrada.etiqueta, "sha": entrada.sha}
    if entrada.subruta == SUBRUTA_DEL_REPOSITORIO:
        return {"source": "github", "repo": entrada.repositorio, **comun}
    if proyeccion is Proyeccion.CLAUDE_CODE:
        return {"source": "git-subdir",
                "url": f"{_HOST}/{entrada.repositorio}{_SUFIJO_DE_CLONADO}",
                "path": entrada.subruta, **comun}
    return {"source": "github", "repo": entrada.repositorio, "path": entrada.subruta, **comun}


def _como_plugin(entrada: Entrada, proyeccion: Proyeccion) -> dict:
    return {
        "name": entrada.name,
        "description": entrada.description,
        "version": entrada.version,
        "source": _fuente(entrada, proyeccion),
    }


def render(indice: Indice, nombre: str, propietario: dict[str, str], version: str,
           proyeccion: Proyeccion) -> str:
    """El contenido del indice para UN cliente.

    La proyeccion es obligatoria y no tiene valor por defecto a proposito: un default elegiria un
    cliente en silencio, y quien olvidara pasarla generaria el marketplace del otro sin enterarse.

    Ordenado por `name` para que el diff del commit muestre solo lo que cambio de verdad.
    """
    marketplace = {
        "name": nombre,
        "owner": propietario,
        "metadata": {"description": _AVISO, "version": version},
        "plugins": [_como_plugin(e, proyeccion)
                    for e in sorted(indice.entradas, key=lambda e: e.name)],
    }
    return json.dumps(marketplace, indent=_SANGRIA, ensure_ascii=False) + "\n"
