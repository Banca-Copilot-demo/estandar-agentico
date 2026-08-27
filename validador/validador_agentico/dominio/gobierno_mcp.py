"""El bloque `mcp` del `GOVERNANCE.json`, en sus DOS formas, normalizado a una sola.

QUE CAMBIO. El gobierno del MCP declaraba una LISTA POSICIONAL de servidores y pasa a ser un OBJETO
INDEXADO POR EL NOMBRE DEL SERVIDOR -- la misma clave que `mcpServers` usa en `.mcp.json` --:

    "mcp": {
      "aws-knowledge": {
        "write_operations": false,
        "tools_digest": "4f6f34...",
        "tools_digest_date": "2026-08-23",
        "credentials": [],
        "approval": { ... }
      }
    }

POR QUE, y es lo que desbloquea dos comprobaciones que antes no existian. Con una lista, el gobierno y
la configuracion se cotejaban por lo que IDENTIFICA a cada servidor -- su URL o su `paquete@version`
--, que sigue siendo el criterio correcto para decir «esto es lo que se ejecuta», pero deja fuera la
pregunta de gobierno: ¿QUIEN aprobo ESTE servidor? Con el nombre como clave, cada entrada del gobierno
apunta a una entrada exacta de `mcpServers`, y aparecen las dos derivas que antes pasaban en verde:

  1. un servidor CONFIGURADO y sin entrada de aprobacion -- se ejecuta sin que nadie lo haya aprobado;
  2. una APROBACION que sobrevive a un servidor que ya no esta -- el aprobador cree que reviso lo que
     se ejecuta y lo que reviso no existe. Es el sintoma tipico de un renombrado a medias.

Y el nombre sirve para ESTO aunque no sea un control de seguridad -- la plataforma documenta que un
`serverName` es la etiqueta que asigna el usuario --: aqui no se usa para decidir si algo es de fiar,
se usa para EMPAREJAR dos declaraciones del mismo repositorio. Quien decide que se ejecuta sigue
siendo la identidad, y esa comprobacion se mantiene intacta.

QUE CAMPOS DESAPARECEN, y el motivo es el mismo para los cuatro: `source`, `transport`, `endpoint` y
`version_pin` REPITEN o DERIVAN lo que ya esta en `.mcp.json`. Una copia que nada obliga a
sincronizar se queda atras, y entonces el gate compara la configuracion contra una copia rancia en vez
de contra la realidad. El fijado de version se DERIVA leyendo `.mcp.json`, que es el archivo que el
cliente ejecuta.

TRANSICION SIN BLOQUEO. La forma vieja -- `{"servers": [...], "credentials": {...}, "approval": {...}}`
-- se ACEPTA con AVISO y se normaliza a la nueva. El gate es comprobacion REQUERIDA: rechazar la forma
vieja de golpe pondria rojos a la vez todos los repositorios de dominio e impediria mergear incluso el
pull request que viene a migrarlos. Se podra endurecer cuando ningun `GOVERNANCE.json` declare
`mcp.servers`.

PURO (G5): recibe el bloque ya parseado y devuelve datos.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CLAVE_SERVIDORES_ANTIGUA = "servers"
_CLAVE_NOMBRE = "name"
_CLAVE_CREDENCIALES = "credentials"
_CLAVE_APROBACION = "approval"

# Las claves de NIVEL DE BLOQUE de la forma antigua. Su presencia es lo que identifica esa forma, y el
# esquema las prohibe como nombres de servidor para que la distincion no dependa de adivinar.
CLAVES_DE_LA_FORMA_ANTIGUA = (CLAVE_SERVIDORES_ANTIGUA, _CLAVE_CREDENCIALES, _CLAVE_APROBACION)

# Los campos de la forma vieja que ya no se declaran porque `.mcp.json` los tiene. Se nombran para que
# el aviso de migracion pueda decir exactamente que borrar.
CAMPOS_DERIVADOS_RETIRADOS = ("source", "transport", "endpoint", "version_pin")

_CAMPOS_PROPIOS = ("write_operations", "tools_digest", "tools_digest_date")


@dataclass(frozen=True)
class ServidorAprobado:
    """La aprobacion de UN servidor, ya normalizada, sea cual sea la forma en que se declaro."""

    nombre: str
    write_operations: bool = False
    tools_digest: str = ""
    tools_digest_date: str = ""
    credenciales: tuple[dict, ...] = ()
    aprobacion: dict = field(default_factory=dict)
    # La forma vieja del servidor, tal cual venia, para las comprobaciones que aun la necesitan --
    # el cotejo por identidad usa su `endpoint` y su `source` --. Vacio cuando ya llego en la nueva.
    declaracion_antigua: dict = field(default_factory=dict)


@dataclass(frozen=True)
class GobiernoMcp:
    """El bloque `mcp` entero, normalizado."""

    servidores: dict[str, ServidorAprobado]
    """nombre del servidor -> su aprobacion. El nombre es la clave de `mcpServers`."""
    forma_antigua: bool
    """`True` cuando el bloque llego con `servers`. Es lo que dispara el aviso de migracion."""
    credenciales_del_bloque: dict | None
    """El `credentials` de nivel de bloque de la forma vieja, o `None`. Se conserva porque su
    `ownership` -- quien custodia el secreto y donde se pide -- no tiene equivalente en la forma
    nueva y perderlo dejaria al desarrollador sin saber a quien pedir el acceso."""


def leer(bloque: object) -> GobiernoMcp | None:
    """Normaliza el bloque `mcp`. `None` cuando la unidad no lo declara o no es un objeto."""
    if not isinstance(bloque, dict):
        return None
    # COMO SE DISTINGUEN LAS DOS FORMAS: por la presencia de CUALQUIERA de las tres claves de nivel de
    # bloque de la antigua. No basta con mirar `servers`, y se descubrio al pasar la suite: un bloque
    # a medias -- `{"credentials": {...}}`, sin `servers`, que es un caso real durante una migracion --
    # caia en la rama nueva y `credentials` se interpretaba como un SERVIDOR llamado «credentials».
    # Ahi el gate habria reclamado la aprobacion de un servidor inexistente y habria dejado de aplicar
    # la regla de custodia, que es justo la que ese bloque venia a satisfacer.
    #
    # El esquema prohibe esos tres nombres como nombres de servidor precisamente para que esta
    # decision no tenga que adivinar nada.
    if any(clave in bloque for clave in CLAVES_DE_LA_FORMA_ANTIGUA):
        antiguos = bloque.get(CLAVE_SERVIDORES_ANTIGUA)
        return _desde_la_forma_antigua(bloque, antiguos if isinstance(antiguos, list) else [])
    return _desde_la_forma_nueva(bloque)


def _desde_la_forma_antigua(bloque: dict, servidores: list) -> GobiernoMcp:
    """La lista posicional, con `credentials` y `approval` COMPARTIDOS por todos los servidores.

    Compartirlos era justamente uno de los defectos de esa forma: una sola aprobacion cubria N
    servidores, asi que no se le podia dar a cada uno el plazo de revision de SU perfil de riesgo. Al
    normalizar se copia el mismo bloque a cada servidor, que es lo que significaba de hecho.
    """
    credenciales_del_bloque = bloque.get(_CLAVE_CREDENCIALES)
    aprobacion = bloque.get(_CLAVE_APROBACION) or {}
    normalizados: dict[str, ServidorAprobado] = {}
    for declarado in servidores:
        if not isinstance(declarado, dict):
            continue
        nombre = str(declarado.get(_CLAVE_NOMBRE, ""))
        if not nombre:
            continue
        normalizados[nombre] = ServidorAprobado(
            nombre=nombre,
            write_operations=bool(declarado.get("write_operations", False)),
            tools_digest=str(declarado.get("tools_digest", "")),
            tools_digest_date=str(declarado.get("tools_digest_date", "")),
            credenciales=(),
            aprobacion=aprobacion if isinstance(aprobacion, dict) else {},
            declaracion_antigua=declarado,
        )
    return GobiernoMcp(
        servidores=normalizados, forma_antigua=True,
        credenciales_del_bloque=(credenciales_del_bloque
                                 if isinstance(credenciales_del_bloque, dict) else None))


def _desde_la_forma_nueva(bloque: dict) -> GobiernoMcp:
    """El objeto indexado por nombre. Cada entrada trae SU aprobacion y SUS credenciales.

    Se ignoran las claves cuyo valor no es un objeto: un `mcp` mal tecleado lo senala el esquema con
    un mensaje que dice el campo exacto, y afirmarlo aqui otra vez daria dos hallazgos por un defecto.
    """
    normalizados: dict[str, ServidorAprobado] = {}
    for nombre, declarado in bloque.items():
        if not isinstance(declarado, dict):
            continue
        credenciales = declarado.get(_CLAVE_CREDENCIALES)
        aprobacion = declarado.get(_CLAVE_APROBACION)
        normalizados[str(nombre)] = ServidorAprobado(
            nombre=str(nombre),
            write_operations=bool(declarado.get("write_operations", False)),
            tools_digest=str(declarado.get("tools_digest", "")),
            tools_digest_date=str(declarado.get("tools_digest_date", "")),
            credenciales=tuple(c for c in credenciales if isinstance(c, dict))
            if isinstance(credenciales, list) else (),
            aprobacion=aprobacion if isinstance(aprobacion, dict) else {},
        )
    return GobiernoMcp(servidores=normalizados, forma_antigua=False,
                       credenciales_del_bloque=None)


def campos_derivados_declarados(gobierno: GobiernoMcp) -> tuple[str, ...]:
    """Los campos retirados que algun servidor todavia declara, sin repetir.

    Se listan para que el aviso de migracion diga QUE borrar. Sin eso, «migra el bloque» obliga a
    comparar dos esquemas a mano, y lo que cuesta se pospone.
    """
    presentes = {campo
                 for servidor in gobierno.servidores.values()
                 for campo in CAMPOS_DERIVADOS_RETIRADOS
                 if campo in servidor.declaracion_antigua
                 or campo in (servidor.declaracion_antigua.get("source") or {})}
    return tuple(campo for campo in CAMPOS_DERIVADOS_RETIRADOS if campo in presentes)
