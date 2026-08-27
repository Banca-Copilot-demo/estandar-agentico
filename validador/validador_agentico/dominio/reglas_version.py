"""Si una unidad cambio, su VERSION tiene que haber cambiado tambien.

EL DEFECTO QUE CIERRA. La version de una unidad se escribe a mano en su manifiesto y el etiquetado
deriva la etiqueta de ella. Nada obligaba a subirla. Quien cambiaba un artefacto sin tocar la version
no producia etiqueta nueva, y sin etiqueta no hay release, ni paquete, ni atestacion, ni ficha: el
artefacto publicado se quedaba tal cual estaba y NADIE SE ENTERABA de que su cambio no llego a nadie.

EL CASO QUE LO DESTAPO es el peor de todos porque sale en verde de principio a fin: anadirle evals a
un artefacto YA publicado. La suite corre, pasa, el gate aprueba y se mezcla -- y como la version no
cambio, no hay publicacion nueva que promocionar, asi que el artefacto se queda en `conformant` para
siempre. El trabajo de escribir las evaluaciones no cambia nada observable, y no hay ningun mensaje
que lo diga.

CONTRA LA RAMA BASE Y NO CONTRA LA ULTIMA ETIQUETA PUBLICADA. Comparar contra lo publicado exigiria
una segunda subida a quien hiciera un segundo cambio antes de que el primero se publicara: la version
ya subio respecto de lo publicado, y volver a pedirlo seria pedir dos numeros para un solo release.
Contra la base, la pregunta es exactamente la que importa: «este pull request, ¿declara lo que
cambia?».

EL NUMERO LO ELIGE EL AUTOR. Esta regla comprueba que HAYA una decision, nunca cual. Y no es
timidez: solo el autor sabe si su cambio rompe a quien ya lo usa, y en un artefacto agentico eso no
se deduce del diff -- cambiar una `description` puede dejar de activar un skill en los clientes que
ya lo tenian, que es un cambio mayor sin una sola linea de comportamiento tocada --. Un gate que
propusiera el numero acertaria en los casos triviales y se equivocaria justo en los caros.

ES ERROR Y NO AVISO. Un aviso aqui se ignora -- el pull request se mezcla igual -- y el fallo vuelve
intacto: publicacion que no ocurre, sin rastro. Si algo solo protege cuando alguien decide hacerle
caso, no protege.

UNA UNIDAD NUEVA ESTA EXENTA. Si no existia en la base no hay version anterior contra la que
comparar, y exigir una subida seria exigir que la primera version de algo sea la segunda.
"""
from __future__ import annotations

from dataclasses import dataclass

from validador_agentico.dominio.hallazgo import Hallazgo, error
from validador_agentico.dominio.reglas_layout import unidad_de

# Lo que cambia sin viajar en ningun paquete: la maquinaria de CI del repositorio. Un cambio de
# workflow no altera lo que se instala, asi que exigirle una subida de version a la unidad de la raiz
# convertiria la regla en ruido en cada pull request de infraestructura -- y un gate que salta cuando
# no debe se acaba desactivando, que es la forma mas cara de perder una comprobacion --.
#
# `evals/` NO esta aqui, y es deliberado: anadirle evaluaciones a un artefacto publicado es
# EXACTAMENTE el caso que motiva esta regla. Sin publicacion nueva no hay nada que promocionar a
# `certified`, asi que ese cambio SI tiene que subir la version.
_PREFIJOS_QUE_NO_VIAJAN = (".github",)


@dataclass(frozen=True)
class VersionDeUnidad:
    """La version que una unidad declara ahora y la que declaraba en la rama base.

    `version_en_base is None` significa que la unidad NO EXISTIA en la base. No es lo mismo que una
    version vacia: distinguirlo es lo que exime a una unidad nueva de subir un numero que no tiene.
    """

    ruta: str
    """Ruta de la unidad relativa al repositorio, con `.` cuando es el repositorio entero."""
    nombre: str
    version: str
    version_en_base: str | None


def _viaja_en_el_paquete(ruta: str) -> bool:
    primer_segmento = ruta.split("/", 1)[0]
    return primer_segmento not in _PREFIJOS_QUE_NO_VIAJAN


def _unidades_tocadas(archivos_cambiados: tuple[str, ...],
                     unidades: tuple[str, ...]) -> frozenset[str]:
    """Las unidades a las que pertenece al menos un archivo cambiado que viaja en el paquete."""
    return frozenset(
        u for u in (unidad_de(ruta, unidades)
                    for ruta in archivos_cambiados if _viaja_en_el_paquete(ruta))
        if u is not None)


def revisar_subida_de_version(unidades: tuple[VersionDeUnidad, ...],
                              archivos_cambiados: tuple[str, ...]) -> list[Hallazgo]:
    """Un error por cada unidad cuyo contenido cambio sin que su version cambiara."""
    tocadas = _unidades_tocadas(archivos_cambiados, tuple(u.ruta for u in unidades))
    return [
        error(unidad.ruta if unidad.ruta != "." else unidad.nombre,
              f"`{unidad.nombre}` cambia en este pull request y sigue declarando la version "
              f"{unidad.version}, la misma que la rama base. Sin un numero nuevo no se crea "
              "etiqueta, y sin etiqueta no hay release, paquete, atestacion ni ficha: el cambio "
              "se mezcla y lo publicado se queda como estaba, sin que nada lo avise. Elige tu el "
              "numero -- solo tu sabes si esto rompe a quien ya lo usa --.")
        for unidad in unidades
        if unidad.ruta in tocadas
        and unidad.version_en_base is not None
        and unidad.version == unidad.version_en_base
    ]


def revisar_version_del_artefacto(donde: str, version_del_artefacto: str,
                                   version_de_la_unidad: str) -> list[Hallazgo]:
    """La `metadata.version` de un artefacto es LA DE SU UNIDAD. Error, no aviso.

    EL DEFECTO, MEDIDO. `planificar-migracion` declaraba `0.1.0` mientras su plugin iba por `0.1.3`.
    Llevaban asi todo el dia y se habia publicado tres veces sin que nadie lo notara, porque nada
    comparaba los dos numeros: el del manifiesto decide la ETIQUETA y el del frontmatter viaja en la
    FICHA del catalogo, o sea que las dos cifras se leen en sitios distintos y nunca juntas.

    POR QUE IMPORTA, y no es pulcritud. Lo que se instala es la unidad ENTERA, en su version, y lo
    que el catalogo muestra por artefacto es esta otra. Quien mira la ficha ve `0.1.0`, se descarga
    `0.1.3` y no tiene forma de saber si le falta algo: el numero que le ensenaron no identifica nada
    instalable. En un incidente es peor, porque «que version de este skill esta desplegada» pasa a
    tener dos respuestas y ninguna se puede descartar.

    POR QUE NO SE DERIVA Y SE BORRA EL CAMPO. Porque un artefacto tiene que ser AUDITABLE SUELTO, que
    es el motivo entero del envelope: `gh skill install` PRESERVA su `metadata`, y ahi fuera -- sin
    plugin y sin catalogo -- ese numero es lo unico que dice que version es. Borrarlo lo dejaria en
    blanco justo cuando es la unica fuente.

    QUIEN LO MANTIENE AL DIA NO ES UNA PERSONA. `generar.sh` toma la version de la unidad al crear el
    artefacto, y el asistente de autoria hace lo mismo al subirla. Una regla que exige coincidencia
    sin que nada la mantenga solo mueve el trabajo manual de sitio, y lo manual vuelve a divergir.
    """
    if not version_del_artefacto or not version_de_la_unidad:
        # Sin uno de los dos numeros no hay coincidencia que afirmar. Que falten ya lo reprochan sus
        # propias reglas -- la del envelope y la del manifiesto --, y repetirlo aqui daria dos
        # hallazgos por un solo defecto.
        return []
    if version_del_artefacto == version_de_la_unidad:
        return []
    return [error(donde,
                  f"declara la version {version_del_artefacto} y su unidad publica la "
                  f"{version_de_la_unidad}. Lo que se instala es la unidad ENTERA, asi que el numero "
                  f"de la ficha no identifica nada instalable: quien la lea vera "
                  f"{version_del_artefacto}, se descargara {version_de_la_unidad} y no podra saber "
                  f"si le falta algo. Medido: un skill declaraba 0.1.0 con su plugin en 0.1.3 y se "
                  f"publico tres veces sin que nadie lo notara. Igualalas -- `generar.sh` y el "
                  f"asistente de autoria ya las escriben desde la unidad")]
