"""Como se lee el bloque `artifacts` del `GOVERNANCE.json`, en sus DOS formas.

QUE CAMBIO Y POR QUE. El inventario se declaraba con CONTEOS -- `{"skills": 2, "agents": 0}` -- y
pasa a declararse con LISTAS DE IDS -- `{"skills": ["demo.sdlc.revisar-cobertura"]}` --. El motivo
esta medido y es un falso negativo del conteo: en un mismo pull request, borrar un skill y anadir
otro deja el numero EXACTAMENTE igual, asi que el cotejo contra el arbol real no encuentra nada que
decir y el catalogo publica un inventario que ya no corresponde. Con nombres, lo que se compara son
identidades y ese cambio se ve.

QUE SALE DEL BLOQUE, y tampoco es cosmetico:

  `mcps`  el servidor ya se enumera EN `.mcp.json`, que es el archivo que el cliente ejecuta.
          Repetir alli el numero era una segunda declaracion de lo mismo, y dos declaraciones de la
          misma cosa divergen. El gate ya coteja el gobierno contra ese archivo.

  `hooks` los hooks NO TIENEN IDENTIDAD INDIVIDUAL -- verificado contra el formato: un hook se
          distingue por su EVENTO y su `matcher`, y no lleva `id` en ninguna parte --, asi que no son
          enumerables. Contarlos daba un numero que nunca podia ser otro que 0 o 1, porque hay como
          mucho un `hooks.json` por unidad. Que la unidad TRAE hooks se ve del propio archivo.

LA TRANSICION NO BLOQUEA, y esa es la parte que decide si esto se puede desplegar. El gate es
comprobacion REQUERIDA en los repositorios de dominio: si la forma vieja pasara a ERROR de golpe,
todos los repositorios que aun no se han migrado se pondrian rojos a la vez y -- peor -- ninguno
podria mergear NI SIQUIERA el pull request que viene a arreglarlo, porque ese PR tambien pasa por el
gate. Ya ocurrio al retirar `status`. Asi que la forma vieja se ACEPTA con AVISO, y se cotejara por
conteo mientras se declare asi.

CUANDO SE PUEDE ENDURECER: cuando ningun `GOVERNANCE.json` de un repositorio de dominio declare el
inventario por conteo. El aviso nombra la clave exacta, de modo que la migracion es mecanica.

PURO (G5): recibe el bloque ya parseado y devuelve datos. Sin I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

# Los tipos que el inventario enumera, con la clave con la que se declaran. Son los tres que tienen
# IDENTIDAD PROPIA: cada uno lleva su `metadata.id` en su frontmatter.
TIPOS_ENUMERABLES = ("skills", "agents", "prompts")

# Claves que el inventario declaraba y que ya no forman parte del estandar. Se aceptan y se DESCARTAN
# con aviso, por el mismo motivo que `status`: quitarlas del esquema convertiria su presencia en un
# error automatico -- el esquema declara `additionalProperties: false` -- y eso es justo el bloqueo
# que hay que evitar.
CLAVES_RETIRADAS = ("mcps", "hooks", "scripts")

_POR_QUE_SALE = {
    "mcps": "el servidor ya se enumera en `.mcp.json`, que es el archivo que ejecuta el cliente, y "
            "el gate coteja el gobierno contra ese archivo. Declararlo aqui era una segunda "
            "declaracion de lo mismo",
    "hooks": "los hooks no tienen identidad individual -- se distinguen por evento y `matcher`, no "
             "llevan `id` -- asi que no son enumerables. Que la unidad trae hooks se ve del propio "
             "`hooks.json`",
    "scripts": "un script no es un artefacto publicable: viaja DENTRO del que lo referencia, y su "
               "integridad la cubre el digesto por archivo de la ficha",
}


@dataclass(frozen=True)
class InventarioDeclarado:
    """El bloque `artifacts` normalizado, sin perder CON QUE FORMA se declaro cada tipo.

    La forma importa porque decide como se coteja: por identidad cuando se declaro una lista, por
    numero cuando se declaro un conteo. Un unico campo `dict[str, int | list]` habria obligado a cada
    consumidor a hacer `isinstance` -- justo el contrato fragil que P7 prohibe --.
    """

    ids: dict[str, tuple[str, ...]]
    """tipo -> ids declarados. Solo lleva los tipos declarados con la forma NUEVA."""
    conteos: dict[str, int]
    """tipo -> numero declarado. Solo lleva los tipos declarados con la forma VIEJA."""
    tipos_por_conteo: tuple[str, ...]
    """Los tipos que llegaron como numero. Vacio cuando la unidad ya esta migrada."""
    claves_retiradas: tuple[str, ...]
    """Las claves del bloque que ya no forman parte del estandar y se descartan."""


def leer(bloque: object) -> InventarioDeclarado:
    """Normaliza el bloque `artifacts`. Un bloque ausente o ilegible se lee como vacio.

    Ilegible se trata como vacio y NO como un error propio: la forma la comprueba el esquema, que da
    un mensaje mucho mas preciso que «no se entiende», y afirmarlo dos veces daria dos hallazgos por
    un solo defecto.
    """
    if not isinstance(bloque, dict):
        return InventarioDeclarado(ids={}, conteos={}, tipos_por_conteo=(), claves_retiradas=())

    ids: dict[str, tuple[str, ...]] = {}
    conteos: dict[str, int] = {}
    por_conteo: list[str] = []
    for tipo in TIPOS_ENUMERABLES:
        declarado = bloque.get(tipo)
        if isinstance(declarado, list):
            ids[tipo] = tuple(str(elemento) for elemento in declarado)
        elif isinstance(declarado, bool):
            # `True` es un `int` en Python y se colaria como conteo 1. No es un caso hipotetico: un
            # `"skills": true` es un error de tecleo plausible y contarlo como «hay uno» seria peor
            # que ignorarlo, porque el cotejo podria cuadrar por casualidad.
            continue
        elif isinstance(declarado, int):
            conteos[tipo] = declarado
            por_conteo.append(tipo)

    retiradas = tuple(clave for clave in CLAVES_RETIRADAS if clave in bloque)
    return InventarioDeclarado(ids=ids, conteos=conteos,
                               tipos_por_conteo=tuple(por_conteo),
                               claves_retiradas=retiradas)


def por_que_sale(clave: str) -> str:
    """El motivo por el que una clave retirada ya no se declara, para el mensaje del aviso.

    Va en el hallazgo y no solo en este modulo porque un aviso que dice «quita esto» sin decir por
    que se lee como burocracia, y lo que se lee como burocracia se ignora.
    """
    return _POR_QUE_SALE.get(clave, "ya no forma parte del inventario del estandar")
