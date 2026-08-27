#!/usr/bin/env python3
"""Que suites hay que ejecutar, dados los archivos que cambia una solicitud de cambio.

EL PROBLEMA QUE RESUELVE, y es de escala, no de comodidad. Ejecutar TODAS las suites del repositorio
en cada solicitud tiene dos costes que crecen con el inventario:

  - TIEMPO Y CUOTA. Las suites corren en secuencia y cada una tarda minutos. En un repositorio con
    decenas de artefactos, cambiar un skill obligaria a evaluarlos todos.
  - ACOPLAMIENTO, que es peor. Una suite en rojo bloquea a TODO el que toque el repositorio, aunque
    no sea suya y no pueda arreglarla. MEDIDO: un cambio de cableado quedo bloqueado por la suite de
    un agente ajeno.

LA REGLA: se evalua la unidad que el cambio TOCA. Una unidad es lo que el estandar publica por
separado -- un plugin anidado o un artefacto suelto con manifiesto propio --, y NO se redefine aqui:
se recibe ya resuelta por `listar_plugins`, que es la misma regla que usan el gate, el etiquetado y el
empaquetado. Inventar una segunda definicion de «unidad» es exactamente como divergen las cosas.

SIN ARCHIVOS CAMBIADOS SE DEVUELVEN TODAS LAS PROPIAS. Es el caso de la publicacion y del push a
main: ahi no hay «lo que cambia», hay un estado que evaluar entero.

Y «LAS PROPIAS» NO ES UN MATIZ: es un filtro distinto de los otros dos y se aplica SIEMPRE. Una suite
solo cuenta si PERTENECE a una unidad publicable del repositorio evaluado. MEDIDO en un push a main de
`agentes-sdlc` (run 33016050350): el trabajo de comportamiento se puso rojo por
`./.estandar/plantillas/artefactos/evals/promptfooconfig.yaml` -- una PLANTILLA del repositorio del
estandar, que el propio workflow clona dentro del workspace para traerse el puente y las reglas --.
Junto a ella corrieron 3 suites legitimas, 3 de 3 cada una. Un repositorio de dominio quedo en rojo
por un artefacto que no controla, se pago cuota de inferencia por evaluar algo que no se publica, y la
plantilla se midio fuera de su sitio, donde es esperable que no pase.

No se veia en una solicitud de cambio porque alli el acotado por cambios ya la descartaba: la
plantilla no la toca nadie. En un push a main no hay contra que acotar y corre todo lo que se
encuentra, asi que el defecto solo aparece en la rama donde mas duele.

Y ESA PLANTILLA NO ES UNA SUITE MAL ESCRITA: NO PUEDE PASAR NUNCA, POR CONSTRUCCION. Es el esqueleto
que el asistente de autoria copia, y lleva los marcadores sin rellenar. COMPROBADO leyendo el archivo:
promptfoo le pregunta al modelo la cadena literal `<<CONSULTA>>` y comprueba si la respuesta contiene
`<<PALABRA_QUE_TIENE_QUE_APARECER>>`. Ademas del rojo espurio, se paga inferencia por preguntarle a un
modelo un marcador de posicion. Por eso no basta con descartarla cuando llega prestada desde
`.estandar/`: no debe evaluarse NUNCA, tampoco en el repositorio del estandar. De ahi la segunda
regla, `sin_plantillas`.

SALIDA A STDOUT PORQUE LA CONSUME OTRO PROCESO; el logging va a stderr (L8).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections.abc import Callable
from pathlib import Path

# LA PERTENENCIA DE UN ARCHIVO A UNA UNIDAD NO SE DEFINE AQUI. Vivio en este modulo mientras fue su
# unico consumidor; al necesitarla tambien el gate -- para exigirle a toda unidad que cambia que suba
# su version -- mantener dos copias habria significado que un archivo pudiera pertenecer a una unidad
# para la seleccion de suites y a otra para el versionado: se evaluaria una y se publicaria otra.
# Vive en `reglas_layout`, junto a la regla que dice cuales son las unidades.
#
# La suite de una unidad vive DENTRO de ella, a cualquier profundidad: la de un skill en
# `<unidad>/evals/`, la de un agente en `<unidad>/agents/evals/`. Por eso basta con comparar prefijos.
from validador_agentico.dominio.reglas_layout import unidad_de as _unidad_de

log = logging.getLogger(__name__)

# UN HUECO SIN RELLENAR DEL ESQUELETO DE AUTORIA: `<<CONSULTA>>`, `<<PALABRA_QUE_TIENE_QUE_APARECER>>`.
# Se reconoce la plantilla POR ESTA PROPIEDAD y no por una lista de rutas conocidas, y la eleccion es
# deliberada: una lista hay que acordarse de actualizarla al anadir el siguiente esqueleto, y el olvido
# no avisa -- se manifiesta meses despues como una suite en rojo que nadie escribio --. Un marcador sin
# rellenar, en cambio, esta en el archivo por definicion mientras siga siendo una plantilla, y
# desaparece solo cuando alguien la convierte en una suite de verdad.
_MARCADOR_SIN_RELLENAR = re.compile(r"<<[^<>\n]+>>")


def es_plantilla(contenido: str) -> bool:
    """Si el archivo es un ESQUELETO sin rellenar y no una suite ejecutable."""
    return _MARCADOR_SIN_RELLENAR.search(contenido) is not None


def sin_plantillas(suites: list[str], contenido_de: Callable[[str], str]) -> list[str]:
    """Descarta los esqueletos de autoria, que no pueden pasar por construccion.

    EL LECTOR SE INYECTA para que la regla se pruebe sin tocar disco (T1/T4): decidir si un texto es
    una plantilla es una regla pura, y solo el punto de entrada sabe de donde sale ese texto.
    """
    ejecutables = [s for s in suites if not es_plantilla(contenido_de(s))]
    descartadas = len(suites) - len(ejecutables)
    if descartadas:
        log.info("%d plantilla(s) descartada(s): traen marcadores sin rellenar, no son suites "
                 "ejecutables", descartadas)
    return ejecutables


def _suites_del_repositorio(suites: list[str], unidades: list[str]) -> list[str]:
    """Solo las suites que cuelgan de una unidad publicable. Descarta lo ajeno al repositorio.

    LA PREGUNTA NO ES «¿ESTA EN EL WORKSPACE?» SINO «¿SE PUBLICA?». El workspace de la evaluacion
    contiene mas cosas que el repositorio evaluado -- el estandar se clona en `.estandar/` para
    aportar el puente y las reglas --, y en el futuro puede contener otras. Filtrar por el nombre de
    ese directorio arreglaria el caso medido y ninguno de los siguientes; preguntar por la
    PERTENENCIA los cubre todos, porque lo que no cuelga de una unidad no se etiqueta, no se empaqueta
    y no se certifica: evaluarlo no puede cambiar ningun veredicto.

    Se reutiliza `unidad_de`, que es la UNICA definicion de pertenencia del repo -- la misma que usa
    el gate para exigir la subida de version --, y por eso este filtro no puede divergir de ella.
    """
    propias = [s for s in suites if _unidad_de(s, unidades) is not None]
    ajenas = len(suites) - len(propias)
    if ajenas:
        # SE DICE CUANTAS SE DESCARTAN Y POR QUE. Un repositorio sin ninguna unidad publicable -- sin
        # gobierno con version -- perderia aqui TODAS sus suites, y una cobertura que cae a cero en
        # silencio se lee como «todo en verde». Que quede en el log del paso.
        log.info("%d suite(s) descartada(s): no pertenecen a ninguna unidad publicable de este "
                 "repositorio", ajenas)
    return propias


def suites_a_evaluar(suites: list[str], unidades: list[str],
                     cambiados: list[str]) -> list[str]:
    """Las suites que corresponde ejecutar. Todas las PROPIAS si `cambiados` esta vacio."""
    suites = _suites_del_repositorio(suites, unidades)
    if not cambiados:
        log.info("sin lista de archivos cambiados: se evaluan las %d suite(s)", len(suites))
        return suites

    tocadas = {u for u in (_unidad_de(c, unidades) for c in cambiados) if u}
    log.info("unidades tocadas por el cambio: %s", ", ".join(sorted(tocadas)) or "ninguna")

    elegidas = [s for s in suites if _unidad_de(s, unidades) in tocadas]
    omitidas = len(suites) - len(elegidas)
    if omitidas:
        # SE DICE CUANTAS SE OMITEN. Una cobertura que se acota en silencio se lee como cobertura
        # completa, y es justo lo que hace que nadie note que dejo de comprobarse algo.
        log.info("%d suite(s) omitida(s): su unidad no la toca este cambio", omitidas)
    return elegidas


def unidades_a_evaluar(suites: list[str], unidades: list[str],
                       cambiados: list[str]) -> list[str]:
    """Las unidades que tienen al menos una suite que ejecutar, ordenadas.

    ES LA MISMA PREGUNTA QUE `suites_a_evaluar`, PROYECTADA A LA UNIDAD, y por eso se apoya en ella
    en vez de repetir los filtros: si divergieran, se evaluaria una unidad cuya suite el otro filtro
    ya habia descartado -- o peor, se dejaria de evaluar una que si corre --.

    QUIEN LA CONSUME Y PARA QUE: la evaluacion abre UN TRABAJO POR UNIDAD, de modo que cada una emita
    SU PROPIA comprobacion. Con un solo trabajo para todo el repositorio, su unica conclusion se
    contagiaba: MEDIDO en el run 33040368778 de `agentes-sdlc`, `revisar-jql` con 3 de 3 y
    `referencia` con 3 de 3 no se promocionaron porque la suite de `migracion` estaba en 2 de 3. Dos
    artefactos que cumplian se quedaron sin certificar por una unidad que sus equipos no habian
    tocado.
    """
    elegidas = suites_a_evaluar(suites, unidades, cambiados)
    con_suites = sorted({u for u in (_unidad_de(s, unidades) for s in elegidas) if u})
    log.info("unidades con suites que evaluar: %s", ", ".join(con_suites) or "ninguna")
    return con_suites


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suites", required=True, type=argparse.FileType(encoding="utf-8"),
                        help="archivo con una ruta de suite por linea")
    parser.add_argument("--unidades", required=True, type=argparse.FileType(encoding="utf-8"),
                        help="archivo con una subruta de unidad por linea, de `listar_plugins`")
    parser.add_argument("--cambiados", type=argparse.FileType(encoding="utf-8"),
                        help="archivo con los archivos cambiados. Sin el, se evaluan todas")
    parser.add_argument("--agrupado-por-unidad", action="store_true",
                        help="Imprime un ARRAY JSON con las unidades que tienen alguna suite que "
                             "ejecutar, en vez de una ruta de suite por linea. Es lo que alimenta "
                             "la matriz de la evaluacion, que abre un trabajo por unidad.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Activa logging DEBUG (detalles internos de ejecucion).")
    argumentos = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if argumentos.verbose else logging.INFO,
                        stream=sys.stderr, format="%(levelname)-8s %(name)s — %(message)s")

    def _lineas(archivo) -> list[str]:
        return [l.strip().removeprefix("./") for l in archivo if l.strip()] if archivo else []

    def _texto(ruta: str) -> str:
        # SIN CAPTURAR LA LECTURA A PROPOSITO. Las rutas vienen de un `find` que acaba de verlas, asi
        # que un fallo aqui es un defecto real y tiene que romper el paso: tragarselo convertiria una
        # suite ilegible en una suite ausente, o sea en verde. `errors="replace"` solo evita que una
        # codificacion rara la haga desaparecer, porque los marcadores son ASCII y se ven igual.
        return Path(ruta).read_text(encoding="utf-8", errors="replace")

    ejecutables = sin_plantillas(_lineas(argumentos.suites), _texto)
    unidades = _lineas(argumentos.unidades)
    cambiados = _lineas(argumentos.cambiados)

    # UN ARRAY JSON Y NO UNA LISTA DE LINEAS cuando se agrupa: lo consume `fromJSON` de Actions para
    # construir la matriz, y ese es el unico formato que entiende. `json.dumps` ademas escapa lo que
    # haga falta, que es lo que una concatenacion a mano se dejaria.
    if argumentos.agrupado_por_unidad:
        print(json.dumps(unidades_a_evaluar(ejecutables, unidades, cambiados)))
        return 0

    for suite in suites_a_evaluar(ejecutables, unidades, cambiados):
        print(suite)
    return 0


if __name__ == "__main__":
    sys.exit(main())
