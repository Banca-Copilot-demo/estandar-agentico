"""La politica de la organizacion: decisiones que la cadena de publicacion honra.

POR QUE ES UN DATO Y NO UNA CONDICION EN EL WORKFLOW. La pregunta «¿lo Conforme se distribuye?» se
responde en TRES sitios -- al crear el release, al generar el catalogo y al instalar --, y si cada uno
la decidiera por su cuenta, cambiar de opinion obligaria a tocar los tres y a acertar en los tres. El
cliente ya cambio de criterio una vez sobre esto; asumir que no volvera a cambiar seria ignorar la
evidencia.

LO QUE **NO** CAMBIA ENTRE POLITICAS, y conviene tenerlo claro antes de leer el resto: los estados del
ciclo de vida, sus transiciones, el sellado, la atestacion y la ficha de Port son los mismos en las dos.
Lo unico que cambia es EN QUE ESTADO se entra al catalogo instalable.
"""
from __future__ import annotations

from enum import Enum

RUTA_POLITICA = "POLITICA.json"

# El estado que la publicacion escribe siempre. La promocion a `certified` la decide la evaluacion,
# despues, y nunca este paso.
ESTADO_AL_PUBLICAR = "conformant"
ESTADO_CERTIFICADO = "certified"


class Promocion(str, Enum):
    """Cuando un artefacto entra al catalogo instalable."""

    AL_CERTIFICAR = "al_certificar"
    """Solo lo Certificado se distribuye. Lo Conforme queda publicado, sellado y verificable, pero
    fuera del catalogo: no se encuentra buscando ni se instala por nombre."""

    AL_PUBLICAR = "al_publicar"
    """Todo lo Conforme se distribuye. Era el comportamiento antes de que el cliente pidiera separar
    publicar de distribuir."""


# El valor que se usa cuando no hay politica declarada.
#
# ES EL MAS RESTRICTIVO A PROPOSITO. Un fallo al leer la politica -- archivo ausente, JSON roto, campo
# con un valor que no existe -- no debe convertirse en «distribuyelo todo»: eso seria un fail-open, y
# el modo de fallo que este proyecto ha encontrado una y otra vez es exactamente ese, el que no rompe
# nada y por eso nadie ve. Con este default, un error de configuracion se nota porque algo NO se
# distribuye, que es visible y reversible, en vez de porque algo se distribuyo sin querer.
PROMOCION_POR_DEFECTO = Promocion.AL_CERTIFICAR


def promocion_declarada(politica: dict | None) -> Promocion:
    """La politica de promocion, o la mas restrictiva si no se puede determinar.

    `politica` es el contenido YA LEIDO de `POLITICA.json`, no una ruta: esta regla es de dominio y no
    toca disco (G5).
    """
    valor = (politica or {}).get("promocion_al_catalogo")
    try:
        return Promocion(valor)
    except ValueError:
        # Un valor no reconocido es un error de configuracion, no una tercera politica.
        return PROMOCION_POR_DEFECTO


def entra_al_catalogo(estado: str, promocion: Promocion) -> bool:
    """Si un artefacto en `estado` debe estar en el catalogo instalable.

    Es la UNICA funcion que responde esa pregunta, y de ella dependen las tres decisiones que antes
    se tomaban por separado: si el release nace como prelanzamiento, si el indice lo incluye y si el
    asistente permite instalarlo.
    """
    if estado == ESTADO_CERTIFICADO:
        return True
    if estado == ESTADO_AL_PUBLICAR:
        return promocion is Promocion.AL_PUBLICAR
    # Cualquier otro estado -- suspendido, obsoleto, retirado -- no se distribuye por esta via: su
    # salida del catalogo la decide su propio flujo, no la politica de promocion.
    return False
