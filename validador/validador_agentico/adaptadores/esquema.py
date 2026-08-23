"""Adaptador de entrada: valida un objeto ensamblado contra el esquema de su tipo.

POR QUE EXISTE. Hasta ahora los esquemas eran documentos que NINGUN codigo ejecutaba: las reglas del
gate estaban escritas a mano en Python y el esquema decia lo mismo por su cuenta. Dos fuentes de
verdad sobre el mismo contrato, y ya divergieron -- el esquema declaraba que el gobierno del `mcp`
vivia en un `METADATA.json` hermano y el gate lo exigia dentro del `.mcp.json`, que es justo donde el
esquema decia que no iba --. Eso no se descubrio leyendo: se descubrio al montar el primer `mcp` real.

QUE APORTA CADA LADO, para que no se dupliquen:

  el ESQUEMA valida la FORMA -- que los campos esten, que sean del tipo correcto, que los enums
  tengan un valor admitido, que no haya claves inventadas. Es declarativo y no necesita codigo.

  las REGLAS validan lo que un esquema NO PUEDE: que una fecha no haya vencido, que un equipo
  resuelva contra la organizacion, que una ruta referenciada exista en el arbol, que el inventario
  declarado coincida con lo que hay. Todo eso son comprobaciones contra el MUNDO, no contra la forma.

SE REGISTRAN POR SU `$id`, no por el nombre de archivo. Cada esquema declara uno, y una referencia
relativa -- `envelope.schema.json` desde `skill.schema.json` -- se resuelve contra el `$id` del que la
contiene, no contra el sistema de archivos. MEDIDO: registrar por nombre da `Unresolvable`, y asi se
descubrio que dos esquemas tenian un `$id` fuera del patron.

EL COMPROBADOR DE `format` SE ACTIVA A PROPOSITO. Sin el, `format: date` NO valida nada y un
`approval.date` de «ayer por la tarde» pasaria en verde -- y de esa fecha depende que la aprobacion de
un `mcp` caduque --. Es un requisito que el propio envelope declara.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

log = logging.getLogger(__name__)

# El directorio de esquemas, relativo a la raiz del repositorio del estandar. Es el contrato
# publicado; no se empaqueta dentro del validador para que no haya dos copias que puedan derivar (G2).
DIRECTORIO_POR_DEFECTO = Path("schemas")

CLAVE_ID = "$id"
_PATRON_ESQUEMAS = "*.json"
# La palabra clave cuyo fallo es DERIVADO de otros. Ver el comentario en `incumplimientos`.
_VALIDADOR_NO_EVALUADAS = "unevaluatedProperties"


class EsquemasNoDisponiblesError(FileNotFoundError):
    """No se encontraron los esquemas. Es un ERROR y no una degradacion: un gate que no puede
    comprobar y calla es indistinguible de uno que comprobo y aprobo."""


@lru_cache(maxsize=None)
def cargar(directorio: Path = DIRECTORIO_POR_DEFECTO) -> Registry:
    """El registro con todos los esquemas, indexado por su `$id`. UNA sola lectura por directorio.

    La cache esta AQUI y no solo en `_validador_de` porque el registro es el recurso COMPARTIDO: los
    tres esquemas de artefacto lo necesitan igual, y sin memoizar `cargar` se construia uno por
    esquema -- tres lecturas completas del directorio en vez de una --. Se vio en el log: al arreglar
    solo la capa de arriba, «8 esquema(s) cargados» bajo de seis veces a tres, no a una.
    """
    recursos = []
    for ruta in sorted(directorio.glob(_PATRON_ESQUEMAS)):
        try:
            contenido = json.loads(ruta.read_text(encoding="utf-8"))
        except json.JSONDecodeError as fallo:
            raise EsquemasNoDisponiblesError(f"{ruta} no es JSON valido: {fallo}") from fallo
        except OSError as fallo:
            raise EsquemasNoDisponiblesError(f"no se pudo leer {ruta}: {fallo}") from fallo
        if CLAVE_ID not in contenido:
            raise EsquemasNoDisponiblesError(
                f"{ruta.name} no declara `{CLAVE_ID}`: sin el, las referencias relativas de los "
                f"demas esquemas no resuelven contra el")
        recursos.append((contenido[CLAVE_ID], Resource.from_contents(contenido)))

    if not recursos:
        raise EsquemasNoDisponiblesError(
            f"no hay ningun esquema en {directorio}: sin ellos el gate no comprueba la forma")
    log.debug("%d esquema(s) cargados de %s", len(recursos), directorio)
    return Registry().with_resources(recursos)


@lru_cache(maxsize=None)
def _validador_de(nombre_del_esquema: str, directorio: Path) -> Draft202012Validator:
    """El validador de un esquema, construido UNA vez por (esquema, directorio).

    POR QUE SE MEMOIZA, y como se detecto. `incumplimientos` llamaba a `cargar` en CADA invocacion, o
    sea que releia y reparseaba los OCHO esquemas de disco por cada artefacto validado. Se vio en el
    log al ejecutar el gate con `--verbose`: «8 esquema(s) cargados» aparecia SEIS veces en una sola
    corrida sobre cuatro plugins. A escala de BCP -- 33 skills mas agentes y prompts, en 6-10 plugins
    -- son mas de cuarenta relecturas completas del directorio para obtener siempre lo mismo.

    Es cache de PROCESO, no estado de modulo: no se puebla al importar (P5), y se llena solo cuando
    alguien valida algo. Los esquemas no cambian mientras el gate corre -- vienen fijados por SHA
    desde el repositorio del estandar -- asi que releerlos no aporta frescura, solo I/O.

    `directorio` es un `Path`, que es hashable, asi que sirve de clave sin convertirlo.
    """
    registro = cargar(directorio)
    ruta = directorio / nombre_del_esquema
    try:
        esquema = json.loads(ruta.read_text(encoding="utf-8"))
    except OSError as fallo:
        raise EsquemasNoDisponiblesError(f"no se pudo leer {ruta}: {fallo}") from fallo
    return Draft202012Validator(esquema, registry=registro, format_checker=FormatChecker())


def incumplimientos(objeto: dict, nombre_del_esquema: str,
                    directorio: Path = DIRECTORIO_POR_DEFECTO) -> list[str]:
    """Los defectos de FORMA del objeto, ya legibles. Lista vacia = conforme.

    Cada mensaje lleva la ruta dentro del objeto, porque un «is not of type 'string'» sin decir de
    que campo obliga a adivinar.
    """
    validador = _validador_de(nombre_del_esquema, directorio)
    fallos = sorted(validador.iter_errors(objeto), key=lambda f: list(f.path))

    # SE SUPRIME EL «unevaluated» CUANDO HAY OTROS FALLOS, y es una decision de legibilidad con un
    # motivo medido. En JSON Schema 2020-12, si un subesquema falla se DESCARTAN sus anotaciones: al
    # fallar el envelope -- por un enum o una version mal escrita --, todos SUS campos aparecen como
    # «no evaluados». Medido sobre un skill con dos defectos reales: el mensaje listaba diez campos
    # perfectamente validos como inesperados, y habria mandado a alguien a BORRARLOS. Es un fallo
    # derivado, no un defecto propio: se arregla arreglando los otros, y entonces si aparece solo con
    # las claves que de verdad sobran.
    otros = [f for f in fallos if f.validator != _VALIDADOR_NO_EVALUADAS]
    utiles = otros if otros else fallos

    return [f"{'.'.join(str(t) for t in f.path) or '(raiz)'}: {f.message}" for f in utiles]
