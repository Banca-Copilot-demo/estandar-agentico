"""`hooks` en el predicado firmado: su ficha y el digesto de sus scripts.

EL DEFECTO QUE CIERRA, medido mirando el predicado tras instalar el plugin de referencia de verdad:
los cuatro artefactos con frontmatter y el `mcp` llevaban `sha256`, y `hooks` NO APARECIA. Se declaraba
en el inventario y se aprobaba en el `GOVERNANCE.json`, pero no llegaba al catalogo ni tenia digesto
propio, asi que su integridad dependia solo del digesto del paquete completo.

Dicho de otra forma: el UNICO tipo que ejecuta codigo era el UNICO cuyo contenido no se podia
verificar archivo a archivo, que es al reves de lo que uno querria.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from validador_agentico.aplicacion.validar_repositorio import validar
from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.scripts_de_hooks import (
    VARIABLE_RAIZ_DEL_ARTEFACTO,
    VARIABLE_RAIZ_DEL_CONSUMIDOR,
)

_GOBIERNO = {
    "id": "demo.sdlc.x",
    "domain": "sdlc",
    "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
    "status": "draft",
    "data_classification": "internal",
    # SIN `version`: este fixture tiene `plugin.json` -- se le añadio cuando unos hooks sueltos
    # pasaron a ser error -- y con manifiesto la `version` esta PROHIBIDA en el gobierno, porque la
    # del paquete es la del manifiesto. Las dos reglas dejan una sola forma valida al fixture.
    "standard_version": "8.0.0",
    "artifacts": {"hooks": 1},
    "hooks": {"approval": {"approved_by": "squad-seguridad", "date": "2026-08-23",
                           "review_by": "2027-02-23", "security_review": True}},
}


def _repositorio(raiz: Path, manejador: dict, scripts: dict[str, str] | None = None,
                  gobierno: dict = _GOBIERNO) -> Path:
    """Un repositorio con un `hooks.json` y, si se piden, los scripts que referencia."""
    # EL MANIFIESTO FORMA PARTE DEL FIXTURE desde que unos `hooks` sueltos son error: van siempre dentro
    # de un plugin, porque un hook suelto SE SUMA a los demas y no lo quita ninguna capa superior --
    # solo `enabledPlugins` revoca por artefacto, y solo alcanza a los de un plugin --.
    manifiesto = raiz / ".claude-plugin"
    manifiesto.mkdir(parents=True, exist_ok=True)
    (manifiesto / "plugin.json").write_text(json.dumps(
        {"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
         "name": "demo.sdlc.x", "version": "1.0.0", "description": "Plugin del fixture de hooks."}),
        encoding="utf-8")
    directorio = raiz / "hooks"
    directorio.mkdir(parents=True)
    (directorio / "hooks.json").write_text(json.dumps(
        {"hooks": {"PostToolUse": [{"matcher": "Write", "timeoutSec": 5,
                                    "hooks": [manejador]}]}}), encoding="utf-8")
    (raiz / "GOVERNANCE.json").write_text(json.dumps(gobierno), encoding="utf-8")
    for ruta, contenido in (scripts or {}).items():
        archivo = raiz / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        # BYTES EXPLICITOS y no `write_text`: en Windows `write_text` convierte `\n` en `\r\n`, asi que
        # el digesto del archivo no seria el del texto que la prueba cree haber escrito. El digesto del
        # predicado es de BYTES CRUDOS -- sin normalizar -- que es tambien el motivo por el que el
        # `.gitattributes` con `eol=lf` es requisito del estandar y no una preferencia.
        archivo.write_bytes(contenido.encode("utf-8"))
    return raiz


def _ficha_de_hooks(raiz: Path):
    return next((a for a in validar(raiz).artefactos if a.tipo == "hooks"), None)


def _errores(raiz: Path) -> str:
    return " | ".join(h.mensaje for h in validar(raiz).hallazgos
                      if h.severidad is Severidad.ERROR)


def _sha256(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


# ── la ficha, que antes no existia ──────────────────────────────────────────────────────────
def test_hooks_TIENE_ficha_en_el_predicado(tmp_path):
    _repositorio(tmp_path, {"type": "prompt", "prompt": "Revisa el commit."})

    ficha = _ficha_de_hooks(tmp_path)

    assert ficha is not None, "hooks no llego al predicado"
    assert ficha.id == "demo.sdlc.x.hooks", ficha.id
    assert ficha.sha256, "sin digesto del hooks.json"


def test_la_ficha_hereda_el_dueno_del_gobierno(tmp_path):
    # Igual que el `mcp`, y por el mismo motivo: es uno por unidad, asi que declarar dueno aparte
    # serian campos duplicados que acabarian divergiendo.
    _repositorio(tmp_path, {"type": "prompt", "prompt": "x"})

    ficha = _ficha_de_hooks(tmp_path)

    assert ficha.owner_team == "squad-sdlc"
    assert ficha.data_classification == "internal"


def test_sin_bloque_hooks_en_el_gobierno_no_hay_ficha(tmp_path):
    """Un hook sin su aprobacion declarada no se publica: el gate ya lo marca como error, y publicar
    su ficha diria que esta gobernado cuando no lo esta."""
    sin_bloque = {c: v for c, v in _GOBIERNO.items() if c != "hooks"}
    _repositorio(tmp_path, {"type": "prompt", "prompt": "x"}, gobierno=sin_bloque)

    assert _ficha_de_hooks(tmp_path) is None


# ── el digesto de dos niveles ───────────────────────────────────────────────────────────────
def test_el_digesto_incluye_CADA_script_que_el_hook_ejecuta(tmp_path):
    _repositorio(tmp_path,
                 {"type": "command", "command": f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/formatear.sh"},
                 scripts={"scripts/formatear.sh": "#!/bin/sh\necho formateando\n"})

    ficha = _ficha_de_hooks(tmp_path)

    assert list(ficha.scripts) == ["scripts/formatear.sh"], ficha.scripts
    assert ficha.scripts["scripts/formatear.sh"] == _sha256("#!/bin/sh\necho formateando\n")
    assert ficha.scripts_digest, "sin digesto del conjunto"


def test_cambiar_el_SCRIPT_sin_tocar_el_json_cambia_el_digesto_del_conjunto(tmp_path):
    """Es el caso que un digesto solo del `hooks.json` NO detecta, y es el que importa: el JSON declara
    comandos y el script es el que hace algo. Sin esto, editar el script pasaba desapercibido."""
    manejador = {"type": "command", "command": f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/x.sh"}
    antes = _repositorio(tmp_path / "antes", manejador, scripts={"scripts/x.sh": "echo uno\n"})
    despues = _repositorio(tmp_path / "despues", manejador, scripts={"scripts/x.sh": "echo DOS\n"})

    ficha_antes, ficha_despues = _ficha_de_hooks(antes), _ficha_de_hooks(despues)

    assert ficha_antes.sha256 == ficha_despues.sha256, "el hooks.json es el mismo"
    assert ficha_antes.scripts_digest != ficha_despues.scripts_digest, "y el conjunto cambio"


def test_un_hook_sin_scripts_igual_tiene_digesto_del_conjunto(tmp_path):
    # Con `type: prompt` no hay scripts, y el conjunto es solo el JSON. Tiene que haber digesto igual:
    # un campo vacio obligaria a cada consumidor a distinguir «no hay» de «no se calculo».
    _repositorio(tmp_path, {"type": "prompt", "prompt": "x"})

    ficha = _ficha_de_hooks(tmp_path)

    assert ficha.scripts == {}
    assert ficha.scripts_digest


# ── la regla: un script de fuera del artefacto no se puede firmar ───────────────────────────
def test_un_script_del_repositorio_del_CONSUMIDOR_es_ERROR(tmp_path):
    """Lo mas grave que puede tener un hook: el script vive en la maquina de otro, no viaja en el
    paquete, no entra en el digesto y nadie lo reviso. La firma cubriria el JSON y no lo que se
    ejecuta -- y una firma que dice menos de lo que aparenta es peor que ninguna --."""
    _repositorio(tmp_path,
                 {"type": "command",
                  "command": f"{VARIABLE_RAIZ_DEL_CONSUMIDOR}/.claude/hooks/comprobar.sh"})

    mensajes = _errores(tmp_path)

    assert "FUERA del artefacto" in mensajes, mensajes


def test_un_script_referenciado_que_NO_existe_es_ERROR(tmp_path):
    # Mismo razonamiento que la regla de recursos de un skill: el paquete se publicaria sellado y el
    # fallo aparece al ejecutarse en la maquina de quien lo instale.
    _repositorio(tmp_path,
                 {"type": "command", "command": f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/fantasma.sh"},
                 scripts={"scripts/otro.sh": "echo x\n"})

    mensajes = _errores(tmp_path)

    assert "fantasma.sh" in mensajes and "no existe" in mensajes, mensajes


def test_un_script_que_SI_existe_no_produce_error(tmp_path):
    _repositorio(tmp_path,
                 {"type": "command", "command": f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/existe.sh"},
                 scripts={"scripts/existe.sh": "echo x\n"})

    assert _errores(tmp_path) == ""
