#!/usr/bin/env python3
"""Imprime los CLAIMS de un token OIDC de GitHub Actions. Nunca el token.

POR QUE EXISTE. En la demo de custodia con Vault, lo que hace entendible el mecanismo es ver sobre que
decide la boveda: `job_workflow_ref` identifica el archivo de workflow y su rama, y es lo que impide
que otro workflow del mismo repositorio obtenga la credencial. Sin verlo, la demo es un comando que
funciona por razones invisibles.

EL TOKEN NO SE IMPRIME NUNCA. Un token OIDC es una credencial de corta vida, pero mientras vive sirve
para autenticarse en la boveda. Se leen sus claims -- que no son secretos -- y se descarta.

NO SE VERIFICA LA FIRMA aqui, y no hace falta: quien la verifica es la boveda, que es la que decide.
Esto solo hace legible lo que va a evaluar.
"""
from __future__ import annotations

import base64
import json
import logging
import sys

log = logging.getLogger(__name__)

# Los claims que deciden el acceso en el atado de Vault, en el orden en que ayudan a leerlo.
CLAIMS_QUE_DECIDEN = ("iss", "aud", "repository", "ref", "job_workflow_ref", "actor")

_PARTES_DE_UN_JWT = 3
_INDICE_DEL_CUERPO = 1


def _claims_de(jwt: str) -> dict:
    """Los claims del cuerpo del JWT, sin verificar la firma."""
    partes = jwt.strip().split(".")
    if len(partes) != _PARTES_DE_UN_JWT:
        raise ValueError(f"no parece un JWT: tiene {len(partes)} partes y no {_PARTES_DE_UN_JWT}")
    cuerpo = partes[_INDICE_DEL_CUERPO]
    # base64url sin relleno: se repone para que `b64decode` no falle.
    cuerpo += "=" * (-len(cuerpo) % 4)
    return json.loads(base64.urlsafe_b64decode(cuerpo))


def _configurar_logging() -> None:
    """El diagnostico va a `stderr` por un handler, no por un `print` suelto (L1/L4/L8).

    Se configura AQUI y no al importar: este archivo tambien se lee como ejemplo del mecanismo y un
    modulo que toca el logger raiz al importarse se lo cambia a quien lo importe.
    """
    handler = logging.StreamHandler(sys.stderr)
    # El mismo formato que `registro.py` usa en CI, y con el mismo separador ASCII: el runner ya
    # sella cada linea con su hora, asi que aqui no se repite.
    handler.setFormatter(logging.Formatter(fmt="%(levelname)-8s %(name)s - %(message)s"))
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    raiz.addHandler(handler)


def main() -> int:
    _configurar_logging()
    try:
        claims = _claims_de(sys.stdin.read())
    except (ValueError, json.JSONDecodeError) as fallo:
        # `exc_info` en vez del texto del fallo a mano: sin traza, un JWT con el numero de partes
        # equivocado y un cuerpo que no es JSON dan el mismo mensaje y no se sabe cual paso (L6).
        log.error("no se pudieron leer los claims", exc_info=fallo)
        return 1
    for clave in CLAIMS_QUE_DECIDEN:
        print(f"  {clave}: {claims.get(clave, '(ausente)')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
