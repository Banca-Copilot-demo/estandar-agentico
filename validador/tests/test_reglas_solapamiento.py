"""Pruebas de la prevencion de conflictos entre `instructions` distribuidas.

El defecto que cubren se MIDIO leyendo el esquema contra el codigo: `instructions.schema.json`
declaraba que el conflicto «se PREVIENE en publicacion exigiendo que dos instructions no declaren
globs que se solapen», y esa comprobacion NO existia en el validador. El esquema prometia un gate
que nadie habia implementado.
"""
from __future__ import annotations

from validador_agentico.dominio.reglas_solapamiento import revisar_solapamiento


def _mensajes(hallazgos):
    return " ".join(h.mensaje for h in hallazgos)


# ── el solapamiento CIERTO: lo que debe bloquear ────────────────────────────────────────────
def test_dos_instructions_con_el_mismo_glob_se_bloquean():
    hallazgos = revisar_solapamiento([("a.instructions.md", "**/*.java"),
                                      ("b.instructions.md", "**/*.java")])
    assert len(hallazgos) == 1
    assert "b.instructions.md" == hallazgos[0].donde


def test_un_glob_universal_solapa_con_cualquiera():
    # El caso que el usuario planteo: alguien pone `*` «para que aplique a todo». A partir de ahi
    # NINGUNA otra instruction puede convivir con ella.
    for universal in ("*", "**", "**/*", "./**"):
        hallazgos = revisar_solapamiento([("acotada.instructions.md", "src/api/**"),
                                          ("todo.instructions.md", universal)])
        assert hallazgos, f"no se detecto que {universal} solapa con un glob acotado"


def test_un_arbol_que_contiene_a_otro_se_bloquea():
    # `src/**` abarca cuanto cubre `src/api/**`: publicarlas juntas deja sin definir quien gana
    # en los archivos de `src/api`.
    hallazgos = revisar_solapamiento([("amplia.instructions.md", "src/**"),
                                      ("estrecha.instructions.md", "src/api/**")])
    assert hallazgos
    assert "src/**" in _mensajes(hallazgos)


def test_el_hallazgo_se_reporta_en_la_SEGUNDA_y_nombra_a_la_primera():
    # Asi el mensaje aparece junto al archivo que llega en el pull request, no en el que ya estaba
    # publicado y que su autor no esta tocando.
    hallazgos = revisar_solapamiento([("vieja.instructions.md", "**/*.py"),
                                      ("nueva.instructions.md", "**/*.py")])
    assert hallazgos[0].donde == "nueva.instructions.md"
    assert "vieja.instructions.md" in hallazgos[0].mensaje


# ── lo que NO debe bloquear: los falsos positivos cuestan publicaciones legitimas ────────────
def test_dos_ambitos_disjuntos_conviven():
    assert not revisar_solapamiento([("java.instructions.md", "src/java/**"),
                                     ("web.instructions.md", "src/web/**")])


def test_extensiones_distintas_conviven():
    assert not revisar_solapamiento([("a.instructions.md", "**/*.java"),
                                     ("b.instructions.md", "**/*.py")])


def test_una_sola_instruction_no_se_solapa_consigo_misma():
    assert not revisar_solapamiento([("sola.instructions.md", "**/*.ts")])


def test_un_ambito_ausente_no_produce_solapamiento():
    # La falta de `applies_to` YA la senala la regla por artefacto: senalarla otra vez aqui daria
    # dos hallazgos por el mismo defecto.
    assert not revisar_solapamiento([("sin.instructions.md", None),
                                     ("otra.instructions.md", "**/*.go")])


# ── las dos formas que los clientes usan para lo mismo ──────────────────────────────────────
def test_el_ambito_vale_como_cadena_con_comas_y_como_lista():
    """`applyTo` es una CADENA separada por comas en Copilot y `paths` una LISTA en Claude Code:
    el mismo artefacto se publica a los dos, asi que las dos formas deben detectarse igual."""
    for ambito in ("**/*.java, **/*.kt", ["**/*.java", "**/*.kt"]):
        hallazgos = revisar_solapamiento([("a.instructions.md", ambito),
                                          ("b.instructions.md", "**/*.kt")])
        assert hallazgos, f"no se detecto el solapamiento con el ambito {ambito!r}"
