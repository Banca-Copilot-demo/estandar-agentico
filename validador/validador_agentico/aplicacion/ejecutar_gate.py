"""Caso de uso: ejecutar el GATE COMPLETO y devolver un solo veredicto.

Es la pieza que antes vivia como pasos de bash en una accion compuesta. Traerla aqui cambia tres
cosas que importan:

  1. **Se puede probar.** La agregacion es una funcion pura del dominio y este orquestador recibe
     sus dependencias por parametro, asi que las pruebas cubren los tres resultados sin `gh`.
  2. **Se puede ejecutar en local.** El autor corre EL MISMO comando que corre CI, asi que el pull
     request nace en verde en vez de rebotar. Antes la agregacion solo existia dentro del `.yml` y
     reproducirla a mano era imposible en la practica.
  3. **G1 deja de estar partido.** Antes habia un paso llamado `G1` y otro llamado `G1 G3 G4`, y
     ninguno de los dos sabia del otro. G1 es UNA comprobacion con dos fuentes.

Este modulo ORQUESTA: no decide si algo esta conforme -- eso lo hace `comprobacion.agrega_conforme`
-- ni comprueba reglas -- eso lo hace `validar_repositorio` --.
"""
from __future__ import annotations

import logging
from pathlib import Path

from validador_agentico.adaptadores import gh_skill
from validador_agentico.aplicacion.validar_repositorio import validar
from validador_agentico.dominio.comprobacion import (
    Comprobacion,
    Resultado,
    ResultadoGate,
)
from validador_agentico.dominio.hallazgo import Veredicto
from validador_agentico.puertos.especificacion_oficial import NOMBRE_COMPROBACION_OFICIAL

log = logging.getLogger(__name__)

NOMBRE_COMPROBACION_PROPIA = "estandar agentico (G1 G3 G4)"


def _comprobacion_propia(veredicto: Veredicto) -> Comprobacion:
    if veredicto.conforme:
        detalle = f"sin errores; {len(veredicto.avisos)} aviso(s)"
        return Comprobacion(NOMBRE_COMPROBACION_PROPIA, Resultado.CONFORME, detalle)
    return Comprobacion(NOMBRE_COMPROBACION_PROPIA, Resultado.NO_CONFORME,
                        f"{len(veredicto.errores)} error(es) que bloquean")


def ejecutar(raiz: Path, *, comprobador_oficial=gh_skill,
             con_comprobacion_oficial: bool = True,
             equipos_conocidos: frozenset[str] | None = None,
             archivos_cambiados: tuple[str, ...] | None = None,
             directorio_de_esquemas: Path | None = None) -> ResultadoGate:
    """Corre TODAS las comprobaciones y agrega al final.

    `con_comprobacion_oficial=False` existe para poder correr el gate sin salir a un proceso
    externo -- util en local y en las pruebas del propio validador --. No cambia el criterio: una
    comprobacion que no se ejecuta se declara `NO_APLICA` con su motivo, nunca se da por buena en
    silencio.
    """
    veredicto = validar(raiz, equipos_conocidos=equipos_conocidos,
                        archivos_cambiados=archivos_cambiados,
                        directorio_de_esquemas=directorio_de_esquemas)
    comprobaciones = [_comprobacion_propia(veredicto)]

    if con_comprobacion_oficial:
        comprobaciones.append(comprobador_oficial.comprobar(raiz))
    else:
        comprobaciones.append(Comprobacion(
            NOMBRE_COMPROBACION_OFICIAL, Resultado.NO_APLICA,
            "desactivada explicitamente con --sin-comprobacion-oficial"))

    resultado = ResultadoGate(veredicto=veredicto, comprobaciones=tuple(comprobaciones))
    log.info("gate %s: %d comprobacion(es)",
             "CONFORME" if resultado.conforme else "NO CONFORME", len(comprobaciones))
    return resultado
