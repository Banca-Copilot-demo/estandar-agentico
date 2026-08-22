"""Pruebas del descubrimiento de raices de plugin.

El defecto que cubren se MIDIO ejecutando el gate sobre un repositorio con dos plugins bajo
`plugins/`: respondio «0 skills, 0 agentes, plugin: no» y veredicto CONFORME. Tres artefactos
reales, y el gate no vio ninguno.
"""
from __future__ import annotations

from validador_agentico.dominio.reglas_layout import es_multiplugin, raices_de_plugin

RUTAS = (".claude-plugin/plugin.json", "plugin.json")


def _crear_plugin(directorio, ruta_manifiesto=".claude-plugin/plugin.json"):
    destino = directorio / ruta_manifiesto
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("{}", encoding="utf-8")
    return directorio


# ── el caso que estaba roto ─────────────────────────────────────────────────────────────────
def test_dos_plugins_bajo_plugins_dan_DOS_raices(tmp_path):
    for nombre in ("contratos", "migracion"):
        _crear_plugin(tmp_path / "plugins" / nombre)
    raices = raices_de_plugin(tmp_path, RUTAS)
    assert [r.name for r in raices] == ["contratos", "migracion"]
    assert es_multiplugin(raices, tmp_path)


def test_el_orden_es_ESTABLE_entre_ejecuciones(tmp_path):
    # Sin orden estable, el veredicto cambia de forma entre corridas y el digesto que se atesta
    # deja de ser reproducible.
    for nombre in ("zeta", "alfa", "media"):
        _crear_plugin(tmp_path / "plugins" / nombre)
    assert [r.name for r in raices_de_plugin(tmp_path, RUTAS)] == ["alfa", "media", "zeta"]


# ── lo que NO debe cambiar: el caso de siempre ──────────────────────────────────────────────
def test_un_plugin_en_la_raiz_sigue_dando_la_raiz(tmp_path):
    _crear_plugin(tmp_path)
    assert raices_de_plugin(tmp_path, RUTAS) == (tmp_path,)
    assert not es_multiplugin(raices_de_plugin(tmp_path, RUTAS), tmp_path)


def test_un_repositorio_de_artefactos_SUELTOS_sigue_siendo_una_unidad(tmp_path):
    """Sin manifiesto no hay plugin, pero el repositorio SI se valida: devolver una tupla vacia
    lo dejaria sin revisar, que es el defecto que esta regla viene a cerrar."""
    (tmp_path / "skills" / "x").mkdir(parents=True)
    assert raices_de_plugin(tmp_path, RUTAS) == (tmp_path,)


# ── un plugin se reconoce por su MANIFIESTO, no por su carpeta ───────────────────────────────
def test_una_carpeta_bajo_plugins_SIN_manifiesto_no_es_una_raiz(tmp_path):
    # Si contara como raiz, una carpeta de material compartido se validaria como plugin vacio.
    _crear_plugin(tmp_path / "plugins" / "real")
    (tmp_path / "plugins" / "compartido").mkdir(parents=True)
    assert [r.name for r in raices_de_plugin(tmp_path, RUTAS)] == ["real"]


def test_el_manifiesto_en_la_RAIZ_del_plugin_tambien_cuenta(tmp_path):
    """Copilot lee `plugin.json` en la raiz del plugin y Claude Code `.claude-plugin/plugin.json`:
    las dos formas identifican una raiz, o el gate solo veria los plugins de un cliente."""
    _crear_plugin(tmp_path / "plugins" / "para-copilot", "plugin.json")
    assert [r.name for r in raices_de_plugin(tmp_path, RUTAS)] == ["para-copilot"]


def test_sin_carpeta_plugins_no_se_inventan_raices(tmp_path):
    (tmp_path / "otra-cosa" / "x").mkdir(parents=True)
    assert raices_de_plugin(tmp_path, RUTAS) == (tmp_path,)
