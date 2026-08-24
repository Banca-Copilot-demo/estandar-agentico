"""Entry point: el PROVEEDOR de Copilot que el motor de evals no trae.

QUE ES ESTO EN UNA LINEA: promptfoo pone el motor -- lee los casos, comprueba, agrega y decide con un
exit code -- y no sabe hablar con Copilot. Este archivo es lo unico que falta.

COMO LO LLAMA EL MOTOR: su proveedor `exec:` invoca un programa pasandole el prompt como PRIMER
ARGUMENTO y toma su STDOUT como la respuesta del modelo. El contrato de este script es deliberadamente
tonto: un argumento entra, texto sale. Todo lo demas -- aserciones, repeticiones, umbrales, veredicto,
codigo de salida -- es del motor y NO se implementa aqui. Esa frontera es la razon de que la pieza propia
sean cuarenta lineas y no un motor.

POR QUE UN SOLO ARCHIVO Y NO UN PAQUETE POR CAPAS (G5): este componente tiene UN adaptador y UN entry
point, y el adaptador no es polimorfico -- no hay dos implementaciones de «hablar con el CLI de Copilot»
ni se anticipan --. Repartir cuarenta lineas en `adaptadores/`, `dominio/` y `puertos/` seria indireccion
sin beneficio, que es lo que la propia regla advierte al final. Si algun dia hay un segundo proveedor
propio, ESE es el momento de introducir el puerto.

POR QUE `-s` Y NO `--output-format json`: con `-s` la salida ES la respuesta del agente, sin estadisticas,
que es exactamente lo que el motor espera. La forma JSONL existe y hara falta el dia que se quiera
comprobar la ACTIVACION de verdad en Copilot -- expone la sesion completa, o sea que se puede ver si el
artefacto se cargo --; para comprobar la SALIDA es ruido. Queda anotado como el siguiente paso, porque hoy
la activacion en Copilot se infiere del contenido de la respuesta, y eso es un compromiso, no una
equivalencia (ver §G5 del lineamiento).

`--allow-all-tools` NO es una comodidad: la ayuda del CLI dice que es *requerido para modo no
interactivo*. Y `--no-ask-user` evita que el agente espere a una persona que no existe.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# SE RESUELVE POR NOMBRE, no por ruta, y la primera version de este archivo lo hacia al contrario:
# apuntaba al `copilot.bat` que VS Code deja en su carpeta de extension. Dos cosas lo desaconsejan, y las
# dos se midieron:
#
#   1. ESE ARCHIVO NO ES EL CLI, es un SHIM que busca el binario real en el PATH. Si el real no esta,
#      imprime «Cannot find GitHub Copilot CLI» por stdout -- o sea que el motor lo recibe como si fuera
#      la respuesta del modelo y falla el caso por la razon equivocada.
#   2. UNA RUTA DENTRO DE UNA EXTENSION DE VS CODE no existe en CI, y ademas cambia cuando la extension
#      se actualiza.
#
# El CLI real se instala como paquete global (`@github/copilot`), asi que basta el nombre: `cmd` lo
# resuelve del PATH. El prefijo `cmd /c` sigue haciendo falta porque en Windows el ejecutable es un `.cmd`
# y `CreateProcess` no sabe correrlo.
NOMBRE_DEL_CLI = "copilot"

VARIABLE_DE_ENTORNO_CLI = "COPILOT_CLI"
"""Permite apuntar a otra instalacion del CLI sin tocar el codigo. En CI la ruta no sera la de una
extension de VS Code, asi que clavarla haria el script inutil justo donde mas se usa."""

VARIABLE_DE_ENTORNO_PROYECTO = "EVALS_PROYECTO"
"""El directorio cuyos artefactos debe descubrir el cliente.

POR ENTORNO Y NO POR ARGUMENTO, y la razon es el contrato con el motor: `exec:` pasa el prompt como
PRIMER argumento. Si este script esperara tambien el proyecto como argumento, el orden dependeria de como
se escribio el `exec:` -- y un despiste ahi manda la consulta como ruta y la ruta como consulta, con un
fallo que parece del artefacto y no lo es. El motor da UN argumento; lo demas viene del entorno.
"""

VARIABLE_DE_ENTORNO_VERBOSE = "EVALS_VERBOSE"
"""Sube el registro a DEBUG.

POR ENTORNO Y NO CON UN FLAG `--verbose`, que es lo que L5 pide para un CLI: el contrato con el motor es
que `exec:` pasa el prompt como PRIMER argumento y nada mas. Anadir un flag propio significaria parsear
argumentos y arriesgarse a confundir una consulta que empiece por guion con una opcion. Se conserva el
espiritu de la regla -- el diagnostico se enciende sin tocar el codigo -- por la unica via que el contrato
deja libre.
"""

_PREFIJO_DEL_INTERPRETE = ["cmd", "/c"] if os.name == "nt" else []
_TIEMPO_LIMITE_S = 180
_MAX_STDERR_REGISTRADO = 400


def ruta_del_cli() -> str:
    """Como invocar el CLI: lo declarado en el entorno, o el nombre a resolver del PATH."""
    return os.getenv(VARIABLE_DE_ENTORNO_CLI) or NOMBRE_DEL_CLI


def _en_una_linea(consulta: str) -> str:
    """La consulta con los saltos de linea colapsados a espacios.

    EL DEFECTO QUE ESTO ARREGLA, medido corriendo una suite real y no leyendo nada: en Windows la orden
    llega al proceso hijo como UNA cadena y `cmd` la parte en el primer salto de linea. Un caso cuya
    consulta ocupaba dos lineas -- «Revisa esta consulta JQL:» y debajo la consulta -- llegaba SOLO con la
    primera, y el modelo respondia «no has incluido la consulta». El caso fallaba, el informe decia que el
    artefacto no cumplia, y el artefacto estaba bien: el defecto era del cable.

    Es el peor tipo de fallo de un arnes de evaluacion, porque acusa al artefacto de algo que hizo la
    herramienta.

    LO QUE SE PIERDE, y hay que decirlo: para una consulta JQL o una peticion en prosa, colapsar saltos es
    inocuo. Para un caso cuya entrada sea un fragmento de codigo con sangrado significativo -- Python,
    YAML -- esto lo altera. Ese caso necesita otra via: montar el insumo como ARCHIVO en el proyecto y
    pedir en la consulta que lo lea, que es ademas como el formato de `skill-creator` modela su campo
    `files`.
    """
    return " ".join(consulta.split())


def construir_orden(consulta: str, raiz_del_proyecto: Path, cli: str) -> list[str]:
    """La orden completa, como LISTA (P10). Pura: se puede comprobar sin ejecutar nada.

    `-C` en vez de cambiar de directorio: el CLI lo soporta, y asi el script se invoca desde donde sea
    sin depender del directorio de trabajo de quien lo llama -- que en promptfoo no es el nuestro --.
    """
    return [
        *_PREFIJO_DEL_INTERPRETE,
        cli,
        "-C", str(raiz_del_proyecto),
        "-p", _en_una_linea(consulta),
        "-s",
        "--allow-all-tools",
        "--no-ask-user",
    ]


def responder(consulta: str, raiz_del_proyecto: Path, *, ejecutar=subprocess.run) -> str:
    """Lo que Copilot responde a `consulta`, con los artefactos del proyecto disponibles.

    `ejecutar` es inyectable con un default sobreescribible (T4): las pruebas sustituyen el lanzador en
    vez de parchear `subprocess`, asi que el cableado esta en la firma y no escondido dentro.
    """
    hecho = ejecutar(construir_orden(consulta, raiz_del_proyecto, ruta_del_cli()),
                     capture_output=True, text=True, encoding="utf-8", errors="replace",
                     timeout=_TIEMPO_LIMITE_S)
    if hecho.returncode != 0:
        # Se REGISTRA y NO se lanza: el motor lee stdout como la respuesta, asi que abortar aqui le
        # quitaria la oportunidad de reportar el caso como fallido con su propio formato y su propio
        # codigo de salida. Un fallo del CLI tiene que llegar al informe, no matar la corrida.
        #
        # ERROR y no WARNING (L3): aborta ESTA operacion -- el caso no va a tener respuesta -- aunque no
        # tumbe el proceso.
        log.error("el CLI salio con %s: %s", hecho.returncode, hecho.stderr[:_MAX_STDERR_REGISTRADO])
    return hecho.stdout


def raiz_del_proyecto() -> Path:
    """El proyecto cuyos artefactos debe ver el cliente, o el directorio actual si no se declara."""
    declarada = os.getenv(VARIABLE_DE_ENTORNO_PROYECTO)
    return Path(declarada) if declarada else Path.cwd()


def _configurar_registro() -> None:
    """Una sola vez y solo aqui (L4). A stderr, porque stdout es la respuesta que el motor consume (L8)."""
    nivel = logging.DEBUG if os.getenv(VARIABLE_DE_ENTORNO_VERBOSE) else logging.INFO
    manejador = logging.StreamHandler(sys.stderr)
    manejador.setFormatter(logging.Formatter("%(levelname)-8s %(name)s — %(message)s"))
    raiz = logging.getLogger()
    raiz.setLevel(nivel)
    raiz.addHandler(manejador)


def main() -> int:
    _configurar_registro()
    if len(sys.argv) < 2:
        log.critical("falta la consulta. Uso: %s \"<consulta>\"; el proyecto se declara en $%s",
                     Path(__file__).name, VARIABLE_DE_ENTORNO_PROYECTO)
        return 2
    consulta = sys.argv[1]
    log.debug("consulta de %d caracteres contra el proyecto %s", len(consulta), raiz_del_proyecto())
    # El UNICO `print` del modulo, y es la salida estructurada que el motor consume (L8).
    print(responder(consulta, raiz_del_proyecto()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
