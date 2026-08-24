"""Pruebas del tipo `agent`, que el estandar declaraba y el gate no comprobaba.

El defecto de fondo era de cobertura, no de logica: `agent` estaba en el esquema y ninguna regla lo
tocaba, asi que un agente sin `description` pasaba en verde. Un tipo declarado y no comprobado promete
un control que no existe.

Aqui hubo tambien pruebas de `instructions`. Se retiraron con el tipo: no tiene canal de distribucion,
no esta en el blueprint del catalogo ni en el enum de `kind` del envelope, y no existe ni un artefacto de
ese tipo en los repositorios. Lo unico que sobrevive es la regresion de `test_reglas_aprobacion`, que fija
que un archivo con ese nombre NO exija firmante -- porque llego a exigirlo y bloqueaba pull requests por
un tipo que ya no se gobernaba --.
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


def test_el_name_distinto_del_archivo_es_aviso_y_no_error():
    # MEDIDO en el activo real de BCP: `atla.cnf-support.consultant.agent.md` declara
    # `name: atla.cnf-migrator.consultant` y DOS handoffs de otros agentes apuntan al NAME. Si el
    # archivo mandara, esas transferencias estarian rotas. La regla afirmaba «el cliente no lo
    # encontrara» y era falso: la especificacion usa el archivo solo cuando se OMITE el `name`.
    hallazgos = revisar_agente("agents/migrador.agent.md", "otro", _agente())
    assert _errores(hallazgos) == [], "no debe bloquear: es legal segun la especificacion"
    assert "no coincide con el archivo" in _mensajes(hallazgos)


def test_un_name_con_espacios_es_aviso_y_no_error():
    # MEDIDO: los 5 agentes de `.github-private` se llaman `DeployGo Onboarding` o
    # `CI/CD GitHub Actions Specialist`. El patron `^[a-z0-9]+([.-][a-z0-9]+)*$` los rechazaba a los
    # 5 -- una poblacion entera declarada no conforme por una preferencia nuestra, no por la especificacion.
    for nombre in ("DeployGo Onboarding", "CI/CD GitHub Actions Specialist"):
        hallazgos = revisar_agente("a.agent.md", nombre, _agente(name=nombre))
        assert _errores(hallazgos) == [], nombre
        assert "convencion" in _mensajes(hallazgos), nombre


def test_model_como_array_es_aviso_y_no_error():
    # MEDIDO dos veces, en direcciones opuestas. Los 5 agentes de `atla` declaran cuatro modelos en
    # array, y la regla lo trataba como ERROR. La especificacion de VS Code admite el array como lista
    # de PRIORIDAD, asi que como defecto de FORMA era falso; la objecion real es de gobierno.
    hallazgos = revisar_agente("a.agent.md", "a", {**_agente(name="a"), "_forma": {"model_es_array": True}})
    assert _errores(hallazgos) == []
    assert "model_allowlist" in _mensajes(hallazgos)


def test_handoffs_con_target_en_la_nube_avisa_de_que_se_ignoran():
    # La documentacion de GitHub dice que `handoffs` y `argument-hint` NO se soportan en el agente en
    # la nube y se IGNORAN por compatibilidad. Nada falla -- y por eso hace falta el aviso: la cadena
    # de agentes deja de delegar en silencio.
    hallazgos = revisar_agente("a.agent.md", "a", _agente(
        name="a", target="github-copilot", handoffs=[{"label": "x", "agent": "b"}]))
    assert _errores(hallazgos) == []
    assert "IGNORA" in _mensajes(hallazgos)


def test_capacidad_ejecutable_declarada_en_el_agente_avisa():
    # `mcp-servers` y `hooks` son campos legales del agente, y son una segunda via para introducir un
    # MCP o codigo automatico ESQUIVANDO el sitio donde vive su gobierno: el bloque del GOVERNANCE.json
    # y la firma de seguridad sobre `hooks/`.
    for campo, esperado in (("mcp-servers", "tools_digest"), ("hooks", "firma de seguridad")):
        hallazgos = revisar_agente("a.agent.md", "a", _agente(name="a", **{campo: {"x": 1}}))
        assert _errores(hallazgos) == [], campo
        assert esperado in _mensajes(hallazgos), campo


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
