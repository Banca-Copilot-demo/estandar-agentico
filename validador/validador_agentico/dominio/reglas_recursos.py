"""G2 — los archivos que el artefacto REFERENCIA tienen que existir en el arbol.

EL DEFECTO QUE CIERRA, medido en el harness del CoE: de las 70 rutas de archivos de apoyo que sus
`METADATA.json` declaran, **ninguna resuelve**. Se escribieron para un layout anterior y nadie las
volvio a comprobar, porque ningun gate las comprobaba. Un campo que nadie verifica se convierte en
decoracion.

Nosotros no declaramos esas rutas, asi que no tenemos ese campo -- pero SI las referenciamos desde
el cuerpo del artefacto, y tampoco las comprobabamos. El fallo es peor que un adorno: el paquete se
publica conforme y sellado, y el artefacto revienta EN LA MAQUINA DEL DESARROLLADOR al seguir una
ruta que no existe. Eso es exactamente lo que G2 -- que funcione al instalarse en otra maquina --
tiene que atrapar antes.

POR QUE SOLO DOS FORMAS DE REFERENCIA. Un gate con falsos positivos se desactiva, asi que aqui solo
cuenta lo que no admite otra lectura:

  - el enlace markdown `[texto](ruta)`, que es una referencia y no puede ser otra cosa;
  - la ruta entre acentos graves que empieza por uno de los directorios de recursos de la
    especificacion, porque `scripts/x.sh` en un `SKILL.md` no es un ejemplo generico.

Un parrafo que MENCIONE un archivo en prosa no se detecta, y es deliberado: preferimos no ver una
referencia real antes que inventar una que no existe.

LAS RUTAS SON RELATIVAS A LA CARPETA DEL ARTEFACTO, no a la raiz del repositorio. Lo impone la
especificacion -- la divulgacion progresiva funciona por rutas relativas desde la raiz del skill --
y es la razon de que mover un recurso rompa el artefacto.
"""
from __future__ import annotations

import re

from validador_agentico.dominio.hallazgo import Hallazgo, error

# `[texto](ruta)`. Se corta en el primer espacio o parentesis para no tragarse el titulo opcional.
_ENLACE_MARKDOWN = re.compile(r"]\(\s*([^)\s]+)")
_ENTRE_ACENTOS = re.compile(r"`([^`\n]+)`")

# Los directorios de recursos de la especificacion, mas los dos que el CoE usa y v7 dejo caer.
DIRECTORIOS_DE_RECURSOS = ("scripts/", "references/", "assets/", "templates/", "examples/")
# Prefijos que NO son un archivo del repositorio: una url, un ancla, una ruta absoluta.
_PREFIJOS_EXTERNOS = ("http://", "https://", "mailto:", "#", "/", "~")
_MARCA_DE_PLANTILLA = ("$", "{", "<")
# Una referencia terminada en barra apunta a un DIRECTORIO, y un directorio no esta en el conjunto
# de rutas: solo lo estan sus archivos. MEDIDO en nuestro propio SKILL.md, que referencia `assets/`
# y salia como inexistente teniendo cuatro archivos dentro.
_MARCA_DE_DIRECTORIO = "/"


def _es_ruta_del_repositorio(referencia: str) -> bool:
    """Descarta lo que no puede resolverse contra el arbol: urls, anclas, rutas absolutas y
    plantillas con variables -- `$skill/assets/...` no se puede comprobar sin ejecutar nada."""
    if not referencia or referencia.startswith(_PREFIJOS_EXTERNOS):
        return False
    return not any(marca in referencia for marca in _MARCA_DE_PLANTILLA)


def _referencias_del_cuerpo(cuerpo: str) -> list[str]:
    """Las referencias a archivos que el cuerpo declara, sin repetir y en orden de aparicion."""
    candidatas = list(_ENLACE_MARKDOWN.findall(cuerpo))
    candidatas += [
        texto for texto in _ENTRE_ACENTOS.findall(cuerpo)
        if texto.startswith(DIRECTORIOS_DE_RECURSOS)
    ]
    unicas: list[str] = []
    for referencia in candidatas:
        limpia = referencia.strip().rstrip(".,;:")
        if _es_ruta_del_repositorio(limpia) and limpia not in unicas:
            unicas.append(limpia)
    return unicas


def _resolver(directorio: str, referencia: str) -> str | None:
    """La ruta desde la raiz del repositorio, o `None` si la referencia se sale del arbol."""
    partes: list[str] = [] if not directorio else directorio.split("/")
    for parte in referencia.split("/"):
        if parte in ("", "."):
            continue
        if parte == "..":
            if not partes:
                return None
            partes.pop()
            continue
        partes.append(parte)
    return "/".join(partes) if partes else None


def revisar_recursos_referenciados(donde: str, cuerpo: str,
                                   rutas_del_repositorio: frozenset[str]) -> list[Hallazgo]:
    """Revisa que cada archivo referenciado desde `cuerpo` exista. `donde` es la ruta del
    artefacto, y las referencias se resuelven contra SU carpeta."""
    directorio = donde.rsplit("/", 1)[0] if "/" in donde else ""
    hallazgos: list[Hallazgo] = []
    for referencia in _referencias_del_cuerpo(cuerpo):
        resuelta = _resolver(directorio, referencia)
        if resuelta is not None and referencia.endswith(_MARCA_DE_DIRECTORIO):
            if not any(r.startswith(resuelta + "/") for r in rutas_del_repositorio):
                hallazgos.append(error(
                    donde, f"referencia al directorio `{referencia}` y esta vacio o no existe "
                           f"({resuelta})"))
            continue
        if resuelta is None:
            hallazgos.append(error(donde, f"la referencia `{referencia}` se sale del repositorio"))
        elif resuelta not in rutas_del_repositorio:
            hallazgos.append(error(
                donde, f"referencia a `{referencia}` y ese archivo NO existe ({resuelta}): el "
                       "paquete se publicaria sellado y el artefacto fallaria al seguir la ruta "
                       "en la maquina donde se instale"))
    return hallazgos
