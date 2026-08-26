"""Un artefacto SUELTO publicado por separado: que el gate lo trate como su propia unidad.

POR QUE EXISTE ESTE CAMINO. Un artefacto suelto sin manifiesto propio NO entra al catalogo, y sin
entrada de catalogo no queda sujeto al estado: se instala igual este certificado, conforme o
suspendido. Esta MEDIDO contra los dos clientes -- con el contenido en otro repositorio, que es la
topologia real, la instalacion falla con «No plugin.json found in repository» --.

Con manifiesto propio cada suelto es una unidad: version, digesto y entrada de catalogo propios. Lo
que estas pruebas fijan es lo que se rompio al montarlo, que fue siempre la misma clase de defecto:
el gobierno HEREDADO describe el REPOSITORIO, y compararlo con la unidad da errores garantizados.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from validador_agentico.aplicacion.validar_repositorio import validar

_ESQUEMAS = Path(__file__).resolve().parent.parent.parent / "schemas"

_ENVELOPE = """  id: {identificador}
  owner_team: squad-sdlc
  owner_contact: squad-sdlc@ejemplo.dev
  status: draft
  version: 1.0.0
  data_classification: internal
  standard_version: 8.0.0"""


def _gobierno_de_la_raiz(raiz: Path, skills: int = 0, agents: int = 0, prompts: int = 0) -> None:
    """El `GOVERNANCE.json` del repositorio. Su inventario cuenta los artefactos del REPOSITORIO."""
    (raiz / "GOVERNANCE.json").write_text(json.dumps({
        "id": "demo.sdlc.sueltos",
        "domain": "sdlc",
        "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
        "status": "draft",
        "data_classification": "internal",
        "version": "1.0.2",
        "standard_version": "8.0.0",
        "artifacts": {"skills": skills, "agents": agents, "prompts": prompts},
    }), encoding="utf-8")


def _manifiesto(directorio: Path, nombre: str) -> None:
    destino = directorio / ".claude-plugin"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "plugin.json").write_text(json.dumps({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": nombre,
        "version": "0.1.0",
        "description": "Artefacto suelto de prueba.",
    }), encoding="utf-8")


def _skill_suelto(raiz: Path, nombre: str = "revisar-jql") -> Path:
    """El skill se queda DONDE EL AUTOR YA LO ESCRIBE: solo se le anade el manifiesto.

    Su `SKILL.md` queda en la raiz de la unidad, que es la forma que los clientes esperan de un
    plugin de un solo skill -- y entonces el nombre de invocacion sale del frontmatter, sin prefijo.
    """
    directorio = raiz / "skills" / nombre
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / "SKILL.md").write_text(
        f"---\nname: {nombre}\ndescription: Revisa una consulta y explica cada cambio que propone."
        f"\nmetadata:\n{_ENVELOPE.format(identificador=f'demo.sdlc.{nombre}')}\n---\n\n# {nombre}\n",
        encoding="utf-8")
    _manifiesto(directorio, f"demo.sdlc.{nombre}")
    return directorio


def _prompt_suelto(raiz: Path, nombre: str = "resumir") -> Path:
    """Un prompt es un ARCHIVO, no un directorio, asi que no puede alojar el manifiesto a su lado:
    necesita directorio propio con su `commands/` dentro. Es la forma que se probo instalando."""
    directorio = raiz / "commands" / nombre
    (directorio / "commands").mkdir(parents=True, exist_ok=True)
    (directorio / "commands" / f"demo.sdlc.{nombre}.prompt.md").write_text(
        f"---\nname: demo.sdlc.{nombre}\ndescription: \"Resume un hilo en acuerdos y pendientes.\""
        f"\nmetadata:\n{_ENVELOPE.format(identificador=f'demo.sdlc.{nombre}')}\n---\n\n# {nombre}\n",
        encoding="utf-8")
    _manifiesto(directorio, f"demo.sdlc.{nombre}")
    return directorio


def _agente_suelto(raiz: Path, nombre: str = "auditor") -> Path:
    directorio = raiz / "agents" / nombre
    (directorio / "agents").mkdir(parents=True, exist_ok=True)
    (directorio / "agents" / f"demo.sdlc.{nombre}.agent.md").write_text(
        f"---\nname: demo.sdlc.{nombre}\ndescription: \"Audita las dependencias de un servicio y "
        f"senala las que no estan fijadas. Delegale la auditoria cuando haya varios manifiestos.\""
        f"\nmetadata:\n{_ENVELOPE.format(identificador=f'demo.sdlc.{nombre}')}\n---\n\n# {nombre}\n",
        encoding="utf-8")
    _manifiesto(directorio, f"demo.sdlc.{nombre}")
    return directorio


def _errores(veredicto):
    return [h for h in veredicto.hallazgos if h.severidad.name == "ERROR"]


def _validar(raiz: Path):
    return validar(raiz, directorio_de_esquemas=_ESQUEMAS,
                   equipos_conocidos=frozenset({"squad-sdlc"}))


# ── los tres tipos se publican por separado ─────────────────────────────────────────────────
@pytest.mark.parametrize("construir", [_skill_suelto, _prompt_suelto, _agente_suelto],
                         ids=["skill", "prompt", "agente"])
def test_cada_tipo_suelto_con_manifiesto_es_CONFORME(construir, tmp_path):
    _gobierno_de_la_raiz(tmp_path)
    construir(tmp_path)

    veredicto = _validar(tmp_path)

    assert _errores(veredicto) == [], [h.mensaje for h in _errores(veredicto)]


# ── el defecto que casi pasa desapercibido ──────────────────────────────────────────────────
@pytest.mark.parametrize("construir", [_prompt_suelto, _agente_suelto], ids=["prompt", "agente"])
def test_un_tipo_distinto_del_que_declara_la_raiz_no_produce_error_de_inventario(construir,
                                                                                  tmp_path):
    """REGRESION del defecto que MAS CERCA estuvo de colarse.

    El gobierno heredado cuenta los artefactos del REPOSITORIO, y el gate lo cotejaba contra el arbol
    de la unidad. Con un solo skill suelto el cotejo CUADRABA POR CASUALIDAD -- la raiz declaraba 1
    skill y esa unidad tenia 1 --, asi que el camino parecia correcto. Solo al anadir un agente y un
    prompt aparecieron los cuatro errores: «declara 1 skills y el arbol real tiene 0».

    Un control que pasa por azar es peor que uno que falla: se lee como cobertura y no lo es. Por eso
    el caso que se monta aqui es aquel en el que la coincidencia NO PUEDE darse -- la raiz declara un
    SKILL y la unidad publica un prompt o un agente -- y no el que paso de casualidad.
    """
    _gobierno_de_la_raiz(tmp_path, skills=1)
    construir(tmp_path)

    mensajes = [h.mensaje for h in _errores(_validar(tmp_path))]

    assert not [m for m in mensajes if "inventario" in m], mensajes


def test_varios_sueltos_conviven_como_unidades_independientes(tmp_path):
    """Cada uno con su version y su etiqueta: es lo que da cadencia propia, que era el motivo de
    publicarlos por separado en vez de en un unico paquete comun."""
    _gobierno_de_la_raiz(tmp_path)
    _skill_suelto(tmp_path)
    _prompt_suelto(tmp_path)
    _agente_suelto(tmp_path)

    veredicto = _validar(tmp_path)

    assert _errores(veredicto) == [], [h.mensaje for h in _errores(veredicto)]
    nombres = {p.nombre for p in veredicto.plugins}
    assert nombres == {"demo.sdlc.revisar-jql", "demo.sdlc.resumir", "demo.sdlc.auditor"}


@pytest.mark.parametrize("construir", [_skill_suelto, _prompt_suelto, _agente_suelto],
                         ids=["skill", "prompt", "agente"])
def test_un_suelto_con_unidad_propia_NO_se_reporta_como_huerfano(construir, tmp_path):
    """REGRESION de un defecto que la coincidencia volvio a esconder.

    `artefactos_sin_unidad` acusa a los artefactos de la raiz que no publica nadie. Un suelto con
    manifiesto SI tiene quien lo publique -- el mismo --, pero la regla no recibia las rutas del
    manifiesto y lo contaba como huerfano: acusaba justo al artefacto mejor publicado.

    NO SALIO EN LA PRUEBA DE EXTREMO A EXTREMO porque su repositorio declaraba `version` en la raiz,
    y con eso la regla sale por su primera condicion. Hizo falta montar el caso SIN esa version.
    """
    plugin = tmp_path / "plugins" / "otro" / ".claude-plugin"
    plugin.mkdir(parents=True)
    (plugin / "plugin.json").write_text(json.dumps({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "demo.sdlc.otro", "version": "0.1.0", "description": "Vecino.",
    }), encoding="utf-8")
    # La raiz NO declara `version`: es lo que hace que la regla llegue a mirar los directorios.
    (tmp_path / "GOVERNANCE.json").write_text(json.dumps({
        "id": "demo.sdlc.sueltos", "domain": "sdlc",
        "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
        "status": "draft", "data_classification": "internal", "standard_version": "8.0.0",
        "artifacts": {},
    }), encoding="utf-8")
    construir(tmp_path)

    mensajes = [h.mensaje for h in _errores(_validar(tmp_path))]

    assert not [m for m in mensajes if "unidad" in m or "huerfan" in m], mensajes


def test_el_suelto_SIN_manifiesto_sigue_publicandose_con_el_conjunto(tmp_path):
    """Poner manifiesto es opcional y gradual: si no lo fuera, anadir esta regla romperia todos los
    repositorios existentes de golpe."""
    _gobierno_de_la_raiz(tmp_path, skills=1)
    directorio = tmp_path / "skills" / "sin-manifiesto"
    directorio.mkdir(parents=True)
    (directorio / "SKILL.md").write_text(
        f"---\nname: sin-manifiesto\ndescription: Hace algo concreto cuando alguien lo pide."
        f"\nmetadata:\n{_ENVELOPE.format(identificador='demo.sdlc.sin-manifiesto')}\n---\n\n# x\n",
        encoding="utf-8")

    veredicto = _validar(tmp_path)

    assert _errores(veredicto) == [], [h.mensaje for h in _errores(veredicto)]
    assert not veredicto.plugins, "sin manifiesto no es una unidad propia"
