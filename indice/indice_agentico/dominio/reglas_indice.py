"""La unica regla que importa del indice: NO SE INDEXA LO QUE NO ESTA PROBADO.

Es lo que cierra un hueco real del diseno. El workflow que publica vive en el repositorio del
dominio -- tiene que vivir ahi, se dispara al mergear alli -- y por tanto un equipo puede editarlo.
Si el indice se creyera lo que le llega, bastaria con quitar el paso de atestacion para publicar
contenido sin sellar. Con esta regla, un release sin firmar simplemente NO ES INSTALABLE, y el
equipo del dominio no controla el repositorio del indice.

Que se exige, y por que cada cosa:
  - atestacion VERIFICADA sobre el digest -> prueba que el paquete salio del workflow del estandar
  - atestacion del VEREDICTO              -> prueba que paso los gates; el digest solo prueba origen
  - `conforme: true` en ese veredicto     -> se puede sellar un veredicto negativo; no se indexa
  - manifiesto dentro del PAQUETE         -> se lee de los bytes sellados, no del repositorio
  - version del manifiesto = etiqueta     -> si difieren, el puntero y el contenido dicen cosas
                                             distintas y el consumidor no sabe que instalo
"""
from __future__ import annotations

from indice_agentico.dominio.candidato import Candidato, Entrada, Motivo

_SIN_DESCRIPCION = "(sin descripcion en el manifiesto)"


def evaluar(candidato: Candidato) -> tuple[Entrada | None, Motivo | None]:
    """Devuelve la entrada indexable, o el motivo del rechazo. Nunca las dos cosas."""
    if candidato.digest is None:
        return None, Motivo.SIN_PAQUETE
    if not candidato.atestacion_verificada:
        return None, Motivo.SIN_ATESTACION
    if candidato.veredicto is None:
        return None, Motivo.SIN_VEREDICTO
    if not candidato.veredicto.get("conforme"):
        return None, Motivo.NO_CONFORME
    if not candidato.manifiesto:
        return None, Motivo.SIN_MANIFIESTO

    version_etiqueta = candidato.etiqueta.removeprefix("v")
    if candidato.manifiesto.get("version") != version_etiqueta:
        return None, Motivo.VERSION_DISCREPANTE

    return Entrada(
        name=candidato.manifiesto["name"],
        description=candidato.manifiesto.get("description") or _SIN_DESCRIPCION,
        version=version_etiqueta,
        repositorio=candidato.repositorio,
        etiqueta=candidato.etiqueta,
        sha=candidato.sha,
    ), None
