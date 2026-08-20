"""Pruebas de G2 sobre los recursos referenciados. Puras: reciben el cuerpo y el conjunto de rutas.

El defecto que cubren se MIDIO en el harness del CoE: de 70 rutas de archivos de apoyo declaradas en
sus `METADATA.json`, ninguna resolvia -- se escribieron para un layout anterior y ningun gate las
comprobaba.
"""
from __future__ import annotations

from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_recursos import revisar_recursos_referenciados

ARBOL = frozenset({
    "skills/crear/SKILL.md",
    "skills/crear/scripts/generar.sh",
    "skills/crear/assets/skill/SKILL.md",
    "skills/crear/references/guia.md",
    "docs/estandar.md",
})
DONDE = "skills/crear/SKILL.md"


def _mensajes(hallazgos) -> str:
    return " | ".join(h.mensaje for h in hallazgos)


def _errores(hallazgos):
    return [h for h in hallazgos if h.severidad is Severidad.ERROR]


# ── lo que tiene que atrapar ────────────────────────────────────────────────────────────────
def test_un_recurso_que_no_existe_es_error():
    """El defecto: el paquete se publica conforme y sellado, y el artefacto revienta al seguir la
    ruta en la maquina del desarrollador."""
    cuerpo = "Aplica la plantilla de `assets/skill/SKILL-VIEJO.md`."
    errores = _errores(revisar_recursos_referenciados(DONDE, cuerpo, ARBOL))
    assert errores
    assert "NO existe" in _mensajes(errores)


def test_el_mensaje_dice_la_ruta_RESUELTA_y_no_solo_la_escrita():
    # Sin la ruta resuelta, el autor no sabe si el fallo es la referencia o su carpeta.
    cuerpo = "Ver `scripts/falta.sh`."
    assert "skills/crear/scripts/falta.sh" in _mensajes(
        revisar_recursos_referenciados(DONDE, cuerpo, ARBOL))


def test_cada_forma_de_referencia_se_detecta():
    for cuerpo in ("[la guia](references/inexistente.md)", "usa `scripts/inexistente.sh`"):
        assert _errores(revisar_recursos_referenciados(DONDE, cuerpo, ARBOL)), cuerpo


def test_una_referencia_que_sale_del_repositorio_es_error():
    # `../../../etc/passwd` no es un recurso del artefacto, y resolverlo daria una ruta fuera.
    assert _errores(revisar_recursos_referenciados(
        "SKILL.md", "ver [algo](../fuera.md)", ARBOL))


def test_las_referencias_se_resuelven_contra_la_CARPETA_del_artefacto():
    """La especificacion lo impone: rutas relativas desde la raiz del skill. Resolverlas contra la
    raiz del repositorio daria por bueno un `scripts/generar.sh` que no es el del artefacto."""
    arbol_con_señuelo = ARBOL | {"scripts/generar.sh"}
    assert _errores(revisar_recursos_referenciados(
        "skills/otro/SKILL.md", "usa `scripts/generar.sh`", arbol_con_señuelo))


# ── lo que NO debe marcar: un gate con falsos positivos se desactiva ────────────────────────
def test_un_recurso_que_existe_no_produce_hallazgos():
    cuerpo = ("Ejecuta `scripts/generar.sh`, parte de [la plantilla](assets/skill/SKILL.md) "
              "y consulta [la guia](references/guia.md).")
    assert revisar_recursos_referenciados(DONDE, cuerpo, ARBOL) == []


def test_una_url_no_es_un_archivo_del_repositorio():
    cuerpo = "Ver [la especificacion](https://agentskills.io/specification) y [el ancla](#uso)."
    assert revisar_recursos_referenciados(DONDE, cuerpo, ARBOL) == []


def test_una_ruta_con_variable_no_se_comprueba():
    """`$skill/assets/...` es lo que hace `generar.sh`, y no se puede resolver sin ejecutar nada.
    Marcarlo seria un falso positivo garantizado."""
    cuerpo = "La plantilla vive en `assets/skill/SKILL.md` y el script usa $skill/assets/."
    assert revisar_recursos_referenciados(DONDE, cuerpo, ARBOL) == []


def test_una_ruta_mencionada_en_prosa_sin_marcar_no_se_detecta():
    """Deliberado: preferimos no ver una referencia real antes que inventar una que no existe."""
    cuerpo = "El esqueleto esta en la carpeta assets del asistente."
    assert revisar_recursos_referenciados(DONDE, cuerpo, ARBOL) == []


def test_un_nombre_entre_acentos_que_no_es_una_ruta_de_recursos_se_ignora():
    # `--verbose` o `name` van entre acentos graves constantemente y no son archivos.
    cuerpo = "Pasa `--verbose` para ver el detalle y revisa el campo `description`."
    assert revisar_recursos_referenciados(DONDE, cuerpo, ARBOL) == []


def test_la_misma_referencia_repetida_da_UN_solo_hallazgo():
    # Repetirla por cada mencion haria creer que faltan varios archivos.
    cuerpo = "usa `scripts/falta.sh` y luego otra vez `scripts/falta.sh`"
    assert len(_errores(revisar_recursos_referenciados(DONDE, cuerpo, ARBOL))) == 1


def test_un_cuerpo_vacio_no_produce_hallazgos():
    assert revisar_recursos_referenciados(DONDE, "", ARBOL) == []


# ── regresion: directorios ──────────────────────────────────────────────────────────────────
def test_una_referencia_a_un_DIRECTORIO_que_existe_no_es_error():
    # Medido corriendo el gate sobre nuestro propio repo: `assets/` salia como inexistente aunque
    # tiene cuatro archivos dentro, porque un directorio no esta en el conjunto de rutas -- solo
    # lo estan sus archivos.
    assert revisar_recursos_referenciados(DONDE, "el esqueleto vive en `assets/`", ARBOL) == []


def test_un_directorio_vacio_o_inexistente_SI_es_error():
    # `templates/` no esta en ARBOL. Primer intento de esta prueba: use `references/`, que SI esta
    # en el arbol de prueba -- la prueba fallo y el codigo estaba bien.
    errores = _errores(revisar_recursos_referenciados(DONDE, "ver `templates/`", ARBOL))
    assert errores
    assert "directorio" in _mensajes(errores)
