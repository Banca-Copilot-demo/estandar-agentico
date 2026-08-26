"""Un artefacto SUELTO publicado por separado: que el gate lo trate como su propia unidad.

POR QUE EXISTE ESTE CAMINO. Un artefacto suelto sin manifiesto propio NO entra al catalogo, y sin
entrada de catalogo no queda sujeto al estado: se instala igual este certificado, conforme o
suspendido. Esta MEDIDO contra los dos clientes -- con el contenido en otro repositorio, que es la
topologia real, la instalacion falla con «No plugin.json found in repository» --.

Con manifiesto propio cada suelto es una unidad: version, digesto, entrada de catalogo Y GOBIERNO
propios. El gobierno lo trae la unidad y no se hereda de la raiz, que es el defecto que estas
pruebas fijan: heredarlo atribuia el `owner.team` del repositorio a un artefacto que se publica
solo, en silencio y sin que ningun hallazgo lo dijera.
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


def _gobierno_de_la_unidad(directorio: Path, nombre: str, **cuentas: int) -> None:
    """El `GOVERNANCE.json` DE LA UNIDAD, hermano de `.claude-plugin/` y no dentro de el.

    FUERA DEL DIRECTORIO DEL CLIENTE a proposito: `.claude-plugin/` lo lee el cliente y su contenido
    lo fija una especificacion ajena, y ademas todo lo que vive en la unidad viaja en el paquete
    sellado hasta la maquina de quien instala -- el gobierno lleva equipo dueno, correo y
    clasificacion del dato, que un consumidor no necesita --.

    Sin `version`: la unidad tiene `plugin.json` y la version del paquete es la del manifiesto.
    """
    (directorio / "GOVERNANCE.json").write_text(json.dumps({
        "id": nombre,
        "domain": "sdlc",
        "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
        "status": "draft",
        "data_classification": "internal",
        "standard_version": "8.0.0",
        "artifacts": {"skills": 0, "agents": 0, "prompts": 0, **cuentas},
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
    _gobierno_de_la_unidad(directorio, f"demo.sdlc.{nombre}", skills=1)
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
    _gobierno_de_la_unidad(directorio, f"demo.sdlc.{nombre}", prompts=1)
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
    _gobierno_de_la_unidad(directorio, f"demo.sdlc.{nombre}", agents=1)
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


# ── la herencia retirada ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("construir", [_skill_suelto, _prompt_suelto, _agente_suelto],
                         ids=["skill", "prompt", "agente"])
def test_un_suelto_SIN_gobierno_propio_NO_se_queda_con_el_dueno_de_la_raiz(construir, tmp_path):
    """EL DEFECTO, medido sobre `agentes-sdlc`: `skills/revisar-jql/` es su propia unidad publicable
    -- manifiesto, etiqueta, paquete y ficha propios -- y no traia gobierno, asi que el gate le
    aplicaba el `GOVERNANCE.json` de la raiz con su `owner.team` incluido. Consecuencia: todos los
    sueltos de un repositorio acaban con el MISMO dueno por el mero hecho de vivir ahi, y ocurre EN
    SILENCIO -- ningun hallazgo, veredicto CONFORME --.

    El dueno es el eje del gobierno: a quien se pide la aprobacion y a quien se abre el issue.
    Atribuirlo por vecindad es justo lo que este marco existe para impedir.

    SI ALGUIEN REINTRODUCE EL RESPALDO, este error desaparece y la prueba falla. La raiz se monta CON
    gobierno a proposito: es la condicion exacta en la que la herencia funcionaba y tapaba el hueco.
    """
    _gobierno_de_la_raiz(tmp_path)
    unidad = construir(tmp_path)
    (unidad / "GOVERNANCE.json").unlink()

    mensajes = [h.mensaje for h in _errores(_validar(tmp_path))]

    assert [m for m in mensajes if "no declara su GOVERNANCE.json" in m], mensajes
    assert [m for m in mensajes if unidad.relative_to(tmp_path).as_posix() in m], mensajes


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
    _gobierno_de_la_unidad(plugin.parent, "demo.sdlc.otro")
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


# ── el caso en el que el gobierno de la RAIZ es el de la unidad ──────────────────────────────
def test_un_repositorio_de_UN_SOLO_PLUGIN_en_la_raiz_usa_el_gobierno_de_la_raiz(tmp_path):
    """LO QUE NO SE PUEDE ROMPER AL RETIRAR LA HERENCIA, y es una topologia distinta que se parece.

    Aqui la raiz del repositorio ES la unidad publicable -- es la que etiqueta corto, `vX.Y.Z`, en vez
    de `<nombre>--vX.Y.Z` -- asi que su `GOVERNANCE.json` no es el gobierno de un vecino: es el suyo.
    Un `GOVERNANCE.json` de la raiz solo sobra cuando la raiz NO publica nada, que es lo que pasa en
    un repositorio cuyos sueltos tienen todos unidad propia.

    Sin esta prueba, «retirar el gobierno de la raiz» se lee como una regla general y se lleva por
    delante el repositorio de un solo plugin, que es la forma mas comun de todas.
    """
    _manifiesto(tmp_path, "demo.sdlc.solo")
    _gobierno_de_la_unidad(tmp_path, "demo.sdlc.solo", skills=1)
    directorio = tmp_path / "skills" / "revisar-jql"
    directorio.mkdir(parents=True)
    (directorio / "SKILL.md").write_text(
        f"---\nname: revisar-jql\ndescription: Revisa una consulta y explica cada cambio que propone."
        f"\nmetadata:\n{_ENVELOPE.format(identificador='demo.sdlc.revisar-jql')}\n---\n\n# x\n",
        encoding="utf-8")

    veredicto = _validar(tmp_path)

    assert _errores(veredicto) == [], [h.mensaje for h in _errores(veredicto)]
    assert [p.subruta for p in veredicto.plugins] == ["."], "la unidad es el repositorio entero"
