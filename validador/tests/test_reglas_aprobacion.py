"""Pruebas de las dos reglas que protegen el rastro de aprobacion. Puras: reciben rutas y conjuntos.

Las dos nacen de un defecto MEDIDO: un repositorio de prueba con tres artefactos, tres equipos duenos
distintos que no existian, y un skill mezclado con un `mcp`, daba CONFORME con cero hallazgos.
"""
from __future__ import annotations

from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_aprobacion import (
    ClaseAprobador,
    clase_de,
    revisar_equipo_resoluble,
    revisar_mezcla_de_aprobadores,
)

EQUIPOS = frozenset({"squad-sdlc", "plataforma-agentica"})


def _errores(hallazgos):
    return [h for h in hallazgos if h.severidad is Severidad.ERROR]


def _mensajes(hallazgos) -> str:
    return " | ".join(h.mensaje for h in hallazgos)


# ── clasificacion por ruta ──────────────────────────────────────────────────────────────────
def test_cada_tipo_cae_en_la_clase_de_firmante_que_le_toca():
    esperado = {
        ".mcp.json": ClaseAprobador.SEGURIDAD,
        "hooks.json": ClaseAprobador.SEGURIDAD,
        "hooks/auditoria.json": ClaseAprobador.SEGURIDAD,
        "docs/api.instructions.md": ClaseAprobador.ARQUITECTURA,
        "skills/validar/SKILL.md": ClaseAprobador.DOMINIO,
        "agents/migrador.agent.md": ClaseAprobador.DOMINIO,
        "commands/migrar.prompt.md": ClaseAprobador.DOMINIO,
    }
    for ruta, clase in esperado.items():
        assert clase_de(ruta) is clase, ruta


def test_un_archivo_que_no_es_artefacto_no_exige_firmante():
    # Si un README exigiera clase, cambiar la documentacion arrastraria a un revisor y ademas
    # contaria como mezcla.
    for ruta in ("README.md", ".gitignore", "GOVERNANCE.json", "docs/notas.md"):
        assert clase_de(ruta) is None, ruta


# ── mezcla de firmantes ─────────────────────────────────────────────────────────────────────
def test_varios_artefactos_de_la_MISMA_clase_no_son_mezcla():
    """Permitir varios artefactos es deliberado: un PR que anade un skill y su prompt asociado es lo
    natural. Lo que se prohibe es mezclar CLASES DE FIRMANTE, no cantidad."""
    cambios = ("skills/uno/SKILL.md", "skills/dos/SKILL.md", "commands/tres.prompt.md")
    assert revisar_mezcla_de_aprobadores(cambios) == []


def test_un_skill_junto_a_un_mcp_es_error():
    """El defecto que cubre: el revisor de seguridad aprueba un PR que contiene cosas que no
    examino, y la aprobacion deja de ser atribuible a lo que se aprobo."""
    errores = _errores(revisar_mezcla_de_aprobadores(("skills/uno/SKILL.md", ".mcp.json")))
    assert errores
    assert "firmantes DISTINTOS" in _mensajes(errores)


def test_el_mensaje_dice_QUE_archivos_causan_la_mezcla():
    # Sin los archivos, el autor sabe que hay mezcla y no sabe que separar.
    errores = _errores(revisar_mezcla_de_aprobadores((".mcp.json", "skills/uno/SKILL.md")))
    assert ".mcp.json" in _mensajes(errores)
    assert "skills/uno/SKILL.md" in _mensajes(errores)


def test_instructions_con_un_skill_tambien_es_mezcla():
    # Distinta clase: arquitectura frente a dominio.
    assert _errores(revisar_mezcla_de_aprobadores(
        ("docs/api.instructions.md", "skills/uno/SKILL.md")))


def test_solo_archivos_sin_clase_no_produce_mezcla():
    assert revisar_mezcla_de_aprobadores(("README.md", ".gitignore")) == []


def test_sin_cambios_no_hay_mezcla():
    assert revisar_mezcla_de_aprobadores(()) == []


# ── dueno resoluble ─────────────────────────────────────────────────────────────────────────
def test_un_equipo_que_existe_no_produce_hallazgos():
    assert revisar_equipo_resoluble("x", "squad-sdlc", EQUIPOS) == []


def test_un_equipo_inventado_es_error():
    """El defecto medido: tres artefactos declaraban `squad-a`, `squad-b` y `squad-c`, ninguno
    existia, y el gate daba CONFORME. Sin dueno resoluble no hay a quien avisar."""
    errores = _errores(revisar_equipo_resoluble("SKILL.md", "squad-a", EQUIPOS))
    assert errores
    assert "NO existe en la organizacion" in _mensajes(errores)


def test_no_poder_consultar_los_equipos_AVISA_y_no_da_por_bueno():
    """La distincion que importa: `None` es «no lo se», no «esta bien». Un gate que no puede
    comprobar algo y calla es indistinguible de uno que lo comprobo."""
    hallazgos = revisar_equipo_resoluble("SKILL.md", "squad-a", None)
    assert hallazgos
    assert all(h.severidad is Severidad.AVISO for h in hallazgos)
    assert "no se pudo resolver" in _mensajes(hallazgos)


def test_un_conjunto_vacio_de_equipos_NO_es_lo_mismo_que_None():
    # Vacio significa «la organizacion no tiene equipos», asi que cualquier dueno es inexistente.
    assert _errores(revisar_equipo_resoluble("SKILL.md", "squad-a", frozenset()))


def test_sin_equipo_declarado_esta_regla_no_dice_nada():
    # Que falte `owner_team` ya es error del envelope; duplicarlo aqui daria dos hallazgos para un
    # solo defecto y el autor creeria que son dos.
    assert revisar_equipo_resoluble("SKILL.md", None, EQUIPOS) == []
