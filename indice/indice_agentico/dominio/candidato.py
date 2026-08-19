"""Tipos del dominio del indice. Inmutables y sin dependencias: describen QUE se indexa y POR QUE
se rechaza, sin saber de donde salio la informacion.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Destino(str, Enum):
    """Que se hace con un candidato. TRES destinos y no dos, por la misma razon que el gate tiene
    tres resultados: «no es material de marketplace» NO es «esta mal publicado».

    El plugin es OPCIONAL en el estandar. Un skill o un mcp suelto se gobierna por su propia
    metadata y se instala por su canal -- lo que no puede es tener entrada en `marketplace.json`,
    porque las entradas de un marketplace SON plugins. Meterlo en la misma categoria que un release
    sin firmar haria que el equipo del dominio buscase un defecto que no existe.
    """

    INDEXAR = "indexar"
    OMITIR = "omitir"
    RECHAZAR = "rechazar"


class Motivo(str, Enum):
    """Por que un candidato no se indexa. Es un enum y no una cadena libre porque el motivo se
    muestra al equipo del dominio y se cuenta en el resumen: tiene que ser un valor cerrado."""

    SIN_PLUGIN = "no lleva plugin: se gobierna y se instala igual, pero no va al marketplace"
    SIN_RELEASE = "no tiene ningun release publicado"
    SIN_PAQUETE = "el release no trae el paquete .tar.gz"
    SIN_MANIFIESTO = "el paquete no contiene .claude-plugin/plugin.json"
    SIN_ATESTACION = "no hay atestacion verificable para el digest del paquete"
    SIN_VEREDICTO = "no hay atestacion del veredicto de conformidad del estandar"
    NO_CONFORME = "el veredicto atestado dice que no es conforme"
    VERSION_DISCREPANTE = "la version del manifiesto no coincide con la etiqueta"
    SHA_NO_RESUELTO = "el sha no es un commit de 40 caracteres: seria un puntero movil"


@dataclass(frozen=True)
class Candidato:
    """Lo que se sabe de un repositorio de dominio antes de decidir si se indexa."""

    repositorio: str
    etiqueta: str
    sha: str
    digest: str | None = None
    # `lleva_plugin` y `manifiesto` son dos cosas distintas y hace falta saber las dos: sin plugin
    # es una OMISION correcta; con plugin ilegible es un RECHAZO. Un solo `None` no las distingue.
    lleva_plugin: bool = False
    manifiesto: dict | None = None
    atestacion_verificada: bool = False
    veredicto: dict | None = None


@dataclass(frozen=True)
class Entrada:
    """Una entrada del indice: es lo unico que un cliente necesita para instalar."""

    name: str
    description: str
    version: str
    repositorio: str
    etiqueta: str
    sha: str


@dataclass(frozen=True)
class Descarte:
    """Un candidato que no entra al indice, con su motivo. La misma forma sirve para una OMISION
    -- correcta, por diseno -- y para un RECHAZO -- publicado mal --: lo que las separa es en que
    tupla del `Indice` acaban, no su estructura."""

    repositorio: str
    motivo: Motivo


@dataclass(frozen=True)
class Decision:
    """Que hacer con un candidato. Un solo tipo de retorno en vez de una tupla cuyo significado
    cambia segun el primer elemento: `destino` dice como leer el resto."""

    destino: Destino
    entrada: Entrada | None = None
    motivo: Motivo | None = None


@dataclass(frozen=True)
class Indice:
    entradas: tuple[Entrada, ...]
    omisiones: tuple[Descarte, ...] = ()
    rechazos: tuple[Descarte, ...] = ()
