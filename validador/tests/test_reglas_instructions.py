"""Pruebas de lo que se OBSERVA de unas `instructions`, que no son un tipo gobernado.

EL CAMBIO QUE ESTAS PRUEBAS FIJAN. Antes eran un tipo con envelope, version y deprecacion, y su
solapamiento BLOQUEABA. Se comprobo en fuente primaria que no hay canal para distribuirlas -- la
referencia de plugins de Claude Code dice que un CLAUDE.md en la raiz de un plugin no se carga como
contexto, y el conjunto de componentes de un plugin de Copilot no las incluye --, asi que un ciclo de
vida prometia un mantenimiento que ningun workflow puede hacer.

Lo que queda es higiene: dejar constancia. Y por eso lo que estas pruebas vigilan sobre todo es que
NADA de aqui bloquee: tener unas instructions locales es legitimo, y bloquear seria imponer una regla
que la herramienta no impone.
"""
from __future__ import annotations

from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_instructions import (
    LIMITE_LINEAS_SIN_TECHO,
    revisar_instructions,
    revisar_solapamiento,
)

DONDE = "plugins/x/api.instructions.md"


def _errores(hallazgos):
    return [h for h in hallazgos if h.severidad is Severidad.ERROR]


def _mensajes(hallazgos):
    return " ".join(h.mensaje for h in hallazgos)


# ── la propiedad que gobierna todo el modulo ────────────────────────────────────────────────
def test_NADA_de_instructions_bloquea_nunca():
    """Es la propiedad central. Un `.instructions.md` local es legitimo -- es como funciona el
    cliente --, asi que ningun caso puede impedir un merge: ni sin ambito, ni aplicando a todo, ni
    solapandose con otro."""
    casos = [
        revisar_instructions(DONDE, {}, 10),
        revisar_instructions(DONDE, {"applyTo": "**"}, 10),
        revisar_instructions(DONDE, {"applyTo": "src/**"}, LIMITE_LINEAS_SIN_TECHO + 50),
        revisar_solapamiento([("a.instructions.md", "**/*.java"),
                              ("b.instructions.md", "**/*.java")]),
    ]
    for hallazgos in casos:
        assert not _errores(hallazgos), f"algo bloqueo: {_mensajes(hallazgos)}"


# ── se deja constancia de que existe y de su alcance ────────────────────────────────────────
def test_se_informa_del_ambito_y_de_que_esta_fuera_del_ciclo_de_vida():
    """El riesgo no es el contenido, es la INVISIBILIDAD: es el unico archivo que cambia el
    comportamiento del agente sin que nadie lo elija."""
    hallazgos = revisar_instructions(DONDE, {"applyTo": "**/*.java"}, 20)
    assert hallazgos
    assert "**/*.java" in _mensajes(hallazgos)
    assert "ciclo de vida" in _mensajes(hallazgos)


def test_sin_applyTo_se_avisa_de_que_el_archivo_queda_INERTE():
    """Las dos fuentes oficiales se contradicen -- GitHub lo redacta como imperativo y VS Code lo
    declara opcional diciendo que sin el no se aplica automaticamente --, asi que se informa del
    efecto en vez de decidir por ellas."""
    hallazgos = revisar_instructions(DONDE, {}, 10)
    assert "inerte" in _mensajes(hallazgos)


def test_un_ambito_que_cubre_todo_el_repositorio_se_senala_aparte():
    # `**` deja de ser una regla acotada: su cuerpo se paga en cualquier peticion.
    for todo in ("**", "**/*", "*", "./**"):
        hallazgos = revisar_instructions(DONDE, {"applyTo": todo}, 10)
        assert "TODO el repositorio" in _mensajes(hallazgos), todo


def test_se_admite_applyTo_y_applies_to():
    """`applyTo` es la ortografia de Copilot y `applies_to` aparece en artefactos reales. Lo que se
    mide es el AMBITO, no la ortografia: el gate no decide cual lee el cliente."""
    for clave in ("applyTo", "applies_to"):
        hallazgos = revisar_instructions(DONDE, {clave: "src/**"}, 10)
        assert "src/**" in _mensajes(hallazgos), clave


def test_muchas_lineas_se_avisan_diciendo_que_el_umbral_es_NUESTRO():
    """No hay limite documentado por la plataforma -- se comprobo --, asi que el aviso tiene que
    decir de quien es el numero. Si no, parece un requisito del cliente."""
    hallazgos = revisar_instructions(DONDE, {"applyTo": "src/**"}, LIMITE_LINEAS_SIN_TECHO + 1)
    assert "umbral nuestro" in _mensajes(hallazgos)


def test_pocas_lineas_no_dicen_nada_del_tamano():
    hallazgos = revisar_instructions(DONDE, {"applyTo": "src/**"}, 10)
    assert "lineas SIEMPRE activas" not in _mensajes(hallazgos)


# ── el solapamiento: ahora avisa, y sigue siendo conservador ────────────────────────────────
def test_dos_ambitos_identicos_se_avisan_diciendo_que_el_cliente_no_desempata():
    """La documentacion oficial dice que «all sets of relevant instructions are provided» y no define
    orden entre dos archivos que casen con el mismo. El conflicto no lo resuelve nadie."""
    hallazgos = revisar_solapamiento([("a.instructions.md", "**/*.java"),
                                      ("b.instructions.md", "**/*.java")])
    assert len(hallazgos) == 1
    assert hallazgos[0].severidad is Severidad.AVISO
    assert "NO garantiza" in hallazgos[0].mensaje


def test_un_ambito_universal_solapa_con_cualquiera():
    for universal in ("**", "**/*", "*"):
        assert revisar_solapamiento([("acotada.instructions.md", "src/api/**"),
                                     ("todo.instructions.md", universal)]), universal


def test_un_arbol_que_contiene_a_otro_se_senala():
    # `src/**` abarca cuanto cubre `src/api/**`.
    assert revisar_solapamiento([("amplia.instructions.md", "src/**"),
                                 ("estrecha.instructions.md", "src/api/**")])


def test_extensiones_distintas_NO_se_senalan():
    """Falso positivo MEDIDO al escribir la regla: la primera version comparaba el prefijo e ignoraba
    el sufijo, asi que daba `**/*.java` y `**/*.py` como solapados. Un aviso por un conflicto que no
    existe ensena a ignorar los avisos."""
    assert not revisar_solapamiento([("a.instructions.md", "**/*.java"),
                                     ("b.instructions.md", "**/*.py")])


def test_dos_ambitos_disjuntos_conviven():
    assert not revisar_solapamiento([("java.instructions.md", "src/java/**"),
                                     ("web.instructions.md", "src/web/**")])


def test_el_ambito_vale_como_cadena_con_comas_y_como_lista():
    """`applyTo` es una CADENA separada por comas en Copilot y `paths` una LISTA en Claude Code."""
    for ambito in ("**/*.java, **/*.kt", ["**/*.java", "**/*.kt"]):
        assert revisar_solapamiento([("a.instructions.md", ambito),
                                     ("b.instructions.md", "**/*.kt")]), f"{ambito!r}"


def test_una_sola_no_se_solapa_consigo_misma():
    assert not revisar_solapamiento([("sola.instructions.md", "**/*.ts")])
