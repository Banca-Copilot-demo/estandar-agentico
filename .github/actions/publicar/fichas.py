"""Publica en Port una ficha por artefacto, construida del PREDICADO FIRMADO.

POR QUE ES UN SCRIPT Y NO BASH. Hay que leer un JSON, derivar campos por artefacto y hacer una
llamada por cada uno. En bash serian varias invocaciones a `python3 -c` con el JSON interpolado en
la linea de comandos: el patron fragil que ya nos rompio dos veces.

POR QUE SE LEE DEL PREDICADO Y NO DEL REPOSITORIO. El predicado es lo que se firmo. Si la ficha se
construyera releyendo los archivos, podria decir algo distinto de lo sellado y habria dos fuentes de
verdad sobre el mismo artefacto -- el problema que el sello existe para eliminar.

UN FALLO AQUI NO DESHACE LA PUBLICACION. El release y las atestaciones ya existen y son
inmutables; la ficha es la vitrina. Si Port no responde, se avisa y se sigue: el artefacto YA es
instalable y el catalogo se pone al dia en la siguiente publicacion.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_PORT = "https://api.port.io"
BLUEPRINT = "artefacto_agentico"
# Quien FIRMA las atestaciones: el workflow reutilizable del estandar, no el repo del dominio.
SIGNER = "Banca-Copilot-demo/estandar-agentico"
# `name` del catalogo del marketplace, el que resuelve `<plugin>@<catalogo>`.
CATALOGO = "agentico"
# Donde espera cada cliente un prompt. `commands/` en el origen; en el destino cambia por cliente.
_DESTINO_PROMPT = ".github/prompts"
_TIEMPO_LIMITE_S = 30
# `upsert` actualiza si ya existe, y `merge` conserva las propiedades que este payload no trae.
_RUTA_ENTIDADES = f"/v1/blueprints/{BLUEPRINT}/entities?upsert=true&merge=true"

# Los tipos que un plugin TRANSPORTA. Agent Plugins v1 cubre skills y MCP; Copilot documenta
# cinco componentes -- agents, skills, hooks, .mcp.json, lsp.json --. NI `prompt` NI `instructions`
# estan en ninguna de las dos listas, asi que viajan por otro canal aunque vivan en el mismo
# repositorio y esten dentro del paquete sellado.
_TIPOS_EN_PLUGIN = frozenset({"skill", "agent", "mcp", "hooks"})


def _pista_de_instalacion(artefacto: dict, en_marketplace: bool, repositorio: str,
                          sha: str, etiqueta: str, nombre_plugin: str) -> str:
    """El COMANDO exacto que el consumidor ejecuta. Siempre un comando: una descripcion en prosa
    obliga al consumidor a averiguar como se instala, que es justo lo que la ficha evita."""
    if en_marketplace:
        # Se instala el PLUGIN, no el artefacto: un plugin se instala completo. Poner aqui el id del
        # artefacto daba un comando que no resuelve contra ninguna entrada del marketplace.
        return f"copilot plugin install {nombre_plugin}@{CATALOGO}"
    if artefacto["tipo"] == "skill":
        return f"gh skill install {repositorio}/{artefacto['ruta']} --pin {etiqueta}"

    # Un `prompt` no lo instala ninguna herramienta oficial: no es componente de plugin y `gh skill`
    # es exclusivo de skills. Se trae el archivo FIJADO AL SHA -- no a la etiqueta -- porque el sha
    # es lo que quedo sellado, y el nombre del destino lo fija el cliente, no nosotros.
    destino = f"{_DESTINO_PROMPT}/{artefacto['ruta'].rsplit('/', 1)[-1]}"
    return (f"curl -fsSL https://raw.githubusercontent.com/{repositorio}/{sha}/"
            f"{artefacto['ruta']} -o {destino}")


def _pista_de_verificacion(artefacto: dict, en_marketplace: bool, repositorio: str,
                           paquete_o_archivo: str) -> str:
    """Como comprobar el sello ANTES de confiar en lo instalado.

    MEDIDO: ni `copilot plugin install` ni `gh skill install` documentan verificacion de
    atestaciones, y el `--help` de `gh skill install` no la menciona. Asi que verificar es un paso
    EXPLICITO, y la ficha tiene que decir como -- incluido el `--signer-repo`, sin el cual la
    verificacion falla con un mensaje que no menciona al firmante.
    """
    if en_marketplace or artefacto["tipo"] == "skill":
        return (f"gh attestation verify <paquete>.tar.gz --repo {repositorio} "
                f"--signer-repo {SIGNER}")
    # Un archivo copiado fuera del paquete no se verifica contra la atestacion: se compara su sha256
    # contra el que quedo firmado en el predicado.
    return f"sha256sum {paquete_o_archivo}  # debe dar {artefacto.get('sha256', '')}"


def _entidad(artefacto: dict, veredicto: dict, argumentos: argparse.Namespace) -> dict:
    en_marketplace = veredicto["inventario"]["tiene_plugin"] and \
        artefacto["tipo"] in _TIPOS_EN_PLUGIN
    return {
        "identifier": artefacto["id"],
        "title": f"{artefacto['id']} ({artefacto['tipo']})",
        "properties": {
            "tipo": artefacto["tipo"],
            # `conformant` y no `certified`: la promocion la decide G5, despues, y no este paso.
            "status": "conformant",
            "owner_team": artefacto["owner_team"],
            "owner_contact": artefacto["owner_contact"],
            "data_classification": artefacto["data_classification"],
            "standard_version": artefacto["standard_version"],
            "repo": argumentos.repositorio,
            "ref": argumentos.etiqueta,
            "sha": argumentos.sha,
            "digest": argumentos.digest,
            "install_hint": _pista_de_instalacion(
                artefacto, en_marketplace, argumentos.repositorio, argumentos.sha,
                argumentos.etiqueta, veredicto["inventario"].get("nombre_plugin", "")),
            "verify_hint": _pista_de_verificacion(
                artefacto, en_marketplace, argumentos.repositorio, artefacto["ruta"]),
            "sha256_archivo": artefacto.get("sha256", ""),
            "en_marketplace": en_marketplace,
        },
    }


def _publicar(entidad: dict, token: str) -> str:
    peticion = urllib.request.Request(
        API_PORT + _RUTA_ENTIDADES,
        data=json.dumps(entidad).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=_TIEMPO_LIMITE_S) as respuesta:
            return f"HTTP {respuesta.status}"
    except urllib.error.HTTPError as fallo:
        return f"HTTP {fallo.code}: {fallo.read()[:200].decode('utf-8', 'replace')}"
    except (urllib.error.URLError, TimeoutError) as fallo:
        return f"sin respuesta: {fallo}"


def _parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publica las fichas del catalogo en Port.")
    parser.add_argument("--veredicto", type=Path, required=True,
                        help="predicado firmado del que se construye la ficha")
    parser.add_argument("--repositorio", required=True)
    parser.add_argument("--etiqueta", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--token", required=True)
    return parser.parse_args()


def main() -> int:
    argumentos = _parsear_argumentos()
    veredicto = json.loads(argumentos.veredicto.read_text(encoding="utf-8"))
    artefactos = veredicto.get("artefactos") or []

    if not artefactos:
        print("El predicado no declara artefactos: no hay ficha que publicar.", file=sys.stderr)
        return 0

    fallos = 0
    for artefacto in artefactos:
        resultado = _publicar(_entidad(artefacto, veredicto, argumentos), argumentos.token)
        print(f"  {artefacto['id']:50} {resultado}")
        if not resultado.startswith("HTTP 2"):
            fallos += 1

    if fallos:
        # Aviso y no error: el release y las atestaciones ya son inmutables, y el artefacto YA es
        # instalable. La ficha se pone al dia en la siguiente publicacion.
        print(f"::warning::{fallos} ficha(s) no se pudieron publicar en el catalogo. "
              "El artefacto ya es instalable: la vitrina se pone al dia despues.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
