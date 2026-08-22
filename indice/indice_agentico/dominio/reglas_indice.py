"""La unica regla que importa del indice: NO SE INDEXA LO QUE NO ESTA PROBADO.

Es lo que cierra un hueco real del diseno. El workflow que publica vive en el repositorio del
dominio -- tiene que vivir ahi, se dispara al mergear alli -- y por tanto un equipo puede editarlo.
Si el indice se creyera lo que le llega, bastaria con quitar el paso de atestacion para publicar
contenido sin sellar. Con esta regla, un release sin firmar simplemente NO ES INSTALABLE, y el
equipo del dominio no controla el repositorio del indice.

Y una distincion que NO es la misma pregunta: el plugin es OPCIONAL en el estandar. Un artefacto
suelto se gobierna por su propia metadata y se instala por su canal; simplemente no tiene entrada en
`marketplace.json`, porque las entradas de un marketplace SON plugins. Eso se OMITE, no se rechaza
-- pero se le exige el sello igual: el plugin decide DONDE se lista, no SI es instalable.

Que se exige a lo que SI lleva plugin, y por que cada cosa:
  - atestacion VERIFICADA sobre el digest -> prueba que el paquete salio del workflow del estandar
  - atestacion del VEREDICTO              -> prueba que paso los gates; el digest solo prueba origen
  - `conforme: true` en ese veredicto     -> se puede sellar un veredicto negativo; no se indexa
  - manifiesto dentro del PAQUETE         -> se lee de los bytes sellados, no del repositorio
  - version del manifiesto = etiqueta     -> si difieren, el puntero y el contenido dicen cosas
                                             distintas y el consumidor no sabe que instalo
"""
from __future__ import annotations

from indice_agentico.dominio.candidato import (
    Candidato,
    Decision,
    Destino,
    Entrada,
    Motivo,
)

_SIN_DESCRIPCION = "(sin descripcion en el manifiesto)"
LONGITUD_SHA_COMMIT = 40

# Separador de la etiqueta por plugin: `<nombre>--vX.Y.Z`. Un repositorio de dominio que aloja
# varios plugins publica una etiqueta por plugin, porque un solo `vX.Y.Z` no dice de cual es.
_SEPARADOR_DE_ETIQUETA_POR_PLUGIN = "--v"
_PREFIJO_DE_VERSION = "v"


def version_de_la_etiqueta(etiqueta: str) -> str:
    """La version que una etiqueta declara, en sus DOS formas.

    `vX.Y.Z` cuando el repositorio es un solo plugin en la raiz, y `<nombre>--vX.Y.Z` cuando aloja
    varios. Sin esto, la etiqueta por plugin se comparaba entera contra la version del manifiesto y
    el candidato se rechazaba por VERSION_DISCREPANTE -- un mensaje que manda al equipo del dominio
    a buscar un desajuste de version que no existe.
    """
    if _SEPARADOR_DE_ETIQUETA_POR_PLUGIN in etiqueta:
        return etiqueta.rsplit(_SEPARADOR_DE_ETIQUETA_POR_PLUGIN, 1)[1]
    return etiqueta.removeprefix(_PREFIJO_DE_VERSION)


def es_etiqueta_por_plugin(etiqueta: str) -> bool:
    """Si la etiqueta identifica UN plugin dentro de un repositorio que aloja varios."""
    return _SEPARADOR_DE_ETIQUETA_POR_PLUGIN in etiqueta


def _omitir(motivo: Motivo) -> Decision:
    return Decision(destino=Destino.OMITIR, motivo=motivo)


def _rechazar(motivo: Motivo) -> Decision:
    return Decision(destino=Destino.RECHAZAR, motivo=motivo)


def evaluar(candidato: Candidato) -> Decision:
    """Decide el destino de un candidato: indexar, omitir o rechazar.

    EL ORDEN DE LAS PREGUNTAS ES DELIBERADO, y se corrigio: el SELLO se exige PRIMERO y a TODOS.
    Preguntar antes por el plugin dejaba que un artefacto suelto se omitiera sin verificar nada, y
    entonces algo publicado sin sellar llegaba a la ficha del catalogo como si estuviera bien --
    exactamente el hueco que el sello existe para cerrar.

    El plugin se pregunta DESPUES porque no decide si algo es instalable, solo DONDE se lista.
    """
    if candidato.digest is None:
        return _rechazar(Motivo.SIN_PAQUETE)
    # El `sha` tiene que ser un commit resuelto. Un nombre de rama pasaria las demas comprobaciones y
    # produciria una entrada instalable con puntero movil, que es peor que no publicar.
    if len(candidato.sha) != LONGITUD_SHA_COMMIT:
        return _rechazar(Motivo.SHA_NO_RESUELTO)
    if not candidato.atestacion_verificada:
        return _rechazar(Motivo.SIN_ATESTACION)
    if candidato.veredicto is None:
        return _rechazar(Motivo.SIN_VEREDICTO)
    if not candidato.veredicto.get("conforme"):
        return _rechazar(Motivo.NO_CONFORME)

    # Sellado y conforme. A partir de aqui el plugin solo decide el canal de distribucion.
    if not candidato.lleva_plugin:
        return _omitir(Motivo.SIN_PLUGIN)
    if not candidato.manifiesto:
        return _rechazar(Motivo.SIN_MANIFIESTO)

    version_etiqueta = version_de_la_etiqueta(candidato.etiqueta)
    if candidato.manifiesto.get("version") != version_etiqueta:
        return _rechazar(Motivo.VERSION_DISCREPANTE)

    # UN PLUGIN ANIDADO NO SE INDEXA TODAVIA, y se rechaza en voz alta en vez de indexarse mal. Para
    # instalarlo, el cliente necesita la SUBRUTA dentro del repositorio, y aqui no hay de donde
    # sacarla: el paquete trae el manifiesto en su raiz -- a proposito, es lo que el cliente espera
    # al extraerlo -- asi que los bytes sellados no dicen de que subdirectorio salieron. Emitir la
    # fuente del repositorio COMPLETO seria un puntero valido en forma y equivocado en contenido:
    # Claude Code instalaria el repositorio entero creyendo instalar este plugin, sin dar error.
    if es_etiqueta_por_plugin(candidato.etiqueta):
        return _rechazar(Motivo.SUBRUTA_NO_RESUELTA)

    return Decision(destino=Destino.INDEXAR, entrada=Entrada(
        name=candidato.manifiesto["name"],
        description=candidato.manifiesto.get("description") or _SIN_DESCRIPCION,
        version=version_etiqueta,
        repositorio=candidato.repositorio,
        etiqueta=candidato.etiqueta,
        sha=candidato.sha,
    ))
