"""Que el gate INVOQUE cada regla. No que la regla funcione: eso lo cubren sus pruebas propias.

POR QUE ESTE ARCHIVO EXISTE, y no es una precaucion teorica. Se barrio `validar()` con un arnes de
mutacion -- desconectar una invocacion, correr la suite, restaurar, siguiente -- y el resultado fue que
DIEZ DE QUINCE reglas se podian desconectar con las 220 pruebas EN VERDE. Entre ellas `_revisar_skills`
(el tipo principal) y `_revisar_higiene` (el escaneo de secretos). Comprobado en concreto: con la
higiene desconectada, un skill que contiene `ghp_...` sale CONFORME con cero errores.

QUE FALLO EN EL DISENO DE LAS PRUEBAS. Cada regla tenia su prueba de unidad, asi que la LOGICA estaba
cubierta al detalle. Lo que nadie comprobaba era el CABLE, y un cable roto no se parece a un fallo: la
regla deja de comprobar y el gate sigue diciendo CONFORME. Es el unico defecto de esta clase que
ninguna prueba de unidad puede ver, y afecta justo al codigo que decide si algo se publica (T6).

POR QUE ES UN MODULO APARTE de `test_gate.py`: aquel prueba la AGREGACION del veredicto y ya pasa de
350 lineas; esto prueba el CABLEADO. Son dos responsabilidades (G1).

COMO SE MANTIENE. Cada entrada de `_CABLES` construye el repositorio minimo que dispara UNA regla y
declara un fragmento del mensaje que SOLO esa regla produce. Los fragmentos no se adivinaron: se
observaron ejecutando cada escenario. Si se añade una regla a `validar()`, se añade su cable aqui -- y
la forma de comprobar que la prueba nueva sirve de algo es desconectar la regla y ver que falla.
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

from validador_agentico.aplicacion.validar_repositorio import validar

# Los esquemas del propio repositorio: el gate solo ejecuta la comprobacion de forma si se le pasan.
_ESQUEMAS = Path(__file__).resolve().parent.parent.parent / "schemas"

_ENVELOPE = """  id: demo.sdlc.x
  owner_team: squad-sdlc
  owner_contact: squad-sdlc@ejemplo.dev
  status: draft
  version: 1.0.0
  data_classification: internal
  standard_version: 8.0.0"""

_SKILL_CONFORME = f"""---
name: valido
description: Hace algo concreto y se usa cuando alguien lo pide por su nombre.
metadata:
{_ENVELOPE}
---

# Valido
"""


def _escribir_skill(raiz: Path, nombre: str = "valido", texto: str = _SKILL_CONFORME) -> None:
    directorio = raiz / "skills" / nombre
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / "SKILL.md").write_text(texto, encoding="utf-8")


def _escribir_manifiesto(raiz: Path) -> None:
    directorio = raiz / ".claude-plugin"
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / "plugin.json").write_text(
        json.dumps({"name": "demo.sdlc.x", "version": "1.0.0", "description": "Plugin de prueba."}),
        encoding="utf-8")


# ── un repositorio por regla ───────────────────────────────────────────────────────────────
def _sin_plugin(raiz: Path) -> None:
    _escribir_skill(raiz)


def _con_plugin_sin_gobierno(raiz: Path) -> None:
    _escribir_skill(raiz)
    _escribir_manifiesto(raiz)


def _skill_sin_frontmatter(raiz: Path) -> None:
    directorio = raiz / "skills" / "sin-frontmatter"
    directorio.mkdir(parents=True)
    (directorio / "SKILL.md").write_text("# Sin frontmatter\n", encoding="utf-8")


def _prompt_con_skills_reference(raiz: Path) -> None:
    _escribir_skill(raiz)
    directorio = raiz / "commands"
    directorio.mkdir(parents=True)
    (directorio / "demo.sdlc.p.prompt.md").write_text(
        f"---\nname: demo.sdlc.p\ndescription: Invoca algo concreto cuando el usuario lo teclea.\n"
        f"skillsReference: ./skills\nmetadata:\n{_ENVELOPE}\n---\n", encoding="utf-8")


def _agente_sin_description(raiz: Path) -> None:
    _escribir_skill(raiz)
    directorio = raiz / "agents"
    directorio.mkdir(parents=True)
    (directorio / "demo.sdlc.a.agent.md").write_text(
        f'---\nname: demo.sdlc.a\ndescription: ""\nmetadata:\n{_ENVELOPE}\n---\n', encoding="utf-8")


def _hooks_sin_aprobacion(raiz: Path) -> None:
    _escribir_skill(raiz)
    _escribir_manifiesto(raiz)
    (raiz / "GOVERNANCE.json").write_text(json.dumps({
        "id": "demo.sdlc.x", "domain": "sdlc",
        "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
        "status": "draft", "data_classification": "internal", "standard_version": "8.0.0",
        "artifacts": {"skills": 1}}), encoding="utf-8")
    directorio = raiz / "hooks"
    directorio.mkdir(parents=True)
    # LA ESTRUCTURA REAL: el `type` y el tope van en la ACCION, dentro del `hooks[]` del grupo. El
    # fixture los tenia en el grupo -- la forma que el gate exigia y el cliente ignora --.
    (directorio / "hooks.json").write_text(json.dumps({
        "version": 1,
        "hooks": {"SessionStart": [{"hooks": [
            {"type": "command", "timeout": 5,
             "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/x.sh"}]}]}}),
        encoding="utf-8")


def _recurso_inexistente(raiz: Path) -> None:
    _escribir_skill(raiz, texto=_SKILL_CONFORME + "\nVer `references/no-existe.md` para el detalle.\n")


def _secreto_literal(raiz: Path) -> None:
    # Token con la forma que el escaneo busca, inventado: no es una credencial real.
    _escribir_skill(raiz,
                    texto=_SKILL_CONFORME + "\ntoken: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\n")


def _skill_en_la_raiz_que_nadie_publica(raiz: Path) -> None:
    """Un plugin anidado Y un skill en la raiz, pero SIN `version` en el gobierno de la raiz.

    El repositorio mixto es legitimo; lo que no lo es es tener artefactos en la raiz sin declarar con
    que version se publican, porque entonces no hay etiqueta y nadie los empaqueta.
    """
    del_plugin = raiz / "plugins" / "uno"
    manifiesto = del_plugin / ".claude-plugin"
    manifiesto.mkdir(parents=True)
    (manifiesto / "plugin.json").write_text(json.dumps(
        {"name": "demo.sdlc.uno", "version": "1.0.0", "description": "Un plugin."}),
        encoding="utf-8")
    _escribir_skill(del_plugin, "dentro-del-plugin")
    _escribir_skill(raiz, "en-la-raiz")


def _mcp_con_json_corrupto(raiz: Path) -> None:
    """Un `.mcp.json` que no parsea.

    ES EL UNICO EMISOR de «JSON invalido» para los tres archivos JSON de una unidad -- el manifiesto, el
    gobierno y el mcp -- y ninguna prueba lo ejercitaba por esa via: un arnes de mutacion lo neutralizo
    a `[]` y la suite entera siguio verde. O sea que el gate podia dejar de reportar un JSON ilegible
    sin que nada fallara, y un `GOVERNANCE.json` corrupto se lee como «no hay gobierno».
    """
    _escribir_skill(raiz)
    _escribir_manifiesto(raiz)
    (raiz / ".mcp.json").write_text('{"mcpServers": {', encoding="utf-8")


def _artefacto_con_bytes_que_no_son_utf8(raiz: Path) -> None:
    """Un `SKILL.md` con un byte invalido en UTF-8.

    NO ES UN CABLE MAS: es la regresion de un bug que ABORTABA EL GATE. `contar_lineas` leia el archivo
    sin guarda mientras su hermana `leer_cuerpo` degradaba, y se la llama en los cuatro barridos de
    artefactos, asi que un unico archivo con encoding roto tumbaba la ejecucion con traceback en vez de
    producir un hallazgo. Un gate que revienta no dice «no conforme»: no dice nada.
    """
    _escribir_skill(raiz)
    directorio = raiz / "skills" / "roto"
    directorio.mkdir(parents=True)
    (directorio / "SKILL.md").write_bytes(b"---\nname: roto\n\xff\xfe---\n")


def _suite_de_evals_que_apunta_a_nada(raiz: Path) -> None:
    """Una suite bien formada que evalua un id que la unidad no publica.

    Es el defecto propio de G5 y el peor de los posibles: la suite corre, no falla y no evalua nada,
    mientras su existencia se lee como cobertura. Se elige este escenario para el cable -- y no una
    suite mal formada -- porque este solo lo detecta la REGLA, no el esquema.
    """
    _escribir_skill(raiz)
    directorio = raiz / "evals"
    directorio.mkdir(parents=True)
    (directorio / "cobertura.eval.json").write_text(json.dumps({
        "schema_version": "1.0",
        "artifact": "demo.sdlc.artefacto-que-no-existe",
        "level": 1,
        "eval_type": "trigger",
        "cases": [
            {"id": "c1", "title": "Se activa ante la consulta esperada.",
             "category": "happy_path", "query": "revisa la cobertura", "should_trigger": True},
            {"id": "c2", "title": "Consulta de otro dominio, no debe activarse.",
             "category": "negative", "query": "reinicia el servidor", "should_trigger": False},
            {"id": "c3", "title": "Consulta ambigua en el limite del alcance.",
             "category": "edge_case", "query": "mira los tests", "should_trigger": False},
        ],
    }), encoding="utf-8")


# (regla que se prueba, como montar el repositorio, fragmento que SOLO esa regla emite)
_CABLES = (
    ("_revisar_plugin", _sin_plugin,
     "sin plugin: los artefactos se gobiernan por su propia metadata"),
    ("_revisar_gobierno", _con_plugin_sin_gobierno,
     "no declara su GOVERNANCE.json"),
    ("_revisar_skills", _skill_sin_frontmatter,
     "sin frontmatter: el artefacto es indescubrible"),
    ("_revisar_prompts", _prompt_con_skills_reference,
     "`skillsReference` no es un campo estandar"),
    ("_revisar_agentes", _agente_sin_description,
     "falta `description`: es lo que decide si el modelo le delega"),
    ("_revisar_hooks", _hooks_sin_aprobacion,
     "no declara `hooks.approval`"),
    ("_revisar_recursos", _recurso_inexistente,
     "y ese archivo NO existe"),
    ("_revisar_higiene", _secreto_literal,
     "posible token de GitHub"),
    ("_revisar_sin_unidad", _skill_en_la_raiz_que_nadie_publica,
     "no declara `version`"),
    ("_revisar_evals", _suite_de_evals_que_apunta_a_nada,
     "no publica ningun artefacto con ese id"),
    ("_hallazgo_de_formato", _mcp_con_json_corrupto,
     "JSON invalido"),
)


def test_un_artefacto_con_bytes_QUE_NO_SON_UTF8_no_tumba_el_gate(tmp_path):
    """REGRESION de un bug que abortaba la ejecucion, medido con un `SKILL.md` de bytes invalidos.

    `contar_lineas` leia sin guarda mientras `leer_cuerpo` degradaba con el mismo `except`, y se la
    llama en los cuatro barridos de artefactos. El gate no daba NO CONFORME: reventaba con
    `UnicodeDecodeError`, que en CI se lee como fallo de infraestructura y no como artefacto defectuoso.

    Lo que se afirma es que el gate TERMINA. Que ese artefacto ademas produzca hallazgos es cosa de las
    reglas del tipo; aqui lo que se fija es que un archivo ilegible no se lleve por delante a los otros.
    """
    _artefacto_con_bytes_que_no_son_utf8(tmp_path)

    veredicto = validar(tmp_path)

    assert veredicto is not None


@pytest.mark.parametrize("regla,construir,fragmento", _CABLES, ids=[c[0] for c in _CABLES])
def test_el_gate_invoca_la_regla(regla, construir, fragmento, tmp_path):
    """Se recorren en bucle con el nombre de la regla en el id y en el mensaje: cuando falla, dice
    QUE cable se rompio sin obligar a leer el codigo (T5)."""
    construir(tmp_path)

    veredicto = validar(tmp_path, directorio_de_esquemas=_ESQUEMAS)

    mensajes = [h.mensaje for h in veredicto.hallazgos]
    assert any(fragmento in m for m in mensajes), (
        f"{regla} no se invoco, o dejo de emitir {fragmento!r}. Hallazgos: {mensajes}")


# Las reglas que `validar()` invoca de verdad, leidas de su propio codigo. Los argumentos no llevan
# parentesis anidados, asi que `[^()]*` basta.
_INVOCACION_DE_REGLA = re.compile(r"\*(_revisar_\w+)\([^()]*\)")


def test_toda_regla_invocada_por_el_gate_tiene_su_cable_probado():
    """El unico hueco que las pruebas de arriba NO pueden cubrir: una regla NUEVA sin cable.

    POR QUE ESTA PRUEBA Y NO UN ARNES DE MUTACION EN CI. Desconectar una regla existente ya lo atrapan
    las pruebas de arriba, que corren en CI en cada cambio de `validador/**`. Lo unico que quedaba
    fuera es que alguien AÑADA una regla a `validar()` y se olvide de su entrada en `_CABLES`: la
    regla entraria sin que nada compruebe que se invoca, y volveriamos al punto de partida sin
    enterarnos. Barrer quince mutaciones en CI para detectar eso cuesta tres minutos por corrida;
    comparar dos listas cuesta un milisegundo y detecta exactamente lo mismo.

    Lee el codigo fuente de `validar()` a proposito: la lista de reglas invocadas no esta disponible
    de otra forma, y cualquier registro paralelo que hubiera que mantener a mano tendria el mismo
    problema que esta prueba existe para evitar.
    """
    invocadas = set(_INVOCACION_DE_REGLA.findall(inspect.getsource(validar)))
    con_cable = {nombre for nombre, _, _ in _CABLES}

    # Estas tres tienen su cable probado en `test_gate.py`, no aqui: llegan por parametro opcional y
    # necesitan que el gate reciba contexto (esquemas, equipos, archivos cambiados).
    probadas_en_test_gate = {"_revisar_forma_contra_esquemas", "_revisar_duenos", "_revisar_mezcla",
                             "_revisar_subida_de_version"}
    # Y estas dos las cubren las pruebas de `mcp` y de YAML invalido que ya existian en `test_gate.py`.
    probadas_de_antes = {"_revisar_mcp", "_revisar_yaml"}

    sin_cable = invocadas - con_cable - probadas_en_test_gate - probadas_de_antes
    assert not sin_cable, (
        f"reglas invocadas por el gate sin prueba de cableado: {sorted(sin_cable)}. "
        f"Añade su entrada en `_CABLES` y comprueba que sirve desconectando la regla: si la prueba "
        f"nueva no falla al desconectarla, no esta probando el cable.")
