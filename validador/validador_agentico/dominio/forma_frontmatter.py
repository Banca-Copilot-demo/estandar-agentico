"""La FORMA en que se escribio un frontmatter: tres cosas que se observan de su YAML, no que declare.

QUE ES UNA «OBSERVACION DE FORMA». No es una clave del artefacto: es un hecho sobre COMO se escribio.
Que `allowed-tools` se puso como lista cuando la especificacion exige una cadena. Que `model` es un
array. Que hay un `skillsReference`, que no existe en ninguna especificacion. Las reglas razonan sobre
esos hechos, asi que son vocabulario del DOMINIO -- igual que `Severidad` o `ClaseAprobador` --.

POR QUE ESTA AQUI Y NO EN EL ADAPTADOR, que es de donde vino. Vivia en `adaptadores/frontmatter` y dos
modulos de `dominio/` lo importaban desde ahi, con la flecha de dependencia apuntando HACIA FUERA:
justo lo que G5 prohibe -- «domain no importa nada del proyecto fuera de domain» --. Y no era una
violacion inocente: significaba que las reglas no se podian probar sin el adaptador, cuando la razon
de que el dominio sea puro es precisamente que se pruebe con datos y nada mas.

Invertida la flecha, el adaptador importa de aqui -- que es hacia dentro -- y las reglas solo hablan
con su propia capa.

TODO EN ESTE MODULO ES PURO: recibe dicts, devuelve valores. Sin I/O, sin logging, sin estado.
"""
from __future__ import annotations

# La clave del mapa `metadata` de la especificacion Agent Skills, donde vive el envelope de gobierno.
# ESTABA DEFINIDA DOS VECES -- en el adaptador de frontmatter y en `ensamblado` -- con el mismo valor,
# que es el caso que G2 nombra literalmente: «constantes con el mismo valor definidas en mas de un
# lugar». Aqui una sola vez, y las dos capas la importan.
CLAVE_METADATA = "metadata"

# Bajo que clave viajan las observaciones dentro del dict del frontmatter. Empieza por `_` para que se
# vea que no es del artefacto, y el motivo de separarlas se MIDIO al ejecutar los esquemas por primera
# vez: mezcladas con las claves declaradas, el esquema del skill las rechazaba como «propiedades no
# evaluadas» en los cinco artefactos reales de la demo. Y con razon: no son claves del frontmatter.
CLAVE_OBSERVACIONES = "_forma"

# Las tres claves cuyo TIPO delata una forma mal escrita.
CLAVE_ALLOWED_TOOLS = "allowed-tools"
CLAVE_MODEL = "model"
CLAVE_SKILLS_REFERENCE = "skillsReference"

OBSERVACION_ALLOWED_TOOLS_LISTA = "allowed_tools_es_lista"
OBSERVACION_MODEL_ARRAY = "model_es_array"
OBSERVACION_SKILLS_REFERENCE = "tiene_skills_reference"


def observacion(frontmatter: dict, cual: str) -> bool:
    """Lee una observacion de forma. Se expone como funcion para que las reglas no tengan que saber
    donde se guardan: si mañana cambia la clave, cambia aqui y no en cada regla."""
    return bool((frontmatter.get(CLAVE_OBSERVACIONES) or {}).get(cual))


def solo_lo_declarado(frontmatter: dict) -> dict:
    """El frontmatter SIN las observaciones: solo lo que el artefacto declara de verdad.

    Es lo que se valida contra el esquema, y por eso existe: sin esto, el propio marcador que añade el
    lector aparecia como una clave inesperada del artefacto.
    """
    return {c: v for c, v in frontmatter.items() if c != CLAVE_OBSERVACIONES}


def observar(analizado: dict) -> dict[str, bool]:
    """Las tres formas mal escritas, vistas sobre la estructura ya parseada.

    Son comprobaciones de TIPO -- que es lo que de verdad se quiere saber -- y no de como se escribio
    el texto. Antes se detectaban por expresiones regulares sobre el YAML crudo.
    """
    return {
        OBSERVACION_ALLOWED_TOOLS_LISTA: isinstance(analizado.get(CLAVE_ALLOWED_TOOLS), list),
        OBSERVACION_MODEL_ARRAY: isinstance(analizado.get(CLAVE_MODEL), list),
        OBSERVACION_SKILLS_REFERENCE: CLAVE_SKILLS_REFERENCE in analizado,
    }
