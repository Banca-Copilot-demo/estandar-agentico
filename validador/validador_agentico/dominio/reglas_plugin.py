"""Reglas del plugin: manifiesto Agent Plugins 1.0, gobierno del conjunto e inventario.

EL PLUGIN ES OPCIONAL, SIEMPRE. Es una decision de EMPAQUETADO, no de riesgo: ningun tipo lo
exige por ser peligroso, porque el riesgo de cada uno lo cubre otro control que funciona con
plugin o sin el — `allowedMcpServers` y los `scopes` de la credencial para `mcp`, el `CODEOWNERS`
de seguridad para `hooks`, y G3 mas los permisos del repositorio para los datos sensibles.

PURAS (G5): reciben datos ya parseados y devuelven hallazgos.
"""
from __future__ import annotations

import re

from validador_agentico.dominio.especificacion import (
    CAMPOS_PLUGIN_OBLIGATORIOS,
    CAMPOS_PLUGIN_PERMITIDOS,
    PATRON_SEMVER,
    RUTA_MANIFIESTO_UNIFICADA,
)
from validador_agentico.dominio.hallazgo import Hallazgo, Inventario, aviso, error


def revisar_manifiesto(ruta_relativa: str, manifiesto: dict) -> list[Hallazgo]:
    """El `plugin.json` conforme a Agent Plugins 1.0, cuando el repositorio declara uno."""
    hallazgos: list[Hallazgo] = []
    if ruta_relativa != RUTA_MANIFIESTO_UNIFICADA:
        hallazgos.append(aviso(ruta_relativa,
                               f"esta ruta la reconoce Copilot pero NO Claude Code. Usa "
                               f"`{RUTA_MANIFIESTO_UNIFICADA}` para que el mismo plugin sirva "
                               "a los dos clientes"))
    hallazgos += [
        error(ruta_relativa, f"falta el campo obligatorio `{campo}`")
        for campo in CAMPOS_PLUGIN_OBLIGATORIOS if campo not in manifiesto
    ]
    sobrantes = sorted(set(manifiesto) - CAMPOS_PLUGIN_PERMITIDOS)
    if sobrantes:
        hallazgos.append(error(ruta_relativa,
                               f"campos de primer nivel no permitidos por la especificacion: "
                               f"{sobrantes}. Lo especifico del estandar va en `extensions` bajo "
                               "namespace DNS-inverso"))
    version = manifiesto.get("version")
    if version and not re.fullmatch(PATRON_SEMVER, str(version)):
        hallazgos.append(error(ruta_relativa, f"`version` no es SemVer: {version}"))
    return hallazgos


def revisar_gobierno(gobierno: dict, manifiesto: dict | None) -> list[Hallazgo]:
    """El `GOVERNANCE.json` del conjunto, cuando hay plugin."""
    donde = "GOVERNANCE.json"
    hallazgos: list[Hallazgo] = []
    identificador = gobierno.get("id")
    nombre_plugin = (manifiesto or {}).get("name")
    if identificador and nombre_plugin and identificador != nombre_plugin:
        hallazgos.append(error(donde, f"`id` ({identificador}) no coincide con `name` de "
                                      f"plugin.json ({nombre_plugin})"))
    if not (gobierno.get("owner") or {}).get("team"):
        hallazgos.append(error(donde, "`owner.team` vacio: el dueno debe ser RESOLUBLE contra la "
                                      "organizacion. Un artefacto sin dueno real no se puede "
                                      "deprecar, corregir ni retirar"))
    return hallazgos


def revisar_gobierno_ausente() -> list[Hallazgo]:
    """El repositorio declara un plugin pero no su gobierno."""
    return [error("GOVERNANCE.json", "el repositorio declara un plugin pero no su gobierno")]


def revisar_inventario(declarado: dict, inventario: Inventario) -> list[Hallazgo]:
    """Lo declarado contra el arbol real. Un catalogo que publica un inventario inexistente da
    falsa confianza, que es peor que no publicar nada."""
    return [
        error("GOVERNANCE.json",
              f"inventario: declara {declarado.get(tipo, 0)} `{tipo}` y el arbol real tiene {real}")
        for tipo, real in inventario.como_declarado().items()
        if declarado.get(tipo, 0) != real
    ]


def revisar_ausencia_de_plugin() -> list[Hallazgo]:
    """Sin plugin no hay error: los artefactos quedan gobernados por su propia metadata. Lo que
    se pierde es la capa de DISTRIBUCION, y conviene que el autor lo sepa."""
    return [aviso(RUTA_MANIFIESTO_UNIFICADA,
                  "sin plugin: los artefactos quedan gobernados por su propia metadata, pero NO "
                  "entran al marketplace ni se instalan o bloquean como conjunto")]
