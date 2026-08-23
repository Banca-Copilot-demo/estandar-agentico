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
    """El `GOVERNANCE.json` del conjunto, con plugin o sin el."""
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
    hallazgos += _revisar_version_del_paquete(donde, gobierno, manifiesto)
    return hallazgos


def _revisar_version_del_paquete(donde: str, gobierno: dict,
                                  manifiesto: dict | None) -> list[Hallazgo]:
    """`version` en el gobierno: OBLIGATORIA sin plugin, PROHIBIDA con plugin.

    De donde sale la etiqueta es lo unico que decide si un repositorio tiene cadena de publicacion.
    Con plugin sale del `plugin.json`, que es lo que el marketplace resuelve; sin plugin no hay otro
    sitio, y sin ella el repositorio no se etiqueta -- asi que no hay release, ni atestacion, ni ficha,
    y el consumidor no puede verificar nada antes de instalar. Ese era exactamente el estado del
    camino del artefacto suelto: el lineamiento prometia catalogo y sello, y no habia de donde sacar
    la version.

    Y PROHIBIDA CUANDO HAY MANIFIESTO por el motivo de siempre: dos declaraciones de la misma cosa
    divergen, y aqui la divergencia produciria una etiqueta que no corresponde al paquete.
    """
    declarada = gobierno.get("version")
    if manifiesto is not None:
        if declarada:
            return [error(donde, f"declara `version` ({declarada}) y ademas hay un `plugin.json`: "
                                 f"la version del paquete es la del manifiesto, que es lo que el "
                                 f"marketplace resuelve. Dos declaraciones divergen, y la etiqueta "
                                 f"saldria de una de las dos sin saber cual")]
        return []
    if not declarada:
        return [error(donde, "sin `version` y sin `plugin.json`: no hay de donde derivar la etiqueta, "
                             "asi que este repositorio NO se publica -- sin release no hay atestacion "
                             "ni ficha, y quien lo instale no podra verificar que es lo aprobado. "
                             "Declara `version` en SemVer para publicar los artefactos sueltos")]
    return []


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
    """Sin plugin no hay error: los artefactos quedan gobernados por su propia metadata. Lo que se
    pierde es la ENTRADA AL MARKETPLACE, y conviene que el autor lo sepa.

    El mensaje decia antes que sin plugin no hay distribucion, y era impreciso: un repositorio de
    sueltos SI se publica -- etiqueta, paquete, atestacion y ficha -- si declara su `version` en el
    `GOVERNANCE.json`. Lo unico que no puede tener es entrada de marketplace, porque las entradas de
    un marketplace SON plugins. Decirlo mal empujaba a empaquetar en un plugin para conseguir algo que
    no hacia falta.
    """
    return [aviso(RUTA_MANIFIESTO_UNIFICADA,
                  "sin plugin: los artefactos se gobiernan por su propia metadata y el repositorio se "
                  "publica como paquete suelto -- con atestacion y ficha -- si su GOVERNANCE.json "
                  "declara `version`. Lo que NO puede tener es entrada en el marketplace, ni "
                  "instalarse o bloquearse como conjunto")]
