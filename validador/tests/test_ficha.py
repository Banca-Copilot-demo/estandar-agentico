"""Lo que la ficha del catalogo dice de un artefacto segun su ESTADO.

Cubre los tres defectos que se midieron en el catalogo REAL despues de separar publicar de
distribuir, y que tenian la misma causa: la ficha se construia con datos que no dependian del estado,
asi que decia lo mismo antes y despues de una transicion.
"""
from __future__ import annotations

import pytest

from validador_agentico.dominio import ficha, reglas_layout
from validador_agentico.dominio.politica import (ESTADO_AL_PUBLICAR, ESTADO_CERTIFICADO, Promocion)

_UNIDADES = [
    {"nombre": "demo.sdlc.contratos", "subruta": "plugins/contratos"},
    {"nombre": "demo.sdlc.revisar-jql", "subruta": "skills/revisar-jql"},
]


# ── que se distribuye, y que no ─────────────────────────────────────────────────────────────
def test_lo_CONFORME_no_se_distribuye_cuando_la_politica_promociona_al_certificar():
    """REGRESION del defecto medido en el catalogo real: la ficha de un artefacto `conformant`
    declaraba `en_marketplace: True` y mandaba a `copilot plugin install`, un comando que NO
    RESUELVE porque el release nace como prelanzamiento y el indice lo excluye.

    La causa era que `en_marketplace` se derivaba de «es un componente que un plugin transporta»
    -- una propiedad del TIPO -- e ignoraba por completo el estado.
    """
    assert not ficha.esta_distribuido(
        ESTADO_AL_PUBLICAR, Promocion.AL_CERTIFICAR, True, "skill")


def test_lo_CERTIFICADO_se_distribuye_con_cualquiera_de_las_dos_politicas():
    for promocion in Promocion:
        assert ficha.esta_distribuido(
            ESTADO_CERTIFICADO, promocion, True, "skill"), promocion


def test_lo_conforme_SI_se_distribuye_si_la_organizacion_promociona_al_publicar():
    # La politica existe porque el cliente ya cambio de criterio una vez: la regla tiene que
    # responder distinto con cada una, no tener el criterio escrito dentro.
    assert ficha.esta_distribuido(
        ESTADO_AL_PUBLICAR, Promocion.AL_PUBLICAR, True, "skill")


def test_un_artefacto_fuera_de_todo_plugin_no_se_distribuye_ni_certificado():
    """Las entradas de un marketplace son PLUGINS. Un suelto sin manifiesto propio no tiene entrada,
    asi que ningun estado lo mete en el catalogo."""
    assert not ficha.esta_distribuido(ESTADO_CERTIFICADO, Promocion.AL_PUBLICAR, False, "skill")


def test_un_tipo_que_ningun_plugin_transporta_no_se_distribuye():
    assert not ficha.esta_distribuido(
        ESTADO_CERTIFICADO, Promocion.AL_PUBLICAR, True, "instructions")


# ── la pista coherente con el estado ────────────────────────────────────────────────────────
def test_sin_distribuir_la_pista_NO_manda_al_catalogo():
    """Es la mitad visible del defecto: quien siguiera la pista ejecutaba un `plugin install` que
    falla, porque el artefacto no esta en el catalogo. La ficha prometia lo que el catalogo no podia
    cumplir."""
    for tipo in sorted(ficha.TIPOS_QUE_UN_PLUGIN_TRANSPORTA):
        pista = ficha.pista_de_instalacion(
            tipo, "plugins/contratos/skills/x/SKILL.md", False, "org/repo", "0" * 40,
            "demo--v0.1.0", "demo")
        assert "plugin install" not in pista, f"{tipo}: {pista}"


@pytest.mark.parametrize("tipo, ruta", [
    ("skill", "skills/revisar-jql/SKILL.md"),
    ("prompt", "commands/resumir/commands/demo.prompt.md"),
    ("agent", "agents/auditor/agents/demo.agent.md"),
    ("mcp", "plugins/aws/.mcp.json"),
])
def test_toda_pista_sin_catalogo_va_FIJADA_a_la_version(tipo, ruta):
    """Una pista sin fijar instalaria lo que haya en la rama, que es contenido que nadie reviso.
    Cada rama tiene que llevar la etiqueta o el sha sellado."""
    pista = ficha.pista_de_instalacion(
        tipo, ruta, False, "org/repo", "a" * 40, "demo--v0.1.0", "demo")
    assert "demo--v0.1.0" in pista or "a" * 40 in pista, pista


def test_una_ficha_SIN_ruta_no_revienta_al_cambiar_de_estado():
    """REGRESION de un defecto que se vio al escribir la pieza de transicion: `ruta` se anadio al
    catalogo justo para que una transicion pudiera reconstruir la pista, asi que las fichas
    anteriores a ese cambio la tienen vacia. Partir una cadena vacia por `/` reventaba, y reventar a
    mitad de una transicion deja el catalogo con unas fichas movidas y otras no."""
    pista = ficha.pista_de_instalacion("skill", "", False, "org/repo", "b" * 40, "v1.0.0", "")
    assert pista


def test_distribuido_manda_al_plugin_que_lo_contiene():
    assert ficha.pista_de_instalacion(
        "skill", "plugins/contratos/skills/x/SKILL.md", True, "org/repo", "0" * 40,
        "demo.sdlc.contratos--v0.1.0", "demo.sdlc.contratos"
    ) == f"copilot plugin install demo.sdlc.contratos@{ficha.CATALOGO}"


# ── el alcance de una publicacion ───────────────────────────────────────────────────────────
def test_publicar_una_unidad_NO_alcanza_a_los_artefactos_de_las_vecinas():
    """REGRESION del defecto medido: el predicado firmado es del REPOSITORIO entero, asi que
    recorrerlo tal cual reescribia la ficha de TODOS los artefactos con la etiqueta, el sha y el
    digesto de una version que no es la suya. La ficha de un vecino acababa apuntando a un paquete
    que no lo contiene, sin que nadie hubiera tocado ese vecino."""
    assert ficha.es_de_la_unidad(
        "plugins/contratos/skills/x/SKILL.md", "plugins/contratos", _UNIDADES)
    assert not ficha.es_de_la_unidad(
        "skills/revisar-jql/SKILL.md", "plugins/contratos", _UNIDADES)


def test_publicar_el_conjunto_suelto_no_arrastra_a_los_plugins_anidados():
    """En un repositorio MIXTO la subruta del conjunto suelto es `.`, y por prefijo todo el
    repositorio empieza por ella -- incluidos los artefactos de los plugins, que tienen su propia
    etiqueta --. La pertenencia se decide por la unidad RESUELTA, no por el prefijo."""
    assert ficha.es_de_la_unidad("docs/notas/SKILL.md", ".", _UNIDADES)
    assert not ficha.es_de_la_unidad(
        "plugins/contratos/skills/x/SKILL.md", ".", _UNIDADES)


def test_un_repositorio_que_es_UNA_sola_unidad_alcanza_a_todos_sus_artefactos():
    unica = [{"nombre": "demo.plataforma", "subruta": "."}]
    assert ficha.es_de_la_unidad("skills/crear/SKILL.md", ".", unica)


def test_la_unidad_ANIDADA_gana_sobre_la_que_la_contiene():
    anidadas = [
        {"nombre": "demo.fuera", "subruta": "plugins/uno"},
        {"nombre": "demo.dentro", "subruta": "plugins/uno/interno"},
    ]
    ruta = "plugins/uno/interno/skills/x/SKILL.md"

    assert ficha.es_de_la_unidad(ruta, "plugins/uno/interno", anidadas)
    assert not ficha.es_de_la_unidad(ruta, "plugins/uno", anidadas)


# ── una sola definicion de pertenencia ──────────────────────────────────────────────────────
def test_un_nombre_de_unidad_que_es_prefijo_de_otro_no_se_lleva_sus_artefactos():
    """CLAVA EL COMPORTAMIENTO al unificar la pertenencia en una sola regla (G2/P9).

    NO es la regresion de un defecto vivo, y conviene decirlo: la copia que `ficha` tenia resolvia
    por `startswith` y la unica regla resuelve por SEGMENTOS de ruta, pero aquella comparaba contra
    `<subruta>/` -- con la barra --, asi que ya daba la respuesta correcta aqui. Se comprobo antes de
    sustituirla. Lo que esta prueba fija es que la respuesta sigue siendo esa despues del cambio, que
    es lo unico que se puede afirmar de una unificacion sin cambio de comportamiento.
    """
    vecinas = [
        {"nombre": "demo.referencia", "subruta": "plugins/referencia"},
        {"nombre": "demo.referencia-vieja", "subruta": "plugins/referencia-vieja"},
    ]
    ruta = "plugins/referencia-vieja/skills/x/SKILL.md"

    assert ficha.es_de_la_unidad(ruta, "plugins/referencia-vieja", vecinas)
    assert not ficha.es_de_la_unidad(ruta, "plugins/referencia", vecinas)
    assert ficha.plugin_que_contiene(ruta, vecinas) == "demo.referencia-vieja"


def test_la_ficha_y_el_gate_atribuyen_cada_artefacto_a_LA_MISMA_unidad():
    """La pertenencia tiene un solo dueño: `reglas_layout.unidad_de`. Si `ficha` volviera a tener
    su propia copia, el gate exigiria subir la version de una unidad y la ficha sellaria otra.
    """
    unidades = [
        {"nombre": "demo.fuera", "subruta": "plugins/uno"},
        {"nombre": "demo.dentro", "subruta": "plugins/uno/interno"},
        {"nombre": "demo.suelto", "subruta": "skills/revisar-jql"},
        {"nombre": "demo.raiz", "subruta": "."},
    ]
    subrutas = [u["subruta"] for u in unidades]
    rutas = (
        "plugins/uno/skills/x/SKILL.md",
        "plugins/uno/interno/skills/x/SKILL.md",
        "skills/revisar-jql/SKILL.md",
        "docs/notas/SKILL.md",
    )

    for ruta in rutas:
        segun_el_gate = reglas_layout.unidad_de(ruta, subrutas)
        assert ficha.es_de_la_unidad(ruta, segun_el_gate, unidades), ruta
