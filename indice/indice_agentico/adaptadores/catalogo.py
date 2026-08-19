"""Adaptador de salida: renderiza el indice como `marketplace.json`.

La forma del archivo NO es nuestra: es la que consumen los clientes. `source` se emite como OBJETO
-- no como la cadena abreviada -- porque la forma abreviada no admite `sha`, y sin `sha` el puntero
seria movil: la etiqueta se puede reescribir si el repositorio no tiene releases inmutables.
"""
from __future__ import annotations

import json

from indice_agentico.dominio.candidato import Entrada, Indice

_SANGRIA = 2
_AVISO = "GENERADO por el workflow del indice: no editar a mano."


def _como_plugin(entrada: Entrada) -> dict:
    return {
        "name": entrada.name,
        "description": entrada.description,
        "version": entrada.version,
        "source": {
            "source": "github",
            "repo": entrada.repositorio,
            "ref": entrada.etiqueta,
            "sha": entrada.sha,
        },
    }


def render(indice: Indice, nombre: str, propietario: dict[str, str], version: str) -> str:
    """Ordenado por `name` para que el diff del commit muestre solo lo que cambio de verdad."""
    catalogo = {
        "name": nombre,
        "owner": propietario,
        "metadata": {"description": _AVISO, "version": version},
        "plugins": [_como_plugin(e) for e in sorted(indice.entradas, key=lambda e: e.name)],
    }
    return json.dumps(catalogo, indent=_SANGRIA, ensure_ascii=False) + "\n"
