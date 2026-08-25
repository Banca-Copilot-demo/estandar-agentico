---
name: <<ID>>
description: "<<DESCRIPCION>>"
argument-hint: "<<ARGUMENTOS>>"
model: <<MODELO>>
metadata:
  id: <<ID>>
  owner_team: <<EQUIPO>>
  owner_contact: <<CONTACTO>>
  data_classification: internal
  status: draft
  version: "<<VERSION>>"
  standard_version: "8.0.0"
---

<!--
  DONDE VA: `commands/<<ID>>.prompt.md`.

  UN PROMPT ES UN PUNTO DE ENTRADA que una persona invoca a mano, a diferencia de un skill, que el modelo
  decide cargar. Esa diferencia se esta borrando aguas arriba -- en algunos clientes ya son el mismo
  artefacto con una bandera de frontmatter -- asi que no construyas nada que dependa de que sigan siendo
  cosas distintas.

  CONSECUENCIA PRACTICA para su evaluacion: un prompt no tiene eje de ACTIVACION que medir. Si lo invoca
  una persona, no hay decision del modelo que comprobar; queda solo la calidad de la salida.

  SI DELEGA EN UN AGENTE, declaralo con `agent: <<ID-DEL-AGENTE>>`. Es el patron habitual: el prompt es la
  puerta y el agente hace el trabajo.

  NO USES `skillsReference`: no es un campo del estandar y una ruta de sistema de archivos no resuelve en
  la maquina de otra persona. Para depender de otro artefacto se usa su `id`.

  `argument-hint` lo IGNORA el agente en la nube; sirve en el cliente local. Si no acepta argumentos,
  borra la clave en vez de dejarla vacia.

  BORRA ESTE COMENTARIO al rellenar la plantilla.
-->

# <<TITULO>>

<<INSTRUCCIONES>>
