"""Que una solicitud de cambio evalue lo que TOCA, y no todo el repositorio.

EL PROBLEMA QUE CUBRE es de escala y de acoplamiento, y el segundo es el que duele: con todas las
suites corriendo, UNA en rojo bloquea a todo el que toque el repositorio, aunque no sea suya y no
pueda arreglarla. MEDIDO: un cambio de cableado quedo bloqueado por la suite de un agente ajeno.

Y el de escala llega solo: el inventario del cliente tiene decenas de artefactos, las suites corren en
secuencia y cada una tarda minutos.
"""
from __future__ import annotations

import pytest

from suites_a_evaluar import suites_a_evaluar

_UNIDADES = ["plugins/contratos", "plugins/referencia", "skills/revisar-jql"]
_SUITES = [
    "plugins/referencia/agents/evals/promptfooconfig.yaml",
    "skills/revisar-jql/evals/promptfooconfig.yaml",
]


def test_un_cambio_en_un_skill_NO_arrastra_las_suites_de_los_demas():
    """El caso que motiva todo: tocar un artefacto no debe obligar a evaluar el inventario entero."""
    elegidas = suites_a_evaluar(_SUITES, _UNIDADES, ["skills/revisar-jql/SKILL.md"])

    assert elegidas == ["skills/revisar-jql/evals/promptfooconfig.yaml"]


def test_una_suite_en_rojo_ajena_no_bloquea_a_quien_no_la_toca():
    """REGRESION del acoplamiento medido: un cambio de cableado quedo bloqueado por la suite de un
    agente que su autor no habia tocado y no podia arreglar."""
    elegidas = suites_a_evaluar(_SUITES, _UNIDADES, ["plugins/contratos/GOVERNANCE.json"])

    assert "plugins/referencia/agents/evals/promptfooconfig.yaml" not in elegidas


def test_tocar_CUALQUIER_archivo_de_la_unidad_evalua_su_suite():
    """No solo el artefacto: sus recursos, su gobierno o su propia suite. Un cambio en cualquiera de
    ellos puede alterar el comportamiento, y acotar mas seria dejar de comprobar lo que cambio."""
    for cambiado in ["plugins/referencia/GOVERNANCE.json",
                     "plugins/referencia/agents/demo.sdlc.revisor.agent.md",
                     "plugins/referencia/agents/evals/promptfooconfig.yaml"]:
        elegidas = suites_a_evaluar(_SUITES, _UNIDADES, [cambiado])
        assert "plugins/referencia/agents/evals/promptfooconfig.yaml" in elegidas, cambiado


def test_un_cambio_que_toca_VARIAS_unidades_evalua_todas_las_suyas():
    elegidas = suites_a_evaluar(_SUITES, _UNIDADES,
                                ["skills/revisar-jql/SKILL.md",
                                 "plugins/referencia/agents/demo.sdlc.revisor.agent.md"])

    assert len(elegidas) == 2


def test_sin_lista_de_cambios_se_evaluan_TODAS():
    """Es el caso de la publicacion y del disparo manual: ahi no hay «lo que cambia», hay un estado
    que evaluar entero. Devolver una lista vacia dejaria la certificacion sin comprobar nada y en
    verde, que es el modo de fallo que este proyecto persigue."""
    assert suites_a_evaluar(_SUITES, _UNIDADES, []) == _SUITES


def test_un_cambio_fuera_de_toda_unidad_no_evalua_nada():
    """Tocar el README o un workflow no cambia el comportamiento de ningun artefacto."""
    assert suites_a_evaluar(_SUITES, _UNIDADES, ["README.md", ".github/workflows/validar.yml"]) == []


def test_un_prefijo_PARCIAL_no_cuenta_como_pertenencia():
    """`plugins/referencia-vieja` NO esta dentro de `plugins/referencia`. Comparando texto en vez de
    segmentos, un cambio en una evaluaria la suite de la otra -- el mismo defecto que ya aparecio en
    la pista de instalacion, por otra via."""
    elegidas = suites_a_evaluar(_SUITES, _UNIDADES,
                                ["plugins/referencia-vieja/agents/x.agent.md"])

    assert elegidas == []


@pytest.mark.parametrize("cambiado", ["skills/revisar-jql/SKILL.md", "./skills/revisar-jql/SKILL.md"])
def test_da_igual_que_las_rutas_lleguen_con_o_sin_el_punto_inicial(cambiado, tmp_path):
    """`find` las emite con `./` y `git diff` sin el. Si solo funcionara con una forma, el filtro
    quedaria vacio segun quien lo alimentara -- y un filtro vacio evalua de menos EN SILENCIO."""
    normalizado = cambiado.removeprefix("./")

    assert suites_a_evaluar(_SUITES, _UNIDADES, [normalizado])
