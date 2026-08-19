"""Adaptador de la comprobacion oficial: `gh skill publish --dry-run`.

QUE CUBRE Y QUE NO, MEDIDO. La herramienta oficial comprueba UN TIPO DE SEIS -- solo `skill` --.
Frente a un prompt sin `description`, a un `.mcp.json` que no es JSON valido y a unas
`instructions` con `name` invalido responde `ok`: los ignora. Y en un repositorio sin ningun skill
FALLA con «no skills found».

De ahi las dos decisiones de este adaptador:
  - Si no hay skills, devuelve `NO_APLICA` sin invocar nada. Invocarlo rechazaria un dominio de
    solo prompts por el motivo equivocado.
  - Si `gh` no esta instalado, devuelve `NO_APLICA` con el motivo escrito. En CI `gh` viene en el
    runner, asi que este caso solo ocurre en la maquina del autor, y ahi el gate no debe ser un
    muro: se avisa y se sigue con el resto.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from validador_agentico.dominio.comprobacion import Comprobacion, Resultado
from validador_agentico.puertos.especificacion_oficial import NOMBRE_COMPROBACION_OFICIAL

log = logging.getLogger(__name__)

_ORDEN = ("gh", "skill", "publish", "--dry-run")
_TIEMPO_LIMITE_S = 120
_MAX_CARACTERES_DETALLE = 500


def _hay_skills(raiz: Path) -> bool:
    return (raiz / "SKILL.md").is_file() or any(raiz.glob("skills/*/SKILL.md"))


def comprobar(raiz: Path) -> Comprobacion:
    if not _hay_skills(raiz):
        return Comprobacion(NOMBRE_COMPROBACION_OFICIAL, Resultado.NO_APLICA,
                            "el repositorio no tiene skills; la herramienta oficial solo los cubre")

    if shutil.which("gh") is None:
        log.warning("`gh` no esta instalado: se omite la comprobacion oficial")
        return Comprobacion(NOMBRE_COMPROBACION_OFICIAL, Resultado.NO_APLICA,
                            "`gh` no esta instalado en esta maquina (en CI si lo esta)")

    log.debug("ejecutando: %s", " ".join(_ORDEN))
    try:
        salida = subprocess.run(_ORDEN, cwd=raiz, capture_output=True, text=True,
                                encoding="utf-8", timeout=_TIEMPO_LIMITE_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return Comprobacion(NOMBRE_COMPROBACION_OFICIAL, Resultado.NO_APLICA,
                            f"no se pudo ejecutar la herramienta oficial: {error}")

    if salida.returncode == 0:
        return Comprobacion(NOMBRE_COMPROBACION_OFICIAL, Resultado.CONFORME, "los skills cumplen la especificacion")

    detalle = (salida.stderr or salida.stdout or "sin salida").strip()
    return Comprobacion(NOMBRE_COMPROBACION_OFICIAL, Resultado.NO_CONFORME, detalle[:_MAX_CARACTERES_DETALLE])
