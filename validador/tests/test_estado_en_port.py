"""La pieza que fija el estado en el catalogo toca el estado y NADA MAS.

QUE DEFECTO CUBRE, medido en el catalogo real: promocionar quitaba la marca de prelanzamiento del
release -- con lo que el artefacto YA entraba al catalogo instalable -- y no tocaba Port. La ficha se
quedaba en `conformant`, diciendo que el artefacto no se distribuye, mientras cualquiera podia
instalarlo por nombre. Quien gobierna mirando fichas veia lo contrario de lo que pasaba.

Y LA OTRA MITAD, que es igual de importante: al arreglarlo, la tentacion es reescribir la ficha
entera. No se puede: una transicion de estado NO vuelve a sellar nada, asi que escribir `sha`,
`digest` o `ref` significaria pisar con datos releidos lo que ya estaba firmado.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from validador_agentico.dominio.politica import ESTADO_CERTIFICADO, Promocion

_RUTA = (Path(__file__).resolve().parents[2]
         / ".github" / "actions" / "estado-en-port" / "estado_en_port.py")


def _cargar():
    """El modulo vive en `.github/actions/`, fuera del paquete, asi que se carga por ruta."""
    especificacion = importlib.util.spec_from_file_location("estado_en_port", _RUTA)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


estado_en_port = _cargar()

_FICHA_CONFORME = {
    "identifier": "demo.sdlc.revisar-jql",
    "properties": {
        "tipo": "skill",
        "status": "conformant",
        "ruta": "skills/revisar-jql/SKILL.md",
        "ref": "demo.sdlc.revisar-jql--v0.1.1",
        "sha": "a" * 40,
        "digest": "b" * 64,
        "owner_team": "sdlc",
        "en_marketplace": False,
    },
}


def test_solo_se_escriben_el_estado_y_lo_que_de_el_se_deriva():
    """Los campos sellados -- `sha`, `digest`, `ref`, propietario -- se conservan POR FUSION, sin
    aparecer en el payload. Si aparecieran, una transicion los reescribiria con datos releidos."""
    cambio = estado_en_port.cambio_de_estado(
        _FICHA_CONFORME, ESTADO_CERTIFICADO, Promocion.AL_CERTIFICAR, "org/repo", "demo.sdlc.x")

    assert set(cambio["properties"]) == {"status", "en_marketplace", "install_hint"}


def test_certificar_pone_la_ficha_EN_EL_MARKETPLACE():
    cambio = estado_en_port.cambio_de_estado(
        _FICHA_CONFORME, ESTADO_CERTIFICADO, Promocion.AL_CERTIFICAR, "org/repo", "demo.sdlc.x")

    assert cambio["properties"]["status"] == ESTADO_CERTIFICADO
    assert cambio["properties"]["en_marketplace"] is True


def test_la_pista_se_RECONSTRUYE_y_no_se_arrastra_la_del_estado_anterior():
    """Una ficha que cambie de estado y conserve la pista del estado anterior vuelve a mentir: es el
    mismo defecto al reves. Conforme mandaba a descargar el paquete; Certificado tiene que mandar al
    catalogo."""
    cambio = estado_en_port.cambio_de_estado(
        _FICHA_CONFORME, ESTADO_CERTIFICADO, Promocion.AL_CERTIFICAR, "org/repo", "demo.sdlc.x")

    assert cambio["properties"]["install_hint"].startswith("copilot plugin install demo.sdlc.x@")


def test_un_estado_que_saca_del_catalogo_deja_de_mandar_a_instalar_por_nombre():
    """La misma pieza sirve a la suspension y a la retirada, y ahi la direccion es la contraria: si
    la pista siguiera diciendo `plugin install`, suspender no cambiaria nada de lo que el consumidor
    ve."""
    cambio = estado_en_port.cambio_de_estado(
        _FICHA_CONFORME, "suspended", Promocion.AL_PUBLICAR, "org/repo", "demo.sdlc.x")

    assert cambio["properties"]["en_marketplace"] is False
    assert "plugin install" not in cambio["properties"]["install_hint"]


def test_solo_alcanza_a_las_fichas_de_ESA_etiqueta():
    """El `ref` es lo que la publicacion escribio para decir de que version es cada ficha, asi que
    filtrar por el alcanza a los artefactos que esa publicacion sello y a nadie mas: ni los vecinos
    del repositorio ni las versiones anteriores del mismo artefacto."""
    vecino = {"identifier": "demo.sdlc.contratos",
              "properties": {"ref": "demo.sdlc.contratos--v0.1.3"}}

    alcanzadas = estado_en_port.fichas_de_la_etiqueta(
        [_FICHA_CONFORME, vecino], "demo.sdlc.revisar-jql--v0.1.1")

    assert [f["identifier"] for f in alcanzadas] == ["demo.sdlc.revisar-jql"]
