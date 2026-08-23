"""La regla del tipo `agent`: el estandar lo declaraba y el gate no lo comprobaba.

Estaba en el esquema desde el principio y ningun gate lo tocaba, asi que un agente sin `description`
pasaba en verde. Un tipo declarado y no comprobado es peor que un tipo no declarado: promete un
control que no existe.

QUE DISTINGUE A UN `agent`: se INVOCA, asi que su `description` decide si el modelo le delega, igual
que en un skill. Y su `name` tiene que coincidir con el archivo o el cliente no lo encuentra.

`instructions` vivia aqui y se fue a `reglas_instructions`: dejo de ser un tipo gobernado -- no hay
canal para distribuirlas -- y lo que queda de ellas es higiene, que es otra responsabilidad.
"""
from __future__ import annotations

from validador_agentico.dominio.especificacion import MAX_CARACTERES_DESCRIPCION
from validador_agentico.dominio.hallazgo import Hallazgo, error



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
