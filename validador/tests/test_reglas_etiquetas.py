"""Como se llama la etiqueta de una unidad publicable.

EL DEFECTO QUE CUBREN se midio en `agentes-sdlc`: la etiqueta del conjunto suelto salio `v1.0.0`
conviviendo con cuatro etiquetas nombradas, y ahi `v1.0.0` significaba «todo excepto los plugins» --
una definicion por RESTA que nadie deduce leyendo la etiqueta --.

POR QUE NO SE VIO ANTES: la regla vivia en tres lineas de bash dentro del workflow de etiquetado, donde
ninguna prueba la alcanzaba. Y es el contrato mas caro de equivocar de la cadena, porque con releases
inmutables una etiqueta mal puesta NO SE BORRA.
"""
from __future__ import annotations

import pytest

from validador_agentico.dominio.reglas_etiquetas import etiqueta_de


def test_una_unidad_sola_usa_la_forma_CORTA():
    """Con una sola unidad la etiqueta se refiere al repositorio y no hay nada que desambiguar, sea
    ese repositorio un plugin o un conjunto de sueltos."""
    assert etiqueta_de("demo.sdlc.contratos", "1.2.3", unidad_unica=True) == "v1.2.3"
    assert etiqueta_de("demo.sdlc.sueltos", "1.0.0", unidad_unica=True) == "v1.0.0"


def test_con_vecinas_la_etiqueta_dice_QUE_publica():
    assert etiqueta_de("demo.sdlc.contratos", "1.2.3",
                       unidad_unica=False) == "demo.sdlc.contratos--v1.2.3"


def test_el_conjunto_suelto_de_un_repo_mixto_va_NOMBRADO():
    # El caso exacto que produjo el defecto: la subruta es `.` pero NO esta solo.
    assert etiqueta_de("demo.sdlc.sueltos", "1.0.0",
                       unidad_unica=False) == "demo.sdlc.sueltos--v1.0.0"


def test_la_misma_unidad_cambia_de_etiqueta_segun_tenga_vecinas():
    """Es lo que el `if` de bash no sabia: la forma no depende de la unidad, depende del REPOSITORIO.
    Por eso `unidad_unica` es un parametro y no algo que la regla pueda deducir."""
    sola = etiqueta_de("demo.sdlc.x", "1.0.0", unidad_unica=True)
    acompañada = etiqueta_de("demo.sdlc.x", "1.0.0", unidad_unica=False)
    assert sola != acompañada, (sola, acompañada)


@pytest.mark.parametrize("nombre", ["catalogo-datos", "demo.sdlc.catalogo-datos"])
def test_un_nombre_con_guiones_sigue_siendo_separable(nombre):
    # El separador es `--v` y no `-` justamente por esto: los nombres de plugin llevan guiones, y con
    # un separador de un guion `catalogo-datos-v1.0.0` seria ambiguo.
    etiqueta = etiqueta_de(nombre, "1.0.0", unidad_unica=False)
    assert etiqueta.rsplit("--v", 1) == [nombre, "1.0.0"], etiqueta
