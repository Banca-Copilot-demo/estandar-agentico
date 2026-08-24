"""G5: las suites de evals. Lo que el esquema NO puede comprobar, y el descubrimiento de la suite.

REPARTO CON EL ESQUEMA. `eval-suite.schema.json` valida la forma; estas reglas validan contra el ARBOL
que el `artifact` de la suite exista y que los ids de caso no se repitan. Las pruebas de forma no se
duplican aqui: lo que se prueba aqui es lo que ningun esquema puede saber.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from validador_agentico.adaptadores import esquema, repositorio
from validador_agentico.dominio.reglas_evals import revisar_suite

_ESQUEMAS = Path(__file__).resolve().parents[2] / "schemas"
_ESQUEMA = "eval-suite.schema.json"

_SUITE = {
    "schema_version": "1.0",
    "artifact": "demo.sdlc.x.mcp",
    "level": 1,
    "eval_type": "mcp_contract",
    "cases": [
        {"id": "conecta", "title": "Conecta.", "category": "happy_path"},
        {"id": "sin-escritura", "title": "No expone escritura.", "category": "negative"},
        {"id": "borde", "title": "Un borde.", "category": "edge_case"},
    ],
}


def _mensajes(hallazgos) -> str:
    return " | ".join(h.mensaje for h in hallazgos)


# ── el cotejo contra el arbol ───────────────────────────────────────────────────────────────
def test_una_suite_que_apunta_a_un_id_que_no_existe_es_error():
    """El peor resultado posible de G5: la suite corre, no falla y no evalua nada, mientras su mera
    presencia se lee como cobertura."""
    hallazgos = revisar_suite("evals/x.eval.json", _SUITE, frozenset({"demo.sdlc.otro"}))

    assert "no publica ningun artefacto con ese id" in _mensajes(hallazgos)


def test_una_suite_que_apunta_a_un_id_publicado_no_produce_hallazgos():
    assert revisar_suite("evals/x.eval.json", _SUITE, frozenset({"demo.sdlc.x.mcp"})) == []


def test_el_mensaje_dice_QUE_ids_hay_publicados():
    # Sin la lista, el error obliga a ir a buscar el id correcto a mano; con ella, la correccion es
    # evidente. Es el mismo criterio que el mensaje del inventario desalineado.
    hallazgos = revisar_suite("evals/x.eval.json", _SUITE, frozenset({"demo.sdlc.real"}))

    assert "demo.sdlc.real" in _mensajes(hallazgos)


# ── los ids de caso ─────────────────────────────────────────────────────────────────────────
def test_dos_casos_con_el_MISMO_id_es_error():
    """El id existe para comparar el reporte de una version con el de la siguiente; repetido, el
    reporte no se puede leer. El esquema no lo puede expresar."""
    repetido = {**_SUITE, "cases": [*_SUITE["cases"],
                                    {"id": "conecta", "title": "Otra vez.", "category": "negative"}]}

    hallazgos = revisar_suite("evals/x.eval.json", repetido, frozenset({"demo.sdlc.x.mcp"}))

    assert "esta declarado mas de una vez" in _mensajes(hallazgos)


# ── el descubrimiento, que es donde estaba el bug ───────────────────────────────────────────
def _escribir_suite(directorio: Path, artefacto: str) -> None:
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / "contrato.eval.json").write_text(
        json.dumps({**_SUITE, "artifact": artefacto}), encoding="utf-8")


def _escribir_manifiesto(raiz: Path, nombre: str) -> None:
    manifiesto = raiz / ".claude-plugin"
    manifiesto.mkdir(parents=True, exist_ok=True)
    (manifiesto / "plugin.json").write_text(json.dumps(
        {"name": nombre, "version": "1.0.0", "description": "Un plugin."}), encoding="utf-8")


def test_la_suite_de_un_plugin_ANIDADO_no_se_atribuye_al_conjunto_suelto(tmp_path):
    """MEDIDO ejecutando el gate sobre el repositorio de dominio real, no leyendo el codigo.

    El descubrimiento hacia `rglob` desde la raiz de la unidad, con el razonamiento de que «cada unidad
    se lee con su propia raiz, asi que no hay plugins debajo». Es FALSO para el conjunto suelto de un
    repositorio mixto: su raiz ES la del repositorio y `plugins/` cuelga de ahi. El sintoma fue doble --
    la suite aparecia DOS veces, y en la segunda el cotejo la comparaba contra los ids de la RAIZ y
    producia un error falso sobre una suite correcta --.
    """
    del_plugin = tmp_path / "plugins" / "uno"
    _escribir_manifiesto(del_plugin, "demo.sdlc.uno")
    _escribir_suite(del_plugin / "evals", "demo.sdlc.uno.mcp")

    desde_la_raiz = repositorio._leer_suites_de_evals(tmp_path)
    desde_el_plugin = repositorio._leer_suites_de_evals(del_plugin)

    assert desde_la_raiz == (), "la suite del plugin anidado se atribuyo al conjunto suelto"
    assert len(desde_el_plugin) == 1


def test_la_suite_de_la_propia_unidad_SI_se_descubre(tmp_path):
    # La otra mitad: la exclusion no debe cortar tanto que deje de ver lo suyo. Un `mcp` es uno por
    # unidad y no tiene carpeta propia, asi que su suite vive en `evals/` de la raiz de la unidad.
    _escribir_manifiesto(tmp_path, "demo.sdlc.x")
    _escribir_suite(tmp_path / "evals", "demo.sdlc.x.mcp")

    assert len(repositorio._leer_suites_de_evals(tmp_path)) == 1


def test_la_suite_de_un_skill_se_descubre_en_su_carpeta(tmp_path):
    # Co-localizada con lo que evalua: la del skill cuelga del skill, no de un directorio central.
    _escribir_manifiesto(tmp_path, "demo.sdlc.x")
    _escribir_suite(tmp_path / "skills" / "revisar" / "evals", "demo.sdlc.revisar")

    assert len(repositorio._leer_suites_de_evals(tmp_path)) == 1


# ── la exigencia de caso negativo, que el esquema enunciaba y no comprobaba ──────────────────
def test_una_suite_SIN_caso_negativo_no_pasa_el_esquema():
    """El esquema decia en la descripcion de `category` que una suite sin caso negativo no verifica
    que el artefacto se ABSTENGA cuando debe -- y admitia tres casos felices --. Un requisito enunciado
    en prosa y no comprobado es exactamente el hueco que un contrato existe para cerrar."""
    sin_negativo = {**_SUITE, "cases": [
        {**caso, "category": "happy_path"} for caso in _SUITE["cases"]]}

    defectos = esquema.incumplimientos(sin_negativo, _ESQUEMA, _ESQUEMAS)

    assert any("does not contain" in defecto for defecto in defectos), defectos


def test_la_suite_REAL_del_mcp_de_la_demo_cumple_su_esquema():
    """Contra el archivo de verdad y no contra un fixture: es la unica suite del repositorio y el
    unico ejemplo que un equipo va a copiar. Si deja de cumplir, esta prueba lo dice antes que nadie.

    Se salta -- no falla -- si no esta el repositorio de dominio al lado: la prueba del validador no
    puede depender de que otro repositorio este clonado.
    """
    ruta = (Path(__file__).resolve().parents[3] / "agentes-sdlc" / "plugins"
            / "mcp-aws-knowledge" / "evals" / "contrato.eval.json")
    if not ruta.is_file():
        pytest.skip(f"no esta el repositorio de dominio en {ruta}")

    suite = json.loads(ruta.read_text(encoding="utf-8"))

    assert esquema.incumplimientos(suite, _ESQUEMA, _ESQUEMAS) == []
