"""Adaptador de salida para GitHub Actions: anotaciones y resumen del job.

POR QUE ESTO IMPORTA MAS DE LO QUE PARECE. Hasta ahora el veredicto era una lista de texto en el
registro del job: el autor tenia que leer el log, encontrar la ruta, abrir el archivo y buscar la
linea. Una anotacion aparece **sobre la linea exacta del diff del pull request**, donde ya esta
mirando.

Las anotaciones se emiten como COMANDOS DE WORKFLOW por stdout -- `::error file=...,line=...::` --.
Eso no necesita ningun permiso ni llamada a la API: los recoge el runner. La API de Check Runs haria
falta solo para publicar un check con NOMBRE PROPIO, o para publicarlo en OTRO repositorio.

El escape NO es opcional: si el mensaje llevara un salto de linea o un `%`, el comando se cortaria y
la anotacion se perderia en silencio -- justo el fallo que este gate existe para no tener.
"""
from __future__ import annotations

from validador_agentico.dominio.comprobacion import ResultadoGate
from validador_agentico.dominio.hallazgo import Hallazgo, Severidad

_COMANDO = {Severidad.ERROR: "error", Severidad.AVISO: "warning"}
_SEPARADOR_LINEA = ":"

# Orden obligatorio: `%` primero, o se re-escaparian los `%` que introducen los demas.
_ESCAPES = (("%", "%25"), ("\r", "%0D"), ("\n", "%0A"))


def _escapar(mensaje: str) -> str:
    for literal, codificado in _ESCAPES:
        mensaje = mensaje.replace(literal, codificado)
    return mensaje


def _ubicacion(donde: str) -> str:
    """`donde` es `ruta` o `ruta:linea`. Sin linea, la anotacion se ancla al archivo completo."""
    ruta, separador, linea = donde.rpartition(_SEPARADOR_LINEA)
    if separador and linea.isdigit():
        return f"file={ruta},line={linea}"
    return f"file={donde}"


def _anotacion(hallazgo: Hallazgo) -> str:
    return (f"::{_COMANDO[hallazgo.severidad]} {_ubicacion(hallazgo.donde)}"
            f"::{_escapar(hallazgo.mensaje)}")


def render_anotaciones(resultado: ResultadoGate) -> str:
    """Los errores antes que los avisos, por el mismo motivo que en el informe de texto."""
    veredicto = resultado.veredicto
    return "\n".join(_anotacion(h) for h in (*veredicto.errores, *veredicto.avisos))


def render_resumen(resultado: ResultadoGate, nombre_repositorio: str) -> str:
    """Resumen en Markdown para el panel del job.

    Es lo que ve quien revisa el pull request sin abrir el registro, asi que lleva el veredicto
    primero y el detalle despues.
    """
    estado = "CONFORME" if resultado.conforme else "NO CONFORME"
    lineas = [f"## Gate de conformidad — {nombre_repositorio}", "",
              f"**{estado}**", "",
              "| Comprobación | Resultado | Detalle |", "|---|---|---|"]
    lineas += [f"| {c.nombre} | {c.resultado.value} | {c.detalle} |"
               for c in resultado.comprobaciones]

    veredicto = resultado.veredicto
    if veredicto.errores or veredicto.avisos:
        lineas += ["", "| | Dónde | Qué |", "|---|---|---|"]
        lineas += [f"| {h.severidad.value} | `{h.donde}` | {h.mensaje} |"
                   for h in (*veredicto.errores, *veredicto.avisos)]

    if not resultado.conforme:
        lineas += ["", "Corrige **todo** lo listado antes de volver a empujar: el gate agrega, "
                       "así que esta lista está completa."]
    return "\n".join(lineas) + "\n"
