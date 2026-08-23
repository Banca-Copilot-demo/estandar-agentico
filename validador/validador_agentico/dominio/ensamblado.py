"""Ensambla el objeto que los esquemas describen. Funcion pura: recibe datos, devuelve un dict.

POR QUE HACE FALTA ENSAMBLAR. Los esquemas NO describen un archivo: describen el objeto que resulta de
juntar lo que hay en varios sitios. Cada campo lo dice en su `x-read-from`:

  frontmatter           las claves de primer nivel del YAML del artefacto
  frontmatter.metadata  el mapa `metadata:`, que la especificacion define como cadena->cadena
  METADATA.json         el archivo hermano, para lo que no cabe en ese mapa
  artifact-path         lo deduce el gate de la ruta -- hoy solo `kind` --

Ese reparto no es arbitrario y no se decide aqui: sale de la regla de tres preguntas del estandar --
si lo lee un cliente va al frontmatter; si es texto plano que debe sobrevivir a una instalacion suelta
va en `metadata:`; el resto, al hermano --. Este modulo solo lo EJECUTA.

POR QUE ES DOMINIO Y NO ADAPTADOR: no lee ningun archivo. Recibe los tres diccionarios ya leidos y los
combina, asi que se prueba sin disco.

EL ORDEN DE PRECEDENCIA IMPORTA Y ES DELIBERADO: si la misma clave aparece en el frontmatter y en el
hermano, gana el FRONTMATTER. Es lo que el cliente lee de verdad, y un hermano que contradijera al
frontmatter estaria describiendo un artefacto que no existe.
"""
from __future__ import annotations

CLAVE_METADATA = "metadata"
CLAVE_KIND = "kind"


def ensamblar(frontmatter: dict, metadata_hermana: dict | None, kind: str) -> dict:
    """El objeto que se valida contra el esquema del tipo.

    `metadata_hermana` es el contenido del `METADATA.json` del artefacto, o `None` si no lo tiene --
    que es el caso normal: el hermano solo hace falta para lo que no cabe en el mapa `metadata:`.
    """
    ensamblado = {**(metadata_hermana or {})}

    # El mapa `metadata:` del frontmatter se APLANA al nivel superior: el esquema declara `id` y
    # `owner_team` como campos del objeto, no dentro de un sub-objeto. Aplanar aqui evita que cada
    # esquema tenga que describir la anidacion, que es una forma del archivo y no del contrato.
    ensamblado.update(frontmatter.get(CLAVE_METADATA) or {})

    ensamblado.update({c: v for c, v in frontmatter.items() if c != CLAVE_METADATA})
    ensamblado[CLAVE_KIND] = kind
    return ensamblado
