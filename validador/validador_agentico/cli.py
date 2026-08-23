"""Punto de entrada del validador: parsea argumentos, configura el logging y cablea los adaptadores.

Es el composition root (G5): el UNICO modulo que conoce implementaciones concretas y el UNICO que
convierte el resultado en un codigo de salida. Cualquier otra funcion del paquete es invocable
desde una prueba sin que el proceso muera (P3).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from validador_agentico.adaptadores import (
    anotaciones_github,
    cambios_git,
    gh_skill,
    informe,
    organizacion,
    registro,
)
from validador_agentico.aplicacion.ejecutar_gate import ejecutar

log = logging.getLogger(__name__)

SALIDA_CONFORME = 0
SALIDA_NO_CONFORME = 1


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="validar-artefactos",
        description="Ejecuta el gate de conformidad: G1 estructura, G3 higiene y G4 gobierno, "
                    "mas la comprobacion oficial de la especificacion cuando hay skills. Es el "
                    "MISMO comando que corre CI, para que un pull request nazca en verde.")
    parser.add_argument("raiz", nargs="?", default=".", type=Path,
                        help="raiz del repositorio a validar (por defecto, el directorio actual)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="logging de diagnostico en stderr")
    parser.add_argument("--formato", choices=informe.FORMATOS, default=informe.FORMATO_TEXTO,
                        help="`texto` para leerlo; `json` para firmarlo como predicado")
    parser.add_argument("--anotaciones", action="store_true",
                        help="emite comandos de workflow para que cada hallazgo aparezca SOBRE su "
                             "linea en el diff del pull request")
    parser.add_argument("--escribir-resumen", type=Path, metavar="RUTA",
                        help="escribe el resumen en Markdown en RUTA (en CI, $GITHUB_STEP_SUMMARY)")
    parser.add_argument("--organizacion", metavar="ORG",
                        help="organizacion de GitHub contra la que resolver `owner_team` (G4). "
                             "Sin esto, el dueno declarado queda como texto libre y se avisa")
    parser.add_argument("--rama-base", metavar="REF",
                        help="rama base del pull request. Activa la regla de que un PR no mezcle "
                             "artefactos con firmantes distintos. Sin esto, la regla no aplica")
    parser.add_argument("--esquemas", type=Path, metavar="RUTA",
                        help="directorio con los esquemas JSON contra los que comprobar la FORMA de "
                             "cada artefacto. Sin este flag esa comprobacion no se ejecuta, y el "
                             "informe lo dice: un gate que no comprueba y calla es indistinguible de "
                             "uno que comprobo y aprobo.")
    parser.add_argument("--sin-comprobacion-oficial", action="store_true",
                        help="no invoca `gh skill publish --dry-run`. La comprobacion se declara "
                             "`no aplica` con su motivo: nunca se da por buena en silencio")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argumentos = _parsear_argumentos(argv)
    registro.configurar(argumentos.verbose)
    raiz = argumentos.raiz.resolve()
    if not raiz.is_dir():
        log.error("la raiz no existe o no es un directorio: %s", raiz)
        return SALIDA_NO_CONFORME
    # El composition root resuelve el contexto UNA vez y lo pasa como datos, y es el unico que
    # conoce la implementacion concreta del puerto (G5).
    equipos = organizacion.equipos(argumentos.organizacion) if argumentos.organizacion else None
    cambios = (cambios_git.archivos_cambiados(raiz, argumentos.rama_base)
               if argumentos.rama_base else None)

    resultado = ejecutar(raiz, comprobador_oficial=gh_skill,
                         con_comprobacion_oficial=not argumentos.sin_comprobacion_oficial,
                         equipos_conocidos=equipos, archivos_cambiados=cambios,
                         directorio_de_esquemas=argumentos.esquemas)
    if argumentos.anotaciones:
        # Antes del informe: los comandos de workflow los recoge el runner de stdout, y asi quedan
        # arriba en el registro, no sepultados bajo el detalle.
        anotaciones = anotaciones_github.render_anotaciones(resultado)
        if anotaciones:
            print(anotaciones)

    informe.imprimir_gate(resultado, raiz.name, argumentos.formato)

    if argumentos.escribir_resumen is not None:
        argumentos.escribir_resumen.write_text(
            anotaciones_github.render_resumen(resultado, raiz.name), encoding="utf-8")
        log.info("resumen escrito en %s", argumentos.escribir_resumen)

    return SALIDA_CONFORME if resultado.conforme else SALIDA_NO_CONFORME


if __name__ == "__main__":
    sys.exit(main())
