"""Las plantillas producen artefactos CONFORMES. Se instancian y se les corre el gate de verdad.

POR QUE ESTA PRUEBA ES LA QUE DA VALOR A LAS PLANTILLAS. Una plantilla que produjera un artefacto no
conforme seria PEOR que no tener plantilla: ensenaria a hacerlo mal, y con la autoridad de venir del
repositorio del estandar. Y el modo de fallo es silencioso -- nadie revisa una plantilla que «ya
funcionaba» -- asi que en cuanto el estandar cambie una regla, la plantilla se queda atras sin que nadie
lo note.

Con esta prueba, ese desfase es un fallo de CI.

QUE SE PRUEBA Y QUE NO. Se comprueba que el resultado de instanciar las plantillas pase el gate. NO se
comprueba la calidad del contenido -- si la `description` es buena, si el procedimiento tiene sentido --,
porque eso no es comprobable mecanicamente y es justo lo que la plantilla pide que escriba una persona.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from validador_agentico.aplicacion.validar_repositorio import validar
from validador_agentico.dominio.hallazgo import Severidad

_RAIZ_DEL_ESTANDAR = Path(__file__).resolve().parents[2]
_PLANTILLAS = _RAIZ_DEL_ESTANDAR / "plantillas"
_ESQUEMAS = _RAIZ_DEL_ESTANDAR / "schemas"

# Los valores con los que se instancian los marcadores. Son los que un equipo pondria de verdad, no
# cadenas de relleno: si el gate acepta `xxx` pero rechaza un nombre con la forma real, la prueba no
# probaria nada.
_VALORES = {
    "ID": "demo.sdlc.revisar-consulta",
    "NOMBRE": "revisar-consulta",
    "DOMINIO": "sdlc",
    "DOMINIO_COMPLETO": "demo.sdlc",
    "EQUIPO": "squad-sdlc",
    "CONTACTO": "squad-sdlc@ejemplo.dev",
    # SIN comillas en el valor: las pone la plantilla. En YAML `version` tiene que ir entrecomillado
    # -- `1.10` sin comillas se interpreta como numero y pierde el cero -- y en JSON ya lo esta por la
    # sintaxis. Meterlas aqui las doblaba en los `.json` y los dejaba invalidos.
    "VERSION": "1.0.0",
    "DESCRIPCION": ("Revisa una consulta y senala lo que degrada su rendimiento. Usalo cuando alguien "
                    "escriba o pegue una consulta."),
    "TITULO": "Revisar una consulta",
    "MODELO": "claude-sonnet-4-6",
    "ORGANIZACION": "Banca-Copilot-demo",
    "REPOSITORIO": "agentes-sdlc",
    "ARGUMENTOS": "rama-base (opcional)",
    "CUANDO": "Cuando alguien pegue una consulta.",
    "PROCEDIMIENTO": "Revisar los filtros y el orden.",
    "SALIDA": "La consulta corregida y el motivo de cada cambio.",
    "LIMITES": "No planifica migraciones.",
    "INSTRUCCIONES": "Revisa la consulta del argumento.",
}

_MARCADOR = re.compile(r"<<([A-Z_]+)>>")


def _instanciar(texto: str) -> str:
    """Sustituye los marcadores conocidos. Los desconocidos se dejan, para que la prueba los delate."""
    return _MARCADOR.sub(lambda m: _VALORES.get(m.group(1), m.group(0)), texto)


def _copiar_instanciando(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(_instanciar(origen.read_text(encoding="utf-8")), encoding="utf-8")


def _errores(raiz: Path) -> str:
    resultado = validar(raiz, directorio_de_esquemas=_ESQUEMAS)
    return " | ".join(f"{h.donde}: {h.mensaje}" for h in resultado.hallazgos
                      if h.severidad is Severidad.ERROR)


def _con_inventario(gobierno: Path, **cuentas: int) -> None:
    """El inventario declarado tiene que cuadrar con el arbol, asi que se ajusta al montar el caso."""
    datos = json.loads(gobierno.read_text(encoding="utf-8"))
    datos["artifacts"] = {**datos["artifacts"], **cuentas}
    gobierno.write_text(json.dumps(datos, indent=2), encoding="utf-8")


# ── que las plantillas existan, antes de nada ───────────────────────────────────────────────
@pytest.mark.parametrize("relativa", [
    "README.md",
    "unidad-plugin/.claude-plugin/plugin.json",
    "unidad-plugin/GOVERNANCE.json",
    "unidad-suelta/GOVERNANCE.json",
    "artefactos/skill/SKILL.md",
    "artefactos/agente/NOMBRE.agent.md",
    "artefactos/prompt/NOMBRE.prompt.md",
    "artefactos/mcp/.mcp.json",
    "artefactos/mcp/bloque-de-gobierno.json",
    "artefactos/hooks/hooks.json",
    "artefactos/evals/promptfooconfig.yaml",
])
def test_la_plantilla_existe(relativa):
    """Fija el inventario de plantillas. Si alguien borra o renombra una, se sabe aqui y no cuando el
    asistente de autoria intente copiarla."""
    assert (_PLANTILLAS / relativa).is_file(), relativa


# ── el plugin, con un artefacto de cada tipo que admite ─────────────────────────────────────
def test_un_PLUGIN_instanciado_de_las_plantillas_pasa_el_gate(tmp_path):
    unidad = tmp_path / "plugins" / "revisar-consulta"
    _copiar_instanciando(_PLANTILLAS / "unidad-plugin" / ".claude-plugin" / "plugin.json",
                         unidad / ".claude-plugin" / "plugin.json")
    _copiar_instanciando(_PLANTILLAS / "unidad-plugin" / "GOVERNANCE.json",
                         unidad / "GOVERNANCE.json")
    _copiar_instanciando(_PLANTILLAS / "artefactos" / "skill" / "SKILL.md",
                         unidad / "skills" / _VALORES["NOMBRE"] / "SKILL.md")
    _copiar_instanciando(_PLANTILLAS / "artefactos" / "agente" / "NOMBRE.agent.md",
                         unidad / "agents" / f"{_VALORES['ID']}.agent.md")
    _copiar_instanciando(_PLANTILLAS / "artefactos" / "prompt" / "NOMBRE.prompt.md",
                         unidad / "commands" / f"{_VALORES['ID']}.prompt.md")
    _con_inventario(unidad / "GOVERNANCE.json", skills=1, agents=1, prompts=1)

    assert _errores(tmp_path) == ""


def test_el_CONJUNTO_SUELTO_instanciado_de_las_plantillas_pasa_el_gate(tmp_path):
    _copiar_instanciando(_PLANTILLAS / "unidad-suelta" / "GOVERNANCE.json",
                         tmp_path / "GOVERNANCE.json")
    _copiar_instanciando(_PLANTILLAS / "artefactos" / "skill" / "SKILL.md",
                         tmp_path / "skills" / _VALORES["NOMBRE"] / "SKILL.md")
    _con_inventario(tmp_path / "GOVERNANCE.json", skills=1)

    assert _errores(tmp_path) == ""


# ── el marcador que nadie sustituyo ─────────────────────────────────────────────────────────
def test_un_marcador_SIN_SUSTITUIR_no_pasa_desapercibido(tmp_path):
    """La forma `<<NOMBRE>>` existe para esto: que un artefacto a medio rellenar sea un error VISIBLE y no
    un valor plausible. Se comprueba que el gate lo rechace, en vez de publicar un skill llamado
    literalmente `<<NOMBRE>>`."""
    _copiar_instanciando(_PLANTILLAS / "unidad-suelta" / "GOVERNANCE.json",
                         tmp_path / "GOVERNANCE.json")
    skill = tmp_path / "skills" / _VALORES["NOMBRE"] / "SKILL.md"
    skill.parent.mkdir(parents=True)
    # Se instancia TODO menos el nombre, que es lo que se deja a medias.
    texto = _instanciar((_PLANTILLAS / "artefactos" / "skill" / "SKILL.md").read_text(encoding="utf-8"))
    skill.write_text(texto.replace(f"name: {_VALORES['NOMBRE']}", "name: <<NOMBRE>>"),
                     encoding="utf-8")
    _con_inventario(tmp_path / "GOVERNANCE.json", skills=1)

    assert _errores(tmp_path) != "", "un marcador sin sustituir tiene que bloquear"


# ── que no queden marcadores desconocidos en las plantillas ─────────────────────────────────
def test_todos_los_marcadores_de_las_plantillas_tienen_valor_conocido():
    """Si alguien anade un marcador nuevo a una plantilla y no lo documenta aqui, las pruebas de arriba
    lo dejarian pasar sin sustituir -- y el gate podria aceptarlo por casualidad, segun donde caiga --.
    Esto lo convierte en un fallo explicito.

    Los marcadores que solo aparecen en documentacion o en comentarios de plantilla se declaran abajo:
    no se instancian porque nadie los sustituye por codigo, los rellena una persona leyendo.
    """
    solo_documentales = {
        "NOMBRE_DEL_SERVIDOR", "ENDPOINT", "DIGESTO_DE_HERRAMIENTAS", "FECHA", "FECHA_DE_REVISION",
        "EQUIPO_DE_SEGURIDAD", "POR_QUE_SE_APRUEBA", "PATRON_DE_HERRAMIENTA", "SCRIPT",
        "QUE_SE_EVALUA", "CASO_FELIZ", "CONSULTA", "PALABRA_QUE_TIENE_QUE_APARECER",
        "CRITERIO_VERIFICABLE", "CASO_BORDE", "CONSULTA_BORDE", "PALABRA_BORDE", "CASO_NEGATIVO",
        "CONSULTA_AJENA", "SEÑAL_DE_QUE_ACTUO_CUANDO_NO_DEBIA", "ID-DEL-AGENTE",
    }
    desconocidos = {}
    for archivo in sorted(_PLANTILLAS.rglob("*")):
        if not archivo.is_file():
            continue
        for marcador in _MARCADOR.findall(archivo.read_text(encoding="utf-8")):
            if marcador not in _VALORES and marcador not in solo_documentales:
                desconocidos.setdefault(marcador, archivo.relative_to(_PLANTILLAS).as_posix())

    assert not desconocidos, f"marcadores sin valor ni declarar como documentales: {desconocidos}"
