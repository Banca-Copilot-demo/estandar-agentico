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


def _escribir_instruccion(raiz: Path, nombre: str, ambito: str | None) -> None:
    directorio = raiz / ".github" / "instructions"
    directorio.mkdir(parents=True, exist_ok=True)
    cabecera = f"---\napplyTo: '{ambito}'\n---\n" if ambito else ""
    (directorio / f"{nombre}.instructions.md").write_text(
        f"{cabecera}# Reglas\nAlgo.\n", encoding="utf-8")


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


def _instruccion_sin_ambito(raiz: Path) -> None:
    _escribir_skill(raiz)
    _escribir_instruccion(raiz, "todo", ambito=None)


def _hooks_no_declarados(raiz: Path) -> None:
    _escribir_skill(raiz)
    _escribir_manifiesto(raiz)
    (raiz / "GOVERNANCE.json").write_text(json.dumps({
        "id": "demo.sdlc.x", "domain": "sdlc",
        "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
        "status": "draft", "data_classification": "internal", "standard_version": "8.0.0",
        "artifacts": {"skills": 1}}), encoding="utf-8")
    directorio = raiz / "hooks"
    directorio.mkdir(parents=True)
    (directorio / "hooks.json").write_text(json.dumps({
        "version": 1,
        "hooks": {"sessionStart": [{"type": "command", "bash": "echo x", "timeoutSec": 5}]}}),
        encoding="utf-8")


def _recurso_inexistente(raiz: Path) -> None:
    _escribir_skill(raiz, texto=_SKILL_CONFORME + "\nVer `references/no-existe.md` para el detalle.\n")


def _secreto_literal(raiz: Path) -> None:
    # Token con la forma que el escaneo busca, inventado: no es una credencial real.
    _escribir_skill(raiz,
                    texto=_SKILL_CONFORME + "\ntoken: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\n")


def _dos_instrucciones_que_se_solapan(raiz: Path) -> None:
    _escribir_skill(raiz)
    _escribir_instruccion(raiz, "una", ambito="**/*.py")
    _escribir_instruccion(raiz, "otra", ambito="**/*.py")


# (regla que se prueba, como montar el repositorio, fragmento que SOLO esa regla emite)
_CABLES = (
    ("_revisar_plugin", _sin_plugin,
     "sin plugin: los artefactos quedan gobernados"),
    ("_revisar_gobierno", _con_plugin_sin_gobierno,
     "declara un plugin pero no su gobierno"),
    ("_revisar_skills", _skill_sin_frontmatter,
     "sin frontmatter: el artefacto es indescubrible"),
    ("_revisar_prompts", _prompt_con_skills_reference,
     "`skillsReference` no es un campo estandar"),
    ("_revisar_agentes", _agente_sin_description,
     "falta `description`: es lo que decide si el modelo le delega"),
    ("_revisar_instructions", _instruccion_sin_ambito,
     "sin `applyTo`"),
    ("_revisar_hooks", _hooks_no_declarados,
     "no declara `hooks`"),
    ("_revisar_recursos", _recurso_inexistente,
     "y ese archivo NO existe"),
    ("_revisar_higiene", _secreto_literal,
     "posible token de GitHub"),
    ("_revisar_solapamiento_de_instructions", _dos_instrucciones_que_se_solapan,
     "su ambito se solapa con"),
)


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
    probadas_en_test_gate = {"_revisar_forma_contra_esquemas", "_revisar_duenos", "_revisar_mezcla"}
    # Y estas dos las cubren las pruebas de `mcp` y de YAML invalido que ya existian en `test_gate.py`.
    probadas_de_antes = {"_revisar_mcp", "_revisar_yaml"}

    sin_cable = invocadas - con_cable - probadas_en_test_gate - probadas_de_antes
    assert not sin_cable, (
        f"reglas invocadas por el gate sin prueba de cableado: {sorted(sin_cable)}. "
        f"Añade su entrada en `_CABLES` y comprueba que sirve desconectando la regla: si la prueba "
        f"nueva no falla al desconectarla, no esta probando el cable.")
