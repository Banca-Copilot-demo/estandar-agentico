"""Pruebas del gobierno del `mcp` indexado por el NOMBRE del servidor.

QUE MIDEN. El bloque `mcp` del `GOVERNANCE.json` dejo de ser una lista posicional y pasa a ser un
objeto cuyas claves son los nombres de `mcpServers`. Ese cambio no es de estilo: es lo que permite
EMPAREJAR cada aprobacion con la entrada exacta de la configuracion, y con ello ver dos derivas que
la lista dejaba pasar en verde.

  - un servidor CONFIGURADO Y NO APROBADO -- se ejecuta, sale por la red, nadie lo reviso;
  - una APROBACION QUE SOBREVIVE a un servidor que ya no esta -- el aprobador cree que reviso lo que
    se ejecuta, y quien anada despues un servidor con ese nombre lo encontrara «ya aprobado».

Y la tercera pieza: `credentials` paso de una AFIRMACION -- `{"mechanism": "none"}`, que el gate no
podia contrastar contra nada -- a una lista VERIFICABLE contra los `${VAR}` reales del `.mcp.json`.

Cada prueba nombra el DEFECTO que cubre (T2), no la funcion que llama.
"""
from __future__ import annotations

from validador_agentico.dominio import gobierno_mcp
from validador_agentico.dominio.reglas_credenciales import revisar_credenciales_declaradas
from validador_agentico.dominio.reglas_mcp import (
    revisar_aprobacion_por_servidor,
    revisar_forma_del_bloque,
)

DONDE = "plugins/x/.mcp.json"

_APROBACION = {"approved_by": "squad-seguridad", "date": "2026-08-23",
               "review_by": "2027-08-23", "security_review": True}


def _errores(hallazgos):
    return [h for h in hallazgos if h.bloquea]


def _mensajes(hallazgos):
    return " || ".join(h.mensaje for h in hallazgos)


def _configuracion(**servidores):
    return {"mcpServers": servidores}


def _remoto(url="https://knowledge-mcp.global.api.aws", **extra):
    return {"type": "http", "url": url, **extra}


def _gobierno(**servidores):
    return gobierno_mcp.leer(servidores)


# ── deriva 1: se ejecuta lo que nadie aprobo ─────────────────────────────────────────────────
def test_un_servidor_configurado_y_sin_aprobacion_es_error():
    gobierno = _gobierno(**{"aws-knowledge": {"write_operations": False,
                                              "approval": _APROBACION}})
    errores = _errores(revisar_aprobacion_por_servidor(
        DONDE, _configuracion(**{"aws-knowledge": _remoto(), "interno": _remoto("https://interno")}),
        gobierno))
    assert "`interno`" in _mensajes(errores)
    assert "no lo aprueba" in _mensajes(errores)


# ── deriva 2: la aprobacion sobrevive a su servidor ──────────────────────────────────────────
def test_una_aprobacion_que_sobrevive_a_su_servidor_es_error():
    gobierno = _gobierno(**{"catalogo-viejo": {"write_operations": False,
                                               "approval": _APROBACION}})
    # El servidor se fue del `.mcp.json` y su aprobacion se quedo. Se mide sin anadir otro para que
    # el fallo senale UNA sola causa (T5): con un renombrado saltarian las dos derivas a la vez y no
    # se sabria cual de las dos comprobaciones esta viva.
    errores = _errores(revisar_aprobacion_por_servidor(DONDE, _configuracion(), gobierno))
    assert "catalogo-viejo" in _mensajes(errores)
    assert "sobrevivio al servidor" in _mensajes(errores)


def test_gobierno_y_configuracion_emparejados_no_producen_hallazgos():
    gobierno = _gobierno(**{"aws-knowledge": {"write_operations": False,
                                              "approval": _APROBACION}})
    assert revisar_aprobacion_por_servidor(
        DONDE, _configuracion(**{"aws-knowledge": _remoto()}), gobierno) == []


# ── transicion: la forma antigua avisa, nunca bloquea ────────────────────────────────────────
def test_la_lista_posicional_avisa_y_no_bloquea_el_pull_request_que_la_migra():
    # Es la condicion que hace desplegable el cambio. El gate es comprobacion REQUERIDA: si la forma
    # antigua bloqueara, todos los repositorios de dominio se pondrian rojos a la vez y ninguno podria
    # mergear NI SIQUIERA el PR que viene a migrarla. Ya paso al retirar `status`.
    gobierno = gobierno_mcp.leer({
        "servers": [{"name": "aws-knowledge", "transport": "http",
                     "endpoint": "https://knowledge-mcp.global.api.aws",
                     "source": {"kind": "remote", "ref": "https://knowledge-mcp.global.api.aws",
                                "version_pin": "sin-version"}}],
        "credentials": {"mechanism": "none"},
        "approval": _APROBACION,
    })
    hallazgos = revisar_forma_del_bloque(gobierno)
    assert _errores(hallazgos) == []
    assert "mcp.servers" in _mensajes(hallazgos)
    # El aviso nombra los campos que hay que borrar: sin eso, «migra el bloque» obliga a comparar dos
    # esquemas a mano, y lo que cuesta se pospone.
    for campo in ("source", "transport", "endpoint", "version_pin"):
        assert campo in _mensajes(hallazgos), campo


def test_el_emparejamiento_por_nombre_no_se_aplica_a_la_forma_antigua():
    # La lista posicional no indexa por nombre, asi que exigirle el emparejamiento produciria un error
    # en CADA repositorio sin migrar -- justo el bloqueo que la transicion existe para evitar.
    gobierno = gobierno_mcp.leer({"servers": [{"name": "otro"}], "approval": _APROBACION})
    assert revisar_aprobacion_por_servidor(
        DONDE, _configuracion(**{"aws-knowledge": _remoto()}), gobierno) == []


def test_un_bloque_a_medias_sin_servers_se_lee_como_forma_antigua():
    # MEDIDO al pasar la suite: `{"credentials": {...}}` sin `servers` -- un caso real a mitad de
    # migracion -- caia en la rama nueva y `credentials` se interpretaba como un SERVIDOR llamado
    # «credentials». El gate reclamaba la aprobacion de un servidor inexistente y dejaba de aplicar la
    # regla de custodia, que es justo la que ese bloque venia a satisfacer.
    gobierno = gobierno_mcp.leer({"credentials": {"mechanism": "oauth"}})
    assert gobierno.forma_antigua
    assert gobierno.servidores == {}


# ── credenciales: de afirmacion a comprobacion ───────────────────────────────────────────────
def test_declarar_cero_credenciales_y_traer_un_authorization_es_error():
    # EL DEFECTO QUE CIERRA. Con `{"mechanism": "none"}` el gobierno AFIRMABA que no habia credencial
    # y no habia nada contra que contrastarlo, asi que un servidor con `Authorization: ${API_TOKEN}`
    # salia CONFORME. Ese es justo el caso en que alguien aprueba «un servidor publico sin credencial»
    # y lo que se instala pide un token del banco.
    gobierno = _gobierno(**{"aws": {"write_operations": False, "credentials": [],
                                    "approval": _APROBACION}})
    servidores = {"aws": _remoto(headers={"Authorization": "Bearer ${API_TOKEN}"})}
    errores = _errores(revisar_credenciales_declaradas("GOVERNANCE.json", gobierno, servidores))
    assert "API_TOKEN" in _mensajes(errores)


def test_declarar_como_entorno_lo_que_viaja_en_una_cabecera_es_error():
    # No es un matiz de nomenclatura: una cabecera SALE POR LA RED al servidor del tercero y una
    # variable de entorno se queda en el proceso. Quien aprueba esta valorando otra cosa.
    gobierno = _gobierno(**{"aws": {
        "write_operations": False,
        "credentials": [{"name": "API_TOKEN", "kind": "env",
                         "is_secret": True, "is_required": True}],
        "approval": _APROBACION}})
    servidores = {"aws": _remoto(headers={"Authorization": "Bearer ${API_TOKEN}"})}
    errores = _errores(revisar_credenciales_declaradas("GOVERNANCE.json", gobierno, servidores))
    assert "header" in _mensajes(errores)


def test_una_credencial_declarada_y_no_usada_avisa_y_no_bloquea():
    # Sobra permiso declarado, que es higiene, no una via de acceso abierta. Y hay un caso legitimo --
    # el servidor la pide por su cuenta al arrancar --, asi que convertirlo en error obligaria a
    # mentir en el gobierno para pasar el gate.
    gobierno = _gobierno(**{"aws": {
        "write_operations": False,
        "credentials": [{"name": "TOKEN_QUE_NADIE_USA", "kind": "env",
                         "is_secret": False, "is_required": False}],
        "approval": _APROBACION}})
    hallazgos = revisar_credenciales_declaradas("GOVERNANCE.json", gobierno, {"aws": _remoto()})
    assert _errores(hallazgos) == []
    assert "TOKEN_QUE_NADIE_USA" in _mensajes(hallazgos)


def test_una_ruta_del_cliente_no_es_una_credencial():
    # `${CLAUDE_PLUGIN_ROOT}` es una RUTA que el cliente sustituye. Tratarla como credencial daria un
    # error por cada servidor bien escrito, y un gate que se equivoca en el caso normal se desactiva.
    gobierno = _gobierno(**{"local": {"write_operations": False, "credentials": [],
                                      "approval": _APROBACION}})
    servidores = {"local": {"command": "node", "args": ["s.js"],
                            "env": {"DATA": "${CLAUDE_PLUGIN_ROOT}/data"}}}
    assert revisar_credenciales_declaradas("GOVERNANCE.json", gobierno, servidores) == []


def test_una_credencial_declarada_y_usada_no_produce_hallazgos():
    gobierno = _gobierno(**{"aws": {
        "write_operations": False,
        "credentials": [{"name": "API_TOKEN", "kind": "header",
                         "is_secret": True, "is_required": True,
                         "ownership": {"credential_owner": "squad-plataforma",
                                       "access_request_url": "https://ejemplo.dev/pedir"}}],
        "approval": _APROBACION}})
    servidores = {"aws": _remoto(headers={"Authorization": "Bearer ${API_TOKEN}"})}
    assert revisar_credenciales_declaradas("GOVERNANCE.json", gobierno, servidores) == []
