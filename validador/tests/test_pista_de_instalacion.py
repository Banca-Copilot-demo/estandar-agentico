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


# ── el artefacto suelto publicado como su propia unidad ─────────────────────────────────────
_SUELTOS = [
    {"nombre": "demo.sdlc.revisar-jql", "subruta": "skills/revisar-jql"},
    {"nombre": "demo.sdlc.resumir", "subruta": "commands/resumir"},
    {"nombre": "demo.sdlc.auditor", "subruta": "agents/auditor"},
]


@pytest.mark.parametrize("tipo, ruta, esperado", [
    ("skill", "skills/revisar-jql/SKILL.md", "demo.sdlc.revisar-jql"),
    ("prompt", "commands/resumir/commands/demo.sdlc.resumir.prompt.md", "demo.sdlc.resumir"),
    ("agent", "agents/auditor/agents/demo.sdlc.auditor.agent.md", "demo.sdlc.auditor"),
])
def test_un_suelto_con_unidad_propia_se_instala_DESDE_EL_CATALOGO(tipo, ruta, esperado):
    """El `install_hint` es lo unico que el consumidor EJECUTA, asi que es donde se decide si pasa
    por el catalogo o se lo salta. Un suelto que se instalara por su canal propio -- `gh skill
    install` o `curl` -- resolveria contra el repositorio y la etiqueta, sin tocar el catalogo: y
    entonces el ESTADO no lo gobierna, que es justo lo que la publicacion por unidad evita.

    EL PROMPT ES EL CASO QUE FALTABA: se excluia por un comentario que decia que no era componente de
    plugin. La referencia de Copilot SI lo lista, con la particularidad de no tener ruta por defecto,
    y al declararla el cliente cambia lo que copia -- prueba de que la lee --.
    """
    artefacto = {"tipo": tipo, "ruta": ruta}
    plugin = fichas.plugin_que_contiene(ruta, _SUELTOS)

    assert plugin == esperado
    pista = fichas._pista_de_instalacion(artefacto, True, "org/repo", "0" * 40, "x--v0.1.0", plugin)
    assert pista == f"copilot plugin install {esperado}@{fichas.CATALOGO}", pista


def test_un_suelto_SIN_plugin_no_manda_a_instalar_del_catalogo():
    """REGRESION de un defecto latente: `en_marketplace` miraba si el REPOSITORIO tenia algun plugin,
    no si ESTE artefacto pertenecia a uno. Un suelto sin manifiesto en un repositorio con plugins
    daba `plugin install @agentico` -- con el nombre vacio, un comando que no resuelve --.

    Dejo de ser teorico al poder publicar sueltos por unidad: en el mismo repositorio conviven ahora
    sueltos con manifiesto y sin el.
    """
    assert fichas.plugin_que_contiene("skills/sin-manifiesto/SKILL.md", _SUELTOS) == ""
