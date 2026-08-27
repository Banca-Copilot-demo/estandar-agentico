"""Que se evalue lo que el cambio TOCA, y solo lo que el repositorio realmente publica.

EL PROBLEMA QUE CUBRE es de escala y de acoplamiento, y el segundo es el que duele: con todas las
suites corriendo, UNA en rojo bloquea a todo el que toque el repositorio, aunque no sea suya y no
pueda arreglarla. MEDIDO: un cambio de cableado quedo bloqueado por la suite de un agente ajeno.

Y el de escala llega solo: el inventario del cliente tiene decenas de artefactos, las suites corren en
secuencia y cada una tarda minutos.

EL SEGUNDO BLOQUE cubre un defecto distinto y peor, medido en el run 33016050350: correr una suite que
NO ES DEL REPOSITORIO. Ese acotado no depende del evento -- se aplica tambien en push a main -- y por
eso sus pruebas van aparte de las del acotado por cambios.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from suites_a_evaluar import (
    es_plantilla,
    sin_plantillas,
    suites_a_evaluar,
    unidades_a_evaluar,
)

# La plantilla REAL del repositorio del estandar, la que puso en rojo el run 33016050350. Se lee del
# arbol y no se copia aqui: una copia se queda atras el dia que alguien edite el esqueleto, que es
# justo el dia en que hay que volver a comprobarlo.
_PLANTILLA_DEL_ESTANDAR = (Path(__file__).resolve().parents[2]
                           / "plantillas" / "artefactos" / "evals" / "promptfooconfig.yaml")

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


# ── LO QUE NO ES DEL REPOSITORIO NO SE EVALUA ─────────────────────────────────────────────────────
#
# REGRESION del run 33016050350 de `agentes-sdlc` (push a main): el trabajo de comportamiento se puso
# rojo por `.estandar/plantillas/artefactos/evals/promptfooconfig.yaml` -- una plantilla del repositorio
# del estandar, que el propio workflow clona dentro del workspace -- mientras las 3 suites del
# repositorio pasaban 3 de 3. En un pull request no se veia: el acotado por cambios ya la descartaba.

_SUITE_PRESTADA = ".estandar/plantillas/artefactos/evals/promptfooconfig.yaml"


def test_una_suite_que_no_cuelga_de_ninguna_unidad_no_se_evalua_en_push_a_main():
    """El caso exacto del run: sin lista de cambios contra la que acotar, la suite ajena entraba."""
    elegidas = suites_a_evaluar([*_SUITES, _SUITE_PRESTADA], _UNIDADES, [])

    assert _SUITE_PRESTADA not in elegidas


def test_descartar_lo_ajeno_no_se_lleva_por_delante_las_suites_propias():
    """El filtro nuevo no puede convertir el rojo espurio en un verde vacio: las 3 suites legitimas
    del run pasaban sus casos y tienen que seguir corriendo."""
    assert suites_a_evaluar([*_SUITES, _SUITE_PRESTADA], _UNIDADES, []) == _SUITES


def test_la_plantilla_del_estandar_no_se_selecciona_ni_desde_su_propio_repositorio():
    """LA PERTENENCIA SOLA NO BASTA y esto lo fija. `plantillas/` cuelga de la RAIZ del repositorio del
    estandar; hoy ese repo publica solo `plugins/asistente-autoria` -- COMPROBADO con `listar_plugins`,
    la raiz NO es unidad -- pero el dia que declare un conjunto suelto la raiz pasa a serlo y la
    plantilla «pertenece» a ella. Por eso se descarta ademas por sus marcadores sin rellenar."""
    contenido = _PLANTILLA_DEL_ESTANDAR.read_text(encoding="utf-8")
    ruta = "plantillas/artefactos/evals/promptfooconfig.yaml"

    ejecutables = sin_plantillas([ruta], lambda _: contenido)

    assert ejecutables == [], "la plantilla del estandar se seleccionaria para evaluar"


def test_la_plantilla_real_conserva_los_marcadores_que_la_hacen_inejecutable():
    """MEDIDO leyendo el archivo del run: promptfoo le pregunto al modelo la cadena literal
    `<<CONSULTA>>` y comprobo si la respuesta contenia `<<PALABRA_QUE_TIENE_QUE_APARECER>>`. No es una
    suite que falla, es una que no puede pasar -- y encima gasta cuota de inferencia --. Si alguien
    rellena esos huecos «para dejarla bonita», deja de descartarse y esta prueba lo dice."""
    assert es_plantilla(_PLANTILLA_DEL_ESTANDAR.read_text(encoding="utf-8"))


_SUITE_REAL = (
    "description: revisar-jql\n"
    "prompts:\n  - \"{{consulta}}\"\n"
    "tests:\n  - vars:\n      consulta: \"revisa este JQL\"\n"
    "    assert:\n      - type: icontains\n        value: proyecto\n"
)


def test_una_suite_de_verdad_no_se_confunde_con_una_plantilla():
    """El filtro por marcadores no puede tragarse suites reales: el riesgo de una regla por contenido
    es justo ese, y sin esta prueba el sintoma seria una cobertura que cae a cero en verde. Las llaves
    de `{{consulta}}` son de plantilla de promptfoo, no huecos sin rellenar, y no deben contar."""
    assert not es_plantilla(_SUITE_REAL)


def test_una_suite_de_verdad_sobrevive_al_descarte_de_plantillas():
    ruta = "skills/revisar-jql/evals/promptfooconfig.yaml"

    assert sin_plantillas([ruta], lambda _: _SUITE_REAL) == [ruta]


# --- La proyeccion a UNIDAD, que es la que alimenta la matriz -----------------------------------
#
# EL DEFECTO QUE CUBRE ESTE BLOQUE, medido en el run 33040368778 de `agentes-sdlc`: con UN solo
# trabajo de evaluacion para todo el repositorio, su unica conclusion se contagiaba. `revisar-jql` con
# 3 de 3 y `referencia` con 3 de 3 no se promocionaron porque la suite de `migracion` estaba en 2 de
# 3. La matriz abre un trabajo por unidad para que cada una emita SU comprobacion, y de esta funcion
# sale la lista de unidades. Si divergiera de la seleccion de suites, se abriria un trabajo para una
# unidad sin suites -- o se dejaria una suite sin trabajo que la corriera --, y ninguna de las dos
# cosas se pondria roja: nadie lo notaria.

def test_cada_unidad_con_suite_aparece_una_sola_vez_en_la_matriz():
    """Una unidad con VARIAS suites es un trabajo, no varios: la matriz se indexa por unidad, y
    repetirla abriria dos celdas con el MISMO nombre -- dos check-runs indistinguibles, que es
    exactamente lo que impediria al guardian elegir el suyo --."""
    dos_suites_de_la_misma_unidad = [
        "plugins/referencia/agents/evals/promptfooconfig.yaml",
        "plugins/referencia/skills/otro/evals/promptfooconfig.yaml",
    ]

    assert unidades_a_evaluar(dos_suites_de_la_misma_unidad, _UNIDADES, []) == ["plugins/referencia"]


def test_una_unidad_sin_suites_no_abre_ningun_trabajo():
    """Abrir una celda para una unidad sin nada que medir la dejaria en verde sin haber evaluado, y
    esa es justo la senal que el guardian confundiria con «certificable»."""
    assert "plugins/contratos" not in unidades_a_evaluar(_SUITES, _UNIDADES, [])


def test_la_matriz_solo_trae_las_unidades_que_el_cambio_toca():
    """El acotado del pull request tiene que llegar tambien a la matriz. Sin esto se abriria un
    trabajo por cada unidad del repositorio en cada solicitud de cambio, y volveria el acoplamiento
    por otra puerta: gasto de inferencia por artefactos que nadie toco."""
    assert unidades_a_evaluar(_SUITES, _UNIDADES, ["skills/revisar-jql/SKILL.md"]) == \
        ["skills/revisar-jql"]


def test_sin_ninguna_suite_la_matriz_queda_vacia():
    """EL CASO VACIO, que es el que hay que distinguir de «pasaron todas». Aqui solo se exige que la
    lista salga vacia; que eso NO se lea como verde lo fija la prueba de forma del workflow."""
    assert unidades_a_evaluar([], _UNIDADES, []) == []


def test_las_unidades_de_la_matriz_son_exactamente_las_de_las_suites_seleccionadas():
    """LAS DOS PROYECCIONES NO PUEDEN DIVERGIR, y es lo unico que garantiza que cada suite tenga un
    trabajo que la corra y cada trabajo tenga una suite que medir. Se comprueba contra la MISMA
    entrada en varios escenarios, porque la divergencia aparecia justo en los bordes -- lo prestado,
    lo acotado por cambios --."""
    escenarios = {
        "todo": ([*_SUITES, _SUITE_PRESTADA], []),
        "acotado por cambios": (_SUITES, ["skills/revisar-jql/SKILL.md"]),
        "nada tocado": (_SUITES, ["README.md"]),
    }
    for nombre, (suites, cambiados) in escenarios.items():
        elegidas = suites_a_evaluar(suites, _UNIDADES, cambiados)
        esperadas = sorted({u for u in _UNIDADES
                            for s in elegidas if s.startswith(f"{u}/")})
        assert unidades_a_evaluar(suites, _UNIDADES, cambiados) == esperadas, nombre
