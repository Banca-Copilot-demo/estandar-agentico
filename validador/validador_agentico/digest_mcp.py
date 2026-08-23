#!/usr/bin/env python3
"""Entry point: pregunta a un servidor MCP que herramientas declara y calcula su digest.

PARA QUE SIRVE, y por que es un comando y no un paso de CI: al APROBAR un `mcp` hay que registrar el
`tools_digest` en su `METADATA.json`, y ese valor tiene que salir de preguntarle al servidor. Sin este
comando el numero habria que calcularlo a mano, que es la clase de paso que se hace mal una vez y
nadie vuelve a mirar.

Tambien sirve para diagnosticar: si un servidor no responde, aqui se ve el motivo exacto antes de que
la comprobacion periodica lo reporte como SIN_COMPROBAR.

LA CREDENCIAL LLEGA POR ENTORNO, nunca por argumento: un token en la linea de comandos queda en el
historial del shell y en la tabla de procesos.

SALIDA A STDOUT PORQUE LA CONSUME UNA PERSONA O UN PROCESO; el diagnostico va a stderr (L8).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from validador_agentico.adaptadores import mcp_cliente
from validador_agentico.dominio.herramientas_mcp import (
    CAMPO_DESCRIPCION,
    CAMPO_NOMBRE,
    HerramientaSinNombreError,
    digest_de,
    forma_canonica,
)

log = logging.getLogger(__name__)

SALIDA_OK = 0
SALIDA_ERROR = 1

VARIABLE_CREDENCIAL = "MCP_CREDENCIAL"
# Cuanto se muestra de cada descripcion en el listado legible. Lo justo para reconocerla sin volcar
# parrafos de texto que escribio un tercero.
_MAX_DESCRIPCION_MOSTRADA = 90


def _configurar_logging(verboso: bool) -> None:
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
    logging.getLogger().setLevel(logging.DEBUG if verboso else logging.INFO)
    logging.getLogger().addHandler(manejador)


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        prog="digest-mcp",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"La credencial, si el servidor la exige, se lee de ${VARIABLE_CREDENCIAL}.")
    ap.add_argument("endpoint", help="URL del servidor MCP (transporte http o sse)")
    ap.add_argument("--formato", choices=("texto", "json", "canonico"), default="texto",
                    help="`texto` para leerlo; `json` para consumirlo; `canonico` para ver EXACTAMENTE"
                         " sobre que se calcula el digest, que es lo que hace falta cuando dos "
                         "digests difieren y se quiere saber por que")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Activa logging DEBUG (detalles internos de ejecucion).")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argumentos = _parsear_argumentos(argv)
    _configurar_logging(argumentos.verbose)

    credencial = os.environ.get(VARIABLE_CREDENCIAL) or None
    if credencial is None:
        log.info("sin credencial en $%s: solo funcionara si el servidor no la exige",
                 VARIABLE_CREDENCIAL)

    try:
        herramientas = mcp_cliente.listar_herramientas(argumentos.endpoint, credencial)
    except mcp_cliente.ServidorInalcanzableError as fallo:
        log.error("no se pudo consultar %s: %s", argumentos.endpoint, fallo)
        return SALIDA_ERROR

    try:
        digest = digest_de(herramientas)
    except HerramientaSinNombreError as fallo:
        log.error("%s", fallo)
        return SALIDA_ERROR

    if argumentos.formato == "canonico":
        print(forma_canonica(herramientas))
        return SALIDA_OK

    if argumentos.formato == "json":
        print(json.dumps({"endpoint": argumentos.endpoint, "tools_digest": digest,
                          "herramientas": [h.get(CAMPO_NOMBRE) for h in herramientas]},
                         indent=2, ensure_ascii=False, sort_keys=True))
        return SALIDA_OK

    print(f"{len(herramientas)} herramienta(s) en {argumentos.endpoint}:")
    for herramienta in sorted(herramientas, key=lambda h: str(h.get(CAMPO_NOMBRE, ""))):
        descripcion = str(herramienta.get(CAMPO_DESCRIPCION) or "").replace("\n", " ")
        recortada = descripcion[:_MAX_DESCRIPCION_MOSTRADA]
        if len(descripcion) > _MAX_DESCRIPCION_MOSTRADA:
            recortada += "..."
        print(f"  - {herramienta.get(CAMPO_NOMBRE)}: {recortada}")
    print()
    print("tools_digest para el METADATA.json:")
    print(f"  {digest}")
    return SALIDA_OK


if __name__ == "__main__":
    sys.exit(main())
