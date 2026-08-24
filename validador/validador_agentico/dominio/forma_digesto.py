"""La FORMA de un sha256: reconocerlo sin recalcularlo.

POR QUE ES UN MODULO Y NO UNA FUNCION EN CADA SITIO. `es_digest` estaba escrita, byte a byte, en
`herramientas_mcp` y en `scripts_de_hooks`, con su `_LONGITUD_SHA256 = 64` cada una. Son la MISMA
pregunta -- «este string tiene forma de sha256» -- planteada por dos dominios distintos, y eso es
exactamente lo que G2 y P9 prohiben: dos copias que nadie mantiene a la vez.

QUE NO SE UNIFICA, y conviene decirlo porque el parecido invita a hacerlo: las dos `forma_canonica`
de esos modulos NO son duplicacion aunque compartan nombre. Una canonicaliza una lista de herramientas
de un servidor MCP y la otra un mapa de ruta a digesto de scripts: distinto tipo de entrada, distinta
forma de salida y distinta razon para cambiar. Unificarlas seria juntar dos conceptos por parecerse en
el nombre, que es el error contrario -- y peor, porque produce una funcion que sirve a dos amos --.

QUIEN LLAMA A `es_digest` HOY: solo las pruebas, y eso NO es que sea codigo muerto, es una pieza que
espera a su consumidor. Los digestos que llegan de FUERA -- el `tools_digest` de la linea base con la
que se compara la deriva de un servidor remoto, el `scripts_digest` de un paquete ya publicado -- se
leen de un predicado firmado y hoy se usan sin comprobar que tengan forma de digesto. Cuando la
comprobacion periodica de deriva se cablee, esta es su guarda de entrada. Queda dicho aqui para que
nadie lo borre por «no lo usa nadie» ni lo de por hecho por «ya existe la funcion».
"""
from __future__ import annotations

# La longitud de un sha256 en hexadecimal.
LONGITUD_SHA256 = 64
_DIGITOS_HEXADECIMALES = "0123456789abcdef"


def es_digest(valor: object) -> bool:
    """Si un valor tiene la forma de un `sha256`. Sirve para validar lo DECLARADO sin recalcularlo."""
    return (isinstance(valor, str)
            and len(valor) == LONGITUD_SHA256
            and all(caracter in _DIGITOS_HEXADECIMALES for caracter in valor))
