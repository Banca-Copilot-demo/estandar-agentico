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
    versiones_en_base,
)
from validador_agentico import listar_plugins
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
                        help="rama base del pull request. Activa las reglas que solo tienen sentido "
                             "comparando contra ella: que el PR no mezcle artefactos con firmantes "
                             "distintos, y que toda unidad que cambia suba su version. Sin esto, "
                             "esas reglas no aplican")
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
    # PEDIR LA BASE Y NO PODER RESOLVERLA NO ES «NO APLICA»: es una comprobacion que se pidio y no
    # corrio. Sin este corte el gate salia CONFORME sin haber ejecutado las reglas que dependen de la
    # base, y eso es indistinguible de haberlas ejecutado y aprobado.
    #
    # MEDIDO en el registro de una solicitud real, donde llevaba pasando desde el principio:
    # `fatal: origin/main...HEAD: no merge base`, un WARNING que nadie lee y un gate en verde. La
    # causa -- un checkout superficial contra un fetch superficial de la base -- se arregla en la
    # accion; esto es lo que impide que el proximo fallo de la misma clase vuelva a pasar callando.
    if argumentos.rama_base and cambios is None:
        log.critical("se pidio validar contra la rama base %s y no se pudo resolver: las reglas que "
                     "dependen de ella NO se han ejecutado. El gate no puede declararse conforme sin "
                     "haberlas corrido", argumentos.rama_base)
        return SALIDA_NO_CONFORME
    # LAS UNIDADES SE TOMAN DE `listar_plugins` Y NO SE VUELVEN A DESCUBRIR AQUI: es la misma lista
    # que usan el etiquetado y el empaquetado, y si el gate exigiera subir la version de una unidad
    # que el etiquetado no reconoce, pediria un numero para algo que nunca se publica.
    versiones = (versiones_en_base.versiones_en_base(
                    raiz, argumentos.rama_base,
                    tuple(ruta for ruta, _, _, _ in listar_plugins.listar(raiz)))
                 if argumentos.rama_base else None)

    resultado = ejecutar(raiz, comprobador_oficial=gh_skill,
                         con_comprobacion_oficial=not argumentos.sin_comprobacion_oficial,
                         equipos_conocidos=equipos, archivos_cambiados=cambios,
                         versiones_en_base=versiones,
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
