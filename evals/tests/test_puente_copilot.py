"""El proveedor de Copilot: que construya la orden correcta y que degrade sin matar la corrida.

QUE SE PRUEBA Y QUE NO. Aqui NO se lanza el CLI: eso consume cuota de inferencia, tarda ~45 segundos por
caso y depende de una sesion autenticada, asi que no puede ser una prueba de CI. Lo que se prueba es lo
unico que este componente decide por si mismo -- la orden que construye y como reacciona a un fallo --,
que es tambien donde estan los dos defectos que aparecieron al montarlo.

El doble se INYECTA por la firma (T4) en vez de parchear `subprocess`: si el cableado se puede sustituir
desde fuera, la prueba no necesita conocer las tripas del modulo.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from puente_copilot import (
    VARIABLE_DE_ENTORNO_AGENTE,
    VARIABLE_DE_ENTORNO_CLI,
    VARIABLE_DE_ENTORNO_PROYECTO,
    agente_declarado,
    construir_orden,
    raiz_del_proyecto,
    call_api,
    responder,
    ruta_del_cli,
)

_RAIZ = Path("C:/proyecto/demo") if os.name == "nt" else Path("/proyecto/demo")
_CLI = "copilot-de-prueba"


@dataclass
class _Ejecucion:
    """Lo que `subprocess.run` devuelve, reducido a lo que el puente mira."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class _LanzadorFalso:
    """Registra la orden recibida y devuelve lo que se le diga. Sustituye a `subprocess.run`."""

    def __init__(self, resultado: _Ejecucion) -> None:
        self.resultado = resultado
        self.orden: list[str] | None = None
        self.entrada: str | None = None

    def __call__(self, orden, **kwargs):
        self.orden = orden
        # La consulta viaja por ENTRADA ESTANDAR, no en la orden: se registra para poder comprobarla.
        self.entrada = kwargs.get("input")
        return self.resultado


# ── la orden ────────────────────────────────────────────────────────────────────────────────
def test_la_consulta_NO_va_en_la_orden_sino_por_entrada_estandar():
    """La orden no debe contener `-p` ni la consulta. Dos razones medidas, y la segunda es la que decide
    si el JUEZ puede correr sobre la suscripcion de Copilot:

      - la linea de comandos de Windows tope unos 8191 caracteres, y un prompt de juez -- rubrica MAS la
        salida completa del artefacto -- lo pasa con facilidad. Al pasarlo, el fallo es cripitco («The
        system cannot find the file specified»), que parece un problema de instalacion y no de tamaño;
      - `cmd` parte la orden en el primer salto de linea.

    Un pipe no tiene ninguno de los dos problemas.
    """
    orden = construir_orden(_RAIZ, _CLI)

    assert "-p" not in orden, "la consulta no va como argumento: va por stdin"


def test_una_consulta_de_VARIAS_LINEAS_llega_INTACTA():
    """REGRESION del defecto mas caro que aparecio montando esto, y aparecio corriendo una suite real.

    Con `-p <texto>`, en Windows la orden llega al hijo como UNA cadena y `cmd` la parte en el primer
    salto de linea: un caso de dos lineas llegaba solo con la primera, el modelo respondia «no has
    incluido la consulta», y el informe acusaba al ARTEFACTO de un fallo de la HERRAMIENTA.

    Hubo un apano intermedio -- colapsar los saltos a espacios -- que funcionaba pero alteraba cualquier
    entrada con sangrado significativo (codigo, YAML). Por stdin no hace falta: el texto llega TAL CUAL,
    y esta prueba lo fija comprobando que el salto de linea SOBREVIVE.
    """
    consulta = 'Revisa esta consulta JQL:\nproject = PAGOS AND summary ~ "*pago"'
    lanzador = _LanzadorFalso(_Ejecucion(stdout="ok"))

    responder(consulta, _RAIZ, ejecutar=lanzador)

    assert lanzador.entrada == consulta, "la consulta tiene que llegar sin alterar, saltos incluidos"
    assert "\n" in lanzador.entrada, "el salto de linea ya no se colapsa"


@pytest.mark.parametrize("bandera", ["-s", "--allow-all-tools", "--no-ask-user"])
def test_las_banderas_del_modo_no_interactivo_estan(bandera):
    """`--allow-all-tools` no es comodidad: la ayuda del CLI dice que es REQUERIDO en modo no
    interactivo. Sin `--no-ask-user` el agente puede quedarse esperando a una persona que no existe, y
    sin `-s` la salida trae estadisticas que el motor leeria como parte de la respuesta."""
    assert bandera in construir_orden(_RAIZ, _CLI)


def test_el_directorio_del_proyecto_se_pasa_con_C_y_no_se_cambia_de_directorio():
    """El motor invoca este script desde SU directorio de trabajo, no desde el del artefacto. Si el
    proyecto no se pasara explicitamente, el CLI buscaria los artefactos donde no estan y todos los
    casos fallarian por una razon que no tiene nada que ver con el artefacto."""
    orden = construir_orden(_RAIZ, _CLI)

    assert "-C" in orden
    assert orden[orden.index("-C") + 1] == str(_RAIZ)


# ── el agente ───────────────────────────────────────────────────────────────────────────────
def test_sin_agente_declarado_NO_se_pasa_la_bandera():
    """Sin `--agent`, el cliente usa su agente por defecto y DESCUBRE los artefactos del proyecto, que
    es justo lo que hay que probar en un skill: no solo que el modelo obedezca un texto, sino que el
    cliente lo encuentre y decida usarlo.

    Y pasar la bandera vacia no seria inocuo: el CLI buscaria un agente sin nombre.
    """
    orden = construir_orden(_RAIZ, _CLI, agente=None)

    assert "--agent" not in orden


def test_con_agente_declarado_se_lanza_ESE_agente():
    orden = construir_orden(_RAIZ, _CLI, agente="demo.sdlc.revisor")

    assert orden[orden.index("--agent") + 1] == "demo.sdlc.revisor"


def test_el_agente_se_declara_por_entorno(monkeypatch):
    monkeypatch.setenv(VARIABLE_DE_ENTORNO_AGENTE, "demo.sdlc.revisor")

    assert agente_declarado() == "demo.sdlc.revisor"


def test_una_variable_de_agente_VACIA_equivale_a_no_declararla(monkeypatch):
    """Un valor vacio es lo que deja una variable declarada sin contenido -- pasa en CI con frecuencia --
    y tiene que comportarse como su ausencia, no producir `--agent ''`."""
    monkeypatch.setenv(VARIABLE_DE_ENTORNO_AGENTE, "")

    assert agente_declarado() is None


# ── la ruta del CLI ─────────────────────────────────────────────────────────────────────────
def test_el_cli_se_puede_declarar_por_entorno(monkeypatch):
    """En CI el CLI puede no estar en el PATH o llamarse de otra forma; declararlo tiene que ser posible
    sin tocar el codigo.

    (Aqui `monkeypatch` SI es lo correcto: lo que se sustituye es una variable de ENTORNO, no el
    cableado del modulo. T4 prohibe parchear la implementacion, no el entorno del proceso.)
    """
    monkeypatch.setenv(VARIABLE_DE_ENTORNO_CLI, _CLI)

    assert ruta_del_cli() == _CLI


def test_sin_declarar_se_resuelve_POR_NOMBRE_y_no_por_una_ruta_clavada(monkeypatch):
    """REGRESION de un defecto medido: la primera version apuntaba al `copilot.bat` de la extension de
    VS Code, que NO es el CLI sino un shim que lo busca en el PATH. Cuando el binario real no estaba,
    imprimia «Cannot find GitHub Copilot CLI» por STDOUT -- y el motor lo recibia como si fuera la
    respuesta del modelo, fallando el caso por una razon que no tenia nada que ver con el artefacto.

    Ademas una ruta dentro de una extension de VS Code no existe en CI y cambia al actualizarse.
    """
    monkeypatch.delenv(VARIABLE_DE_ENTORNO_CLI, raising=False)

    resuelto = ruta_del_cli()

    assert resuelto == "copilot"
    assert "AppData" not in resuelto, "no debe haber una ruta de instalacion clavada"


def test_el_proyecto_se_declara_por_entorno_no_por_argumento(monkeypatch):
    """EL DEFECTO QUE EVITA: el motor pasa el prompt como PRIMER argumento y eso no es negociable. Si el
    script esperara tambien el proyecto por argumento, el orden dependeria de como se escribio el `exec:`
    -- y un despiste manda la consulta como ruta y la ruta como consulta, produciendo un fallo que parece
    del artefacto y no lo es. El motor da UN argumento; lo demas viene del entorno."""
    monkeypatch.setenv(VARIABLE_DE_ENTORNO_PROYECTO, str(_RAIZ))

    assert raiz_del_proyecto() == _RAIZ


def test_sin_proyecto_declarado_se_usa_el_directorio_actual(monkeypatch):
    monkeypatch.delenv(VARIABLE_DE_ENTORNO_PROYECTO, raising=False)

    assert raiz_del_proyecto() == Path.cwd()


# ── la degradacion ──────────────────────────────────────────────────────────────────────────
def test_devuelve_la_respuesta_tal_cual():
    lanzador = _LanzadorFalso(_Ejecucion(stdout="HOLA-BCP-OK-7Q4\n"))

    respuesta = responder("x", _RAIZ, ejecutar=lanzador)

    assert respuesta.salida == "HOLA-BCP-OK-7Q4\n"
    assert respuesta.fallo is None, "salir con 0 no es un fallo, ni siquiera uno vacio"


def test_un_fallo_del_CLI_no_mata_la_corrida(caplog):
    """EL DEFECTO QUE ESTA PRUEBA FIJA: si el puente lanzara al fallar el CLI, el motor perderia la
    oportunidad de reportar el caso con su propio formato y su propio codigo de salida -- y una corrida
    de veinte casos moriria por el primero que tuviera un problema de red.

    El fallo tiene que llegar al informe, no llevarse por delante la ejecucion.
    """
    lanzador = _LanzadorFalso(_Ejecucion(returncode=1, stdout="", stderr="no autenticado"))

    with caplog.at_level(logging.ERROR):
        respuesta = responder("x", _RAIZ, ejecutar=lanzador)

    assert respuesta.fallo is not None, "el fallo tiene que viajar, no perderse"
    # `caplog` y no `capsys`: el motivo va por el sistema de registro (L1), no por un print a stderr.
    assert "no autenticado" in caplog.text, "el motivo real tiene que quedar en el log"


# ── D1: un fallo de la HERRAMIENTA no puede leerse como veredicto sobre el ARTEFACTO ────────
def test_un_codigo_de_salida_no_cero_se_reporta_como_error_del_proveedor_y_NO_como_respuesta():
    """REGRESION DE D1, el defecto mas caro que quedaba LATENTE en esta cadena.

    ESTABA ASI: con `returncode != 0` el puente solo registraba el motivo y devolvia `hecho.stdout`
    igualmente -- vacio o a medias --, y `call_api` se lo entregaba a promptfoo como `{"output": ...}`,
    o sea como si fuera la respuesta del modelo. El motor lo evaluaba contra la rubrica y el caso fallaba
    ACUSANDO AL ARTEFACTO de una caida de la herramienta.

    MEDIDO que hoy no se dispara -- cero salidas no-cero en 12 corridas de CI --, y esa es exactamente la
    razon de fijarlo con una prueba: el dia que se agote la cuota de inferencia el informe diria «el
    artefacto empeoro», que es la conclusion mas cara que se puede sacar de este sistema. Es el mismo
    patron que ya mordio tres veces en 24 horas (un `head` comiendose un codigo de salida, un `tail`
    igual, un 403 leido como «no hay comprobacion»).

    EL CONTRATO QUE SE APOYA, comprobado sobre la version fijada en `VERSION_PROMPTFOO` (0.118.16) y no
    de memoria: el proveedor de Python acepta un dict con `output` O con `error`, y con `error` el motor
    marca `failureReason = ERROR` -- Error, no Failure --, o sea que el caso NO cuenta como que el
    artefacto incumplio.
    """
    lanzador = _LanzadorFalso(_Ejecucion(returncode=7, stdout="respuesta a medi", stderr="quota exceeded"))

    devuelto = call_api("da igual el prompt", ejecutar=lanzador)

    assert "output" not in devuelto, (
        "un stdout truncado por una caida del CLI NO es la respuesta del modelo: entregarlo como "
        "`output` hace que la rubrica juzgue al artefacto por un fallo de la herramienta"
    )
    assert "error" in devuelto, "con `error` el motor lo cuenta como Error del proveedor, no como fallo del artefacto"


def test_el_error_del_proveedor_NOMBRA_el_codigo_de_salida_y_lo_que_dijo_el_CLI():
    """Un `error` que solo dijera «el proveedor fallo» deja al que lee el informe sin por donde empezar,
    que es la mitad del daño del defecto original. El codigo de salida y el stderr son lo unico que
    distingue una cuota agotada de un token sin permisos o de un CLI sin instalar."""
    lanzador = _LanzadorFalso(_Ejecucion(returncode=7, stderr="Access denied by policy settings"))

    motivo = call_api("x", ejecutar=lanzador)["error"]

    assert "7" in motivo, "sin el codigo de salida no se sabe con que murio"
    assert "Access denied by policy settings" in motivo, "el motivo del CLI es la pista real"


def test_el_stderr_del_error_se_ACOTA_para_no_inundar_cada_fila_del_informe():
    """Un volcado del CLI puede traer miles de caracteres y este texto acaba dentro de cada fila del
    informe JSON que ahora se conserva; sin tope, el artefacto util queda sepultado."""
    lanzador = _LanzadorFalso(_Ejecucion(returncode=1, stderr="x" * 10_000))

    assert len(call_api("x", ejecutar=lanzador)["error"]) < 1_000


def test_un_stderr_VACIO_sigue_produciendo_un_error_con_el_codigo():
    """El caso frecuente cuando el CLI muere por politica o por cuota es salir sin decir nada por stderr.
    Si eso produjera un `error` vacio, promptfoo lo trataria como ausencia de error -- comprobado en el
    proveedor de Python de la version fijada: cachea y no marca ERROR salvo que `error` sea no vacio --
    y volveriamos al defecto por la puerta de atras."""
    lanzador = _LanzadorFalso(_Ejecucion(returncode=1, stderr=""))

    motivo = call_api("x", ejecutar=lanzador)["error"]

    assert motivo, "un error vacio equivale a no haberlo reportado"
    assert "1" in motivo


def test_una_respuesta_correcta_sigue_llegando_como_output():
    """La contraparte: arreglar D1 no puede convertir las corridas sanas en errores. Sin esta, un
    `call_api` que devolviera `error` siempre pasaria la prueba de arriba y romperia todo lo demas."""
    lanzador = _LanzadorFalso(_Ejecucion(returncode=0, stdout="el veredicto del artefacto"))

    devuelto = call_api("x", ejecutar=lanzador)

    assert devuelto == {"output": "el veredicto del artefacto"}


def test_la_orden_llega_completa_al_lanzador():
    """Cierra el circulo: que lo que se construye sea lo que se ejecuta. Sin esto, `construir_orden`
    podria estar perfecta y `responder` llamar a otra cosa."""
    lanzador = _LanzadorFalso(_Ejecucion(stdout="ok"))

    responder("la consulta", _RAIZ, ejecutar=lanzador)

    assert lanzador.entrada == "la consulta", "la consulta llega por stdin"
    assert "-C" in lanzador.orden, "y el proyecto en la orden"
