"""El camino de publicacion de un repositorio de artefactos SUELTOS, sin ningun plugin.

QUE ESTABA ROTO, y no eran las pruebas: era el camino. Un repositorio de sueltos pasaba el gate como
CONFORME y ahi se quedaba. `listar_plugins` hacia `continue` al no encontrar manifiesto, asi que no se
etiquetaba nada -- y sin etiqueta no hay release, ni paquete, ni atestacion, ni ficha en el catalogo --.
El lineamiento, en cambio, prometia que un suelto «aparece en el catalogo de Port» y que puede tener
«release y atestacion, uno por artefacto». Las dos cosas eran falsas.

Y NO ERA UN OLVIDO DE DISENO: el comentario de `etiquetar.yml` ya decia que un repositorio de sueltos
declara su version en el `GOVERNANCE.json`. Lo que faltaba era el CAMPO -- el esquema no lo tenia -- y
la rama que lo leyera. Estaba escrito lo que habia que hacer y no estaba hecho.

QUE HACE EL CAMINO AHORA: el repositorio ENTERO es la unidad de publicacion. Una etiqueta `vX.Y.Z` de
la `version` del gobierno, un paquete, una atestacion, y una ficha por artefacto con
`en_marketplace=false`. NINGUNA entrada de marketplace, y eso es correcto y no una carencia: las
entradas de un marketplace SON plugins. El generador del indice ya lo contemplaba -- verifica la
atestacion tambien para un suelto y le niega la entrada -- y nunca recibia nada que verificar.
"""
from __future__ import annotations

import json
from pathlib import Path

from validador_agentico.aplicacion.validar_repositorio import validar
from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.listar_plugins import listar

_PLANTILLA_SKILL = """---
name: {nombre}
description: Hace algo concreto y se usa cuando alguien lo pide por su nombre en una conversacion.
metadata:
  id: {identificador}
  owner_team: squad-sdlc
  owner_contact: squad-sdlc@ejemplo.dev
  status: draft
  version: "1.0.0"
  data_classification: internal
  standard_version: "8.0.0"
---

# {nombre}
"""


def _skill(base: Path, nombre: str, identificador: str) -> None:
    directorio = base / "skills" / nombre
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / "SKILL.md").write_text(
        _PLANTILLA_SKILL.format(nombre=nombre, identificador=identificador), encoding="utf-8")

_GOBIERNO = {
    "id": "demo.sdlc.sueltos",
    "domain": "sdlc",
    "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
    "status": "draft",
    "data_classification": "internal",
    "version": "1.0.0",
    "standard_version": "8.0.0",
    "artifacts": {"skills": 1},
}


def _errores(raiz: Path) -> list[str]:
    return [h.mensaje for h in validar(raiz).hallazgos if h.severidad is Severidad.ERROR]


def _repositorio_suelto(raiz: Path, gobierno: dict | None = _GOBIERNO) -> Path:
    """Un skill en la RAIZ, con el gobierno que lo publica. `gobierno=None` para omitirlo."""
    _skill(raiz, "revisar-jql", "demo.sdlc.revisar-jql")
    if gobierno is not None:
        (raiz / "GOVERNANCE.json").write_text(json.dumps(gobierno), encoding="utf-8")
    return raiz


def _con_plugin(raiz: Path, nombre: str) -> None:
    directorio = raiz / "plugins" / nombre / ".claude-plugin"
    directorio.mkdir(parents=True)
    (directorio / "plugin.json").write_text(json.dumps(
        {"name": f"demo.sdlc.{nombre}", "version": "2.0.0", "description": "Un plugin."}),
        encoding="utf-8")


# ── el descubrimiento, que es donde se rompia la cadena ────────────────────────────────────
def test_un_repositorio_de_sueltos_ES_una_unidad_publicable(tmp_path):
    # El defecto: aqui se devolvia [] y por eso no habia etiqueta, ni release, ni atestacion, ni ficha.
    _repositorio_suelto(tmp_path)

    assert listar(tmp_path) == [(".", "demo.sdlc.sueltos", "1.0.0")]


def test_sin_version_en_el_gobierno_no_hay_nada_que_etiquetar(tmp_path):
    """La version es lo unico que decide si hay cadena de publicacion: sin ella no se puede derivar
    la etiqueta, y etiquetar a ciegas con releases inmutables no se deshace."""
    sin_version = {c: v for c, v in _GOBIERNO.items() if c != "version"}
    _repositorio_suelto(tmp_path, gobierno=sin_version)

    assert listar(tmp_path) == []


def test_un_repositorio_MIXTO_publica_el_plugin_Y_el_conjunto_suelto(tmp_path):
    """El caso que el estandar recomienda: un repositorio por DOMINIO, con lo que haga falta dentro.

    Antes se emitia SOLO el plugin y los artefactos de la raiz no los publicaba nadie -- ni siquiera
    se leian --. Ahora son dos unidades, cada una con su etiqueta, y las dos con NOMBRE: `vX.Y.Z` a
    secas significaria «todo excepto los plugins», una definicion por resta.
    """
    _con_plugin(tmp_path, "uno")
    _repositorio_suelto(tmp_path)

    unidades = listar(tmp_path)

    assert unidades == [
        ("plugins/uno", "demo.sdlc.uno", "2.0.0"),
        (".", "demo.sdlc.sueltos", "1.0.0"),
    ], unidades


def test_el_gate_VE_los_artefactos_de_las_dos_unidades(tmp_path):
    """El defecto original: en un repositorio mixto, los artefactos de la raiz no los leia nadie, asi
    que el inventario los ignoraba y no recibian ficha. Aqui tienen que contar los dos."""
    _con_plugin(tmp_path, "uno")
    _skill(tmp_path / "plugins" / "uno", "del-plugin", "demo.sdlc.del-plugin")
    _repositorio_suelto(tmp_path)

    veredicto = validar(tmp_path)
    fichas = {a.id for a in veredicto.artefactos}

    assert veredicto.inventario.skills == 2, veredicto.inventario
    assert fichas == {"demo.sdlc.del-plugin", "demo.sdlc.revisar-jql"}, fichas


def test_UN_plugin_en_la_raiz_no_se_etiqueta_DOS_veces(tmp_path):
    # El riesgo real de mirar tambien la raiz: en el layout de un solo plugin en la raiz, el
    # `GOVERNANCE.json` y el `plugin.json` describen el MISMO paquete -- el gate exige que su `id`
    # coincida con el `name` --, asi que emitirlo otra vez daria dos etiquetas para el mismo
    # contenido. Y con releases inmutables ninguna se borra.
    manifiesto = tmp_path / ".claude-plugin"
    manifiesto.mkdir(parents=True)
    (manifiesto / "plugin.json").write_text(json.dumps(
        {"name": "demo.sdlc.solo", "version": "3.0.0", "description": "x"}), encoding="utf-8")
    (tmp_path / "GOVERNANCE.json").write_text(json.dumps(
        {**_GOBIERNO, "id": "demo.sdlc.solo"}), encoding="utf-8")

    assert listar(tmp_path) == [(".", "demo.sdlc.solo", "3.0.0")]


# ── el gate: la version sobra con plugin y falta sin el ────────────────────────────────────
def test_sin_plugin_y_sin_version_el_gate_lo_BLOQUEA(tmp_path):
    sin_version = {c: v for c, v in _GOBIERNO.items() if c != "version"}
    _repositorio_suelto(tmp_path, gobierno=sin_version)

    mensajes = " | ".join(_errores(tmp_path))

    assert "no hay de donde derivar la etiqueta" in mensajes, mensajes


def test_sin_plugin_y_CON_version_el_gate_lo_deja_pasar(tmp_path):
    _repositorio_suelto(tmp_path)

    assert _errores(tmp_path) == []


def test_declarar_version_teniendo_plugin_es_ERROR(tmp_path):
    # Dos declaraciones de la misma cosa divergen, y aqui la divergencia produciria una etiqueta que
    # no corresponde al paquete. Manda el manifiesto, que es lo que el marketplace resuelve.
    raiz_plugin = tmp_path / "plugins" / "uno"
    _con_plugin(tmp_path, "uno")
    (raiz_plugin / "GOVERNANCE.json").write_text(
        json.dumps({**_GOBIERNO, "id": "demo.sdlc.uno", "artifacts": {}}), encoding="utf-8")

    mensajes = " | ".join(_errores(tmp_path))

    assert "la version del paquete es la del manifiesto" in mensajes, mensajes
