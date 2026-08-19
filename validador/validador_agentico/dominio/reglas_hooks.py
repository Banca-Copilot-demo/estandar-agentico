"""Reglas de los hooks — el unico artefacto que EJECUTA CODIGO PROPIO automaticamente.

Y el unico que NO se instala: los hooks de repositorio viven en `.github/hooks/*.json` y, una vez
mergeados a la rama por defecto, se ejecutan en cada sesion del agente. Eso hace del pull request
el UNICO punto de control — no hay paso de instalacion donde intervenir— y es la razon por la que
el `CODEOWNERS` de seguridad sobre el archivo no es opcional.

Lo que este modulo comprueba es lo estatico. Lo que NO puede comprobar —si el script exfiltra lo
que el desarrollador escribe— es exactamente lo que revisa la persona.

PURAS (G5): reciben la configuracion ya parseada y devuelven hallazgos.
"""
from __future__ import annotations

import re

from validador_agentico.dominio.especificacion import (
    EVENTO_HOOK_SENSIBLE,
    PATRON_INTERRUPTOR_SEGURIDAD,
    TECHO_TIMEOUT_HOOK_S,
)
from validador_agentico.dominio.hallazgo import Hallazgo, aviso, error


def revisar_hooks(ruta_relativa: str, configuracion: dict,
                  inventario_declarado: dict) -> list[Hallazgo]:
    hallazgos = _revisar_declaracion(ruta_relativa, inventario_declarado)
    for evento, entradas in (configuracion.get("hooks") or {}).items():
        donde = f"{ruta_relativa}:{evento}"
        for entrada in entradas if isinstance(entradas, list) else []:
            hallazgos += _revisar_timeout(donde, entrada.get("timeoutSec"))
            hallazgos += _revisar_entorno(donde, entrada.get("env") or {})
        if evento == EVENTO_HOOK_SENSIBLE:
            hallazgos.append(aviso(donde,
                                   "este evento ve TODO lo que el desarrollador escribe: es un "
                                   "canal de salida de datos por diseno. Revisa si el script "
                                   "accede a la red antes de aprobarlo"))
    return hallazgos


def _revisar_declaracion(ruta_relativa: str, inventario_declarado: dict) -> list[Hallazgo]:
    """Un componente que ejecuta codigo no entra por sorpresa: se declara."""
    if inventario_declarado.get("hooks"):
        return []
    return [error(ruta_relativa,
                  "existe pero el inventario de GOVERNANCE.json no declara `hooks`. Un componente "
                  "que EJECUTA CODIGO no entra sin declararse")]


def _revisar_timeout(donde: str, timeout_s: int | None) -> list[Hallazgo]:
    if timeout_s is None:
        return [error(donde, "sin `timeoutSec`: un hook sin tope puede colgar el cliente")]
    if timeout_s > TECHO_TIMEOUT_HOOK_S:
        return [error(donde, f"`timeoutSec` de {timeout_s}s supera el techo de "
                             f"{TECHO_TIMEOUT_HOOK_S}s")]
    return []


def _revisar_entorno(donde: str, entorno: dict) -> list[Hallazgo]:
    """Un control de seguridad apagado por defecto, en un archivo que nadie abre."""
    return [
        aviso(donde, f"`env.{clave}` viene en `false`: parece un control de seguridad desactivado "
                     "por defecto")
        for clave, valor in entorno.items()
        if str(valor).lower() == "false" and re.search(PATRON_INTERRUPTOR_SEGURIDAD, clave)
    ]
