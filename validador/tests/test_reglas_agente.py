"""Pruebas del tipo `agent`, que el estandar declaraba y el gate no comprobaba.

El defecto de fondo era de cobertura, no de logica: `agent` estaba en el esquema y ninguna regla lo
tocaba, asi que un agente sin `description` pasaba en verde. Un tipo declarado y no comprobado promete
un control que no existe.

Las de `instructions` estaban aqui y se fueron a `test_reglas_instructions`: dejaron de ser un tipo
gobernado y lo que se comprueba de ellas es otra cosa -- higiene, todo aviso --.
"""
from __future__ import annotations

from validador_agentico.dominio.especificacion import MAX_CARACTERES_DESCRIPCION
from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_agente import revisar_agente


def _errores(hallazgos):
    return [h for h in hallazgos if h.severidad is Severidad.ERROR]


def _mensajes(hallazgos) -> str:
    return " | ".join(h.mensaje for h in hallazgos)


# ── agent ───────────────────────────────────────────────────────────────────────────────────
def _agente(**cambios) -> dict:
    base = {"name": "migrador", "description": "Migra un servicio y se usa cuando toca migrar."}
    return {**base, **cambios}


def test_un_agente_conforme_no_produce_hallazgos():
    assert revisar_agente("agents/migrador.agent.md", "migrador", _agente()) == []


def test_el_name_del_agente_debe_coincidir_con_el_archivo():
    """Si no coinciden el cliente no lo encuentra, exactamente como pasa con un skill y su
    directorio."""
    errores = _errores(revisar_agente("agents/migrador.agent.md", "otro", _agente()))
    assert "no coincide con el archivo" in _mensajes(errores)


def test_un_agente_sin_description_es_error():
    # Es lo que decide si el modelo le delega. Sin ella el agente existe y no se usa nunca.
    errores = _errores(revisar_agente("a.agent.md", "a", _agente(name="a", description="")))
    assert "description" in _mensajes(errores)


def test_un_agente_sin_name_es_error():
    errores = _errores(revisar_agente("a.agent.md", "a", _agente(name="")))
    assert "`name`" in _mensajes(errores)


def test_una_description_demasiado_larga_es_error():
    larga = "x" * (MAX_CARACTERES_DESCRIPCION + 1)
    assert _errores(revisar_agente("a.agent.md", "a", _agente(name="a", description=larga)))
