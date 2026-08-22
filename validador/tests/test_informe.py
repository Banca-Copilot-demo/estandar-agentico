"""Pruebas del adaptador de informe. Puras: `render` y `render_json` devuelven texto, asi que no
hay que capturar stdout para verificarlos.

El JSON se prueba con mas detalle que el texto a proposito: el texto lo lee una persona, que
perdona un cambio de formato; el JSON es el PREDICADO que se firma, y ahi un cambio de forma rompe
a quien lo verifique despues.
"""
from __future__ import annotations

import json

from validador_agentico.adaptadores import informe
from validador_agentico.dominio.hallazgo import Hallazgo, Inventario, Severidad, Veredicto

UN_ERROR = Hallazgo(Severidad.ERROR, "SKILL.md:1", "falta `description`")
UN_AVISO = Hallazgo(Severidad.AVISO, "SKILL.md", "el cuerpo es largo")


def _veredicto(*hallazgos: Hallazgo) -> Veredicto:
    return Veredicto(hallazgos=hallazgos, inventario=Inventario(skills=1, tiene_plugin=True))


def test_los_errores_se_listan_antes_de_los_avisos():
    # Al reves, lo que bloquea queda sepultado bajo los avisos en el registro de CI.
    texto = informe.render(_veredicto(UN_AVISO, UN_ERROR), "repo")
    assert texto.index("falta `description`") < texto.index("el cuerpo es largo")


def test_el_texto_dice_no_conforme_cuando_hay_un_error():
    assert "NO CONFORME" in informe.render(_veredicto(UN_ERROR), "repo")


def test_el_texto_dice_conforme_cuando_solo_hay_avisos():
    texto = informe.render(_veredicto(UN_AVISO), "repo")
    assert "CONFORME" in texto and "NO CONFORME" not in texto


def test_el_predicado_es_json_valido_y_declara_su_version_de_formato():
    predicado = json.loads(informe.render_json(_veredicto(UN_AVISO), "repo"))
    assert predicado["formato_version"]


def test_el_predicado_es_estable_entre_ejecuciones():
    # Se firma: si el mismo veredicto se serializara distinto, dos publicaciones del mismo
    # contenido darian predicados distintos y no se podrian comparar.
    veredicto = _veredicto(UN_ERROR, UN_AVISO)
    assert informe.render_json(veredicto, "repo") == informe.render_json(veredicto, "repo")


def test_el_predicado_NO_lleva_los_mensajes_de_los_hallazgos():
    """El predicado se FIRMA y no se puede revocar, asi que lo que entra ahi es permanente. Los
    mensajes llevan rutas internas y describen por donde flojea el repositorio: es lo unico del
    predicado que nadie consume -- se comprobo en toda la cadena -- y lo mas sensible que contenia.
    El detalle sigue en el informe del run y en las anotaciones del PR, que si son borrables."""
    predicado = json.loads(informe.render_json(_veredicto(UN_ERROR, UN_AVISO), "repo"))
    for prohibido in ("mensaje", "donde", "severidad"):
        assert prohibido not in json.dumps(predicado), f"el predicado filtra `{prohibido}`"


def test_los_avisos_van_como_RECUENTO_y_no_como_lista():
    # Se conserva la senal «paso con N reservas», que es lo unico que aportaban.
    predicado = json.loads(informe.render_json(_veredicto(UN_ERROR, UN_AVISO), "repo"))
    assert predicado["avisos"] == 1
    assert predicado["conforme"] is False


def test_el_predicado_NO_emite_errores():
    """En una atestacion publicada la lista era SIEMPRE vacia: el CLI devuelve codigo distinto de
    cero cuando hay errores, asi que la publicacion aborta antes de firmar. Un campo que no puede
    tener contenido induce a pensar que un veredicto sellado podria traer errores."""
    predicado = json.loads(informe.render_json(_veredicto(UN_ERROR, UN_AVISO), "repo"))
    assert "errores" not in predicado


def test_el_predicado_lleva_el_inventario_real_para_poder_auditarlo_despues():
    predicado = json.loads(informe.render_json(_veredicto(), "repo"))
    assert predicado["inventario"]["skills"] == 1
    assert predicado["inventario"]["tiene_plugin"] is True


def test_el_predicado_no_lleva_rutas_de_la_maquina_que_lo_genero():
    """Lo que se firma se publica: una ruta local seria una fuga y ademas no resolveria en
    ninguna otra maquina."""
    predicado = informe.render_json(_veredicto(UN_ERROR), "agentes-sdlc")
    assert "/home/" not in predicado and "C:\\" not in predicado
