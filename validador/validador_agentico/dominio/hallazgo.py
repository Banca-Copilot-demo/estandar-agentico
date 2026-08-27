"""Tipos de dominio del veredicto: severidad, hallazgo y veredicto agregado.

Puro: sin I/O y sin imports del proyecto fuera de `dominio/`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severidad(str, Enum):
    """Severidad de un hallazgo. Enum de dominio y no strings sueltos (P6): un typo en
    `"eror"` seria un bug silencioso que ninguna comprobacion detectaria."""

    ERROR = "error"
    AVISO = "aviso"


@dataclass(frozen=True)
class Hallazgo:
    """Un hallazgo del validador. Dataclass y no `tuple[str, str, str]` (OO1): con la tupla,
    el significado de cada elemento dependia del orden y no se veia en ninguna firma."""

    severidad: Severidad
    donde: str
    """Ruta relativa del archivo, con `:linea` cuando la comprobacion la conoce."""
    mensaje: str
    """Que esta mal Y por que importa. Un hallazgo que solo dice que algo esta mal obliga
    al desarrollador a investigar desde cero."""

    @property
    def bloquea(self) -> bool:
        return self.severidad is Severidad.ERROR


def error(donde: str, mensaje: str) -> Hallazgo:
    return Hallazgo(Severidad.ERROR, donde, mensaje)


def aviso(donde: str, mensaje: str) -> Hallazgo:
    return Hallazgo(Severidad.AVISO, donde, mensaje)


@dataclass(frozen=True)
class Inventario:
    """Cuantos artefactos de cada tipo encontro el validador en el arbol real, y si hay plugin.

    Se compara contra lo DECLARADO en `GOVERNANCE.json`: un catalogo que publica un inventario
    que no existe es peor que no tener catalogo.
    """

    skills: int = 0
    agentes: int = 0
    prompts: int = 0
    mcps: int = 0
    hooks: int = 0
    tiene_plugin: bool = False
    # El `name` del manifiesto. Es lo que se instala -- `copilot plugin install <name>@<catalogo>` --,
    # y no el id de un artefacto: un plugin se instala completo.
    nombre_plugin: str = ""
    # LAS IDENTIDADES DEL ARBOL REAL, por tipo. Estan aqui y no solo el conteo porque un CONTEO tiene
    # un falso negativo MEDIDO: borrar un skill y anadir otro en el mismo pull request deja el numero
    # igual, asi que el cotejo contra el inventario declarado no ve NADA y el catalogo publica una
    # lista que ya no existe. Con nombres, el gate compara identidades y ese cambio si se ve.
    #
    # Un artefacto sin `metadata.id` no aporta identidad -- su propia regla ya lo reprocha --, asi que
    # estas tuplas pueden ser mas cortas que el conteo. El cotejo lo tiene en cuenta.
    ids_skills: tuple[str, ...] = ()
    ids_agentes: tuple[str, ...] = ()
    ids_prompts: tuple[str, ...] = ()

    def como_declarado(self) -> dict[str, int]:
        """Las claves con las que el inventario se declara en `GOVERNANCE.json`."""
        return {"skills": self.skills, "agents": self.agentes, "prompts": self.prompts}

    def ids_como_declarado(self) -> dict[str, tuple[str, ...]]:
        """Los ids del arbol real, bajo las MISMAS claves que `como_declarado()`.

        Las dos vistas conviven mientras dure la transicion de conteos a listas: la de conteos sirve a
        los `GOVERNANCE.json` que todavia declaran numeros y la de ids a los que ya declaran nombres.
        """
        return {"skills": self.ids_skills, "agents": self.ids_agentes,
                "prompts": self.ids_prompts}


@dataclass(frozen=True)
class ArtefactoPublicado:
    """Lo que el catalogo necesita saber de UN artefacto. Sale del envelope, que el gate ya valido."""

    id: str
    tipo: str
    ruta: str
    owner_team: str
    owner_contact: str
    version: str
    data_classification: str
    standard_version: str
    # sha256 del ARCHIVO, no del paquete. Es lo que permite verificar un artefacto que se copio
    # fuera del paquete -- un prompt, unas instructions -- contra lo que se firmo.
    sha256: str = ""
    # SOLO LO USA EL `mcp`, y esta en el dataclass compartido a proposito: el predicado es una lista
    # plana de artefactos, y partirla por tipo obligaria a todo consumidor a saber de tipos para leer
    # un campo. Vacio en los demas.
    #
    # POR QUE VIAJA FIRMADO. Es la referencia contra la que la comprobacion periodica decide si un
    # servidor MCP cambio sus herramientas. Si viviera solo en el `METADATA.json` -- que es un archivo
    # editable del repositorio -- cualquiera con escritura podria ajustarlo para que coincidiera con
    # un servidor ya envenenado, y la comprobacion diria que todo esta en orden.
    tools_digest: str = ""
    # SOLO LO USA EL `mcp`: un elemento por servidor, con `nombre`, `endpoint` y `tools_digest`.
    #
    # POR QUE HACE FALTA, y no es coherencia con `hooks`: es lo que DESBLOQUEA la comprobacion
    # periodica de deriva. Esa comprobacion se conecta a UN endpoint y compara contra UN digesto, y su
    # linea base debe salir del predicado FIRMADO -- nunca del `GOVERNANCE.json`, que es editable, o
    # cualquiera con escritura ajustaria el digesto para que cuadrara con un servidor ya envenenado --.
    # Medido: el predicado no llevaba el endpoint, asi que la linea base no se podia construir de lo
    # firmado NI CON UN SOLO SERVIDOR. Eso explica por que ese paso seguia pendiente: no era solo que
    # faltara verificar la atestacion, es que el dato no estaba en lo sellado.
    #
    # El `tools_digest` de arriba se mantiene: es el AGREGADO, y sigue sirviendo para responder
    # «cambio algo» de un vistazo y para no romper a quien ya lo lea.
    servidores: tuple = ()
    # SOLO LO USA `hooks`, por el mismo motivo que `tools_digest`: el predicado es una lista plana.
    # `scripts` es el nivel POR ARCHIVO -- ruta -> sha256 de cada script que el hook ejecuta -- y
    # `scripts_digest` el nivel del CONJUNTO, que cubre el `hooks.json` y todos sus scripts a la vez.
    #
    # POR QUE DOS NIVELES Y NO UNO. Es lo que hace la industria cuando un manifiesto apunta a archivos
    # -- el `RECORD` de un wheel, el `MANIFEST.MF` de un JAR firmado, el manifiesto de una imagen OCI
    # --, y la razon es practica: el digesto del conjunto dice que ALGO cambio y los digestos por
    # archivo dicen QUE cambio. Medido hoy: con solo el del conjunto, una deriva manda a buscar a mano.
    #
    # Y POR QUE HOOKS LO NECESITA MAS QUE NADIE: es el unico tipo que EJECUTA CODIGO, y era el unico
    # sin digesto propio. Firmar solo el `hooks.json` seria firmar el indice de un libro: el JSON
    # DECLARA comandos, y los scripts son los que hacen algo.
    scripts: dict[str, str] = field(default_factory=dict)
    scripts_digest: str = ""


@dataclass(frozen=True)
class PluginPublicado:
    """Un plugin del repositorio, con DONDE vive dentro de el.

    POR QUE LA SUBRUTA VIAJA EN EL VEREDICTO. Es el unico sitio donde el dato sobrevive firmado. El
    paquete no la lleva -- se le quita el prefijo a proposito, porque el cliente espera el manifiesto
    en la raiz de lo que descomprime --, asi que quien lee los bytes publicados no puede saber de que
    subdirectorio salieron. Sin esto, el indice no puede escribir la entrada de un plugin anidado:
    le falta el `path`, y listarlo como el repositorio completo instalaria los plugins vecinos.

    `subruta` es `.` cuando el plugin ES el repositorio, que es el caso normal.
    """

    nombre: str
    version: str
    subruta: str


@dataclass(frozen=True)
class Veredicto:
    """Resultado de validar un repositorio. Inmutable: se construye una vez, al final.

    Sustituye a la lista global que las comprobaciones mutaban (P5): con estado global, dos
    validaciones seguidas en el mismo proceso acumulaban los hallazgos de la primera, y el
    efecto secundario no aparecia en ninguna firma (G4).
    """

    hallazgos: tuple[Hallazgo, ...]
    inventario: Inventario
    artefactos: tuple[ArtefactoPublicado, ...] = ()
    # Los plugins del repositorio y su subruta. Uno con `subruta = "."` en el caso normal; varios
    # cuando es un repositorio de dominio que aloja mas de uno.
    plugins: tuple[PluginPublicado, ...] = ()
    # Custodia de la credencial del `mcp`, tal como la declaro el repositorio. Vacio
    # cuando no hay mcp o cuando su mecanismo no exige que alguien conceda nada.
    credencial_ownership: dict = field(default_factory=dict)

    @property
    def errores(self) -> tuple[Hallazgo, ...]:
        return tuple(h for h in self.hallazgos if h.bloquea)

    @property
    def avisos(self) -> tuple[Hallazgo, ...]:
        return tuple(h for h in self.hallazgos if not h.bloquea)

    @property
    def conforme(self) -> bool:
        """Los avisos NO bloquean: senalan lo que conviene mirar, no lo que impide publicar."""
        return not self.errores
