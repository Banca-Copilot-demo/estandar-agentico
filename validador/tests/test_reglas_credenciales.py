"""Pruebas de la regla de custodia de credenciales de un `mcp`. Puras: reciben el bloque y devuelven
hallazgos.

El defecto que cubren no es tecnico, es de enrutado: el artefacto viaja sin secreto y el prompt del
cliente aparece en la maquina del desarrollador, que no sabe a que equipo pedirselo. La regla obliga a
declararlo, y solo cuando de verdad hace falta.
"""
from __future__ import annotations

from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_credenciales import (
    MecanismoCredencial,
    revisar_credenciales,
)

PROPIEDAD_COMPLETA = {
    "credential_owner": "equipo-jira",
    "access_request_url": "https://itsm.ejemplo.dev/solicitar/jira-token",
    "entitlement": "grp-jira-lectura",
    "secret_ref": "op://plataforma/jira/token",
}


def _errores(hallazgos):
    return [h for h in hallazgos if h.severidad is Severidad.ERROR]


def _mensajes(hallazgos) -> str:
    return " | ".join(h.mensaje for h in hallazgos)


# ── cuando SÍ se exige ──────────────────────────────────────────────────────────────────────
def test_secret_ref_con_dueno_y_via_de_solicitud_no_produce_hallazgos():
    completo = {"mechanism": "secret-ref", "ownership": PROPIEDAD_COMPLETA}
    assert revisar_credenciales(".mcp.json", completo) == []


def test_secret_ref_sin_dueno_es_error():
    """El defecto que cubre: el desarrollador se queda ante el prompt del cliente sin saber a quien
    pedir el token. El owner_team del artefacto es quien lo PUBLICO, no quien lo custodia."""
    sin_dueno = {"mechanism": "secret-ref",
                 "ownership": {k: v for k, v in PROPIEDAD_COMPLETA.items()
                               if k != "credential_owner"}}
    errores = _errores(revisar_credenciales(".mcp.json", sin_dueno))
    assert "credential_owner" in _mensajes(errores)


def test_secret_ref_sin_via_de_solicitud_es_error():
    # Saber el equipo no basta: hace falta saber DONDE se pide, o el flujo acaba en un correo.
    sin_url = {"mechanism": "secret-ref",
               "ownership": {k: v for k, v in PROPIEDAD_COMPLETA.items()
                             if k != "access_request_url"}}
    assert "access_request_url" in _mensajes(_errores(revisar_credenciales(".mcp.json", sin_url)))


def test_secret_ref_sin_bloque_de_propiedad_reporta_LOS_DOS_campos():
    # Agrega en vez de parar en el primero: el autor corrige una vez, no dos.
    errores = _errores(revisar_credenciales(".mcp.json", {"mechanism": "secret-ref"}))
    assert len(errores) == 2


def test_un_dueno_que_parece_persona_es_aviso_y_no_bloquea():
    """La regla viene de Backstage: SIEMPRE un grupo. Un dueno individual deja la entrada huerfana en
    cuanto esa persona cambia de puesto. Es aviso y no error porque el correo de un equipo tambien
    lleva arroba y no queremos rechazar `plataforma@banco.com`."""
    persona = {"mechanism": "secret-ref",
               "ownership": {**PROPIEDAD_COMPLETA, "credential_owner": "juan.perez@ejemplo.dev"}}
    hallazgos = revisar_credenciales(".mcp.json", persona)
    assert hallazgos
    assert all(h.severidad is Severidad.AVISO for h in hallazgos)
    assert "declara un EQUIPO" in _mensajes(hallazgos)


# ── cuando NO se exige ──────────────────────────────────────────────────────────────────────
def test_oauth_no_exige_dueno_porque_no_hay_nada_que_conceder():
    """Con oauth el desarrollador se autentica con su PROPIA identidad: no hay secreto que pedir, asi
    que exigir un custodio seria pedir un dato que no existe."""
    assert revisar_credenciales(".mcp.json", {"mechanism": "oauth"}) == []


def test_ni_workload_identity_ni_none_exigen_dueno():
    for mecanismo in (MecanismoCredencial.IDENTIDAD_DE_CARGA, MecanismoCredencial.NINGUNO):
        assert revisar_credenciales(".mcp.json", {"mechanism": mecanismo.value}) == [], mecanismo


# ── el bloque mismo ─────────────────────────────────────────────────────────────────────────
def test_sin_bloque_credentials_es_error():
    assert _errores(revisar_credenciales(".mcp.json", None))
    assert _errores(revisar_credenciales(".mcp.json", {}))


def test_un_mecanismo_inventado_es_error_y_lista_los_validos():
    errores = _errores(revisar_credenciales(".mcp.json", {"mechanism": "magia"}))
    assert "invalido" in _mensajes(errores)
    assert "secret-ref" in _mensajes(errores)
