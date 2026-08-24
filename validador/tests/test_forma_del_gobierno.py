"""El `GOVERNANCE.json` se valida COMPLETO contra `plugin-governance.schema.json`.

EL DEFECTO QUE CIERRA, medido auditando el repositorio del propio estandar: el esquema del gobierno se
publica como parte del entregable y NINGUN codigo lo ejecutaba. La consecuencia estaba en el arbol:
`plugins/asistente-autoria/GOVERNANCE.json` declaraba `artifacts.instructions`, que su propio esquema
PROHIBE -- `additionalProperties: false`, y la clave no esta entre las admitidas --, y el gate daba el
repositorio por CONFORME. El esquema decia una cosa, el repositorio otra, y nada lo notaba.

Es el MISMO defecto que la capa de esquemas vino a cerrar para los artefactos, dejado a medias: se
cablearon los tres tipos con frontmatter y se olvido el unico documento que gobierna a todos.

Y CABLEAR ESTE ESQUEMA EJECUTA TAMBIEN EL DEL `mcp`, que es la otra mitad del hallazgo:
`plugin-governance.schema.json` lo alcanza con tres `$ref`. Antes ninguna llamada llegaba a
`mcp.schema.json` -- no porque estuviera de mas, sino porque su unico camino pasaba por un esquema que
nadie ejecutaba --.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from validador_agentico.aplicacion.validar_repositorio import validar
from validador_agentico.dominio.hallazgo import Severidad

_ESQUEMAS = Path(__file__).resolve().parents[2] / "schemas"

_GOBIERNO_CONFORME = {
    "id": "demo.sdlc.x",
    "domain": "sdlc",
    "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
    "status": "draft",
    "data_classification": "internal",
    "standard_version": "8.0.0",
    "artifacts": {"skills": 0, "agents": 0, "prompts": 0},
}


def _repositorio(raiz: Path, gobierno: dict) -> Path:
    manifiesto = raiz / ".claude-plugin"
    manifiesto.mkdir(parents=True)
    (manifiesto / "plugin.json").write_text(json.dumps(
        {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
         "name": "demo.sdlc.x", "version": "1.0.0",
         "description": "Plugin del fixture de forma del gobierno."}), encoding="utf-8")
    (raiz / "GOVERNANCE.json").write_text(json.dumps(gobierno), encoding="utf-8")
    return raiz


def _errores(raiz: Path) -> str:
    resultado = validar(raiz, directorio_de_esquemas=_ESQUEMAS)
    return " | ".join(h.mensaje for h in resultado.hallazgos
                      if h.severidad is Severidad.ERROR)


def test_un_gobierno_conforme_no_produce_errores_de_forma(tmp_path):
    assert "forma invalida" not in _errores(_repositorio(tmp_path, _GOBIERNO_CONFORME))


def test_una_clave_INVENTADA_en_artifacts_es_error(tmp_path):
    # El caso REAL que estaba en el arbol: `instructions` se retiro de los tipos del estandar y quedo
    # declarada en un gobierno, donde el esquema no la admite.
    gobierno = {**_GOBIERNO_CONFORME,
                "artifacts": {**_GOBIERNO_CONFORME["artifacts"], "instructions": 0}}

    mensajes = _errores(_repositorio(tmp_path, gobierno))

    assert "instructions" in mensajes and "forma invalida" in mensajes, mensajes


@pytest.mark.parametrize("campo", sorted(_GOBIERNO_CONFORME))
def test_falta_cada_campo_obligatorio_del_gobierno_se_detecta(tmp_path, campo):
    """En bucle con el campo en el mensaje (T5): una prueba con siete aserciones falla en la primera y
    esconde las otras seis."""
    incompleto = {c: v for c, v in _GOBIERNO_CONFORME.items() if c != campo}

    mensajes = _errores(_repositorio(tmp_path / campo, incompleto))

    assert mensajes, f"no se detecto la falta de `{campo}`"


def test_un_enum_con_valor_INVENTADO_es_error(tmp_path):
    # Lo que un esquema comprueba y una regla escrita a mano suele olvidar: que el valor este entre los
    # admitidos, no solo que el campo exista y sea un string.
    gobierno = {**_GOBIERNO_CONFORME, "data_classification": "ultrasecreto"}

    assert "forma invalida" in _errores(_repositorio(tmp_path, gobierno))


def test_el_esquema_del_mcp_se_ejecuta_a_traves_del_gobierno(tmp_path):
    """La otra mitad del hallazgo: `mcp.schema.json` no es un esquema de documento suelto, es la caja
    de piezas que el gobierno referencia con `$ref`. Si el gobierno no se validara, nada llegaria a
    esas piezas -- que es justo lo que pasaba --. Esta prueba lo fija metiendo un defecto que SOLO
    puede detectar el esquema del mcp."""
    gobierno = {**_GOBIERNO_CONFORME,
                "mcp": {"approval": {"approved_by": "squad-seguridad",
                                     "date": "no-es-una-fecha",
                                     "review_by": "2027-02-23",
                                     "security_review": True}}}

    mensajes = _errores(_repositorio(tmp_path, gobierno))

    assert "forma invalida" in mensajes, mensajes
