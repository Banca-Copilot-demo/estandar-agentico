"""El DIGEST de las herramientas que un servidor MCP declara. Funcion pura: recibe datos, no red.

QUE PROBLEMA RESUELVE. Un servidor MCP puede cambiar la descripcion de una herramienta despues de
haber sido aprobado, y la descripcion de una herramienta es una INSTRUCCION PARA EL MODELO: cambiarla
es inyeccion de prompt sin tocar una linea de codigo nuestro. Es el ataque *rug pull* -- CVE-2025-54136
--, y el protocolo MCP no ofrece ninguna primitiva de integridad contra el: sin firma, sin version que
el cliente deba fijar y sin notificacion que los clientes honren.

LA UNICA DEFENSA PRACTICA es comparar. Se registra el digest de lo que el servidor declaraba cuando
se aprobo, y se vuelve a calcular periodicamente: si difiere, algo cambio sin pasar por revision. La
literatura lo señala como la comprobacion minima viable, y hay una propuesta formal -- ETDI -- que
hace lo mismo firmando las definiciones en el origen.

QUE ENTRA EN EL DIGEST, y por que cada cosa:
  - el NOMBRE de la herramienta   -> añadir o quitar herramientas es un cambio de superficie
  - su DESCRIPCION                -> es lo que el modelo lee; el vector de inyeccion
  - su ESQUEMA DE ENTRADA         -> cambiar un parametro cambia lo que la herramienta puede recibir

QUE NO ENTRA: nada mas. Ni el orden en que el servidor las devuelva -- no esta garantizado y variaria
el digest sin que nada haya cambiado --, ni campos que el servidor pueda añadir por su cuenta, porque
un digest que cambia por ruido se convierte en una alarma que la gente aprende a ignorar.

LIMITE CONOCIDO, y no se debe prometer de mas: esto DETECTA, no PREVIENE. Se sabe que cambio despues
de que cambiara, y la ventana es el intervalo de comprobacion. Un servidor malicioso y selectivo
podria responder una cosa a la comprobacion y otra al desarrollador.
"""
from __future__ import annotations

import hashlib
import json

# Los tres campos que definen la superficie de una herramienta. El nombre de cada clave es el del
# protocolo MCP, no uno nuestro: se leen tal cual llegan de `tools/list`.
CAMPO_NOMBRE = "name"
CAMPO_DESCRIPCION = "description"
CAMPO_ESQUEMA = "inputSchema"

_SIN_VALOR = ""


class HerramientaSinNombreError(ValueError):
    """Una herramienta sin `name` no se puede ordenar ni comparar, asi que el digest no seria
    reproducible. Es un error del servidor, no una degradacion que se pueda ignorar."""


def _canonica(herramienta: dict) -> dict:
    """Los tres campos que cuentan, con el resto descartado."""
    nombre = herramienta.get(CAMPO_NOMBRE)
    if not nombre:
        raise HerramientaSinNombreError(
            f"una herramienta declarada no tiene `{CAMPO_NOMBRE}`: {herramienta!r}")
    return {
        CAMPO_NOMBRE: str(nombre),
        CAMPO_DESCRIPCION: str(herramienta.get(CAMPO_DESCRIPCION) or _SIN_VALOR),
        CAMPO_ESQUEMA: herramienta.get(CAMPO_ESQUEMA) or {},
    }


def forma_canonica(herramientas: list[dict]) -> str:
    """El texto exacto sobre el que se calcula el digest.

    Se expone -- en vez de esconderlo dentro de `digest_de` -- porque cuando una comprobacion
    periodica detecte un cambio, lo primero que alguien va a querer es ver QUE cambio. Con solo el
    digest no hay nada que comparar.

    Ordenado por nombre y con las claves ordenadas: el protocolo no garantiza el orden de
    `tools/list`, y sin fijarlo el digest cambiaria entre dos consultas identicas.
    """
    canonicas = sorted((_canonica(h) for h in herramientas),
                       key=lambda h: h[CAMPO_NOMBRE])
    return json.dumps(canonicas, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest_de(herramientas: list[dict]) -> str:
    """`sha256` de la forma canonica, en hexadecimal."""
    return hashlib.sha256(forma_canonica(herramientas).encode("utf-8")).hexdigest()
