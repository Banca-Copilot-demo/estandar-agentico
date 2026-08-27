"""Pruebas del esquema de `hooks.json`, que hasta ahora NO EXISTIA.

Era el unico de los cuatro archivos que gobiernan una unidad publicable sin esquema, y esa ausencia
tiene un coste medible: lo que el gate exigia -- `timeoutSec` -- y lo que el cliente lee --
`timeout` -- pudieron divergir durante meses sin que nada lo dijera.

Se valida contra el esquema REAL del repositorio y no contra una copia: una prueba con su propio
esquema comprobaria que el codigo funciona, no que el contrato publicado sea correcto.
"""
from __future__ import annotations

from pathlib import Path

from validador_agentico.adaptadores import esquema

ESQUEMAS = Path(__file__).resolve().parents[2] / "schemas"

_ACCION = {"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/x.sh", "timeout": 5}


def _incumplimientos(objeto) -> list[str]:
    return esquema.incumplimientos(objeto, "hooks.schema.json", ESQUEMAS)


def _archivo(evento: str = "PostToolUse", *, grupo=None, accion=None) -> dict:
    return {"hooks": {evento: [{**(grupo or {}), "hooks": [accion or _ACCION]}]}}


def test_un_hooks_json_conforme_no_incumple_nada():
    assert _incumplimientos(_archivo()) == []


def test_un_evento_mal_escrito_es_un_fallo_silencioso_que_solo_el_esquema_atrapa():
    # `PostToolUSe` no falla al instalar ni al ejecutar: simplemente NO DISPARA NUNCA, y el autor cree
    # que su hook esta activo. Es la peor clase de fallo, y ninguna regla en tiempo de ejecucion puede
    # verlo -- solo la lista cerrada del esquema.
    for equivocado in ("PostToolUSe", "postToolUse", "post_tool_use", "OnFileSave"):
        assert _incumplimientos(_archivo(equivocado)), equivocado


def test_las_dos_grafias_del_ecosistema_no_son_intercambiables():
    # Copilot llama `userPromptSubmitted` a lo que Claude Code llama `UserPromptSubmit`. Este formato
    # es el de Claude Code, asi que la grafia de Copilot NO dispara aqui, y aceptarla en silencio
    # dejaria pasar un hook muerto en el evento mas sensible que existe.
    assert _incumplimientos(_archivo("userPromptSubmitted"))
    assert _incumplimientos(_archivo("UserPromptSubmit")) == []


def test_un_tipo_de_accion_inventado_se_rechaza():
    assert _incumplimientos(_archivo(accion={"type": "webhook", "url": "https://x"}))


def test_cada_tipo_de_accion_exige_su_propio_campo():
    # Sin esto, un `{"type": "command"}` sin `command` seria «valido» y no ejecutaria nada.
    incompletas = (
        {"type": "command"},
        {"type": "http"},
        {"type": "prompt"},
        {"type": "agent"},
        {"type": "mcp_tool", "server": "x"},
    )
    for accion in incompletas:
        assert _incumplimientos(_archivo(accion=accion)), accion["type"]


def test_el_timeout_del_grupo_se_acepta_para_no_bloquear_la_migracion():
    # El esquema NO lo rechaza a proposito: el gate es comprobacion requerida, y un rechazo de forma
    # aqui es un error duro que impediria mergear hasta el PR que viene a corregirlo. Quien avisa es
    # la regla, que no bloquea.
    assert _incumplimientos(_archivo(grupo={"timeoutSec": 5})) == []


def test_un_timeout_que_no_es_un_numero_de_segundos_se_rechaza():
    for malo in ("5s", "cinco", -1, 0):
        assert _incumplimientos(_archivo(accion={**_ACCION, "timeout": malo})), malo


def test_un_archivo_sin_ningun_evento_se_rechaza():
    # Mismo criterio que un `.mcp.json` con cero servidores: si la intencion es no tener hooks, se
    # borra el archivo en vez de dejar uno que no le sirve a nadie.
    assert _incumplimientos({"hooks": {}})


def test_una_clave_inventada_en_el_primer_nivel_se_rechaza():
    assert _incumplimientos({**_archivo(), "gobierno": {"approved_by": "x"}})
