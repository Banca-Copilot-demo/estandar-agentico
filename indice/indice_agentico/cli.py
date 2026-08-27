"""Punto de entrada del generador del indice: parsea, configura el logging y cablea los adaptadores.

Composition root (G5). Es tambien el unico modulo que decide el codigo de salida, y decide una cosa
que conviene leer despacio: **un rechazo NO es un fallo**. Un dominio que publico sin sellar tiene
que quedarse fuera del indice sin tumbar la generacion de los demas; si esto fallara, un solo
dominio mal publicado congelaria el indice de todos.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from indice_agentico.adaptadores import esquema, marketplace
from indice_agentico.aplicacion.generar import generar
from indice_agentico.dominio.candidato import Indice

log = logging.getLogger(__name__)

SALIDA_OK = 0
SALIDA_ERROR = 1
TOPICO_POR_DEFECTO = "agent-skills"
# Donde vive `marketplace.schema.json`: en el repositorio del estandar, que es donde se publica el
# contrato. No se empaqueta dentro del indice para que no haya dos copias que puedan derivar (G2).
DIRECTORIO_DE_ESQUEMAS_POR_DEFECTO = Path("schemas")
NOMBRE_MARKETPLACE_POR_DEFECTO = "agentico"
# ESTOS TRES FORMATOS SON IDENTICOS a los de `validador_agentico.adaptadores.registro`, y la
# duplicacion es DELIBERADA. Se deja escrito porque G2 no admite duplicar en silencio:
#
# `indice-agentico` y `validador-agentico` son dos paquetes INSTALABLES POR SEPARADO -- la accion
# `indexar` instala solo este, y `validar`/`publicar` solo el otro --, asi que compartir el modulo
# exigiria una de dos cosas, y las dos cuestan mas de lo que ahorran:
#
#   (a) un tercer paquete: habria que añadirlo a los cuatro sitios que hoy instalan uno solo, y una
#       dependencia por RUTA entre paquetes hermanos no resuelve con `pip install <ruta>/indice`;
#   (b) que este paquete dependa del validador: acopla el generador del indice al gate, y tampoco
#       instala -- el validador no esta publicado en ningun indice de paquetes.
#
# Lo que se duplica son doce lineas de infraestructura de logging, sin ninguna regla de negocio. Si
# algun dia hay un tercer consumidor, o si estos formatos empiezan a divergir, la balanza cambia y
# toca (a). SI ESTOS FORMATOS SE TOCAN, hay que tocar los dos: son un contrato de legibilidad, y
# medido en este mismo repositorio -- cuatro copias dentro del validador ya habian divergido, dos de
# ellas entre si, y el mismo comando producia logs con nombre de modulo o sin el segun el entry point.
FORMATO_CI = "%(levelname)-8s %(name)s - %(message)s"
FORMATO_LOCAL = "%(asctime)s %(levelname)-8s %(name)s - %(message)s"
FORMATO_HORA = "%H:%M:%S"

# GitHub Actions define `CI=true`. La copia hermana de `registro.py` ya les habia puesto nombre a
# estos dos; la duplicacion deliberada se trajo los formatos y se dejo atras las constantes, que es
# justo la clase de divergencia que el comentario de arriba dice vigilar (P6).
_VARIABLE_CI = "CI"
_VALOR_CI = "true"


def _configurar_logging(verboso: bool) -> None:
    """A stderr; el marketplace generado va a stdout o a un archivo (L8)."""
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter(
        fmt=FORMATO_CI if os.getenv(_VARIABLE_CI) == _VALOR_CI else FORMATO_LOCAL,
        datefmt=FORMATO_HORA))
    raiz = logging.getLogger()
    raiz.setLevel(logging.DEBUG if verboso else logging.INFO)
    raiz.addHandler(manejador)


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generar-indice",
        description="Genera marketplace.json con los plugins que tienen atestacion verificada.")
    parser.add_argument("organizacion", help="organizacion de GitHub donde viven los dominios")
    parser.add_argument("--topico", default=TOPICO_POR_DEFECTO,
                        help="topico que marca un repositorio de dominio")
    parser.add_argument("--nombre", default=NOMBRE_MARKETPLACE_POR_DEFECTO,
                        help="`name` del marketplace")
    parser.add_argument("--equipo", default="Plataforma Agentica (demo)")
    parser.add_argument("--contacto", default="plataforma-agentica@ejemplo.dev")
    parser.add_argument("--version", default="0.1.0", help="version del marketplace")
    parser.add_argument("--raiz", type=Path,
                        help="raiz del repositorio del marketplace donde escribir LAS DOS "
                             "proyecciones, cada una en la ruta que su cliente lee; por defecto, "
                             "stdout")
    parser.add_argument("--esquemas", type=Path, default=DIRECTORIO_DE_ESQUEMAS_POR_DEFECTO,
                        help="directorio con `marketplace.schema.json`, contra el que se valida "
                             "cada proyeccion ANTES de escribirla")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def _informar_descartes(indice: Indice) -> None:
    """Las omisiones se informan como INFO y los rechazos como WARNING, y esa diferencia es el
    punto: una omision es el estandar funcionando -- el plugin es opcional --, mientras que un
    rechazo es algo publicado mal. Con el mismo nivel, el equipo del dominio buscaria un defecto
    donde no hay ninguno."""
    for omision in indice.omisiones:
        log.info("no va al marketplace %s: %s", omision.repositorio, omision.motivo.value)
    for rechazo in indice.rechazos:
        log.warning("FUERA DEL INDICE %s: %s", rechazo.repositorio, rechazo.motivo.value)


def escribir(indice: Indice, raiz: Path, contenidos: dict,
             directorio_de_esquemas: Path = DIRECTORIO_DE_ESQUEMAS_POR_DEFECTO) -> int:
    """Escribe LAS DOS proyecciones, o explica por que ninguna. Separado de `main` para poder probar
    el guardarail sin parchear nada: recibe el indice y la raiz, y devuelve el codigo de salida.

    Las dos se escriben en la misma llamada a proposito: si una se pudiera actualizar sin la otra,
    los usuarios de un cliente veran un marketplace mas viejo que los del otro sin que nada lo
    indique.
    """
    if indice.entradas:
        # SE VALIDAN LAS DOS ANTES DE ESCRIBIR NINGUNA. Validar despues solo documentaria que se
        # publico algo malo, y escribir una y abortar en la otra dejaria el marketplace a medias.
        defectos = {
            proyeccion: esquema.incumplimientos(texto, proyeccion.subesquema,
                                                directorio_de_esquemas)
            for proyeccion, texto in contenidos.items()
        }
        if any(defectos.values()):
            for proyeccion, incumplimientos in defectos.items():
                for defecto in incumplimientos:
                    log.error("%s no cumple el esquema del marketplace: %s",
                              proyeccion.ruta, defecto)
            log.error("no se escribe ninguna proyeccion: un marketplace que no cumple el esquema es "
                      "un marketplace que algun cliente no sabra instalar")
            return SALIDA_ERROR

        for proyeccion, texto in contenidos.items():
            salida = raiz / proyeccion.ruta
            salida.parent.mkdir(parents=True, exist_ok=True)
            salida.write_text(texto, encoding="utf-8")
            log.info("escrito %s con %d plugin(s)", salida, len(indice.entradas))
        return SALIDA_OK

    # Un indice vacio sobreescribiendo uno que funcionaba desinstalaria todo de golpe. Nunca es un
    # marketplace legitimo, asi que no se escribe -- pero el MOTIVO se distingue, porque los dos casos
    # se arreglan en sitios distintos.
    #
    # Medido en CI: con el GITHUB_TOKEN del propio repositorio del indice, el descubrimiento
    # devolvio CERO repositorios aunque en local devolvia uno. El token esta acotado a su
    # repositorio y no ve los dominios privados. Sin distinguir los dos casos, ese fallo de
    # credencial se leia como "nada paso las comprobaciones", y habria mandado a revisar los gates
    # de los dominios en vez de el token.
    if indice.omisiones and not indice.rechazos:
        log.error("los %d repositorio(s) descubiertos son artefactos SUELTOS, sin plugin: no hay "
                  "nada que indexar. No es un fallo -- pero tampoco se sobreescribe un marketplace "
                  "que si tenia entradas", len(indice.omisiones))
    elif indice.rechazos:
        log.error("se descubrieron %d repositorio(s) y NINGUNO paso las comprobaciones: revisa los "
                  "motivos de arriba", len(indice.rechazos))
    else:
        log.error("no se descubrio NINGUN repositorio de dominio: revisa el token -- el "
                  "GITHUB_TOKEN del repositorio del indice no ve los dominios privados -- y que "
                  "los repositorios lleven el topico")
    log.error("no se sobreescribe ninguna proyeccion en %s", raiz)
    return SALIDA_ERROR


def main(argv: list[str] | None = None) -> int:
    argumentos = _parsear_argumentos(argv)
    _configurar_logging(argumentos.verbose)

    indice = generar(argumentos.organizacion, argumentos.topico)
    _informar_descartes(indice)

    propietario = {"name": argumentos.equipo, "email": argumentos.contacto}
    contenidos = {
        proyeccion: marketplace.render(indice, argumentos.nombre, propietario, argumentos.version,
                                       proyeccion)
        for proyeccion in marketplace.Proyeccion
    }

    if argumentos.raiz is None:
        # A stdout va UNA, porque stdout es un solo flujo que otro proceso consume. Se dice cual por
        # el log (stderr) para que nadie asuma que es la del cliente que le interesa.
        proyeccion = marketplace.Proyeccion.CLAUDE_CODE
        log.info("sin --raiz: se emite la proyeccion de %s por stdout", proyeccion.ruta)
        print(contenidos[proyeccion], end="")
        return SALIDA_OK
    return escribir(indice, argumentos.raiz, contenidos, argumentos.esquemas)


if __name__ == "__main__":
    sys.exit(main())
