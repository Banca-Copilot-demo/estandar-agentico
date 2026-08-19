"""Pruebas de la regla del indice. Puras: la regla recibe un candidato y devuelve una decision.

Cada prueba cubre UNA forma de colarse en el indice sin estar probado. Son las pruebas mas
importantes del repositorio: si una de estas se rompe, el estandar deja de ser exigible aunque todo
lo demas siga en verde.
"""
from __future__ import annotations

from indice_agentico.dominio.candidato import Candidato, Destino, Motivo
from indice_agentico.dominio.reglas_indice import evaluar

MANIFIESTO = {"name": "migracion-cnf", "description": "Skills del dominio SDLC.",
              "version": "0.2.0"}
VEREDICTO_CONFORME = {"conforme": True, "errores": [], "avisos": []}


def _candidato(**cambios) -> Candidato:
    base = {"repositorio": "organizacion/agentes-sdlc", "etiqueta": "v0.2.0",
            "sha": "a" * 40, "digest": "b" * 64, "lleva_plugin": True,
            "manifiesto": MANIFIESTO, "atestacion_verificada": True,
            "veredicto": VEREDICTO_CONFORME}
    return Candidato(**{**base, **cambios})


def test_un_candidato_probado_y_conforme_se_indexa():
    decision = evaluar(_candidato())
    assert decision.destino is Destino.INDEXAR
    assert decision.entrada.name == "migracion-cnf"
    assert decision.entrada.version == "0.2.0"
    assert decision.entrada.sha == "a" * 40


def test_sin_atestacion_verificada_no_se_indexa():
    """El hueco que cierra: `publicar.yml` vive en el repo del dominio y es editable. Quitar el
    paso de atestacion NO debe servir para publicar contenido sin sellar."""
    decision = evaluar(_candidato(atestacion_verificada=False))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SIN_ATESTACION


def test_con_procedencia_pero_sin_veredicto_no_se_indexa():
    # La procedencia prueba de DONDE salio; no prueba que pasara ningun gate. Hacen falta las dos.
    decision = evaluar(_candidato(veredicto=None))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SIN_VEREDICTO


def test_un_veredicto_negativo_atestado_no_se_indexa():
    # Se puede firmar un veredicto que diga que no es conforme: firmar no es aprobar.
    decision = evaluar(_candidato(veredicto={"conforme": False, "errores": [{"mensaje": "x"}]}))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.NO_CONFORME


def test_sin_paquete_no_se_indexa():
    decision = evaluar(_candidato(digest=None))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SIN_PAQUETE


def test_version_del_manifiesto_distinta_de_la_etiqueta_no_se_indexa():
    """Si difieren, el puntero dice `v0.2.0` y el contenido se declara `0.1.0`: el consumidor no
    puede saber que instalo, y el numero de version deja de servir para nada."""
    decision = evaluar(_candidato(manifiesto={**MANIFIESTO, "version": "0.1.0"}))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.VERSION_DISCREPANTE


def test_la_etiqueta_sin_v_tambien_vale():
    decision = evaluar(_candidato(etiqueta="0.2.0"))
    assert decision.destino is Destino.INDEXAR
    assert decision.entrada.version == "0.2.0"


def test_un_manifiesto_sin_description_no_bloquea_pero_deja_rastro():
    decision = evaluar(_candidato(manifiesto={"name": "x", "version": "0.2.0"}))
    assert decision.destino is Destino.INDEXAR
    assert "sin descripcion" in decision.entrada.description
