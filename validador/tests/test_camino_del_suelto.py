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

_SKILL = """---
name: revisar-jql
description: Revisa una consulta JQL y senala lo que degrada su rendimiento. Usalo al escribir una.
metadata:
  id: demo.sdlc.revisar-jql
  owner_team: squad-sdlc
  owner_contact: squad-sdlc@ejemplo.dev
  status: draft
  version: "1.0.0"
  data_classification: internal
  standard_version: "8.0.0"
---

# Revisar una consulta JQL
"""

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
    """Un repositorio con un skill y SIN plugin. `gobierno=None` para omitir el GOVERNANCE.json."""
    directorio = raiz / "skills" / "revisar-jql"
    directorio.mkdir(parents=True)
    (directorio / "SKILL.md").write_text(_SKILL, encoding="utf-8")
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


def test_un_repositorio_CON_plugins_no_se_etiqueta_ademas_como_suelto(tmp_path):
    # Si la raiz se consultara ANTES de recorrer los plugins, un repositorio multiplugin con su propio
    # GOVERNANCE.json en la raiz produciria DOS etiquetas para el mismo commit -- la del plugin y la
    # del repositorio -- y con releases inmutables ninguna de las dos se borra.
    _con_plugin(tmp_path, "uno")
    (tmp_path / "GOVERNANCE.json").write_text(json.dumps(_GOBIERNO), encoding="utf-8")

    unidades = listar(tmp_path)

    assert unidades == [("plugins/uno", "demo.sdlc.uno", "2.0.0")], unidades


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
