"""Pruebas de la regla del indice. Puras: la regla recibe un candidato y devuelve una decision.

Cada prueba cubre UNA forma de colarse en el indice sin estar probado. Son las pruebas mas
importantes del repositorio: si una de estas se rompe, el estandar deja de ser exigible aunque todo
lo demas siga en verde.
"""
from __future__ import annotations

from indice_agentico.dominio.candidato import Candidato, Motivo
from indice_agentico.dominio.reglas_indice import evaluar

MANIFIESTO = {"name": "migracion-cnf", "description": "Skills del dominio SDLC.",
              "version": "0.2.0"}
VEREDICTO_CONFORME = {"conforme": True, "errores": [], "avisos": []}


def _candidato(**cambios) -> Candidato:
    base = {"repositorio": "Banca-Copilot-demo/agentes-sdlc", "etiqueta": "v0.2.0",
            "sha": "a" * 40, "digest": "b" * 64, "manifiesto": MANIFIESTO,
            "atestacion_verificada": True, "veredicto": VEREDICTO_CONFORME}
    return Candidato(**{**base, **cambios})


def test_un_candidato_probado_y_conforme_se_indexa():
    entrada, motivo = evaluar(_candidato())
    assert motivo is None
    assert entrada.name == "migracion-cnf"
    assert entrada.version == "0.2.0"
    assert entrada.sha == "a" * 40


def test_sin_atestacion_verificada_no_se_indexa():
    """El hueco que cierra: `publicar.yml` vive en el repo del dominio y es editable. Quitar el
    paso de atestacion NO debe servir para publicar contenido sin sellar."""
    _, motivo = evaluar(_candidato(atestacion_verificada=False))
    assert motivo is Motivo.SIN_ATESTACION


def test_con_procedencia_pero_sin_veredicto_no_se_indexa():
    # La procedencia prueba de DONDE salio; no prueba que pasara ningun gate. Hacen falta las dos.
    _, motivo = evaluar(_candidato(veredicto=None))
    assert motivo is Motivo.SIN_VEREDICTO


def test_un_veredicto_negativo_atestado_no_se_indexa():
    # Se puede firmar un veredicto que diga que no es conforme: firmar no es aprobar.
    _, motivo = evaluar(_candidato(veredicto={"conforme": False, "errores": [{"mensaje": "x"}]}))
    assert motivo is Motivo.NO_CONFORME


def test_sin_paquete_no_se_indexa():
    _, motivo = evaluar(_candidato(digest=None))
    assert motivo is Motivo.SIN_PAQUETE


def test_sin_manifiesto_dentro_del_paquete_no_se_indexa():
    _, motivo = evaluar(_candidato(manifiesto=None))
    assert motivo is Motivo.SIN_MANIFIESTO


def test_version_del_manifiesto_distinta_de_la_etiqueta_no_se_indexa():
    """Si difieren, el puntero dice `v0.2.0` y el contenido se declara `0.1.0`: el consumidor no
    puede saber que instalo, y el numero de version deja de servir para nada."""
    _, motivo = evaluar(_candidato(manifiesto={**MANIFIESTO, "version": "0.1.0"}))
    assert motivo is Motivo.VERSION_DISCREPANTE


def test_la_etiqueta_sin_v_tambien_vale():
    entrada, motivo = evaluar(_candidato(etiqueta="0.2.0"))
    assert motivo is None and entrada.version == "0.2.0"


def test_un_manifiesto_sin_description_no_bloquea_pero_deja_rastro():
    entrada, motivo = evaluar(_candidato(manifiesto={"name": "x", "version": "0.2.0"}))
    assert motivo is None
    assert "sin descripcion" in entrada.description
