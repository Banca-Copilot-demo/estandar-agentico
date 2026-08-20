"""Reglas de los dos tipos que el estandar declaraba y el gate no comprobaba: `agent` e
`instructions`.

Estaban en el esquema desde el principio y ningun gate los tocaba, asi que un agente sin
`description` o unas instructions sin `applies_to` pasaban en verde. Un tipo declarado y no
comprobado es peor que un tipo no declarado: promete un control que no existe.

LO QUE DISTINGUE A CADA UNO:

  - Un `agent` se INVOCA, asi que su `description` decide si el modelo le delega, igual que en un
    skill. Y su nombre tiene que coincidir con el archivo o el cliente no lo encuentra.

  - Unas `instructions` estan SIEMPRE ACTIVAS en el repositorio donde se instalan: cada linea se
    paga en todas las peticiones. De ahi las dos reglas propias: `applies_to`, que acota donde
    aplican, y `token_budget`, que es el techo declarado de ese coste permanente.
"""
from __future__ import annotations

from validador_agentico.dominio.especificacion import MAX_CARACTERES_DESCRIPCION
from validador_agentico.dominio.hallazgo import Hallazgo, aviso, error

# Un `applies_to` de `**` aplica a todo el repositorio: dejaria de ser una regla acotada y volveria
# a pagarse en cada peticion, que es justo lo que `token_budget` intenta contener.
_GLOBS_DEMASIADO_AMPLIOS = frozenset({"**", "**/*", "*", "/"})
# Techo por defecto cuando el artefacto no declara el suyo. Es un aviso, no un limite: sin medir en
# el activo real, imponerlo seria inventarse un numero.
LIMITE_LINEAS_INSTRUCTIONS_SIN_TECHO = 200


def revisar_agente(donde: str, nombre_esperado: str, frontmatter: dict) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []

    nombre = frontmatter.get("name")
    if not nombre:
        hallazgos.append(error(donde, "falta `name`: el cliente identifica al agente por el, y sin "
                                      "el no lo puede invocar"))
    elif nombre != nombre_esperado:
        hallazgos.append(error(donde, f"`name` ({nombre}) no coincide con el archivo "
                                      f"({nombre_esperado}.agent.md): el cliente no lo encontrara"))

    descripcion = frontmatter.get("description") or ""
    if not descripcion:
        hallazgos.append(error(donde, "falta `description`: es lo que decide si el modelo le "
                                      "delega una tarea. Sin ella, el agente no se usa nunca"))
    elif len(descripcion) > MAX_CARACTERES_DESCRIPCION:
        hallazgos.append(error(donde, f"`description` de {len(descripcion)} caracteres: el maximo "
                                      f"es {MAX_CARACTERES_DESCRIPCION}"))
    return hallazgos


def revisar_instructions(donde: str, frontmatter: dict, lineas: int) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []

    aplica_a = frontmatter.get("applies_to") or frontmatter.get("applyTo")
    if not aplica_a:
        hallazgos.append(error(donde, "falta `applies_to`: unas instructions sin ambito aplican a "
                                      "todo, y se pagan en cada peticion del repositorio"))
    elif str(aplica_a).strip() in _GLOBS_DEMASIADO_AMPLIOS:
        hallazgos.append(error(donde, f"`applies_to` es {aplica_a!r}, que aplica a todo el "
                                      "repositorio: acotalo a los archivos donde la regla importa"))

    techo = frontmatter.get("token_budget")
    if techo is None:
        # Aviso y no error: el techo es una practica del estandar, no un requisito del cliente. Pero
        # sin declararlo nadie nota cuando unas instructions crecen hasta doler.
        if lineas > LIMITE_LINEAS_INSTRUCTIONS_SIN_TECHO:
            hallazgos.append(aviso(
                donde, f"{lineas} lineas sin `token_budget` declarado: estan SIEMPRE activas, asi "
                       "que su tamano se paga en todas las peticiones del repositorio"))
    elif not isinstance(techo, int) or techo <= 0:
        hallazgos.append(error(donde, f"`token_budget` tiene que ser un entero positivo: {techo!r}"))
    return hallazgos
