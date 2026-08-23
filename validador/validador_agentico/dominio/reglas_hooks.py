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

from validador_agentico.dominio import scripts_de_hooks
from validador_agentico.dominio.especificacion import (
    EVENTO_HOOK_SENSIBLE,
    PATRON_INTERRUPTOR_SEGURIDAD,
    TECHO_TIMEOUT_HOOK_S,
)
from validador_agentico.dominio.hallazgo import Hallazgo, aviso, error


def revisar_hooks(ruta_relativa: str, configuracion: dict,
                  inventario_declarado: dict,
                  scripts_presentes: frozenset[str] = frozenset()) -> list[Hallazgo]:
    """`scripts_presentes` son las rutas de script que EXISTEN en el artefacto, relativas a su raiz.

    Llega como dato y no se lee aqui porque esta regla es de dominio. Por defecto vacio para que las
    pruebas que miden otra cosa no tengan que construir el arbol.
    """
    hallazgos = _revisar_declaracion(ruta_relativa, inventario_declarado)
    hallazgos += _revisar_scripts_externos(ruta_relativa, configuracion)
    hallazgos += _revisar_scripts_ausentes(ruta_relativa, configuracion, scripts_presentes)
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


def _revisar_scripts_externos(ruta_relativa: str, configuracion: dict) -> list[Hallazgo]:
    """Un hook NO ejecuta scripts de fuera del artefacto. Error, no aviso.

    POR QUE ES LO MAS GRAVE QUE PUEDE TENER UN HOOK. Con `${CLAUDE_PROJECT_DIR}` el script vive en el
    repositorio del CONSUMIDOR: no viaja en el paquete, no entra en el digesto y nadie lo reviso al
    aprobar. El `hooks.json` pasaria cualquier verificacion -- su firma seria perfecta -- y lo que se
    ejecuta no existia cuando se firmo. La firma diria mucho menos de lo que aparenta, que es peor que
    no tener firma: la que no existe no engana a nadie.

    No es un caso hipotetico que convenga permitir «por flexibilidad»: si un artefacto necesita un
    script, ese script es parte del artefacto y va dentro.
    """
    externas = scripts_de_hooks.referencias_externas(configuracion)
    if not externas:
        return []
    return [error(ruta_relativa,
                  f"ejecuta un script de FUERA del artefacto "
                  f"({scripts_de_hooks.VARIABLE_RAIZ_DEL_CONSUMIDOR}): {comando}. Ese archivo vive en "
                  f"el repositorio de quien instala, asi que no viaja en el paquete, no entra en el "
                  f"digesto y nadie lo reviso al aprobar -- la firma cubriria el JSON y no lo que se "
                  f"ejecuta --. Si el script es parte del artefacto, muevelo dentro y referencialo "
                  f"con {scripts_de_hooks.VARIABLE_RAIZ_DEL_ARTEFACTO}")
            for comando in externas]


def _revisar_scripts_ausentes(ruta_relativa: str, configuracion: dict,
                               presentes: frozenset[str]) -> list[Hallazgo]:
    """Un script referenciado que no existe en el arbol: el hook falla al ejecutarse, no al aprobarse.

    Mismo razonamiento que la regla de recursos de un skill: el paquete se publicaria sellado y el
    fallo aparece en la maquina de otro, cuando ya es tarde.

    `presentes` son las rutas REFERENCIADAS que existen, o sea un subconjunto de las referencias. La
    primera version tenia una guarda `if not presentes: return []` con el argumento de que sin
    inventario no se puede afirmar que falte nada -- y era un error que la propia prueba destapo: si
    la unica referencia del hook no existe, `presentes` sale VACIO y la guarda desactivaba la regla
    EXACTAMENTE en el caso para el que existe. Un hook con un solo script, y ese ausente, pasaba en
    verde.
    """
    return [error(ruta_relativa,
                  f"referencia el script `{ruta}` y no existe en el artefacto: el hook fallaria al "
                  f"ejecutarse en la maquina de quien lo instale, no aqui")
            for ruta in scripts_de_hooks.referencias_propias(configuracion)
            if ruta not in presentes]


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
