"""El resolutor que traduce la politica a la bandera de `gh release create`.

ES EL PUNTO EXACTO DONDE PUBLICAR Y DISTRIBUIR SE SEPARAN: si devuelve `--prerelease`, el release nace
fuera del catalogo y el artefacto queda publicado pero no distribuido. Equivocarse aqui no rompe la
publicacion -- por eso hace falta probarlo: fallaria en verde.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from validador_agentico.dominio.politica import Promocion, promocion_declarada

_RUTA = (Path(__file__).resolve().parents[2]
         / ".github" / "actions" / "publicar" / "resolver-politica.py")


def _cargar():
    """El modulo vive en `.github/actions/`, fuera del paquete, asi que se carga por ruta."""
    especificacion = importlib.util.spec_from_file_location("resolver_politica", _RUTA)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


resolver = _cargar()


def test_al_certificar_hace_que_el_release_nazca_FUERA_del_catalogo():
    assert resolver.bandera_de(Promocion.AL_CERTIFICAR) == "--prerelease"


def test_al_publicar_hace_que_el_release_nazca_COMPLETO():
    assert resolver.bandera_de(Promocion.AL_PUBLICAR) == ""


@pytest.mark.parametrize("contenido, motivo", [
    (None, "no existe"),
    ("{no es json", "JSON roto"),
    ('{"promocion_al_catalogo": "inventado"}', "valor que no existe"),
], ids=["ausente", "json-roto", "valor-invalido"])
def test_una_politica_ilegible_NO_distribuye_de_mas(contenido, motivo, tmp_path):
    """EL DEFECTO QUE EVITA, y es el que este proyecto ha encontrado una y otra vez: que un error de
    configuracion se lea como «todo en orden».

    Aqui el fail-open seria publicar al catalogo por no haber podido leer la politica: un artefacto
    sin certificar llegaria a toda la organizacion y nadie lo notaria, porque nada falla. Al reves se
    nota en un minuto -- algo no se distribuyo -- y se arregla promocionandolo.
    """
    ruta = tmp_path / "POLITICA.json"
    if contenido is not None:
        ruta.write_text(contenido, encoding="utf-8")

    leida = resolver._politica_leida(ruta)

    assert resolver.bandera_de(promocion_declarada(leida)) == "--prerelease", motivo


def test_la_RUTA_QUE_USA_EL_WORKFLOW_llega_a_la_politica():
    """EL FALLO SILENCIOSO QUE ESTA PRUEBA CIERRA, y es del tipo mas caro de este proyecto.

    El paso de publicacion resuelve la politica como `<action_path>/../../../POLITICA.json`, porque
    la composite action vive en `.github/actions/publicar/`. Si alguien moviera la action de sitio,
    esa travesia dejaria de llegar al archivo -- y NO fallaria nada: el resolutor trata la ausencia
    como «la politica mas restrictiva», asi que seguiria publicando prelanzamientos para siempre.

    El sintoma seria desconcertante: cambiar `POLITICA.json` a `al_publicar` no tendria ningun efecto
    y nadie sabria por que, porque el archivo estaria bien y el codigo tambien. Aqui la travesia se
    comprueba desde donde la hace el workflow, de modo que mover la action rompe una prueba en vez de
    romper la politica en silencio.
    """
    directorio_de_la_action = _RUTA.parent

    politica = directorio_de_la_action / ".." / ".." / ".." / "POLITICA.json"

    assert politica.resolve().is_file(), (
        f"la travesia del workflow no llega a POLITICA.json: {politica.resolve()}. "
        "Si la composite action cambio de sitio, ajusta tambien la ruta en action.yml")


def test_la_politica_del_repositorio_es_legible_y_declarada():
    """La politica real, no una de prueba: si el archivo del repositorio se rompiera o declarara un
    valor inventado, la publicacion seguiria funcionando -- degradando -- y nadie se enteraria."""
    ruta = Path(__file__).resolve().parents[2] / "POLITICA.json"

    declarado = json.loads(ruta.read_text(encoding="utf-8"))["promocion_al_catalogo"]

    assert declarado in {p.value for p in Promocion}, declarado
