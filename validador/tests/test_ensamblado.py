"""Pruebas del ensamblado del objeto que los esquemas validan.

Lo que protegen: los esquemas NO describen un archivo, describen lo que resulta de juntar tres sitios
-- el frontmatter, su mapa `metadata:` y el `METADATA.json` hermano --. Si el ensamblado se equivoca,
el esquema valida algo que no existe, y eso pasa desapercibido porque el resultado es «conforme».
"""
from __future__ import annotations

from validador_agentico.dominio.ensamblado import ensamblar


def test_el_mapa_metadata_se_APLANA_al_nivel_superior():
    """El esquema declara `id` y `owner_team` como campos del objeto, no dentro de un sub-objeto.
    Aplanar aqui evita que cada esquema tenga que describir la anidacion, que es una forma del
    archivo y no del contrato."""
    objeto = ensamblar({"name": "x", "metadata": {"id": "demo.x", "owner_team": "t"}}, None, "skill")
    assert objeto["id"] == "demo.x"
    assert objeto["owner_team"] == "t"
    assert "metadata" not in objeto


def test_el_kind_se_pone_desde_fuera_y_no_se_lee_del_archivo():
    """`kind` lo DEDUCE el gate de la ruta. Un campo que se teclea puede contradecir al arbol, y
    entonces hay dos verdades sobre la misma cosa."""
    assert ensamblar({"name": "x"}, None, "prompt")["kind"] == "prompt"


def test_el_hermano_aporta_lo_que_no_cabe_en_el_mapa():
    # El mapa `metadata:` es cadena->cadena por especificacion, asi que un objeto anidado no entra.
    objeto = ensamblar({"name": "x"}, {"evals": {"suite": "evals/evals.json"}}, "skill")
    assert objeto["evals"] == {"suite": "evals/evals.json"}


def test_el_FRONTMATTER_gana_al_hermano_cuando_la_clave_esta_en_los_dos():
    """El frontmatter es lo que el cliente lee de verdad. Un hermano que lo contradijera estaria
    describiendo un artefacto que no existe."""
    objeto = ensamblar({"name": "el-del-frontmatter"}, {"name": "el-del-hermano"}, "skill")
    assert objeto["name"] == "el-del-frontmatter"


def test_el_mapa_metadata_tambien_gana_al_hermano():
    objeto = ensamblar({"metadata": {"version": "2.0.0"}}, {"version": "1.0.0"}, "skill")
    assert objeto["version"] == "2.0.0"


def test_sin_hermano_se_ensambla_igual():
    # Es el caso NORMAL: el hermano solo hace falta para lo que no cabe en el mapa.
    assert ensamblar({"name": "x", "metadata": {"id": "y"}}, None, "skill")["id"] == "y"


def test_un_metadata_ausente_no_rompe_el_ensamblado():
    assert ensamblar({"name": "x"}, None, "skill") == {"name": "x", "kind": "skill"}
