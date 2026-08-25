---
name: <<NOMBRE>>
description: <<DESCRIPCION>>
license: Proprietary
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
  DONDE VA ESTE ARCHIVO: `skills/<<NOMBRE>>/SKILL.md`. El directorio TIENE que llamarse igual que el
  campo `name`: es la unica regla de identidad que la especificacion impone, y si no coinciden el
  cliente no encuentra el skill -- sin error, simplemente no aparece --.

  LA `description` ES EL CAMPO MAS IMPORTANTE de todo el archivo, y el que mas se descuida. Es lo que el
  modelo lee para decidir si usa este skill, y lo unico que se carga en CADA peticion. Tiene que decir
  DOS cosas:
      QUE hace          «Revisa una consulta JQL y senala los filtros que faltan...»
      CUANDO usarlo     «...Usalo cuando alguien escriba o pegue una consulta JQL.»
  En TERCERA PERSONA. Nada de «Puedo ayudarte a...» ni «Usa esto para...»: la descripcion se inyecta en
  el prompt del sistema, y mezclar el punto de vista degrada la seleccion.

  EL CUERPO SE CARGA SOLO CUANDO EL SKILL SE USA, asi que puede ser largo -- pero cada linea compite con
  la conversacion cuando se carga. Por debajo de 500 lineas; si necesitas mas, parte el contenido en
  archivos de apoyo y referencialos desde aqui.

  BORRA ESTE COMENTARIO al rellenar la plantilla.
-->

## Cuándo usar esto

<<CUANDO>>

## Qué comprobar

<<PROCEDIMIENTO>>

## Qué devolver

<<SALIDA>>
