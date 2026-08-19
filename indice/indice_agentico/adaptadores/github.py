"""Adaptador de GitHub. Todo pasa por `gh`, no por `requests`, y es una decision deliberada:
`gh attestation verify` trae la raiz de confianza de Sigstore, la logica de verificacion y el
soporte de repositorios privados -- donde NO hay registro publico de transparencia --. Reimplementar
eso con llamadas HTTP seria reescribir criptografia de verificacion para ahorrar una dependencia
que ya esta instalada en todos los runners.
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

TIPO_PREDICADO_VEREDICTO = "https://ejemplo.dev/atestaciones/veredicto-de-conformidad/v1"
SUFIJO_PAQUETE = ".tar.gz"
_TIEMPO_LIMITE_S = 120


def _gh(*argumentos: str) -> str | None:
    """Ejecuta `gh` y devuelve su stdout, o `None` si fallo. Se devuelve `None` en vez de propagar
    la excepcion porque el fallo de UN repositorio no debe tumbar la generacion del indice
    completo: se registra, se rechaza ese candidato y se sigue con los demas."""
    orden = ("gh", *argumentos)
    log.debug("ejecutando: gh %s", " ".join(argumentos))
    try:
        salida = subprocess.run(orden, capture_output=True, text=True, encoding="utf-8",
                                timeout=_TIEMPO_LIMITE_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        log.warning("gh %s no se pudo ejecutar: %s", argumentos[0], error)
        return None
    if salida.returncode != 0:
        log.warning("gh %s fallo: %s", " ".join(argumentos[:2]), salida.stderr.strip())
        return None
    return salida.stdout


def repositorios_del_dominio(organizacion: str, topico: str) -> list[str]:
    """Los repositorios de dominio se DESCUBREN por topico en vez de mantenerse en una lista.
    Una lista habria que actualizarla a mano en el repositorio del indice cada vez que nace un
    dominio, y el equipo del dominio no puede escribir ahi: seria un cuello de botella."""
    salida = _gh("repo", "list", organizacion, "--topic", topico, "--limit", "200",
                 "--json", "nameWithOwner")
    if salida is None:
        return []
    return sorted(repo["nameWithOwner"] for repo in json.loads(salida))


def ultimo_release(repositorio: str) -> tuple[str, str, str | None] | None:
    """Devuelve (etiqueta, sha, nombre del paquete) del ultimo release; el paquete es `None` si el
    release no trae ninguno, y el valor entero es `None` si no hay release.

    LA DISTINCION IMPORTA y no es cosmetica: se midio al ejecutarlo contra la organizacion real. Con
    un solo `None` para los dos casos, un release que existia pero no traia paquete se reportaba
    como "no tiene ningun release publicado", y el equipo del dominio se habria puesto a buscar por
    que no se creo su release -- que si se creo --.
    """
    salida = _gh("release", "view", "--repo", repositorio,
                 "--json", "tagName,targetCommitish,assets")
    if salida is None:
        return None
    release = json.loads(salida)
    paquetes = sorted(a["name"] for a in release.get("assets", [])
                      if a["name"].endswith(SUFIJO_PAQUETE))
    if not paquetes:
        log.warning("%s: el release %s no trae paquete %s",
                    repositorio, release["tagName"], SUFIJO_PAQUETE)
    return release["tagName"], release["targetCommitish"], paquetes[0] if paquetes else None


def descargar_paquete(repositorio: str, etiqueta: str, paquete: str, destino: Path) -> Path | None:
    if _gh("release", "download", etiqueta, "--repo", repositorio,
           "--pattern", paquete, "--dir", str(destino)) is None:
        return None
    descargado = destino / paquete
    return descargado if descargado.is_file() else None


def verificar_atestacion(ruta: Path, repositorio: str) -> bool:
    """Verifica la atestacion de PROCEDENCIA sobre los bytes del paquete descargado."""
    return _gh("attestation", "verify", str(ruta), "--repo", repositorio,
               "--format", "json") is not None


def veredicto_atestado(ruta: Path, repositorio: str) -> dict | None:
    """Devuelve el predicado del veredicto tal como quedo FIRMADO.

    Se lee de la atestacion y no del repositorio a proposito: el objetivo es saber que gates paso
    el paquete, y cualquier archivo del repositorio se puede editar despues de publicar.
    """
    salida = _gh("attestation", "verify", str(ruta), "--repo", repositorio,
                 "--predicate-type", TIPO_PREDICADO_VEREDICTO, "--format", "json")
    if salida is None:
        return None
    try:
        atestaciones = json.loads(salida)
        return atestaciones[0]["verificationResult"]["statement"]["predicate"]
    except (json.JSONDecodeError, IndexError, KeyError, TypeError) as error:
        log.warning("%s: la atestacion del veredicto no tiene la forma esperada: %s",
                    repositorio, error)
        return None
