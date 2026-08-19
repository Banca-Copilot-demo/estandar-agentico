"""Pruebas del adaptador de anotaciones de GitHub Actions.

Puras: el adaptador devuelve texto, asi que no hace falta un runner ni capturar stdout.

Lo que se prueba con mas cuidado es el ESCAPE y la UBICACION, porque los dos fallan en silencio: una
anotacion mal formada no produce ningun error -- el runner simplemente no la muestra --, y el autor
se queda sin ver el defecto justo en el sitio donde estaba mirando.
"""
from __future__ import annotations

from validador_agentico.adaptadores.anotaciones_github import render_anotaciones, render_resumen
from validador_agentico.dominio.comprobacion import Comprobacion, Resultado, ResultadoGate
from validador_agentico.dominio.hallazgo import Inventario, Veredicto, aviso, error

CONFORME = Comprobacion("propia", Resultado.CONFORME, "sin errores")
NO_CONFORME = Comprobacion("propia", Resultado.NO_CONFORME, "1 error(es) que bloquean")


def _resultado(*hallazgos, comprobacion=NO_CONFORME) -> ResultadoGate:
    return ResultadoGate(
        veredicto=Veredicto(hallazgos=hallazgos, inventario=Inventario(skills=1)),
        comprobaciones=(comprobacion,))


# ── ubicacion ──────────────────────────────────────────────────────────────────────────────
def test_un_hallazgo_con_linea_se_ancla_a_esa_linea():
    salida = render_anotaciones(_resultado(error("SKILL.md:6", "posible token")))
    assert salida == "::error file=SKILL.md,line=6::posible token"


def test_un_hallazgo_sin_linea_se_ancla_a_la_primera_y_nunca_a_la_cero():
    """Medido en un pull request real: omitir `line` hace que GitHub registre `start_line: 0`, y una
    linea 0 no existe en ningun diff -- la anotacion no aparece sobre el archivo."""
    salida = render_anotaciones(_resultado(error("GOVERNANCE.json", "falta `owner`")))
    assert salida == "::error file=GOVERNANCE.json,line=1::falta `owner`"


def test_una_ruta_con_dos_puntos_que_no_es_linea_no_se_parte():
    """El defecto que cubre: partir por el ultimo `:` sin comprobar que lo que sigue es un numero
    convertiria `docs/a:b.md` en `file=docs/a,line=b.md`, y la anotacion se perderia."""
    salida = render_anotaciones(_resultado(error("docs/a:b.md", "algo")))
    assert salida == "::error file=docs/a:b.md,line=1::algo"


# ── severidad ──────────────────────────────────────────────────────────────────────────────
def test_un_error_es_error_y_un_aviso_es_warning():
    # Si un aviso se emitiera como `::error`, algo que no bloquea aparentaria bloquear, y el autor
    # perseguiria un defecto inexistente.
    salida = render_anotaciones(_resultado(error("a.md", "x"), aviso("b.md", "y")))
    assert salida.splitlines() == ["::error file=a.md,line=1::x",
                                   "::warning file=b.md,line=1::y"]


def test_los_errores_salen_antes_que_los_avisos():
    salida = render_anotaciones(_resultado(aviso("b.md", "aviso"), error("a.md", "error")))
    assert salida.index("::error") < salida.index("::warning")


# ── escape ─────────────────────────────────────────────────────────────────────────────────
def test_un_salto_de_linea_en_el_mensaje_se_codifica():
    """Sin codificar, el comando se corta en el salto y la anotacion no aparece."""
    salida = render_anotaciones(_resultado(error("a.md", "primera\nsegunda")))
    assert salida == "::error file=a.md,line=1::primera%0Asegunda"


def test_un_porcentaje_se_codifica_una_sola_vez():
    # El orden del escape importa: si `%` no fuera lo primero, se re-escaparian los `%` que
    # introducen los demas y el mensaje saldria como `%250A`.
    salida = render_anotaciones(_resultado(error("a.md", "100% y\nsalto")))
    assert salida == "::error file=a.md,line=1::100%25 y%0Asalto"


def test_sin_hallazgos_no_se_emite_ninguna_anotacion():
    assert render_anotaciones(_resultado(comprobacion=CONFORME)) == ""


# ── resumen ────────────────────────────────────────────────────────────────────────────────
def test_el_resumen_dice_el_veredicto_antes_del_detalle():
    resumen = render_resumen(_resultado(error("a.md", "x")), "agentes-sdlc")
    assert resumen.index("NO CONFORME") < resumen.index("a.md")


def test_el_resumen_de_un_gate_conforme_no_pide_corregir_nada():
    resumen = render_resumen(_resultado(comprobacion=CONFORME), "agentes-sdlc")
    assert "CONFORME" in resumen
    assert "Corrige" not in resumen


def test_el_resumen_lista_cada_comprobacion_con_su_resultado():
    resultado = ResultadoGate(
        veredicto=Veredicto(hallazgos=(), inventario=Inventario()),
        comprobaciones=(CONFORME, Comprobacion("oficial", Resultado.NO_APLICA, "sin skills")))
    resumen = render_resumen(resultado, "repo")
    assert "| propia | conforme |" in resumen
    assert "| oficial | no aplica | sin skills |" in resumen
