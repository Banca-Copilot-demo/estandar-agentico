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
from typing import NamedTuple

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

VARIABLE_DE_ENTORNO_AGENTE = "EVALS_AGENTE"
"""El agente concreto a evaluar, o vacio para el agente por defecto del cliente.

QUE CAMBIA SEGUN ESTE VALOR, y es la diferencia entre evaluar un SKILL y evaluar un AGENTE:

  SIN declarar   se lanza el agente por defecto con los artefactos del proyecto disponibles. Es lo que
                 hace falta para un skill o un prompt: se comprueba que el cliente lo DESCUBRA y lo use.
  DECLARADO      se lanza ESE agente (`--agent <nombre>`). El nombre es el del archivo `.agent.md` sin la
                 extension, tal como lo documenta el CLI.

Por entorno y no como argumento, por la misma razon que el proyecto: el contrato con el motor es que el
prompt es el UNICO argumento posicional.
"""

_PREFIJO_DEL_INTERPRETE = ["cmd", "/c"] if os.name == "nt" else []
_TIEMPO_LIMITE_S = 180
_MAX_STDERR_REGISTRADO = 400


def ruta_del_cli() -> str:
    """Como invocar el CLI: lo declarado en el entorno, o el nombre a resolver del PATH."""
    return os.getenv(VARIABLE_DE_ENTORNO_CLI) or NOMBRE_DEL_CLI


def agente_declarado() -> str | None:
    """El agente a evaluar, o `None` para el agente por defecto del cliente."""
    return os.getenv(VARIABLE_DE_ENTORNO_AGENTE) or None


def construir_orden(raiz_del_proyecto: Path, cli: str, agente: str | None = None) -> list[str]:
    """La orden completa, como LISTA (P10). Pura: se puede comprobar sin ejecutar nada.

    SIN `-p`: LA CONSULTA VA POR ENTRADA ESTANDAR, y ese cambio arregla dos defectos de un golpe y abre
    la puerta a lo mas importante:

      1. EL TRUNCADO POR SALTOS DE LINEA. Con `-p <texto>`, en Windows la orden llega al hijo como UNA
         cadena y `cmd` la parte en el primer salto. Un caso de dos lineas llegaba solo con la primera y
         el informe acusaba al ARTEFACTO de un fallo de la HERRAMIENTA. Habia un apano -- colapsar los
         saltos a espacios -- que alteraba cualquier entrada con sangrado significativo. Por stdin no hace
         falta el apano: el texto llega tal cual.
      2. EL LIMITE DE LONGITUD. La linea de comandos de Windows tope unos 8191 caracteres. Un prompt de
         JUEZ lleva la rubrica MAS la salida completa del artefacto, asi que lo pasa con facilidad -- y
         al pasarlo el fallo es cripitco («The system cannot find the file specified»), que parece un
         problema de instalacion y no de tamaño. Un pipe no tiene ese tope.

      3. Y POR ESO EL JUEZ PUEDE CORRER AQUI. Es la unica razon por la que este cable sirve tambien como
         proveedor de puntuacion, o sea que TODO -- artefacto y juez -- cabe en la suscripcion de Copilot
         sin necesitar un segundo proveedor.

    `-C` en vez de cambiar de directorio: el CLI lo soporta, y asi el script se invoca desde donde sea
    sin depender del directorio de trabajo de quien lo llama -- que en promptfoo no es el nuestro --.
    """
    return [
        *_PREFIJO_DEL_INTERPRETE,
        cli,
        "-C", str(raiz_del_proyecto),
        # `--agent` SOLO si se declara: sin el, el cliente usa su agente por defecto y descubre los
        # artefactos del proyecto -- que es justo lo que hay que probar en un skill --. Anadirlo vacio
        # no seria inocuo: el CLI buscaria un agente sin nombre.
        *(["--agent", agente] if agente else []),
        "-s",
        "--allow-all-tools",
        "--no-ask-user",
    ]


class RespuestaDelCliente(NamedTuple):
    """Lo que el CLI devolvio, con el fallo de la HERRAMIENTA separado de la respuesta del ARTEFACTO.

    ES UN `NamedTuple` Y NO UN `@dataclass`, y no es una preferencia de estilo: con `@dataclass` este
    modulo NO SE PUEDE IMPORTAR por la via que usa promptfoo, y eso dejaba TODAS las evaluaciones en
    rojo. MEDIDO y reproducido: el envoltorio del motor carga el script con
    `spec_from_file_location` + `exec_module` y NO lo registra en `sys.modules`; `dataclasses` resuelve
    las anotaciones diferidas -- las que crea `from __future__ import annotations` -- consultando
    `sys.modules.get(cls.__module__).__dict__`, y ahi ese `get` devuelve `None`:

        dataclasses.py:757  ns = sys.modules.get(cls.__module__).__dict__
        AttributeError: 'NoneType' object has no attribute '__dict__'

    El motor lo reporta como `Error running Python script`, asi que los tres casos de la suite fallaban
    ANTES de preguntarle nada al modelo. `NamedTuple` no hace esa resolucion y sobrevive a la carga por
    ruta -- comprobado con el mismo mecanismo --.

    POR QUE NO LO VIERON LAS PRUEBAS: importan el modulo de la forma normal, que SI lo registra en
    `sys.modules`. La unica forma de atraparlo es importarlo como lo hace el motor, y esa es justo la
    prueba de regresion que acompana a este cambio.

    POR QUE UN TIPO Y NO UN `str` (P7, OO1): estas dos cosas se parecen -- ambas son texto -- y son
    exactamente lo contrario la una de la otra. `salida` es material sobre el que el motor puede opinar;
    `fallo` significa que NO HAY material y que cualquier veredicto sobre el artefacto seria inventado.
    Devolviendolas por el mismo canal (un `str`) la distincion se pierde en la firma, y perdida en la
    firma se pierde en el llamador: era exactamente el defecto D1.

    `fallo` es `None` cuando el CLI salio con 0. No se usa `salida` vacia como senal de fallo: una
    respuesta legitimamente vacia existe y significa otra cosa.
    """

    salida: str
    fallo: str | None = None


def _describir_el_fallo(returncode: int, stderr: str) -> str:
    """El motivo, con el codigo de salida y lo que el CLI dijera, acotado.

    EL CODIGO VA SIEMPRE, aunque `stderr` venga vacio -- que es el caso frecuente cuando el CLI muere por
    cuota o por politica --: sin el, el informe diria «el proveedor fallo» y no habria por donde empezar.
    Se acota `stderr` porque un volcado del CLI puede traer miles de caracteres y este texto acaba dentro
    de cada fila del informe.
    """
    motivo = stderr.strip()[:_MAX_STDERR_REGISTRADO]
    return f"el CLI de Copilot salio con codigo {returncode}: {motivo or '(sin stderr)'}"


def responder(consulta: str, raiz_del_proyecto: Path, *, ejecutar=subprocess.run) -> RespuestaDelCliente:
    """Lo que Copilot responde a `consulta`, con los artefactos del proyecto disponibles.

    `ejecutar` es inyectable con un default sobreescribible (T4): las pruebas sustituyen el lanzador en
    vez de parchear `subprocess`, asi que el cableado esta en la firma y no escondido dentro.
    """
    hecho = ejecutar(construir_orden(raiz_del_proyecto, ruta_del_cli(), agente_declarado()),
                     input=consulta,
                     capture_output=True, text=True, encoding="utf-8", errors="replace",
                     timeout=_TIEMPO_LIMITE_S)
    if hecho.returncode != 0:
        # NO SE LANZA -- el motor perderia la corrida entera por un caso -- y tampoco se devuelve el
        # stdout: se devuelve un FALLO, que es cosa distinta y el llamador tiene que poder verlo.
        #
        # ERROR y no WARNING (L3): aborta ESTA operacion -- el caso no va a tener respuesta -- aunque no
        # tumbe el proceso.
        motivo = _describir_el_fallo(hecho.returncode, hecho.stderr)
        log.error("%s", motivo)
        return RespuestaDelCliente(salida="", fallo=motivo)
    return RespuestaDelCliente(salida=hecho.stdout)


def raiz_del_proyecto() -> Path:
    """El proyecto cuyos artefactos debe ver el cliente, o el directorio actual si no se declara."""
    declarada = os.getenv(VARIABLE_DE_ENTORNO_PROYECTO)
    return Path(declarada) if declarada else Path.cwd()


def call_api(prompt: str, options: dict | None = None, context: dict | None = None,
             *, ejecutar=subprocess.run) -> dict:
    """El contrato de PROVEEDOR de promptfoo. El nombre es suyo, no nuestro: lo busca por reflexion.

    POR QUE EXISTE ADEMAS DEL `main()`, y es la pieza que responde a «¿puede el juez correr sobre la
    suscripcion de Copilot?». Con la forma `exec:` promptfoo invoca el script pasando el prompt como
    ARGUMENTO, y eso topa con el limite de la linea de comandos de Windows justo en el caso del juez, cuyo
    prompt lleva la rubrica mas la salida entera del artefacto. Con la forma `file://...py` promptfoo
    llama a esta funcion y el prompt entra como PARAMETRO: sin shell, sin limite y sin truncados.

    UN FALLO DE LA HERRAMIENTA SE DEVUELVE COMO `error`, NUNCA COMO `output`, y esta es la linea que
    separa «el artefacto no cumple» de «no hemos podido preguntar».

    EL CONTRATO, comprobado sobre la version fijada en `VERSION_PROMPTFOO` y no de memoria: el proveedor
    de Python exige un dict con `output` O con `error` -- si no trae ninguno de los dos, revienta con «must
    return a dict with an `output` string/object or `error` string» --, y el motor, al ver `error`, marca
    el resultado con `failureReason = ERROR` en vez de `ASSERT`, no lo cachea y no lo cuenta como fallo de
    asercion. O sea: el informe distingue *el proveedor reviento* de *el artefacto no cumple*.

    EL DEFECTO QUE ARREGLA, y estaba LATENTE -- medido: cero salidas no-cero en 12 corridas de CI --:
    antes se devolvia `{"output": hecho.stdout}` pasara lo que pasara, y con un codigo de salida distinto
    de cero ese stdout viene vacio o a medias. El motor lo evaluaba como si fuera la respuesta del modelo
    y el caso fallaba ACUSANDO AL ARTEFACTO de una caida de la herramienta. Es el mismo patron que ya
    mordio tres veces en 24 horas -- un `head` comiendose un codigo de salida, un `tail` igual, un 403
    leido como «no hay comprobacion» --: un fallo de INFRAESTRUCTURA disfrazado de veredicto sobre el
    ARTEFACTO. El dia que se agote la cuota, esto es lo que evita que el informe diga «el artefacto
    empeoro», que es la conclusion mas cara que se puede sacar de este sistema.

    `ejecutar` es SOLO-PALABRA-CLAVE y con default (T4): promptfoo llama posicionalmente con tres
    argumentos, asi que anadirlo no toca su contrato, y a cambio la traduccion fallo->`error` -- que es
    justo la linea que se arreglo -- se puede comprobar sin lanzar el CLI ni tocar disco (T1).
    """
    del options, context  # Parte del contrato de promptfoo; este proveedor no los necesita.
    respuesta = responder(prompt, raiz_del_proyecto(), ejecutar=ejecutar)
    if respuesta.fallo is not None:
        return {"error": respuesta.fallo}
    return {"output": respuesta.salida}


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
    respuesta = responder(consulta, raiz_del_proyecto())
    if respuesta.fallo is not None:
        # NO SE IMPRIME NADA POR STDOUT: quien invoque este entry point lee stdout como la respuesta, y
        # una salida vacia con codigo 0 seria el mismo engaño que arregla `call_api` -- la herramienta se
        # cae y el consumidor lo lee como que el artefacto no dijo nada --. El codigo de salida es el
        # canal por el que un fallo del CLI se propaga aqui.
        return 1
    # El UNICO `print` del modulo, y es la salida estructurada que el motor consume (L8).
    print(respuesta.salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
