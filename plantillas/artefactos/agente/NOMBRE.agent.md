---
name: <<ID>>
description: "<<DESCRIPCION>>"
model: <<MODELO>>
tools:
  - Read
  - Grep
metadata:
  id: <<ID>>
  owner_team: <<EQUIPO>>
  owner_contact: <<CONTACTO>>
  data_classification: internal
  status: draft
  version: "<<VERSION>>"
  standard_version: "8.0.0"
---

# <<TITULO>>

<!--
  DONDE VA: `agents/<<ID>>.agent.md`. El nombre del archivo sin `.agent.md` tiene que coincidir con el
  campo `name`.

  `model` VA COMO UN SOLO VALOR, no como lista. Una lista de modelos fijos obliga a tocar todos los
  archivos en cada rotacion del catalogo; la alternativa de varios modelos se declara una vez a nivel de
  plugin, no en cada agente.

  `tools` ES LA SUPERFICIE DE LO QUE PUEDE HACER, y la pregunta de gobierno de este tipo. Declara solo lo
  que necesita: cada herramienta de mas es alcance que hay que justificar en la revision. Un agente que
  solo lee no deberia declarar `Bash`.

  SI DELEGA EN OTRO AGENTE, anade `handoffs`. Las sub-claves son `label`, `agent`, `prompt` y `send`
  -- `send`, no `auto_send` --, y `send: false` significa que propone la delegacion en vez de ejecutarla.
  Ojo: `handoffs` lo IGNORA el agente en la nube; sirve en el cliente local.

  QUE SE EVALUA DE UN AGENTE, para cuando le escribas su suite: el RESULTADO FINAL, no la secuencia de
  pasos. Fijar el orden de las herramientas produce pruebas que fallan cuando el agente mejora, porque
  encuentra caminos validos que nadie anticipo.

  BORRA ESTE COMENTARIO al rellenar la plantilla.
-->

## Qué hace

<<PROCEDIMIENTO>>

## Qué devuelve

<<SALIDA>>

## Qué NO hace

<<LIMITES>>
