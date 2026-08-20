"""Pruebas de los dos tipos que el estandar declaraba y el gate no comprobaba.

El defecto de fondo era de cobertura, no de logica: `agent` e `instructions` estaban en el esquema y
ninguna regla los tocaba, asi que un agente sin `description` pasaba en verde. Un tipo declarado y no
comprobado promete un control que no existe.
"""
from __future__ import annotations

from validador_agentico.dominio.especificacion import MAX_CARACTERES_DESCRIPCION
from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_agente_instructions import (
    LIMITE_LINEAS_INSTRUCTIONS_SIN_TECHO,
    revisar_agente,
    revisar_instructions,
)


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


# ── instructions ────────────────────────────────────────────────────────────────────────────
def test_unas_instructions_acotadas_y_con_techo_no_producen_hallazgos():
    conforme = {"applies_to": "src/api/**/*.py", "token_budget": 800}
    assert revisar_instructions("api.instructions.md", conforme, 120) == []


def test_sin_applies_to_es_error():
    """El defecto que cubre: unas instructions sin ambito aplican a todo, y estan SIEMPRE activas, asi
    que su coste se paga en cada peticion del repositorio."""
    errores = _errores(revisar_instructions("x.instructions.md", {"token_budget": 100}, 10))
    assert "applies_to" in _mensajes(errores)


def test_un_applies_to_que_aplica_a_todo_es_error():
    for glob in ("**", "**/*", "*", "/"):
        errores = _errores(revisar_instructions("x.instructions.md",
                                                {"applies_to": glob, "token_budget": 100}, 10))
        assert errores, glob


def test_se_admite_applyTo_ademas_de_applies_to():
    # Copilot escribe `applyTo`; el esquema del estandar usa `applies_to`. Rechazar el primero
    # obligaria a reescribir artefactos que ya funcionan.
    assert revisar_instructions("x.instructions.md",
                                {"applyTo": "src/**/*.ts", "token_budget": 50}, 10) == []


def test_muchas_lineas_sin_techo_declarado_es_AVISO():
    """Aviso y no error: el techo es practica del estandar, no requisito del cliente. Pero sin
    declararlo nadie nota cuando unas instructions crecen hasta doler."""
    hallazgos = revisar_instructions("x.instructions.md", {"applies_to": "src/**"},
                                     LIMITE_LINEAS_INSTRUCTIONS_SIN_TECHO + 1)
    assert hallazgos
    assert all(h.severidad is Severidad.AVISO for h in hallazgos)


def test_pocas_lineas_sin_techo_no_dice_nada():
    assert revisar_instructions("x.instructions.md", {"applies_to": "src/**"}, 10) == []


def test_un_token_budget_que_no_es_entero_positivo_es_error():
    for malo in ("mucho", 0, -5, 1.5):
        errores = _errores(revisar_instructions("x.instructions.md",
                                                {"applies_to": "src/**", "token_budget": malo}, 10))
        assert errores, malo
