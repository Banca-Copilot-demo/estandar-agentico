"""Caso de uso: descubrir los dominios, comprobar lo que cada uno publico y devolver el indice.

Orquesta; no decide. La decision de indexar o rechazar esta entera en `reglas_indice.evaluar`, que
es pura y se prueba sin red ni disco. Aqui solo se recoge la evidencia y se pasa.

Los adaptadores llegan por parametro con un valor por defecto: asi el CLI no tiene que cablear nada
y una prueba puede sustituirlos sin parchear modulos.
"""
from __future__ import annotations

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from indice_agentico.adaptadores import github as adaptador_github
from indice_agentico.adaptadores import paquete as adaptador_paquete
from indice_agentico.dominio.candidato import (
    Candidato,
    Descarte,
    Destino,
    Entrada,
    Indice,
    Motivo,
)
from indice_agentico.dominio.reglas_indice import evaluar

log = logging.getLogger(__name__)


def _reunir_evidencia(repositorio: str, trabajo: Path, github, lector) -> Candidato | Motivo:
    release = github.ultimo_release(repositorio)
    if release is None:
        return Motivo.SIN_RELEASE
    etiqueta, sha, nombre_paquete = release
    if nombre_paquete is None:
        return Motivo.SIN_PAQUETE

    descargado = github.descargar_paquete(repositorio, etiqueta, nombre_paquete, trabajo)
    if descargado is None:
        return Motivo.SIN_PAQUETE

    lectura = lector.leer_manifiesto(descargado)
    # Sin plugin no se consulta la atestacion: el candidato se va a omitir de todas formas, y cada
    # verificacion es una llamada a `gh` que tarda.
    if not lectura.presente:
        return Candidato(repositorio=repositorio, etiqueta=etiqueta, sha=sha,
                         digest=lector.digest(descargado), lleva_plugin=False)

    return Candidato(
        repositorio=repositorio,
        etiqueta=etiqueta,
        sha=sha,
        digest=lector.digest(descargado),
        lleva_plugin=True,
        manifiesto=lectura.contenido,
        atestacion_verificada=github.verificar_atestacion(descargado, repositorio),
        veredicto=github.veredicto_atestado(descargado, repositorio),
    )


def generar(organizacion: str, topico: str, *, github=adaptador_github,
            lector=adaptador_paquete) -> Indice:
    repositorios = github.repositorios_del_dominio(organizacion, topico)
    log.info("%d repositorio(s) con el topico `%s` en %s",
             len(repositorios), topico, organizacion)

    entradas: list[Entrada] = []
    omisiones: list[Descarte] = []
    rechazos: list[Descarte] = []
    with TemporaryDirectory() as temporal:
        trabajo = Path(temporal)
        for repositorio in repositorios:
            evidencia = _reunir_evidencia(repositorio, trabajo, github, lector)
            if isinstance(evidencia, Motivo):
                rechazos.append(Descarte(repositorio, evidencia))
                continue
            decision = evaluar(evidencia)
            if decision.destino is Destino.INDEXAR:
                entradas.append(decision.entrada)
            elif decision.destino is Destino.OMITIR:
                omisiones.append(Descarte(repositorio, decision.motivo))
            else:
                rechazos.append(Descarte(repositorio, decision.motivo))

    log.info("%d indexado(s), %d omitido(s) sin plugin, %d rechazado(s)",
             len(entradas), len(omisiones), len(rechazos))
    return Indice(entradas=tuple(entradas), omisiones=tuple(omisiones),
                  rechazos=tuple(rechazos))
