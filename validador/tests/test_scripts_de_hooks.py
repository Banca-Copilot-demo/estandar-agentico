"""Los scripts que un hook ejecuta: extraerlos, y su digesto de dos niveles.

EL DEFECTO QUE CIERRA. `hooks` era el unico de los cinco tipos sin ficha ni digesto propio: su
integridad la cubria solo el digesto del paquete completo. O sea que EL TIPO QUE EJECUTA CODIGO era el
unico cuyo contenido no se podia verificar archivo a archivo. Y firmar solo el `hooks.json` no habria
bastado: el JSON DECLARA comandos, y los scripts son los que hacen algo -- es firmar el indice de un
libro --.

Se descubrio mirando el predicado tras instalar el plugin de referencia: los cuatro artefactos con
frontmatter y el `mcp` tenian `sha256`; `hooks` no aparecia.
"""
from __future__ import annotations

import pytest

from validador_agentico.dominio.forma_digesto import es_digest
from validador_agentico.dominio.scripts_de_hooks import (
    VARIABLE_RAIZ_DEL_ARTEFACTO,
    VARIABLE_RAIZ_DEL_CONSUMIDOR,
    digest_del_conjunto,
    forma_canonica,
    referencias_externas,
    referencias_propias,
)


def _hook(*manejadores: dict, evento: str = "PostToolUse") -> dict:
    return {"hooks": {evento: [{"matcher": "Write", "hooks": list(manejadores)}]}}


def _comando(texto: str, argumentos: list | None = None) -> dict:
    manejador = {"type": "command", "command": texto}
    if argumentos is not None:
        manejador["args"] = argumentos
    return manejador


# ── extraer las referencias ─────────────────────────────────────────────────────────────────
def test_la_forma_de_SHELL_declara_el_script_en_command():
    configuracion = _hook(_comando(f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/formatear.sh"))

    assert referencias_propias(configuracion) == ("scripts/formatear.sh",)


def test_la_forma_EXEC_declara_el_script_en_args():
    # Mirar solo `command` dejaria pasar la mitad de los casos: en forma exec el ejecutable es `node`
    # y el script esta en `args`. La especificacion admite las dos formas.
    configuracion = _hook(_comando("node", [f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/formatear.js",
                                            "--fix"]))

    assert referencias_propias(configuracion) == ("scripts/formatear.js",)


def test_un_script_repetido_aparece_UNA_vez_y_en_orden_estable():
    # De esto sale un digesto: si el mismo script apareciera dos veces, o en orden distinto entre
    # ejecuciones, el digesto cambiaria sin que cambiara nada.
    configuracion = _hook(
        _comando(f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/zeta.sh"),
        _comando(f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/alfa.sh"),
        _comando(f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/zeta.sh"))

    assert referencias_propias(configuracion) == ("scripts/alfa.sh", "scripts/zeta.sh")


def test_un_hook_de_tipo_prompt_no_tiene_scripts():
    # Es el caso de nuestro plugin de referencia: `type: prompt`, sin nada que ejecutar.
    configuracion = _hook({"type": "prompt", "prompt": "Revisa el commit."})

    assert referencias_propias(configuracion) == ()
    assert referencias_externas(configuracion) == ()


def test_la_estructura_tiene_hooks_DOS_veces_y_se_recorren_las_dos():
    # El archivo tiene un `hooks` de primer nivel con un array por EVENTO, y cada entrada de ese array
    # tiene su propio `hooks` con los manejadores. Confundirlos daba cero manejadores SIN error.
    configuracion = {"hooks": {"PostToolUse": [{"hooks": [
        _comando(f"{VARIABLE_RAIZ_DEL_ARTEFACTO}/scripts/x.sh")]}]}}

    assert referencias_propias(configuracion) == ("scripts/x.sh",)


@pytest.mark.parametrize("configuracion", [
    {},
    {"hooks": None},
    {"hooks": {"PostToolUse": None}},
    {"hooks": {"PostToolUse": ["no soy un objeto"]}},
    {"hooks": {"PostToolUse": [{"hooks": "tampoco"}]}},
])
def test_una_configuracion_malformada_no_revienta(configuracion):
    """El gate agrega hallazgos: una excepcion aqui mataria el veredicto entero y el autor no veria
    ninguno de los demas defectos de su pull request."""
    assert referencias_propias(configuracion) == ()
    assert referencias_externas(configuracion) == ()


# ── el script de FUERA del artefacto: lo que no se puede firmar ──────────────────────────────
def test_un_script_del_repositorio_del_CONSUMIDOR_se_detecta():
    configuracion = _hook(_comando(f"{VARIABLE_RAIZ_DEL_CONSUMIDOR}/.claude/hooks/comprobar.sh"))

    assert referencias_externas(configuracion) != ()
    # Y NO se cuenta como propio: si se contara, se intentaria calcular su digesto y no existe aqui.
    assert referencias_propias(configuracion) == ()


def test_el_comando_externo_se_devuelve_COMPLETO_no_solo_la_ruta():
    # Quien lea el hallazgo necesita ver la linea entera para entender que se ejecuta.
    linea = f"{VARIABLE_RAIZ_DEL_CONSUMIDOR}/.claude/hooks/x.sh --flag | tee /tmp/log"
    configuracion = _hook(_comando(linea))

    assert referencias_externas(configuracion) == (linea,)


# ── el digesto de dos niveles ───────────────────────────────────────────────────────────────
def test_la_forma_canonica_ordena_por_ruta():
    """Sin orden estable el digesto del conjunto cambiaria entre ejecuciones y dejaria de servir para
    comparar, que es lo unico para lo que existe."""
    canonica = forma_canonica({"z.sh": "b" * 64, "a.sh": "a" * 64})

    assert canonica.splitlines()[0].startswith("a.sh")


def test_el_digesto_del_conjunto_cambia_si_cambia_UN_script():
    antes = digest_del_conjunto({"hooks.json": "1" * 64, "scripts/x.sh": "2" * 64})
    despues = digest_del_conjunto({"hooks.json": "1" * 64, "scripts/x.sh": "3" * 64})

    assert antes != despues


def test_el_digesto_del_conjunto_cambia_si_APARECE_un_script():
    # El caso que un digesto solo del `hooks.json` NO detecta: el JSON no cambia y el conjunto si.
    sin = digest_del_conjunto({"hooks.json": "1" * 64})
    con = digest_del_conjunto({"hooks.json": "1" * 64, "scripts/nuevo.sh": "2" * 64})

    assert sin != con


def test_el_digesto_del_conjunto_es_ESTABLE_ante_el_orden_de_entrada():
    uno = digest_del_conjunto({"a.sh": "1" * 64, "b.sh": "2" * 64})
    otro = digest_del_conjunto({"b.sh": "2" * 64, "a.sh": "1" * 64})

    assert uno == otro


def test_el_digesto_del_conjunto_tiene_forma_de_sha256():
    assert es_digest(digest_del_conjunto({"hooks.json": "1" * 64}))
