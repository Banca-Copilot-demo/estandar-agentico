"""Adaptador de salida: renderiza el veredicto para que lo lea una persona.

Es un ADAPTADOR porque escribe al exterior. Va a `stdout` con `print` y NO por logging (L8): esta
es la salida estructurada que el desarrollador —y el resumen del pull request— consumen. El
logging va a `stderr` y sirve para diagnostico, no para el informe.

Los errores se listan ANTES de los avisos: lo que bloquea primero.
"""
from __future__ import annotations

from validador_agentico.dominio.hallazgo import Hallazgo, Severidad, Veredicto

_ANCHO_SEVERIDAD = 5
_ETIQUETA = {Severidad.ERROR: "ERROR", Severidad.AVISO: "aviso"}


def _linea(hallazgo: Hallazgo) -> str:
    return f"{_ETIQUETA[hallazgo.severidad]:{_ANCHO_SEVERIDAD}}  {hallazgo.donde}  {hallazgo.mensaje}"


def _resumen_inventario(veredicto: Veredicto) -> str:
    inventario = veredicto.inventario
    return (f"Inventario real: {inventario.skills} skills | {inventario.agentes} agentes | "
            f"{inventario.prompts} prompts | {inventario.mcps} mcp | {inventario.hooks} hooks | "
            f"plugin: {'si' if inventario.tiene_plugin else 'no'}")


def _linea_de_veredicto(veredicto: Veredicto) -> str:
    estado = "CONFORME" if veredicto.conforme else "NO CONFORME"
    return (f"Veredicto: {estado} - {len(veredicto.errores)} error(es), "
            f"{len(veredicto.avisos)} aviso(s)")


def render(veredicto: Veredicto, nombre_repositorio: str) -> str:
    """Devuelve el informe como texto. Separado de `imprimir` para poder verificarlo sin capturar
    stdout en las pruebas."""
    partes = [f"Validando {nombre_repositorio}", ""]
    partes += [_linea(h) for h in (*veredicto.errores, *veredicto.avisos)]
    partes += ["", _resumen_inventario(veredicto), "", _linea_de_veredicto(veredicto)]
    return "\n".join(partes)


def imprimir(veredicto: Veredicto, nombre_repositorio: str) -> None:
    print(render(veredicto, nombre_repositorio))
