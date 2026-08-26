"""Que una suite de agente se ejecute COMO agente, y una de skill no.

EL DEFECTO QUE FIJA, medido en la primera ejecucion del gate en CI: el workflow corria todas las
suites igual, sin `--agent`. La del agente dio 1 de 3 y el informe acusaba al ARTEFACTO de un fallo
de la HERRAMIENTA -- exactamente el mismo daño que ya costo caro al montar el puente --.

La causa es que un skill y un agente no se evaluan igual: de un skill se mide si el cliente lo ACTIVA
solo, asi que se invoca sin `--agent`; un agente se INVOCA, y sin `--agent` la suite ejecuta al
asistente por defecto y mide otra cosa.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agente_de_la_suite import agente_de

_FRONTMATTER = """---
name: {nombre}
description: "Hace algo concreto y se le delega cuando toca."
---

# Cuerpo
"""


def _suite_de_agente(raiz: Path, nombre: str = "demo.sdlc.revisor") -> Path:
    """El layout real: la suite cuelga de `agents/evals/` con el `.agent.md` como hermano."""
    agentes = raiz / "agents"
    (agentes / "evals").mkdir(parents=True, exist_ok=True)
    (agentes / f"{nombre}.agent.md").write_text(_FRONTMATTER.format(nombre=nombre),
                                                encoding="utf-8")
    suite = agentes / "evals" / "promptfooconfig.yaml"
    suite.write_text("description: x\ntests: []\n", encoding="utf-8")
    return suite


def _suite_de_skill(raiz: Path) -> Path:
    suite = raiz / "skills" / "revisar-jql" / "evals" / "promptfooconfig.yaml"
    suite.parent.mkdir(parents=True, exist_ok=True)
    suite.write_text("description: x\ntests: []\n", encoding="utf-8")
    return suite


def test_una_suite_de_agente_devuelve_su_nombre_de_invocacion(tmp_path):
    assert agente_de(_suite_de_agente(tmp_path)) == "demo.sdlc.revisor"


def test_una_suite_de_skill_NO_devuelve_agente(tmp_path):
    """Y no es un error: la mayoria de las suites son de skills. Devolver algo aqui haria que el
    skill se evaluara con `--agent`, o sea comprobando que obedece en vez de que se activa."""
    assert agente_de(_suite_de_skill(tmp_path)) is None


def test_el_nombre_sale_del_FRONTMATTER_y_no_del_archivo(tmp_path):
    """El nombre de invocacion lo declara el artefacto. Deducirlo del archivo funcionaria mientras
    los dos coincidieran y fallaria en silencio el dia que dejaran de hacerlo."""
    agentes = tmp_path / "agents"
    (agentes / "evals").mkdir(parents=True)
    (agentes / "archivo-con-otro-nombre.agent.md").write_text(
        _FRONTMATTER.format(nombre="demo.sdlc.el-de-verdad"), encoding="utf-8")
    suite = agentes / "evals" / "promptfooconfig.yaml"
    suite.write_text("description: x\n", encoding="utf-8")

    assert agente_de(suite) == "demo.sdlc.el-de-verdad"


def test_con_VARIOS_agentes_hermanos_no_se_adivina(tmp_path):
    """Elegir uno mediria el artefacto equivocado y el informe culparia al que no fue. Sin agente, la
    suite corre como la de un skill y el fallo, si lo hay, sera visible en vez de enganoso."""
    suite = _suite_de_agente(tmp_path, "demo.sdlc.primero")
    (tmp_path / "agents" / "demo.sdlc.segundo.agent.md").write_text(
        _FRONTMATTER.format(nombre="demo.sdlc.segundo"), encoding="utf-8")

    assert agente_de(suite) is None


@pytest.mark.parametrize("contenido, motivo", [
    ("sin frontmatter\n", "sin frontmatter"),
    ("---\ndescription: falta el name\n---\n", "sin `name`"),
], ids=["sin-frontmatter", "sin-name"])
def test_un_agente_que_no_declara_su_nombre_no_se_inventa(contenido, motivo, tmp_path):
    suite = _suite_de_agente(tmp_path)
    (tmp_path / "agents" / "demo.sdlc.revisor.agent.md").write_text(contenido, encoding="utf-8")

    assert agente_de(suite) is None, motivo
