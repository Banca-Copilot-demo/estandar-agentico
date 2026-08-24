"""Pruebas de las reglas de plugin, hooks e higiene. Puras: sin disco.

La prueba mas importante de este archivo es `test_sin_plugin_es_solo_aviso`: fija por escrito que
el plugin es OPCIONAL, que fue una regla que se corrigio tras verificar que ni `mcp` ni `hooks` lo
exigen —cada uno tiene su propio control—.
"""
from __future__ import annotations

import pytest

from validador_agentico.dominio.especificacion import (
    EVENTOS_HOOK_SENSIBLES,
    RUTA_MANIFIESTO_UNIFICADA,
    TECHO_TIMEOUT_HOOK_S,
)
from validador_agentico.dominio.hallazgo import Inventario, Severidad
from validador_agentico.dominio.reglas_higiene import revisar_higiene
from validador_agentico.dominio.reglas_hooks import revisar_hooks
from validador_agentico.dominio.reglas_plugin import (
    revisar_ausencia_de_plugin,
    revisar_gobierno,
    revisar_inventario,
    revisar_manifiesto,
)

MANIFIESTO_CONFORME = {
    "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
    "name": "demo.sdlc.migracion-cnf",
    "version": "1.0.0",
}


def _mensajes(hallazgos) -> str:
    return " | ".join(h.mensaje for h in hallazgos)


def _errores(hallazgos):
    return [h for h in hallazgos if h.severidad is Severidad.ERROR]


# ── plugin ─────────────────────────────────────────────────────────────────────────────────
def test_manifiesto_conforme_en_la_ruta_unificada_no_produce_hallazgos():
    assert revisar_manifiesto(RUTA_MANIFIESTO_UNIFICADA, MANIFIESTO_CONFORME) == []


def test_manifiesto_en_otra_ruta_avisa_de_que_claude_no_lo_reconoce():
    hallazgos = revisar_manifiesto("plugin.json", MANIFIESTO_CONFORME)
    assert hallazgos and hallazgos[0].severidad is Severidad.AVISO
    assert "Claude Code" in hallazgos[0].mensaje


def test_campo_de_primer_nivel_no_permitido_es_error():
    # La especificacion permite exactamente diez campos; lo del estandar va en `extensions`.
    errores = _errores(revisar_manifiesto(RUTA_MANIFIESTO_UNIFICADA,
                                          {**MANIFIESTO_CONFORME, "governance": "x.json"}))
    assert "extensions" in _mensajes(errores)


def test_sin_plugin_es_solo_aviso():
    """El plugin es una decision de EMPAQUETADO, no de riesgo: ningun tipo lo exige."""
    hallazgos = revisar_ausencia_de_plugin()
    assert hallazgos and all(h.severidad is Severidad.AVISO for h in hallazgos)


def test_id_del_gobierno_debe_coincidir_con_el_name_del_plugin():
    errores = _errores(revisar_gobierno({"id": "otro", "owner": {"team": "t"}},
                                        MANIFIESTO_CONFORME))
    assert "no coincide" in _mensajes(errores)


def test_dueno_sin_equipo_es_error():
    errores = _errores(revisar_gobierno({"owner": {}}, None))
    assert "RESOLUBLE" in _mensajes(errores)


def test_inventario_desalineado_es_error():
    errores = _errores(revisar_inventario({"skills": 1}, Inventario(skills=2)))
    assert "declara 1" in _mensajes(errores)


def test_inventario_alineado_no_produce_hallazgos():
    declarado = {"skills": 2, "agents": 1, "prompts": 0}
    assert revisar_inventario(declarado, Inventario(skills=2, agentes=1)) == []


# ── hooks ──────────────────────────────────────────────────────────────────────────────────
def _hooks(evento: str, **entrada) -> dict:
    return {"version": 1, "hooks": {evento: [{"type": "command", "bash": "s.sh", **entrada}]}}


def test_hook_no_declarado_en_el_inventario_es_error():
    errores = _errores(revisar_hooks("hooks.json", _hooks("sessionStart", timeoutSec=5), {}))
    assert "EJECUTA CODIGO" in _mensajes(errores)


def test_hook_sin_timeout_es_error():
    errores = _errores(revisar_hooks("hooks.json", _hooks("sessionStart"), {"hooks": 1}))
    assert "timeoutSec" in _mensajes(errores)


def test_timeout_por_encima_del_techo_es_error():
    excesivo = TECHO_TIMEOUT_HOOK_S + 1
    errores = _errores(revisar_hooks("hooks.json",
                                     _hooks("sessionStart", timeoutSec=excesivo), {"hooks": 1}))
    assert "techo" in _mensajes(errores)


@pytest.mark.parametrize("evento", sorted(EVENTOS_HOOK_SENSIBLES))
def test_evento_sensible_avisa_de_que_ve_todo_lo_que_se_escribe(evento):
    """LAS DOS GRAFIAS, y tener solo una era un fallo ABIERTO. Copilot llama a este evento
    `userPromptSubmitted` y Claude Code `UserPromptSubmit`: la constante tenia solo la primera, asi que
    el aviso NO disparaba en la forma que usan los plugins de Claude -- la del catalogo oficial, con dos
    apariciones medidas, y la de nuestros propios plugins --."""
    hallazgos = revisar_hooks("hooks.json", _hooks(evento, timeoutSec=5), {"hooks": 1})

    avisos = [h for h in hallazgos if h.severidad is Severidad.AVISO]
    assert any("canal de salida de datos" in h.mensaje for h in avisos), evento


def test_interruptor_de_seguridad_apagado_es_aviso():
    # Sale del ejemplo real de la industria: `BLOCK_ON_THREAT: false` en un archivo que nadie abre.
    hallazgos = revisar_hooks("hooks.json",
                              _hooks("sessionStart", timeoutSec=5,
                                     env={"BLOCK_ON_THREAT": "false"}), {"hooks": 1})
    assert any("desactivado" in h.mensaje for h in hallazgos)


# ── higiene ────────────────────────────────────────────────────────────────────────────────
def test_token_literal_es_error():
    errores = _errores(revisar_higiene("f.md", "usa ghp_A1b2C3d4E5f6G7h8I9j0K1l2"))
    assert "token de GitHub" in _mensajes(errores)


def test_rutas_de_maquina_son_error_en_windows_y_en_unix():
    # El nombre de usuario del ejemplo es INVENTADO a proposito: esta es la prueba de la regla que
    # prohibe rutas de maquina, asi que usar una real aqui seria filtrar exactamente lo que se veta.
    assert _errores(revisar_higiene("f.md", r"C:\Users\jdoe\proyecto\x.yaml"))
    assert _errores(revisar_higiene("f.md", "/Users/t72582/Desktop/Projects/x/SKILL.md"))


def test_una_referencia_no_es_un_secreto():
    """El archivo solo dice COMO obtener la credencial. Sin esta excepcion, la forma CORRECTA de
    configurar un mcp seria rechazada por el gate."""
    assert revisar_higiene("f.md", 'Authorization: Bearer ${input:jira-token-de-servicio}') == []


def test_la_linea_del_hallazgo_es_la_correcta():
    contenido = "primera\nsegunda\nghp_A1b2C3d4E5f6G7h8I9j0K1l2\n"
    hallazgos = revisar_higiene("f.md", contenido)
    assert hallazgos[0].donde == "f.md:3"
