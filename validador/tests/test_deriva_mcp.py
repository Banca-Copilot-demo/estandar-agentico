"""Pruebas de la comparacion entre lo atestado y lo que un servidor MCP declara hoy.

El defecto que estas pruebas cubren no es de calculo, es de CLASIFICACION: si «no se pudo comprobar»
se tratara como «esta en orden», un servidor sin vigilancia pasaria por vigilado indefinidamente, y
nadie lo notaria precisamente porque no hay alarma.
"""
from __future__ import annotations

from validador_agentico.dominio.deriva_mcp import Resultado, comparar, resumir

ATESTADO = "a" * 64
OTRO = "b" * 64


# ── los tres resultados ─────────────────────────────────────────────────────────────────────
def test_el_mismo_digest_es_conforme():
    c = comparar("demo.x", ATESTADO, ATESTADO)
    assert c.resultado is Resultado.CONFORME
    assert not c.exige_atencion


def test_un_digest_distinto_es_deriva():
    c = comparar("demo.x", ATESTADO, OTRO)
    assert c.resultado is Resultado.DERIVA
    assert c.exige_atencion


def test_no_poder_consultar_el_servidor_NO_es_conforme():
    """Es la clasificacion que importa: sin comprobar no es en orden. Si se leyera como conforme, un
    servidor sin credencial pasaria por vigilado para siempre."""
    c = comparar("demo.x", ATESTADO, None, motivo_de_fallo="no hay credencial en la boveda")
    assert c.resultado is Resultado.SIN_COMPROBAR
    assert c.exige_atencion
    assert "credencial" in c.motivo


def test_sin_linea_base_atestada_tampoco_es_conforme():
    """Un `mcp` aprobado antes de que existiera este control no tiene contra que compararse. No es
    conforme: es que no se puede saber."""
    c = comparar("demo.x", "", ATESTADO)
    assert c.resultado is Resultado.SIN_COMPROBAR
    assert "linea base" in c.motivo


# ── que se reporta de una deriva ────────────────────────────────────────────────────────────
def test_la_deriva_dice_que_herramientas_entraron_y_salieron():
    c = comparar("demo.x", ATESTADO, OTRO,
                 nombres_atestados=("leer", "buscar"), nombres_actuales=("leer", "borrar"))
    assert c.herramientas_nuevas == ("borrar",)
    assert c.herramientas_retiradas == ("buscar",)


def test_un_cambio_de_DESCRIPCION_se_reporta_aunque_la_lista_sea_identica():
    """Es el caso mas peligroso: el conjunto de herramientas parece intacto y lo que cambio es lo que
    el modelo lee. Si el resumen dijera solo «nuevas/retiradas: ninguna», pareceria un falso
    positivo."""
    c = comparar("demo.x", ATESTADO, OTRO,
                 nombres_atestados=("leer",), nombres_actuales=("leer",))
    assert c.resultado is Resultado.DERIVA
    assert "descripcion" in resumir([c])


# ── el reporte no filtra texto del proveedor ────────────────────────────────────────────────
def test_el_resumen_no_lleva_texto_del_proveedor():
    """Las descripciones las controla un tercero. Volcarlas en un issue las convertiria en inyeccion
    de prompt dirigida a quien lo lea, o a un agente que revise issues."""
    c = comparar("demo.x", ATESTADO, OTRO,
                 nombres_atestados=("leer",), nombres_actuales=("leer", "exfiltrar"))
    texto = resumir([c])
    assert "exfiltrar" in texto, "los NOMBRES si se reportan: sin ellos no se sabe donde mirar"
    for campo in ("description", "inputSchema", "Ignora las instrucciones"):
        assert campo not in texto


def test_lo_que_exige_atencion_sale_primero_en_el_resumen():
    # Un resumen con veinte conformes y una deriva al final entierra lo unico que importa.
    conforme = comparar("demo.conforme", ATESTADO, ATESTADO)
    deriva = comparar("demo.deriva", ATESTADO, OTRO)
    filas = resumir([conforme, deriva]).splitlines()
    assert "demo.deriva" in filas[2]


def test_sin_mcp_que_comprobar_el_resumen_lo_dice():
    assert "No hay ningun" in resumir([])
