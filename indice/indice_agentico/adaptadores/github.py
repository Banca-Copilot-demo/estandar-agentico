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

# QUIEN FIRMA NO ES DE QUIEN ES EL CONTENIDO, y esto se midio. El paquete sale del repositorio del
# dominio, pero lo firma el workflow reutilizable del ESTANDAR, asi que el certificado lleva:
#
#   sourceRepositoryURI  ->  .../agentes-<dominio>
#   buildSignerURI       ->  .../estandar-agentico/.github/workflows/publicar.yml@main
#
# Sin declarar el firmante, `gh attestation verify --repo <dominio>` falla con codigo 1 y el mensaje
# solo dice «verifying with issuer sigstore.dev» -- no menciona el firmante, asi que el motivo real
# es invisible. Un release perfectamente sellado quedaba FUERA DEL INDICE por esto.
REPOSITORIO_FIRMANTE_POR_DEFECTO = "Banca-Copilot-demo/estandar-agentico"
SUFIJO_PAQUETE = ".tar.gz"
_TIEMPO_LIMITE_S = 120
# Tope de releases que se listan por repositorio. Acota el coste sin recortar nada real: solo se
# evalua la etiqueta VIGENTE de cada plugin, y ningun repositorio de dominio aloja tantos plugins.
_MAX_RELEASES_POR_REPOSITORIO = 100


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


def etiquetas_publicadas(repositorio: str) -> tuple[str, ...]:
    """Las etiquetas de TODOS los releases, de la mas nueva a la mas vieja.

    Solo las etiquetas y no los releases completos: agrupar por plugin se hace con el nombre de la
    etiqueta, asi que basta esta llamada barata para saber cuales merece la pena descargar. Bajar y
    verificar la atestacion de cada release del historial costaria unos diez segundos por release.
    """
    salida = _gh("release", "list", "--repo", repositorio,
                 "--limit", str(_MAX_RELEASES_POR_REPOSITORIO), "--json", "tagName,publishedAt")
    if salida is None:
        return ()
    releases = json.loads(salida)
    # `gh` ya los devuelve de mas nuevo a mas viejo, pero se ordena explicitamente: el orden decide
    # cual version de cada plugin queda vigente, y no conviene que dependa de un detalle del CLI.
    ordenados = sorted(releases, key=lambda r: r.get("publishedAt") or "", reverse=True)
    return tuple(r["tagName"] for r in ordenados)


def release(repositorio: str, etiqueta: str) -> tuple[str, str, str | None] | None:
    """El release de UNA etiqueta: (etiqueta, sha, nombre del paquete). `None` si no existe.

    El paquete es `None` cuando el release existe pero no trae ninguno, y esa DISTINCION importa --
    se midio contra la organizacion real --: con un solo `None` para los dos casos, un release que
    existia pero no traia paquete se reportaba como «no tiene ningun release publicado», y el equipo
    del dominio se habria puesto a buscar por que no se creo su release, que si se creo.
    """
    salida = _gh("release", "view", etiqueta, "--repo", repositorio,
                 "--json", "tagName,targetCommitish,assets")
    if salida is None:
        return None
    datos = json.loads(salida)
    paquetes = sorted(a["name"] for a in datos.get("assets", [])
                      if a["name"].endswith(SUFIJO_PAQUETE))
    if not paquetes:
        log.warning("%s: el release %s no trae paquete %s",
                    repositorio, etiqueta, SUFIJO_PAQUETE)

    sha = _sha_de_la_etiqueta(repositorio, etiqueta)
    if sha is None:
        return None
    return etiqueta, sha, paquetes[0] if paquetes else None


def _sha_de_la_etiqueta(repositorio: str, etiqueta: str) -> str | None:
    """El commit al que apunta la etiqueta, resuelto.

    NO se usa `targetCommitish` del release, y esto se midio: para un release creado desde una
    etiqueta devuelve el NOMBRE DE LA RAMA -- literalmente `main` --, asi que la entrada del catalogo
    quedaba con `sha: main`. Un puntero movil es exactamente lo que el `sha` existe para evitar: la
    etiqueta se puede reescribir si el repositorio no tiene releases inmutables, y `main` avanza con
    cada commit.
    """
    salida = _gh("api", f"repos/{repositorio}/commits/{etiqueta}", "--jq", ".sha")
    if salida is None:
        log.warning("%s: no se pudo resolver el commit de la etiqueta %s", repositorio, etiqueta)
        return None
    sha = salida.strip()
    return sha or None


def descargar_paquete(repositorio: str, etiqueta: str, paquete: str, destino: Path) -> Path | None:
    if _gh("release", "download", etiqueta, "--repo", repositorio,
           "--pattern", paquete, "--dir", str(destino)) is None:
        return None
    descargado = destino / paquete
    return descargado if descargado.is_file() else None


def verificar_atestacion(ruta: Path, repositorio: str,
                         repositorio_firmante: str = REPOSITORIO_FIRMANTE_POR_DEFECTO) -> bool:
    """Verifica la atestacion de PROCEDENCIA sobre los bytes del paquete descargado."""
    return _gh("attestation", "verify", str(ruta), "--repo", repositorio,
               "--signer-repo", repositorio_firmante, "--format", "json") is not None


def veredicto_atestado(ruta: Path, repositorio: str,
                       repositorio_firmante: str = REPOSITORIO_FIRMANTE_POR_DEFECTO) -> dict | None:
    """Devuelve el predicado del veredicto tal como quedo FIRMADO.

    Se lee de la atestacion y no del repositorio a proposito: el objetivo es saber que gates paso
    el paquete, y cualquier archivo del repositorio se puede editar despues de publicar.
    """
    salida = _gh("attestation", "verify", str(ruta), "--repo", repositorio,
                 "--signer-repo", repositorio_firmante,
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
