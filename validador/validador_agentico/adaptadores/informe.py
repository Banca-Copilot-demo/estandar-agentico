"""Adaptador de salida: renderiza el veredicto para que lo lea una persona o una maquina.

Es un ADAPTADOR porque escribe al exterior. Va a `stdout` con `print` y NO por logging (L8): esta
es la salida estructurada que el desarrollador —y el resumen del pull request— consumen. El
logging va a `stderr` y sirve para diagnostico, no para el informe.

Los errores se listan ANTES de los avisos: lo que bloquea primero.

El formato JSON existe para un consumidor concreto: es el PREDICADO de la atestacion que se firma
al publicar. Por eso lleva `formato_version` —quien lo verifique dentro de un ano necesita saber
que esquema esta leyendo— y por eso no incluye rutas absolutas ni nada dependiente de la maquina.
"""
from __future__ import annotations

import json

from validador_agentico.dominio.hallazgo import Hallazgo, Severidad, Veredicto

_ANCHO_SEVERIDAD = 5
_ETIQUETA = {Severidad.ERROR: "ERROR", Severidad.AVISO: "aviso"}

FORMATO_TEXTO = "texto"
FORMATO_JSON = "json"
FORMATOS = (FORMATO_TEXTO, FORMATO_JSON)

# Version del PREDICADO, no del validador: solo cambia si cambia la forma del JSON firmado.
_VERSION_PREDICADO = "1.0.0"
_SANGRIA_JSON = 2


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


def _hallazgo_como_dato(hallazgo: Hallazgo) -> dict[str, str]:
    return {"severidad": hallazgo.severidad.value, "donde": hallazgo.donde,
            "mensaje": hallazgo.mensaje}


def render_json(veredicto: Veredicto, nombre_repositorio: str) -> str:
    """Devuelve el veredicto como predicado de atestacion. Ordenado y con sangria fija para que
    dos ejecuciones del mismo contenido produzcan el mismo texto (el predicado tambien se firma)."""
    predicado = {
        "formato_version": _VERSION_PREDICADO,
        "repositorio": nombre_repositorio,
        "conforme": veredicto.conforme,
        "inventario": {
            "skills": veredicto.inventario.skills,
            "agentes": veredicto.inventario.agentes,
            "prompts": veredicto.inventario.prompts,
            "mcps": veredicto.inventario.mcps,
            "hooks": veredicto.inventario.hooks,
            "tiene_plugin": veredicto.inventario.tiene_plugin,
        },
        "errores": [_hallazgo_como_dato(h) for h in veredicto.errores],
        "avisos": [_hallazgo_como_dato(h) for h in veredicto.avisos],
    }
    return json.dumps(predicado, indent=_SANGRIA_JSON, sort_keys=True, ensure_ascii=False)


def imprimir(veredicto: Veredicto, nombre_repositorio: str, formato: str = FORMATO_TEXTO) -> None:
    renderizar = render_json if formato == FORMATO_JSON else render
    print(renderizar(veredicto, nombre_repositorio))
