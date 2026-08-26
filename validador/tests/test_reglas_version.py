"""Si una unidad cambia, su version tiene que cambiar. Puras: reciben versiones y rutas.

EL DEFECTO QUE CUBREN, y es de los que salen EN VERDE de principio a fin: la version se escribe a
mano y el etiquetado deriva la etiqueta de ella, pero nada obligaba a subirla. Un cambio mezclado sin
tocar la version no produce etiqueta, y sin etiqueta no hay release, ni paquete, ni atestacion, ni
ficha: lo publicado se queda como estaba y nadie se entera.

El caso que lo destapo: anadirle evals a un artefacto YA publicado. La suite pasa, el gate aprueba y
el artefacto se queda en `conformant` para siempre, porque no hay publicacion nueva que promocionar.
"""
from __future__ import annotations

from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_version import (
    VersionDeUnidad,
    revisar_subida_de_version,
)

REFERENCIA = VersionDeUnidad(ruta="plugins/referencia", nombre="demo.sdlc.referencia",
                             version="1.2.0", version_en_base="1.2.0")
CONTRATOS = VersionDeUnidad(ruta="plugins/contratos", nombre="demo.sdlc.contratos",
                            version="2.0.0", version_en_base="2.0.0")


def _errores(hallazgos):
    return [h for h in hallazgos if h.severidad is Severidad.ERROR]


def _mensajes(hallazgos) -> str:
    return " | ".join(h.mensaje for h in hallazgos)


# ── lo que tiene que atrapar ────────────────────────────────────────────────────────────────
def test_cambiar_un_artefacto_sin_subir_la_version_es_error():
    hallazgos = revisar_subida_de_version(
        (REFERENCIA,), ("plugins/referencia/skills/revisar-cobertura/SKILL.md",))

    assert _errores(hallazgos)


def test_anadir_evals_a_un_artefacto_publicado_exige_subir_la_version():
    """EL CASO QUE MOTIVA LA REGLA, y el unico que no se ve por ningun otro medio: la suite pasa, el
    gate aprueba y sin version nueva no hay publicacion que promocionar a `certified`. El trabajo de
    escribir las evaluaciones no cambia nada observable y nada lo avisa."""
    hallazgos = revisar_subida_de_version(
        (REFERENCIA,), ("plugins/referencia/skills/revisar-cobertura/evals/promptfooconfig.yaml",))

    assert _errores(hallazgos)


def test_es_ERROR_y_no_aviso():
    # Un aviso aqui se ignora -- el PR se mezcla igual -- y el fallo vuelve intacto. Si solo protege
    # cuando alguien decide hacerle caso, no protege.
    hallazgos = revisar_subida_de_version((REFERENCIA,), ("plugins/referencia/SKILL.md",))

    assert hallazgos
    assert all(h.severidad is Severidad.ERROR for h in hallazgos)


def test_solo_se_reprocha_la_unidad_que_CAMBIO():
    """Un repositorio de dominio publica varias unidades. Reprocharlas todas obligaria a subir la
    version de plugins que el pull request no toca -- y eso publica de nuevo algo identico --."""
    hallazgos = revisar_subida_de_version(
        (REFERENCIA, CONTRATOS), ("plugins/referencia/skills/x/SKILL.md",))

    assert len(_errores(hallazgos)) == 1
    assert "demo.sdlc.referencia" in _mensajes(hallazgos)
    assert "demo.sdlc.contratos" not in _mensajes(hallazgos)


def test_el_mensaje_NO_propone_un_numero():
    """El gate comprueba que HAYA una decision, nunca cual. Solo el autor sabe si el cambio rompe a
    quien ya lo usa: cambiar una `description` puede dejar de activar un skill en los clientes que ya
    lo tienen -- un cambio mayor sin una linea de comportamiento tocada --."""
    mensaje = _mensajes(revisar_subida_de_version((REFERENCIA,), ("plugins/referencia/SKILL.md",)))

    for numero_propuesto in ("1.2.1", "1.3.0", "2.0.0"):
        assert numero_propuesto not in mensaje, mensaje


# ── lo que NO debe marcar: un gate con falsos positivos se desactiva ────────────────────────
def test_subir_la_version_cierra_la_regla():
    subida = VersionDeUnidad(ruta="plugins/referencia", nombre="demo.sdlc.referencia",
                             version="1.3.0", version_en_base="1.2.0")

    assert revisar_subida_de_version((subida,), ("plugins/referencia/SKILL.md",)) == []


def test_una_unidad_NUEVA_no_tiene_version_anterior_que_subir():
    """Si no existia en la base, exigir una subida seria exigir que la primera version de algo sea la
    segunda."""
    nueva = VersionDeUnidad(ruta="plugins/nuevo", nombre="demo.sdlc.nuevo",
                            version="0.1.0", version_en_base=None)

    assert revisar_subida_de_version((nueva,), ("plugins/nuevo/SKILL.md",)) == []


def test_una_unidad_que_no_cambia_no_se_reprocha():
    assert revisar_subida_de_version((REFERENCIA,), ("docs/estandar.md",)) == []


def test_un_prefijo_PARCIAL_no_cuenta_como_pertenencia():
    """`plugins/referencia-vieja` NO esta dentro de `plugins/referencia`. Sin la comparacion por
    segmentos, tocar el vecino obligaria a subir la version de un plugin que nadie cambio."""
    assert revisar_subida_de_version(
        (REFERENCIA,), ("plugins/referencia-vieja/SKILL.md",)) == []


def test_un_cambio_de_CI_no_obliga_a_subir_la_version_del_repositorio():
    """REGRESION medida al estrenar la regla sobre este mismo repositorio: `.github/` es la unica
    ruta que cambia constantemente y no viaja en ningun paquete, asi que atribuirsela a la unidad de
    la raiz habria hecho saltar el gate en cada pull request de infraestructura -- y un gate que
    salta cuando no debe se acaba desactivando --."""
    raiz = VersionDeUnidad(ruta=".", nombre="demo.plataforma.agentico",
                           version="1.0.0", version_en_base="1.0.0")

    assert revisar_subida_de_version((raiz,), (".github/workflows/validar.yml",)) == []


def test_los_evals_del_conjunto_suelto_SI_obligan_a_subir_la_version():
    """La exclusion es de la maquinaria de CI, no de todo lo que no es un artefacto: si tambien
    callara los evals, el arreglo habria desactivado la regla justo en el caso que la motiva."""
    raiz = VersionDeUnidad(ruta=".", nombre="demo.plataforma.agentico",
                           version="1.0.0", version_en_base="1.0.0")

    assert _errores(revisar_subida_de_version(
        (raiz,), ("skills/revisar-jql/evals/promptfooconfig.yaml",)))


def test_un_pull_request_que_no_cambia_nada_no_produce_hallazgos():
    assert revisar_subida_de_version((REFERENCIA, CONTRATOS), ()) == []


def test_la_unidad_ANIDADA_gana_sobre_la_que_la_contiene():
    """Con dos candidatas, la correcta es la MAS ESPECIFICA: atribuir el archivo a la de fuera
    reprocharia al paquete que no lo publica y dejaria sin reprochar al que si."""
    fuera = VersionDeUnidad(ruta="plugins/uno", nombre="demo.fuera",
                            version="1.0.0", version_en_base="1.0.0")
    dentro = VersionDeUnidad(ruta="plugins/uno/interno", nombre="demo.dentro",
                             version="1.0.0", version_en_base="1.0.0")

    mensaje = _mensajes(revisar_subida_de_version(
        (fuera, dentro), ("plugins/uno/interno/skills/x/SKILL.md",)))

    assert "demo.dentro" in mensaje
    assert "demo.fuera" not in mensaje
