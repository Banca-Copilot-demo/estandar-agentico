"""Reglas de las suites de evals (G5) — lo que el esquema de la suite NO puede comprobar.

REPARTO CON EL ESQUEMA, para que no se dupliquen. `eval-suite.schema.json` valida la FORMA: que estan
los campos, que `eval_type` es uno de los cuatro, que hay al menos tres casos y que al menos uno es
`negative`. Todo eso es declarativo y no necesita codigo.

Lo que queda aqui es lo que solo se puede comprobar contra el ARBOL:

  - que el `artifact` de la suite corresponda a un artefacto que EXISTE en la unidad. Una suite que
    apunta a un id que no esta mide el vacio: corre, no falla y no evalua nada.
  - que los ids de caso no se repitan DENTRO de la suite. El esquema no lo puede expresar, y el campo
    existe precisamente para comparar reportes entre versiones: dos casos con el mismo id hacen que un
    reporte no se pueda leer.

PURAS (G5): reciben lo leido y devuelven hallazgos.
"""
from __future__ import annotations

from collections import Counter

from validador_agentico.dominio.hallazgo import Hallazgo, error

CLAVE_ARTEFACTO = "artifact"
CLAVE_CASOS = "cases"
CLAVE_ID = "id"
CLAVE_TIPO = "eval_type"

# El tipo de evaluacion que NO consume modelo: comprueba el contrato de una configuracion MCP contra el
# servidor real -- que conecta, que aparecen las herramientas de la lista y ninguna de fuera, y que el
# texto de sus descripciones no cambio desde la aprobacion --. Es el unico que no hay razon para
# diferir, y el unico que sirve de linea base de DERIVA.
TIPO_CONTRATO_MCP = "mcp_contract"


def revisar_suite(ruta_relativa: str, suite: dict,
                  ids_de_artefactos: frozenset[str]) -> list[Hallazgo]:
    """`ids_de_artefactos` son los ids que la unidad publica de verdad."""
    return (_revisar_artefacto_referenciado(ruta_relativa, suite, ids_de_artefactos)
            + _revisar_ids_de_casos(ruta_relativa, suite))


def _revisar_artefacto_referenciado(ruta_relativa: str, suite: dict,
                                     ids_de_artefactos: frozenset[str]) -> list[Hallazgo]:
    """Una suite que apunta a un artefacto inexistente CORRE Y NO EVALUA NADA, que es el peor de los
    resultados: no falla, y su existencia se lee como cobertura.

    Es el mismo defecto que el inventario del gobierno desalineado, y se comprueba igual: contra lo que
    hay, no contra lo que el archivo dice de si mismo.
    """
    declarado = suite.get(CLAVE_ARTEFACTO)
    if not declarado or declarado in ids_de_artefactos:
        return []
    conocidos = ", ".join(sorted(ids_de_artefactos)) or "(ninguno)"
    return [error(ruta_relativa,
                  f"la suite evalua `{declarado}` y esa unidad no publica ningun artefacto con ese "
                  f"id. Una suite que apunta a un artefacto que no existe corre sin fallar y no "
                  f"evalua nada, asi que su presencia se lee como cobertura que no hay. Ids "
                  f"publicados: {conocidos}")]


def _revisar_ids_de_casos(ruta_relativa: str, suite: dict) -> list[Hallazgo]:
    """El `id` de un caso existe para comparar reportes entre versiones; repetido, no se puede."""
    casos = suite.get(CLAVE_CASOS)
    if not isinstance(casos, list):
        return []
    repetidos = sorted(
        identificador for identificador, veces in Counter(
            caso.get(CLAVE_ID) for caso in casos
            if isinstance(caso, dict) and caso.get(CLAVE_ID)
        ).items() if veces > 1
    )
    return [error(ruta_relativa,
                  f"el caso `{identificador}` esta declarado mas de una vez. El id sirve para comparar "
                  f"el reporte de una version con el de la siguiente, y repetido hace que no se pueda "
                  f"leer cual de los dos paso")
            for identificador in repetidos]
