"""Pruebas de las reglas de artefacto. Sin disco y sin repositorio: el dominio es puro, asi que
recibe diccionarios y devuelve hallazgos.

Cada prueba nombra el DEFECTO que cubre, no la funcion que llama: si falla, el nombre ya dice que
se rompio.
"""
from __future__ import annotations

from validador_agentico.dominio.especificacion import MAX_CARACTERES_DESCRIPCION, MAX_LINEAS_SKILL
from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_artefacto import (
    revisar_envelope,
    revisar_prompt,
    revisar_skill,
)

ENVELOPE_COMPLETO = {
    "id": "demo.sdlc.ejemplo",
    "owner_team": "squad-sdlc",
    "owner_contact": "squad-sdlc@ejemplo.dev",
    "status": "draft",
    "version": "1.0.0",
    "data_classification": "internal",
    "standard_version": "7.0.0",
}


def _mensajes(hallazgos) -> str:
    return " | ".join(h.mensaje for h in hallazgos)


def _errores(hallazgos):
    return [h for h in hallazgos if h.severidad is Severidad.ERROR]


# ── envelope ───────────────────────────────────────────────────────────────────────────────
def test_envelope_completo_no_produce_hallazgos():
    assert revisar_envelope("x", ENVELOPE_COMPLETO) == []


def test_falta_cada_campo_del_envelope_produce_un_error():
    for campo in ENVELOPE_COMPLETO:
        incompleto = {k: v for k, v in ENVELOPE_COMPLETO.items() if k != campo}
        errores = _errores(revisar_envelope("x", incompleto))
        assert any(campo in h.mensaje for h in errores), f"no se detecto la falta de {campo}"


def test_estado_invalido_es_error_y_estado_avanzado_es_aviso():
    assert _errores(revisar_envelope("x", {**ENVELOPE_COMPLETO, "status": "inventado"}))
    avanzado = revisar_envelope("x", {**ENVELOPE_COMPLETO, "status": "certified"})
    assert avanzado and avanzado[0].severidad is Severidad.AVISO
    assert "DERIVAN" in avanzado[0].mensaje


def test_version_no_semver_es_error():
    # Verificado: al instalar, `version: "1.0.0"` pierde las comillas; con `1.10` el valor se
    # interpretaria como numero y perderia el cero.
    for mala in ("1.0", "v1.0.0", "1.10"):
        assert _errores(revisar_envelope("x", {**ENVELOPE_COMPLETO, "version": mala})), mala


def test_contacto_sin_arroba_es_solo_aviso():
    hallazgos = revisar_envelope("x", {**ENVELOPE_COMPLETO, "owner_contact": "squad-sdlc"})
    assert hallazgos and all(h.severidad is Severidad.AVISO for h in hallazgos)


# ── skill ──────────────────────────────────────────────────────────────────────────────────
def _skill(**cambios) -> dict:
    base = {"name": "mi-skill", "description": "Hace algo y se usa cuando pasa aquello.",
            "metadata": ENVELOPE_COMPLETO}
    return {**base, **cambios}


def test_skill_conforme_no_produce_hallazgos():
    assert revisar_skill("x", "mi-skill", _skill(), lineas_cuerpo=100) == []


def test_name_distinto_del_directorio_es_error():
    errores = _errores(revisar_skill("x", "otro-directorio", _skill(), 10))
    assert "no coincide con el directorio" in _mensajes(errores)


def test_allowed_tools_como_lista_es_error():
    # La forma natural de escribirlo en YAML es una lista, y la especificacion exige una CADENA.
    errores = _errores(revisar_skill("x", "mi-skill",
                                     _skill(allowed_tools_es_lista=True), 10))
    assert "CADENA" in _mensajes(errores)


def test_sin_description_es_error_porque_es_el_mecanismo_de_seleccion():
    errores = _errores(revisar_skill("x", "mi-skill", _skill(description=""), 10))
    assert "description" in _mensajes(errores)


def test_description_demasiado_larga_es_error():
    larga = "a" * (MAX_CARACTERES_DESCRIPCION + 1)
    assert _errores(revisar_skill("x", "mi-skill", _skill(description=larga), 10))


def test_skill_muy_largo_es_aviso_y_no_bloquea():
    hallazgos = revisar_skill("x", "mi-skill", _skill(), MAX_LINEAS_SKILL + 1)
    assert hallazgos and all(h.severidad is Severidad.AVISO for h in hallazgos)


# ── prompt ─────────────────────────────────────────────────────────────────────────────────
def _prompt(**cambios) -> dict:
    base = {"description": "Ejecuta el paso de migracion.", "metadata": ENVELOPE_COMPLETO}
    return {**base, **cambios}


def test_prompt_conforme_no_produce_hallazgos():
    assert revisar_prompt("x", _prompt()) == []


def test_model_como_array_es_error():
    # Defecto medido en el activo del cliente: la misma lista de 4 modelos repetida en 13 archivos.
    errores = _errores(revisar_prompt("x", _prompt(model_es_array=True)))
    assert "model_allowlist" in _mensajes(errores)


def test_skills_reference_es_error_porque_no_es_estandar():
    # Defecto medido: el campo lo invento el equipo, y contenia una ruta del escritorio de un
    # desarrollador que no resuelve en ninguna otra maquina.
    errores = _errores(revisar_prompt("x", _prompt(tiene_skills_reference=True)))
    assert "dependencies" in _mensajes(errores)
