"""Que el blueprint de Port y los esquemas del estandar digan LO MISMO.

POR QUE EXISTE. `port/blueprint-artefacto-agentico.json` es el contrato de Port -- lo que el
cliente ve y lo que Port acepta -- y no tenia ninguna prueba. Se le paso una revision y HABIA DERIVADO:
su enum `tipo` seguia admitiendo `instructions` despues de que el estandar dejara de gobernarla. O sea
que se podia publicar en Port la ficha de un tipo que el estandar ya no reconoce, y nada lo
habria dicho.

QUE SE COMPRUEBA, y por que asi. No se compara contra una lista escrita a mano: eso seria una TERCERA
copia de los tipos, con el mismo problema que esta prueba viene a resolver. Se comprueban RELACIONES
entre los dos archivos que ya existen:

  - todo lo que tiene envelope aparece en Port (nadie gobierna algo que Port ignora);
  - lo que Port tiene DE MAS son exactamente los dos tipos de configuracion, que se gobiernan
    desde el GOVERNANCE.json del plugin y por tanto no tienen `kind`;
  - los campos que estan en los dos archivos tienen los MISMOS valores admitidos.

El tercero es el que de verdad protege: si el blueprint admitiera un `status` que el envelope no,
Port aceptaria un estado que ningun artefacto puede declarar -- y al contrario, rechazaria uno
legitimo, que es peor porque bloquea la publicacion de algo conforme.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parent.parent.parent
_BLUEPRINT = _RAIZ / "port" / "blueprint-artefacto-agentico.json"
_ENVELOPE = _RAIZ / "schemas" / "envelope.schema.json"

# Los dos tipos que Port publica y que NO tienen envelope: son archivos de configuracion, uno
# por plugin, sin frontmatter donde declarar nada. Su gobierno vive en el `GOVERNANCE.json`, asi que
# el envelope no los cubre -- y Port si, porque son capacidades del plugin que alguien tiene
# que poder encontrar y auditar.
_TIPOS_DE_CONFIGURACION = frozenset({"mcp", "hooks"})

_CAMPO_TIPO_EN_PORT = "tipo"
_CAMPO_TIPO_EN_EL_ENVELOPE = "kind"


def _propiedades(ruta: Path, dentro_de_schema: bool) -> dict:
    documento = json.loads(ruta.read_text(encoding="utf-8"))
    raiz = documento["schema"] if dentro_de_schema else documento
    return raiz["properties"]


def _blueprint() -> dict:
    return _propiedades(_BLUEPRINT, dentro_de_schema=True)


def _envelope() -> dict:
    return _propiedades(_ENVELOPE, dentro_de_schema=False)


def test_todo_tipo_con_envelope_aparece_en_port():
    con_envelope = set(_envelope()[_CAMPO_TIPO_EN_EL_ENVELOPE]["enum"])
    en_port = set(_blueprint()[_CAMPO_TIPO_EN_PORT]["enum"])

    ausentes = con_envelope - en_port
    assert not ausentes, (
        f"tipos que el estandar gobierna y Port no admite: {sorted(ausentes)}. Un artefacto "
        f"con envelope que no puede tener ficha es indistinguible de uno que no existe")


def test_lo_que_port_admite_de_mas_son_los_tipos_de_configuracion():
    # MEDIDO: aqui sobraba `instructions`, que dejo de ser un tipo gobernado. Esta prueba lo habria
    # dicho el mismo dia.
    con_envelope = set(_envelope()[_CAMPO_TIPO_EN_EL_ENVELOPE]["enum"])
    en_port = set(_blueprint()[_CAMPO_TIPO_EN_PORT]["enum"])

    de_mas = en_port - con_envelope
    assert de_mas == set(_TIPOS_DE_CONFIGURACION), (
        f"Port admite {sorted(de_mas)} sin envelope; se esperaba exactamente "
        f"{sorted(_TIPOS_DE_CONFIGURACION)}. Si se añade o se retira un tipo, hay que tocar el "
        f"blueprint Y este valor -- que es el unico sitio donde se dice que Port publica dos "
        f"tipos sin frontmatter")


@pytest.mark.parametrize("campo", ["status", "data_classification"])
def test_los_campos_compartidos_admiten_los_mismos_valores(campo):
    """En bucle con el campo en el mensaje: cuando falla, dice cual divergio (T5)."""
    de_port = _blueprint()[campo].get("enum")
    del_envelope = _envelope()[campo].get("enum")

    assert de_port == del_envelope, (
        f"`{campo}` divergio: Port admite {de_port} y el envelope {del_envelope}. "
        f"Un valor que solo admite uno de los dos bloquea la publicacion de algo conforme, o deja "
        f"pasar a Port algo que ningun artefacto puede declarar")
