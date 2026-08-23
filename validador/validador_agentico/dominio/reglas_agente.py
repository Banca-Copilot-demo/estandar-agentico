"""La regla del tipo `agent`: el estandar lo declaraba y el gate no lo comprobaba.

Estaba en el esquema desde el principio y ningun gate lo tocaba, asi que un agente sin `description`
pasaba en verde. Un tipo declarado y no comprobado es peor que un tipo no declarado: promete un
control que no existe.

QUE DISTINGUE A UN `agent`: se INVOCA, asi que su `description` decide si el modelo le delega, igual
que en un skill. Y puede TRANSFERIR la tarea a otro con `handoffs`, que es lo que ningun skill hace.

`instructions` vivia aqui y se fue a `reglas_instructions`: dejo de ser un tipo gobernado -- no hay
canal para distribuirlas -- y lo que queda de ellas es higiene, que es otra responsabilidad.

DOS AFIRMACIONES DE ESTE MODULO ERAN FALSAS, y se cayeron al medir los 10 agentes reales de BCP --
las dos poblaciones, `atla` y `.github-private` -- contra la especificacion:

1. «El `name` tiene que coincidir con el archivo o el cliente no lo encuentra.» FALSO. La
   especificacion de VS Code dice que el `name` es el identificador y que si se OMITE se usa el
   nombre del archivo: el archivo es el respaldo, no la autoridad. Y el activo lo confirma de forma
   concluyente: un agente vive en `atla.cnf-support.consultant.agent.md`, declara
   `name: atla.cnf-migrator.consultant`, y DOS handoffs de otros agentes apuntan al `name`. Si
   mandara el archivo, esas dos transferencias estarian rotas. Baja a AVISO, y el aviso ya no dice
   que el cliente no lo encontrara --la parte falsa-- sino lo que de verdad molesta: dos nombres para
   la misma cosa, y aqui ademas de DOMINIOS distintos (`cnf-support` contra `cnf-migrator`).

2. «`model` como array es un error.» FALSO como defecto de FORMA: la especificacion admite el array
   como lista de PRIORIDAD. La objecion de BCP sigue en pie pero es de GOBIERNO, asi que es aviso.
"""
from __future__ import annotations

import re

from validador_agentico.adaptadores.frontmatter import (
    OBSERVACION_MODEL_ARRAY,
    observacion,
)
from validador_agentico.dominio.especificacion import MAX_CARACTERES_DESCRIPCION
from validador_agentico.dominio.hallazgo import Hallazgo, aviso, error

# La convencion de espacio de nombres de BCP para un agente: minusculas, digitos, guiones y puntos.
# Es AVISO y no error, y el motivo esta medido: 5 agentes reales de `.github-private` se llaman
# `DeployGo Onboarding` o `CI/CD GitHub Actions Specialist`, y la especificacion NO restringe espacios
# ni mayusculas. Exigirlo como error declararia no conforme a una poblacion entera por una preferencia.
_CONVENCION_DE_NOMBRE = re.compile(r"^[a-z0-9]+([.-][a-z0-9]+)*$")

# Campos que declaran capacidad EJECUTABLE dentro del propio agente, esquivando el sitio donde vive
# su gobierno. Un MCP declarado aqui no pasa por el bloque `mcp` del GOVERNANCE.json -- donde estan la
# aprobacion y el `tools_digest` -- y un hook aqui no pasa por la firma de seguridad sobre `hooks/`.
# Ningun agente de BCP los usa todavia; el aviso existe para enterarnos el dia que aparezcan.
_CAPACIDAD_SIN_GOBIERNO = (
    ("mcp-servers", "un servidor MCP declarado en el agente no pasa por el bloque `mcp` del "
                    "GOVERNANCE.json, que es donde viven su aprobacion y su `tools_digest`"),
    ("hooks", "un hook declarado en el agente no pasa por la firma de seguridad sobre `hooks/`, "
              "y es codigo que se ejecuta solo"),
)

# `handoffs` y `argument-hint` NO existen en el agente en la nube de Copilot: la documentacion dice
# que se IGNORAN por compatibilidad. Con `target: github-copilot` declararlos no rompe nada -- y eso
# es justo el problema: la cadena de agentes deja de delegar sin que nada falle.
_TARGET_SIN_TRANSFERENCIAS = "github-copilot"
_CAMPOS_SOLO_IDE = ("handoffs", "argument-hint")


def revisar_agente(donde: str, nombre_esperado: str, frontmatter: dict) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    hallazgos += _revisar_nombre(donde, nombre_esperado, frontmatter.get("name"))
    hallazgos += _revisar_descripcion(donde, frontmatter.get("description") or "")
    hallazgos += _revisar_modelo(donde, frontmatter)
    hallazgos += _revisar_portabilidad(donde, frontmatter)
    hallazgos += _revisar_capacidad_sin_gobierno(donde, frontmatter)
    return hallazgos


def _revisar_nombre(donde: str, nombre_esperado: str, nombre) -> list[Hallazgo]:
    if not nombre:
        return [error(donde, "falta `name`: es el identificador al que apuntan los `handoffs` de "
                             "otros agentes")]
    hallazgos: list[Hallazgo] = []
    if nombre != nombre_esperado:
        hallazgos.append(aviso(donde, f"`name` ({nombre}) no coincide con el archivo "
                                      f"({nombre_esperado}.agent.md). Funciona -- el `name` manda y "
                                      f"los handoffs apuntan a el -- pero son dos nombres para la "
                                      f"misma cosa, y quien busque el archivo por el nombre del "
                                      f"handoff no lo encontrara"))
    if not _CONVENCION_DE_NOMBRE.match(str(nombre)):
        hallazgos.append(aviso(donde, f"`name` ({nombre}) no sigue la convencion "
                                      f"`<org>.<dominio>.<nombre>`. Es legal y el cliente lo "
                                      f"acepta; lo que se pierde es saber de que dominio es un "
                                      f"agente cuando un handoff apunta a el"))
    return hallazgos


def _revisar_descripcion(donde: str, descripcion: str) -> list[Hallazgo]:
    if not descripcion:
        return [error(donde, "falta `description`: es lo que decide si el modelo le delega una "
                             "tarea. Sin ella, el agente no se usa nunca")]
    if len(descripcion) > MAX_CARACTERES_DESCRIPCION:
        return [error(donde, f"`description` de {len(descripcion)} caracteres: el maximo es "
                             f"{MAX_CARACTERES_DESCRIPCION}")]
    return []


def _revisar_modelo(donde: str, frontmatter: dict) -> list[Hallazgo]:
    if not observacion(frontmatter, OBSERVACION_MODEL_ARRAY):
        return []
    return [aviso(donde, "`model` es un array. La especificacion lo admite como lista de PRIORIDAD, "
                         "asi que no es un defecto de forma; lo que molesta es de gobierno: cada "
                         "rotacion del catalogo de modelos obliga a tocar todos los archivos. Deja "
                         "un modelo y pon la lista en el `model_allowlist` del plugin")]


def _revisar_portabilidad(donde: str, frontmatter: dict) -> list[Hallazgo]:
    """Avisa si el agente declara campos que su propio `target` ignora."""
    if frontmatter.get("target") != _TARGET_SIN_TRANSFERENCIAS:
        return []
    declarados = [campo for campo in _CAMPOS_SOLO_IDE if frontmatter.get(campo)]
    if not declarados:
        return []
    return [aviso(donde, f"declara {', '.join('`' + c + '`' for c in declarados)} con "
                         f"`target: {_TARGET_SIN_TRANSFERENCIAS}`, que los IGNORA. No falla nada, y "
                         f"por eso importa: la cadena de agentes deja de delegar en silencio")]


def _revisar_capacidad_sin_gobierno(donde: str, frontmatter: dict) -> list[Hallazgo]:
    return [aviso(donde, f"declara `{campo}`: {motivo}")
            for campo, motivo in _CAPACIDAD_SIN_GOBIERNO if frontmatter.get(campo)]
