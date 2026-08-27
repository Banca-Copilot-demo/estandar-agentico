"""Pruebas de la validacion contra los ESQUEMAS, que hasta ahora no se ejecutaban.

EL DEFECTO DE FONDO QUE ESTO CIERRA: los esquemas eran documentos que ningun codigo tocaba, asi que
declaraban una cosa y las reglas del gate otra. Dos fuentes de verdad sobre el mismo contrato. Al
ejecutarlos por primera vez contra los artefactos REALES de la demo aparecieron tres divergencias, y
cada una tiene su prueba de regresion aqui.

Se validan contra los esquemas de verdad -- los del repositorio -- y no contra copias: una prueba con
su propio esquema comprobaria que el codigo funciona, no que el contrato publicado sea correcto.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from validador_agentico.adaptadores import esquema
from validador_agentico.dominio.ensamblado import ensamblar

# El directorio real del repositorio: `validador/tests` -> `estandar-agentico/schemas`.
ESQUEMAS = Path(__file__).resolve().parents[2] / "schemas"

_ENVELOPE_VALIDO = {
    "id": "demo.x.algo",
    "owner_team": "squad-x",
    "owner_contact": "squad-x@ejemplo.dev",
    "data_classification": "internal",
    "status": "draft",
    "version": "1.0.0",
    "standard_version": "7.0.0",
}


def _skill(**cambios) -> dict:
    frontmatter = {"name": "algo", "description": "Hace algo concreto.",
                   "metadata": dict(_ENVELOPE_VALIDO), **cambios}
    return ensamblar(frontmatter, None, "skill")


def _incumplimientos(objeto, nombre="skill.schema.json"):
    return esquema.incumplimientos(objeto, nombre, ESQUEMAS)


# ── el camino normal ────────────────────────────────────────────────────────────────────────
def test_un_skill_conforme_no_incumple_nada():
    assert _incumplimientos(_skill()) == []


def test_las_referencias_al_envelope_RESUELVEN():
    """Si no resolvieran, el esquema del skill no aportaria ninguno de los campos del envelope y
    `unevaluatedProperties` los daria todos por inesperados. Una referencia colgante no falla al
    cargar: falla al validar."""
    faltan = _incumplimientos(ensamblar({"name": "algo", "description": "d"}, None, "skill"))
    assert any("id" in m for m in faltan), (
        "sin el envelope no se exigiria `id`, asi que la referencia no esta resolviendo")


# ── lo que el esquema SI atrapa y una regla en Python tendria que reimplementar ──────────────
def test_un_valor_fuera_del_enum_se_detecta():
    fallos = _incumplimientos(_skill(metadata={**_ENVELOPE_VALIDO,
                                               "data_classification": "publico-total"}))
    assert any("data_classification" in m for m in fallos)


def test_una_version_que_no_es_semver_se_detecta():
    fallos = _incumplimientos(_skill(metadata={**_ENVELOPE_VALIDO, "version": "no-es-semver"}))
    assert any("version" in m for m in fallos)


def test_una_clave_inventada_se_detecta():
    """`unevaluatedProperties: false` es lo que impide que un campo con un typo parezca gobernar. Un
    esquema permisivo habria aceptado sin protestar las variantes que conviven en artefactos reales --
    `user-invocable` frente a `user-invokable` -- y no habria unificado nada."""
    fallos = _incumplimientos(_skill(**{"clave-inventada": "si"}))
    assert any("clave-inventada" in m for m in fallos)


def test_el_comprobador_de_format_esta_activo():
    """Sin activarlo, `format: date` NO valida nada y una fecha inventada pasaria en verde -- y de una
    de esas fechas depende que la aprobacion de un `mcp` caduque --."""
    gobierno = {
        "id": "demo.x", "domain": "x",
        "owner": {"team": "t", "contact": "t@d.dev"},
        "status": "draft", "data_classification": "internal", "standard_version": "1.0.0",
        "artifacts": {"skills": 1},
        "hooks": {"approval": {"approved_by": "a", "date": "ayer por la tarde",
                               "review_by": "2026-12-01", "security_review": True}},
    }
    fallos = _incumplimientos(gobierno, "plugin-governance.schema.json")
    assert any("date" in m for m in fallos), "el comprobador de `format` no esta activo"


# ── las tres divergencias que aparecieron al ejecutarlos, como regresion ─────────────────────
def test_model_es_una_CADENA_y_no_un_array():
    """DIVERGENCIA MEDIDA: el esquema del prompt pedia `model` como array y la regla del gate trata el
    array como ERROR -- «declara un modelo y deja la lista en el `model_allowlist` del plugin» --. El
    esquema pedia justo lo que la regla prohibe."""
    prompt = ensamblar({"name": "algo", "description": "d", "model": "claude-sonnet-4-6",
                        "metadata": dict(_ENVELOPE_VALIDO)}, None, "prompt")
    assert _incumplimientos(prompt, "prompt.schema.json") == []


def test_produces_NO_es_obligatorio_para_conformant():
    """DIVERGENCIA MEDIDA: era obligatorio y declaraba NO CONFORME al unico prompt real de la demo. Un
    requisito que nadie cumple es un gate apagado; pasa a ser requisito de `certified`."""
    prompt = ensamblar({"name": "algo", "description": "d",
                        "metadata": dict(_ENVELOPE_VALIDO)}, None, "prompt")
    assert not any("produces" in m for m in _incumplimientos(prompt, "prompt.schema.json"))


def test_license_es_un_campo_valido_del_skill():
    """DIVERGENCIA MEDIDA: `license` es uno de los SEIS campos que la especificacion Agent Skills
    admite, y el esquema lo rechazaba como propiedad no evaluada en los cinco skills reales."""
    assert _incumplimientos(_skill(license="Proprietary")) == []


# ── el ruido derivado, que enganaba ─────────────────────────────────────────────────────────
def test_cuando_el_envelope_falla_NO_se_listan_sus_campos_validos():
    """MEDIDO: con dos defectos del envelope, el mensaje listaba DIEZ campos perfectamente validos
    como «inesperados» -- y habria mandado a alguien a borrarlos --. En 2020-12, si un subesquema
    falla se descartan sus anotaciones, asi que sus campos parecen no evaluados. Es un fallo derivado:
    se arregla arreglando los otros."""
    fallos = _incumplimientos(_skill(metadata={**_ENVELOPE_VALIDO, "version": "mal"}))
    assert fallos
    assert not any("Unevaluated" in m for m in fallos)


def test_sin_otros_fallos_el_no_evaluadas_SI_se_reporta():
    # Lo que no debe pasar: que suprimirlo lo esconda cuando es el unico defecto.
    fallos = _incumplimientos(_skill(**{"clave-inventada": "si"}))
    assert any("Unevaluated" in m for m in fallos)


# ── el estandar no puede vetar lo que la plataforma ejecuta ─────────────────────────────────
# Los agentes cierran con `unevaluatedProperties: false`, asi que TODO campo que el esquema no
# declare es un ERROR, no una clave ignorada. Eso convierte cada olvido del esquema en un veto a un
# artefacto legal, que es el fallo mas grave que puede tener un gate de conformidad: no mide el
# estandar, impone el catalogo de campos que a alguien se le ocurrio escribir.

# Los campos que la documentacion oficial de subagentes admite en el frontmatter de un `.agent.md` y
# que el esquema NO declaraba. MEDIDO ejecutando el esquema publicado contra un agente valido: cada
# uno daba «Unevaluated properties are not allowed».
_CAMPOS_OFICIALES_DEL_SUBAGENTE = {
    "skills": ["api-conventions"],
    "disallowedTools": ["Bash"],
    "permissionMode": "plan",
    "maxTurns": 5,
    "memory": "project",
    "background": True,
    "effort": "high",
    "isolation": "worktree",
    "color": "red",
    "initialPrompt": "Empieza por leer el diff.",
    "mcpServers": {"catalogo": {"command": "uvx"}},
}


def _agente(**cambios) -> dict:
    frontmatter = {"name": "code-reviewer", "description": "Revisa el codigo del PR.",
                   "metadata": dict(_ENVELOPE_VALIDO), **cambios}
    return ensamblar(frontmatter, None, "agent")


def test_un_agente_conforme_no_incumple_nada():
    assert _incumplimientos(_agente(), "agent.schema.json") == []


def test_ningun_campo_oficial_del_subagente_se_rechaza_como_inesperado():
    """REGRESION MEDIDA contra el esquema publicado: `skills` -- que la documentacion oficial de
    subagentes muestra en su primer ejemplo de frontmatter -- se rechazaba con «Unevaluated
    properties are not allowed ('skills' was unexpected)», y con el otros diez campos documentados.
    El agente era VALIDO para el cliente y nuestro gate lo declaraba no conforme.

    Se recorren en bucle con el campo en el mensaje (T5) para que el fallo diga CUAL falta y no solo
    que algo falla: cada campo es un veto independiente."""
    for campo, valor in _CAMPOS_OFICIALES_DEL_SUBAGENTE.items():
        fallos = _incumplimientos(_agente(**{campo: valor}), "agent.schema.json")
        assert fallos == [], f"el esquema rechaza `{campo}`, que la plataforma admite: {fallos}"


def test_mcpServers_en_camelCase_es_la_grafia_QUE_LEE_claude_code():
    """El esquema solo declaraba `mcp-servers` (la grafia de Copilot). Consecuencia doble: un agente
    de Claude Code que acotara un MCP se rechazaba, y el aviso de gobierno que ese campo describe
    -- un MCP fuera del bloque `mcp` del GOVERNANCE.json, sin aprobacion ni `tools_digest` -- era
    inalcanzable para el unico cliente que usa camelCase. Las DOS grafias son conformes porque son
    dos clientes, no dos nombres del mismo campo."""
    for grafia in ("mcp-servers", "mcpServers"):
        objeto = _agente(**{grafia: {"catalogo": {"command": "uvx"}}})
        assert _incumplimientos(objeto, "agent.schema.json") == [], grafia


def test_tools_admite_LAS_DOS_formas_que_los_clientes_aceptan():
    """La documentacion oficial escribe `tools: Read, Glob, Grep` -- una CADENA separada por comas --
    y el agente real de BCP escribe un ARRAY. El esquema pedia solo array, asi que un agente copiado
    literalmente de la documentacion del cliente se rechazaba por «is not of type 'array'»."""
    for forma in ("Read, Glob, Grep", ["execute", "read", "search"]):
        assert _incumplimientos(_agente(tools=forma), "agent.schema.json") == [], forma


def test_una_clave_inventada_en_un_agente_SIGUE_siendo_error():
    """El arreglo anterior no debe convertirse en «el esquema del agente ya no comprueba nada»: lo que
    se abre es el conjunto de campos OFICIALES, no la puerta a cualquier clave."""
    fallos = _incumplimientos(_agente(**{"clave-inventada": "si"}), "agent.schema.json")
    assert any("Unevaluated" in m for m in fallos)


# ── sin esquemas es error, no silencio ──────────────────────────────────────────────────────
def test_un_directorio_sin_esquemas_es_ERROR_y_no_silencio(tmp_path):
    """Un gate que no puede comprobar y calla es indistinguible de uno que comprobo y aprobo."""
    with pytest.raises(esquema.EsquemasNoDisponiblesError):
        esquema.incumplimientos(_skill(), "skill.schema.json", tmp_path)


def test_un_esquema_sin_id_es_ERROR(tmp_path):
    """Sin `$id` las referencias relativas de los demas no resuelven contra el, y eso falla al VALIDAR
    -- no al cargar --, asi que pasaria desapercibido."""
    (tmp_path / "roto.schema.json").write_text('{"type": "object"}', encoding="utf-8")
    with pytest.raises(esquema.EsquemasNoDisponiblesError):
        esquema.cargar(tmp_path)
