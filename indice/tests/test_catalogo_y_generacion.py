"""Pruebas del catalogo generado y del caso de uso.

El caso de uso se prueba con DOBLES INYECTADOS, no parcheando `subprocess` (T4): los adaptadores son
argumentos con valor por defecto, asi que la prueba pasa los suyos y no toca red, ni `gh`, ni disco.
"""
from __future__ import annotations

import json
from pathlib import Path

from indice_agentico.adaptadores import catalogo
from indice_agentico.aplicacion.generar import generar
from indice_agentico.dominio.candidato import Entrada, Indice, Motivo, Rechazo

PROPIETARIO = {"name": "Plataforma Agentica (demo)", "email": "plataforma-agentica@ejemplo.dev"}


def _entrada(name: str, version: str = "0.2.0") -> Entrada:
    return Entrada(name=name, description="d", version=version,
                   repositorio=f"Banca-Copilot-demo/agentes-{name}", etiqueta=f"v{version}",
                   sha="c" * 40)


# ── catalogo ───────────────────────────────────────────────────────────────────────────────
def test_toda_entrada_del_catalogo_lleva_sha():
    """Sin `sha` el puntero es movil: la etiqueta se puede reescribir si el repositorio no tiene
    releases inmutables, y entonces `ref` no fija nada."""
    generado = json.loads(catalogo.render(Indice((_entrada("a"), _entrada("b")), ()),
                                          "agentico", PROPIETARIO, "0.1.0"))
    assert generado["plugins"]
    for plugin in generado["plugins"]:
        assert len(plugin["source"]["sha"]) == 40, plugin["name"]


def test_source_se_emite_como_objeto_y_no_como_cadena():
    # La forma abreviada de `source` es una cadena y NO admite `sha`.
    generado = json.loads(catalogo.render(Indice((_entrada("a"),), ()), "agentico", PROPIETARIO, "0.1"))
    assert isinstance(generado["plugins"][0]["source"], dict)


def test_los_plugins_salen_ordenados_por_nombre():
    # Sin orden fijo, cada regeneracion produce un diff distinto sin que nada haya cambiado.
    generado = json.loads(catalogo.render(Indice((_entrada("z"), _entrada("a")), ()),
                                          "agentico", PROPIETARIO, "0.1"))
    assert [p["name"] for p in generado["plugins"]] == ["a", "z"]


def test_el_catalogo_avisa_de_que_esta_generado():
    generado = json.loads(catalogo.render(Indice((), ()), "agentico", PROPIETARIO, "0.1"))
    assert "no editar a mano" in generado["metadata"]["description"]


# ── caso de uso, con dobles ────────────────────────────────────────────────────────────────
class GithubFalso:
    """Doble del adaptador de GitHub. `sellado` decide si la atestacion verifica."""

    def __init__(self, repositorios: list[str], *, sellado: bool = True, con_release: bool = True,
                 con_paquete: bool = True):
        self._repositorios = repositorios
        self._sellado = sellado
        self._con_release = con_release
        self._con_paquete = con_paquete

    def repositorios_del_dominio(self, organizacion, topico):
        return self._repositorios

    def ultimo_release(self, repositorio):
        if not self._con_release:
            return None
        return "v0.2.0", "d" * 40, "paquete.tar.gz" if self._con_paquete else None

    def descargar_paquete(self, repositorio, etiqueta, paquete, destino):
        return Path(destino) / paquete

    def verificar_atestacion(self, ruta, repositorio):
        return self._sellado

    def veredicto_atestado(self, ruta, repositorio):
        return {"conforme": True} if self._sellado else None


class LectorFalso:
    def digest(self, ruta):
        return "e" * 64

    def leer_manifiesto(self, ruta):
        return {"name": "migracion-cnf", "description": "d", "version": "0.2.0"}


def test_un_dominio_sellado_entra_al_indice():
    indice = generar("org", "agent-skills",
                     github=GithubFalso(["org/agentes-sdlc"]), lector=LectorFalso())
    assert [e.name for e in indice.entradas] == ["migracion-cnf"]
    assert indice.rechazos == ()


def test_un_dominio_sin_sellar_se_rechaza_sin_tumbar_la_generacion():
    """El defecto que cubre: si un rechazo abortara, un solo dominio mal publicado congelaria el
    indice de TODOS los demas."""
    indice = generar("org", "agent-skills",
                     github=GithubFalso(["org/agentes-sdlc"], sellado=False),
                     lector=LectorFalso())
    assert indice.entradas == ()
    assert indice.rechazos == (Rechazo("org/agentes-sdlc", Motivo.SIN_ATESTACION),)


def test_un_repositorio_sin_releases_se_rechaza_por_ese_motivo_y_no_por_otro():
    indice = generar("org", "agent-skills",
                     github=GithubFalso(["org/agentes-sdlc"], con_release=False),
                     lector=LectorFalso())
    assert indice.rechazos[0].motivo is Motivo.SIN_RELEASE


def test_un_release_sin_paquete_no_se_confunde_con_no_tener_release():
    """Defecto medido al ejecutar el generador contra la organizacion real: los dos casos daban el
    mismo motivo, y el equipo del dominio habria buscado un release que si existia."""
    indice = generar("org", "agent-skills",
                     github=GithubFalso(["org/agentes-sdlc"], con_paquete=False),
                     lector=LectorFalso())
    assert indice.rechazos[0].motivo is Motivo.SIN_PAQUETE


def test_sin_repositorios_el_indice_sale_vacio_y_no_falla():
    indice = generar("org", "agent-skills", github=GithubFalso([]), lector=LectorFalso())
    assert indice == Indice((), ())
