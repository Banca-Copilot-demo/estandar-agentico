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
    revisar_gobierno_ausente,
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


def test_el_gobierno_de_OTRA_unidad_no_pasa_por_el_de_esta():
    """REGRESION de la herencia retirada, medida sobre `agentes-sdlc`.

    Hubo un modo `heredado` que omitia `id` y `version` cuando el gobierno era el de la raiz del
    repositorio y no el de la unidad. Servia para que el suelto no fallara con dos errores por
    construccion -- «`id` (demo.sdlc.sueltos) no coincide con `name` (demo.sdlc.revisar-jql)» --,
    pero el precio era que la unidad se quedaba con el `owner.team` de la raiz EN SILENCIO. Retirada
    la herencia, un gobierno que describe otra cosa tiene que delatarse en vez de aceptarse: si
    alguien reintroduce el atajo, estos dos errores desaparecen y la prueba falla.
    """
    de_la_raiz = {"id": "demo.sdlc.sueltos", "version": "1.0.2", "owner": {"team": "t"}}

    mensajes = _mensajes(_errores(revisar_gobierno(de_la_raiz, MANIFIESTO_CONFORME)))

    assert "no coincide" in mensajes
    assert "version" in mensajes


def test_una_unidad_que_publica_y_no_declara_gobierno_es_ERROR_que_la_nombra():
    """EL DEFECTO ERA UN SILENCIO. Un artefacto suelto con manifiesto propio -- unidad publicable con
    etiqueta, paquete y ficha propios -- no traia `GOVERNANCE.json` y el gate se lo suplia con el de
    la raiz del repositorio, con su `owner.team` incluido. Asi, todos los sueltos de un repositorio
    acababan con el mismo dueno por vecindad, sin un solo hallazgo que lo dijera.

    El mensaje nombra la unidad y lo que publica porque el repositorio medido tiene SEIS: «falta el
    gobierno» a secas obligaria a ir a buscar cual.
    """
    hallazgos = revisar_gobierno_ausente("skills/revisar-jql", "plugin `demo.sdlc.revisar-jql`")

    assert all(h.severidad is Severidad.ERROR for h in hallazgos)
    assert "skills/revisar-jql" in _mensajes(hallazgos)
    assert "demo.sdlc.revisar-jql" in _mensajes(hallazgos)


def test_dueno_sin_equipo_es_error():
    errores = _errores(revisar_gobierno({"owner": {}}, None))
    assert "RESOLUBLE" in _mensajes(errores)


def test_inventario_desalineado_es_error():
    errores = _errores(revisar_inventario({"skills": 1}, Inventario(skills=2)))
    assert "declara 1" in _mensajes(errores)


def test_inventario_por_conteo_alineado_no_bloquea_pero_avisa_de_la_migracion():
    # El conteo es la forma ANTIGUA. No puede ser error: el gate es comprobacion requerida y
    # rechazarlo de golpe impediria mergear hasta el propio PR que viene a migrarlo -- ya paso al
    # retirar `status` --. Asi que no bloquea, y avisa.
    declarado = {"skills": 2, "agents": 1, "prompts": 0}
    hallazgos = revisar_inventario(declarado, Inventario(skills=2, agentes=1))
    assert _errores(hallazgos) == []
    assert "CONTEO" in _mensajes(hallazgos)


def test_inventario_por_ids_alineado_no_produce_hallazgos():
    declarado = {"skills": ["demo.x.uno"], "agents": [], "prompts": []}
    assert revisar_inventario(declarado, Inventario(skills=1, ids_skills=("demo.x.uno",))) == []


def test_intercambiar_un_artefacto_por_otro_no_pasa_desapercibido():
    # EL FALSO NEGATIVO DEL CONTEO, que es el motivo entero de este cambio. Medido: se borra un skill
    # y se anade otro en el mismo pull request; el numero sigue siendo 1, asi que el cotejo por conteo
    # no encuentra NADA que decir y Port publica un id que ya no existe.
    inventario = Inventario(skills=1, ids_skills=("demo.x.nuevo",))
    errores = _errores(revisar_inventario({"skills": ["demo.x.viejo"]}, inventario))
    assert "demo.x.viejo" in _mensajes(errores)
    assert "demo.x.nuevo" in _mensajes(errores)
    # Y la prueba de que el conteo NO lo veia: mismo arbol, inventario declarado por numero.
    assert _errores(revisar_inventario({"skills": 1}, inventario)) == []


def test_una_clave_retirada_del_inventario_avisa_y_no_bloquea():
    for clave in ("mcps", "hooks", "scripts"):
        hallazgos = revisar_inventario({clave: 1}, Inventario())
        assert _errores(hallazgos) == [], clave
        assert f"artifacts.{clave}" in _mensajes(hallazgos), clave


# ── hooks ──────────────────────────────────────────────────────────────────────────────────
# LA ESTRUCTURA REAL, que este helper no tenia: `hooks` -> EVENTO -> grupos, y cada grupo con su
# `matcher` y su lista `hooks[]` de ACCIONES. El helper anterior ponia `type` y el tope en el nivel del
# GRUPO -- que es exactamente la forma que el gate exigia y el cliente ignora --, asi que las pruebas
# confirmaban el defecto en vez de detectarlo.
_APROBADO = {"approval": {"approved_by": "squad-seguridad", "date": "2026-08-23",
                          "review_by": "2027-02-23", "security_review": True}}


def _hooks(evento: str, *, grupo=None, **accion) -> dict:
    predeterminada = {"type": "command",
                      "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/s.sh"}
    return {"version": 1,
            "hooks": {evento: [{**(grupo or {}), "hooks": [{**predeterminada, **accion}]}]}}


def test_hook_sin_aprobacion_en_el_gobierno_es_error():
    errores = _errores(revisar_hooks("hooks.json", _hooks("SessionStart", timeout=5), {}))
    assert "EJECUTA CODIGO" in _mensajes(errores)


def test_una_accion_sin_ningun_tope_declarado_es_error():
    # Ni `timeout` ni `timeoutSec`: no hay intencion de tope en ninguna parte, asi que el hook correra
    # con el default de su tipo -- 600 s para `command` -- y eso si bloquea.
    errores = _errores(revisar_hooks("hooks.json", _hooks("SessionStart"), _APROBADO))
    assert "600" in _mensajes(errores)


def test_timeout_por_encima_del_techo_es_error():
    excesivo = TECHO_TIMEOUT_HOOK_S + 1
    errores = _errores(revisar_hooks("hooks.json",
                                     _hooks("SessionStart", timeout=excesivo), _APROBADO))
    assert "techo" in _mensajes(errores)


@pytest.mark.parametrize("evento", sorted(EVENTOS_HOOK_SENSIBLES))
def test_evento_sensible_avisa_de_que_ve_todo_lo_que_se_escribe(evento):
    """LAS DOS GRAFIAS, y tener solo una era un fallo ABIERTO. Copilot llama a este evento
    `userPromptSubmitted` y Claude Code `UserPromptSubmit`: la constante tenia solo la primera, asi que
    el aviso NO disparaba en la forma que usan los plugins de Claude -- la del catalogo oficial, con dos
    apariciones medidas, y la de nuestros propios plugins --."""
    hallazgos = revisar_hooks("hooks.json", _hooks(evento, timeout=5), _APROBADO)

    avisos = [h for h in hallazgos if h.severidad is Severidad.AVISO]
    assert any("canal de salida de datos" in h.mensaje for h in avisos), evento


def test_interruptor_de_seguridad_apagado_es_aviso():
    # Sale del ejemplo real de la industria: `BLOCK_ON_THREAT: false` en un archivo que nadie abre.
    hallazgos = revisar_hooks("hooks.json",
                              _hooks("SessionStart", timeout=5,
                                     grupo={"env": {"BLOCK_ON_THREAT": "false"}}), _APROBADO)
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
