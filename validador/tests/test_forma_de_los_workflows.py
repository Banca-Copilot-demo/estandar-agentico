"""Los workflows y composite actions del estandar son YAML valido.

EL DEFECTO QUE FIJA, medido en esta sesion: al anadir un paso a `publicar/action.yml` se metio codigo
Python MULTILINEA dentro de un bloque `run:`. Las lineas quedaron a columna cero, que es donde el
escalar de bloque termina, y el archivo dejo de ser YAML valido.

POR QUE HACIA FALTA UNA PRUEBA Y NO BASTABA CON MIRARLO. El fallo no lo detecta nada del repositorio:
ni el gate, ni las pruebas, ni el editor. Lo habria descubierto GitHub al intentar ejecutar el
workflow -- es decir, al publicar --, y la publicacion es justo el momento en el que un fallo cuesta
mas: la etiqueta ya existe y, con releases inmutables, no se puede rehacer.

Es ademas una clase de defecto que se repite: `run:` acepta cualquier texto, asi que invita a pegar
scripts dentro. Por eso la comprobacion es sobre TODOS los archivos y no sobre el que se rompio.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

_RAIZ = Path(__file__).resolve().parents[2]
_WORKFLOWS = sorted((_RAIZ / ".github" / "workflows").glob("*.yml"))
_ACTIONS = sorted((_RAIZ / ".github" / "actions").glob("*/action.yml"))
_TODOS = _WORKFLOWS + _ACTIONS


def _identificador(ruta: Path) -> str:
    return f"{ruta.parent.name}/{ruta.name}"


def test_hay_workflows_y_actions_que_comprobar():
    """Si los globs dejaran de encontrar archivos -- por una reorganizacion de carpetas -- las
    pruebas de abajo pasarian sin comprobar nada, que es peor que fallar."""
    assert _WORKFLOWS, "no se encontro ningun workflow: el glob quedo obsoleto"
    assert _ACTIONS, "no se encontro ninguna composite action: el glob quedo obsoleto"


@pytest.mark.parametrize("ruta", _TODOS, ids=[_identificador(r) for r in _TODOS])
def test_es_yaml_valido(ruta):
    try:
        documento = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as fallo:
        pytest.fail(f"{_identificador(ruta)} no es YAML valido: {fallo}")
    assert isinstance(documento, dict), f"{_identificador(ruta)} no define un mapa en la raiz"


@pytest.mark.parametrize("ruta", _TODOS, ids=[_identificador(r) for r in _TODOS])
def test_declara_lo_minimo_para_ejecutarse(ruta):
    """Un YAML valido puede seguir sin ser un workflow. Un archivo sin `jobs` ni `runs` es sintaxis
    correcta que GitHub ignora, y eso vuelve a fallar en silencio."""
    documento = yaml.safe_load(ruta.read_text(encoding="utf-8"))

    assert "jobs" in documento or "runs" in documento, \
        f"{_identificador(ruta)} no declara `jobs` ni `runs`: no lo ejecutaria nadie"
