#!/usr/bin/env python3
"""Entry point: comprueba si los servidores MCP cambiaron sus herramientas desde que se aprobaron.

QUE HACE. Recibe una LINEA BASE -- que `mcp` hay, su digest atestado y donde consultarlo --, pregunta
a cada servidor que herramientas declara hoy, y compara. Emite el resultado como JSON a stdout para
que otro proceso lo consuma (L8), y un resumen legible al archivo que se le indique.

QUE NO HACE, y es deliberado:
  - NO produce la linea base. Sale del predicado FIRMADO, y quien sabe verificar atestaciones es el
    indice: replicarlo aqui seria una segunda implementacion del mismo trato con la firma (G2). Este
    programa la recibe ya reunida.
  - NO abre issues. Decidir a quien se avisa y como es politica, no comprobacion; y separarlo permite
    ejecutar esto en local sin escribir en ningun sitio.
  - NO lee la boveda. La credencial llega ya resuelta en la linea base, o no llega y el resultado es
    SIN_COMPROBAR con su motivo. Asi este programa no necesita permisos sobre la boveda.

LO QUE RECIBE DE LOS SERVIDORES ES DATO HOSTIL: las descripciones las escribe un tercero. Entran en el
digest y NO salen en el reporte. Ver `dominio/deriva_mcp.py`.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from validador_agentico.adaptadores import mcp_cliente
from validador_agentico.dominio.deriva_mcp import Comprobacion, Resultado, comparar, resumir
from validador_agentico.dominio.herramientas_mcp import (
    CAMPO_NOMBRE,
    HerramientaSinNombreError,
    digest_de,
)

log = logging.getLogger(__name__)

SALIDA_TODO_CONFORME = 0
# UN CODIGO PROPIO PARA «HAY QUE MIRAR ESTO», distinto del error de ejecucion: el workflow tiene que
# poder distinguir «encontre una deriva» de «me rompi», porque se atienden de forma distinta.
SALIDA_EXIGE_ATENCION = 3
SALIDA_ERROR = 1

_CLAVE_MCPS = "mcps"


def _consultar(entrada: dict) -> Comprobacion:
    """Compara UN `mcp` de la linea base contra lo que su servidor declara ahora."""
    artefacto = entrada.get("artefacto", "(sin id)")
    atestado = entrada.get("tools_digest", "")
    endpoint = entrada.get("endpoint", "")

    if not endpoint:
        return comparar(artefacto, atestado, None,
                        motivo_de_fallo="la metadata no declara `endpoint`: solo se pueden consultar "
                                        "los servidores remotos, y un `stdio` esta cubierto por su "
                                        "`version_pin`")
    try:
        herramientas = mcp_cliente.listar_herramientas(endpoint, entrada.get("credencial"))
    except mcp_cliente.ServidorInalcanzableError as fallo:
        return comparar(artefacto, atestado, None, motivo_de_fallo=str(fallo))

    try:
        actual = digest_de(herramientas)
    except HerramientaSinNombreError as fallo:
        return comparar(artefacto, atestado, None, motivo_de_fallo=str(fallo))

    return comparar(
        artefacto, atestado, actual,
        nombres_atestados=tuple(entrada.get("herramientas_atestadas") or ()),
        nombres_actuales=tuple(str(h.get(CAMPO_NOMBRE, "")) for h in herramientas),
    )


def comprobar(linea_base: list[dict]) -> list[Comprobacion]:
    """Todas las comprobaciones. Una que falle no impide las demas: un servidor caido no puede
    dejar sin vigilar a los otros."""
    return [_consultar(entrada) for entrada in linea_base]


def _como_dato(comprobacion: Comprobacion) -> dict:
    return {
        "artefacto": comprobacion.artefacto,
        "resultado": comprobacion.resultado.value,
        "digest_atestado": comprobacion.digest_atestado,
        "digest_actual": comprobacion.digest_actual,
        "motivo": comprobacion.motivo,
        "herramientas_nuevas": list(comprobacion.herramientas_nuevas),
        "herramientas_retiradas": list(comprobacion.herramientas_retiradas),
    }


def _configurar_logging(verboso: bool) -> None:
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter("%(levelname)-8s %(name)s - %(message)s"))
    logging.getLogger().setLevel(logging.DEBUG if verboso else logging.INFO)
    logging.getLogger().addHandler(manejador)


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="comprobar-mcp",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--linea-base", type=Path, required=True,
                    help="JSON con los `mcp` a comprobar: artefacto, tools_digest, endpoint y, si "
                         "hace falta, credencial ya resuelta")
    ap.add_argument("--resumen", type=Path,
                    help="archivo donde escribir el resumen legible (p. ej. $GITHUB_STEP_SUMMARY)")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Activa logging DEBUG (detalles internos de ejecucion).")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argumentos = _parsear_argumentos(argv)
    _configurar_logging(argumentos.verbose)

    try:
        datos = json.loads(argumentos.linea_base.read_text(encoding="utf-8"))
    except json.JSONDecodeError as fallo:
        log.error("la linea base no es JSON valido: %s", fallo)
        return SALIDA_ERROR
    except OSError as fallo:
        log.error("no se pudo leer la linea base: %s", fallo)
        return SALIDA_ERROR

    comprobaciones = comprobar(datos.get(_CLAVE_MCPS) or [])
    print(json.dumps({_CLAVE_MCPS: [_como_dato(c) for c in comprobaciones]},
                     indent=2, ensure_ascii=False, sort_keys=True))

    if argumentos.resumen is not None:
        argumentos.resumen.write_text(resumir(comprobaciones) + "\n", encoding="utf-8")

    for comprobacion in comprobaciones:
        if comprobacion.resultado is Resultado.DERIVA:
            log.error("DERIVA en %s: %s", comprobacion.artefacto, comprobacion.motivo)
        elif comprobacion.resultado is Resultado.SIN_COMPROBAR:
            log.warning("SIN COMPROBAR %s: %s", comprobacion.artefacto, comprobacion.motivo)

    exigen = [c for c in comprobaciones if c.exige_atencion]
    log.info("%d mcp comprobado(s), %d exigen atencion", len(comprobaciones), len(exigen))
    return SALIDA_EXIGE_ATENCION if exigen else SALIDA_TODO_CONFORME


if __name__ == "__main__":
    sys.exit(main())
