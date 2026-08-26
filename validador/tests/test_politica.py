"""La politica de promocion: quien entra al catalogo instalable y quien no.

POR QUE IMPORTA QUE ESTO TENGA PRUEBAS. Es la regla que decide si un artefacto se distribuye a toda la
organizacion, y el cliente ya cambio de criterio una vez sobre ella. Lo que estas pruebas fijan no es el
valor elegido -- ese cambiara -- sino que **cambiarlo sea un dato y no una reescritura**, y que
equivocarse al configurarlo falle del lado seguro.
"""
from __future__ import annotations

import pytest

from validador_agentico.dominio.politica import (
    ESTADO_AL_PUBLICAR,
    ESTADO_CERTIFICADO,
    PROMOCION_POR_DEFECTO,
    Promocion,
    entra_al_catalogo,
    promocion_declarada,
)


# ── lo que no cambia entre politicas ────────────────────────────────────────────────────────
@pytest.mark.parametrize("promocion", list(Promocion), ids=[p.value for p in Promocion])
def test_lo_certificado_se_distribuye_con_cualquier_politica(promocion):
    """Certificado es el estado que la politica NO discute: si supero la evaluacion, se distribuye.
    Una politica que pudiera excluirlo dejaria el catalogo vacio sin que nadie lo hubiera pedido."""
    assert entra_al_catalogo(ESTADO_CERTIFICADO, promocion)


@pytest.mark.parametrize("estado", ["suspended", "deprecated", "retired"])
@pytest.mark.parametrize("promocion", list(Promocion), ids=[p.value for p in Promocion])
def test_ningun_estado_de_salida_entra_al_catalogo(estado, promocion):
    """Suspendido, Obsoleto y Retirado salen del catalogo por su propio flujo. Si la politica de
    promocion pudiera devolverlos, una suspension urgente se desharia sola al republicar."""
    assert not entra_al_catalogo(estado, promocion)


# ── lo que si cambia ────────────────────────────────────────────────────────────────────────
def test_con_al_certificar_lo_conforme_NO_se_distribuye():
    assert not entra_al_catalogo(ESTADO_AL_PUBLICAR, Promocion.AL_CERTIFICAR)


def test_con_al_publicar_lo_conforme_SI_se_distribuye():
    """El comportamiento anterior a que el cliente pidiera separar publicar de distribuir. Se
    conserva alcanzable: cambiar de opinion debe costar un valor, no una reescritura."""
    assert entra_al_catalogo(ESTADO_AL_PUBLICAR, Promocion.AL_PUBLICAR)


# ── configurar mal falla del lado seguro ────────────────────────────────────────────────────
@pytest.mark.parametrize("politica", [
    None,
    {},
    {"promocion_al_catalogo": None},
    {"promocion_al_catalogo": ""},
    {"promocion_al_catalogo": "al_publicar_todo"},
    {"promocion_al_catalogo": "AL_CERTIFICAR"},
], ids=["ausente", "vacia", "nulo", "cadena-vacia", "valor-inventado", "mayusculas"])
def test_una_politica_ilegible_cae_en_la_MAS_RESTRICTIVA(politica):
    """EL DEFECTO QUE EVITA: que un error de configuracion se lea como «distribuyelo todo».

    Es el modo de fallo que este proyecto ha encontrado una y otra vez -- el que no rompe nada y por
    eso nadie ve --. Con este default, equivocarse se nota porque algo NO se distribuye: visible y
    reversible en un minuto. Al reves, se notaria porque algo llego a toda la organizacion sin que
    nadie lo hubiera certificado, y eso no se deshace.
    """
    assert promocion_declarada(politica) is PROMOCION_POR_DEFECTO
    assert PROMOCION_POR_DEFECTO is Promocion.AL_CERTIFICAR


@pytest.mark.parametrize("promocion", list(Promocion), ids=[p.value for p in Promocion])
def test_una_politica_declarada_se_respeta(promocion):
    assert promocion_declarada({"promocion_al_catalogo": promocion.value}) is promocion
