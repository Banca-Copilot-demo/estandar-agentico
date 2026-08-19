"""La unica regla que importa del indice: NO SE INDEXA LO QUE NO ESTA PROBADO.

Es lo que cierra un hueco real del diseno. El workflow que publica vive en el repositorio del
dominio -- tiene que vivir ahi, se dispara al mergear alli -- y por tanto un equipo puede editarlo.
Si el indice se creyera lo que le llega, bastaria con quitar el paso de atestacion para publicar
contenido sin sellar. Con esta regla, un release sin firmar simplemente NO ES INSTALABLE, y el
equipo del dominio no controla el repositorio del indice.

Y una distincion que NO es la misma pregunta: el plugin es OPCIONAL en el estandar. Un artefacto
suelto se gobierna por su propia metadata y se instala por su canal; simplemente no tiene entrada en
`marketplace.json`, porque las entradas de un marketplace SON plugins. Eso se OMITE, no se rechaza.

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


def _omitir(motivo: Motivo) -> Decision:
    return Decision(destino=Destino.OMITIR, motivo=motivo)


def _rechazar(motivo: Motivo) -> Decision:
    return Decision(destino=Destino.RECHAZAR, motivo=motivo)


def evaluar(candidato: Candidato) -> Decision:
    """Decide el destino de un candidato: indexar, omitir o rechazar.

    EL ORDEN DE LAS PREGUNTAS ES DELIBERADO. Lo primero que se pregunta es si el paquete lleva
    plugin, porque un artefacto suelto es una OMISION -- correcta y esperada -- y no debe llegar a
    las comprobaciones de sellado para acabar rechazado por un motivo que no le aplica.
    """
    if candidato.digest is None:
        return _rechazar(Motivo.SIN_PAQUETE)
    if not candidato.lleva_plugin:
        return _omitir(Motivo.SIN_PLUGIN)
    if not candidato.atestacion_verificada:
        return _rechazar(Motivo.SIN_ATESTACION)
    if candidato.veredicto is None:
        return _rechazar(Motivo.SIN_VEREDICTO)
    if not candidato.veredicto.get("conforme"):
        return _rechazar(Motivo.NO_CONFORME)
    if not candidato.manifiesto:
        return _rechazar(Motivo.SIN_MANIFIESTO)

    version_etiqueta = candidato.etiqueta.removeprefix("v")
    if candidato.manifiesto.get("version") != version_etiqueta:
        return _rechazar(Motivo.VERSION_DISCREPANTE)

    return Decision(destino=Destino.INDEXAR, entrada=Entrada(
        name=candidato.manifiesto["name"],
        description=candidato.manifiesto.get("description") or _SIN_DESCRIPCION,
        version=version_etiqueta,
        repositorio=candidato.repositorio,
        etiqueta=candidato.etiqueta,
        sha=candidato.sha,
    ))
