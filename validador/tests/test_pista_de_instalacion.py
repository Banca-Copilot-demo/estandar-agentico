"""La pista de instalacion apunta AL PLUGIN QUE CONTIENE cada artefacto.

QUE DEFECTO CUBRE, y se vio mirando el catalogo REAL publicado, no el codigo. El `install_hint` se
construia con `inventario.nombre_plugin`, que es UN nombre a nivel de REPOSITORIO. En un repositorio con
cinco plugins ese unico nombre se aplicaba a los cinco, asi que cuatro de cada cinco fichas mandaban a
instalar el plugin equivocado:

    demo.sdlc.revisar-cobertura      (vive en plugins/referencia)  -> instalaba catalogo-datos
    demo.sdlc.validar-contrato-openapi (plugins/contratos)         -> instalaba catalogo-datos
    demo.sdlc.planificar-migracion   (plugins/migracion)           -> instalaba catalogo-datos
    demo.sdlc.mcp-aws-knowledge.mcp  (plugins/mcp-aws-knowledge)   -> instalaba catalogo-datos

Y NO ES UN ERROR COSMETICO NI RUIDOSO: el comando que publicaba **funciona** -- ese plugin existe -- asi
que quien lo seguia instalaba algo, no obtenia el artefacto que buscaba, y no tenia ninguna pista de por
que. Un fallo que no rompe nada es mas caro de encontrar que uno que revienta.

POR QUE NINGUNA PRUEBA LO VIO: las que habia comprobaban la `ruta` publicada y el digesto, que son los
campos que un consumidor VERIFICA. `install_hint` es el campo que un consumidor EJECUTA, y no lo miraba
nadie. La leccion se repite: lo que no se ejercita, no esta comprobado.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_RUTA_FICHAS = (Path(__file__).resolve().parents[2]
                / ".github" / "actions" / "publicar" / "fichas.py")


def _cargar_fichas():
    """El modulo vive en `.github/actions/`, fuera del paquete, asi que se carga por ruta."""
    especificacion = importlib.util.spec_from_file_location("fichas", _RUTA_FICHAS)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


fichas = _cargar_fichas()

# Los cinco plugins del repositorio de demo, tal y como el veredicto los publica.
_PLUGINS = [
    {"nombre": "demo.sdlc.catalogo-datos", "subruta": "plugins/catalogo-datos"},
    {"nombre": "demo.sdlc.contratos", "subruta": "plugins/contratos"},
    {"nombre": "demo.sdlc.mcp-aws-knowledge", "subruta": "plugins/mcp-aws-knowledge"},
    {"nombre": "demo.sdlc.migracion", "subruta": "plugins/migracion"},
    {"nombre": "demo.sdlc.referencia", "subruta": "plugins/referencia"},
]


@pytest.mark.parametrize("ruta, esperado", [
    ("plugins/referencia/skills/revisar-cobertura/SKILL.md", "demo.sdlc.referencia"),
    ("plugins/contratos/skills/validar-contrato-openapi/SKILL.md", "demo.sdlc.contratos"),
    ("plugins/migracion/skills/planificar-migracion/SKILL.md", "demo.sdlc.migracion"),
    ("plugins/mcp-aws-knowledge/.mcp.json", "demo.sdlc.mcp-aws-knowledge"),
    ("plugins/catalogo-datos/.mcp.json", "demo.sdlc.catalogo-datos"),
])
def test_cada_artefacto_apunta_a_SU_plugin(ruta, esperado):
    """Los cinco casos reales del repositorio de demo. Cuatro estaban mal."""
    assert fichas.plugin_que_contiene(ruta, _PLUGINS) == esperado


def test_un_artefacto_suelto_no_pertenece_a_ningun_plugin():
    """Un repositorio mixto tiene artefactos en la raiz, fuera de todo plugin. Devolver el nombre de
    cualquiera de ellos seria peor que no devolver nada: mandaria a instalar un paquete que NO lo
    contiene."""
    assert fichas.plugin_que_contiene("skills/revisar-jql/SKILL.md", _PLUGINS) == ""


def test_un_plugin_que_ocupa_el_repositorio_entero_si_contiene_a_todos():
    """`subruta: "."` es el caso de un repositorio que ES un solo plugin. Ahi todos los artefactos le
    pertenecen, y sin esta rama la pista quedaria vacia justo en el caso mas simple."""
    unico = [{"nombre": "demo.plataforma.agentico", "subruta": "."}]

    assert fichas.plugin_que_contiene("skills/crear/SKILL.md", unico) == "demo.plataforma.agentico"


def test_el_plugin_ANIDADO_gana_sobre_el_que_lo_contiene():
    """Con dos coincidencias de prefijo, la correcta es la MAS LARGA. Sin esa regla, un artefacto de un
    plugin anidado mandaria a instalar el de fuera, que es el mismo defecto en pequeno."""
    anidados = [
        {"nombre": "demo.fuera", "subruta": "plugins/uno"},
        {"nombre": "demo.dentro", "subruta": "plugins/uno/interno"},
    ]

    assert fichas.plugin_que_contiene("plugins/uno/interno/skills/x/SKILL.md", anidados) == "demo.dentro"


def test_un_prefijo_PARCIAL_no_cuenta_como_pertenencia():
    """`plugins/referencia-vieja` NO esta dentro de `plugins/referencia`. Sin la barra en la
    comparacion, la coincidencia de texto los daria por el mismo y la pista seria del plugin
    equivocado -- exactamente el defecto original, por otra via."""
    plugins = [{"nombre": "demo.sdlc.referencia", "subruta": "plugins/referencia"}]

    assert fichas.plugin_que_contiene("plugins/referencia-vieja/skills/x/SKILL.md", plugins) == ""
