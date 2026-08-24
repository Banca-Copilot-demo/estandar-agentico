"""Pruebas de la exigencia de referencias FIJADAS en el `.mcp.json`.

El ataque que cubren tiene nombre y CVE: *rug pull*, CVE-2025-54136. Un servidor MCP nace de
confianza y despues le cambian la descripcion de una herramienta -- que es una INSTRUCCION para el
modelo --, su esquema de entrada o su endpoint. El protocolo MCP no ofrece ninguna primitiva de
integridad para las definiciones, y ningun cliente avisa cuando cambian.

Lo que se mide aqui es lo unico que se puede exigir en publicacion: que la referencia del servidor no
sea movil.
"""
from __future__ import annotations

from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_mcp import (
    revisar_que_esta_en_un_plugin,
    revisar_servidores,
)

DONDE = "plugins/x/.mcp.json"


def _errores(hallazgos):
    return [h for h in hallazgos if h.bloquea]


def _un_servidor(**configuracion):
    return {"mcpServers": {"catalogo": configuracion}}["mcpServers"]


# ── el caso REAL de la industria, que es el que hay que parar ────────────────────────────────
def test_la_referencia_con_latest_de_los_plugins_de_aws_se_RECHAZA():
    """Medido en los plugins oficiales de AWS instalados en una maquina real: usan exactamente
    `awslabs.aws-iac-mcp-server@latest`. El plugin va firmado y fijado a un commit, pero el servidor
    se descarga en tiempo de ejecucion y cambia sin release, sin revision y sin atestacion."""
    hallazgos = revisar_servidores(DONDE, _un_servidor(
        command="uvx", args=["awslabs.aws-iac-mcp-server@latest"]))
    assert _errores(hallazgos)
    assert "rug pull" in _errores(hallazgos)[0].mensaje


def test_toda_etiqueta_movil_se_rechaza_no_solo_latest():
    # `main` o `stable` fijan tan poco como `latest`, y son igual de habituales.
    for movil in ("latest", "main", "stable", "next", "beta"):
        hallazgos = revisar_servidores(DONDE, _un_servidor(
            command="uvx", args=[f"paquete-mcp@{movil}"]))
        assert _errores(hallazgos), f"no se rechazo la etiqueta movil `{movil}`"


def test_un_rango_de_semver_tampoco_es_una_version_fijada():
    # `^1.2.0` acepta cualquier 1.x posterior: fija un limite, no un contenido.
    for rango in ("^1.2.0", "~1.2.0", ">=1.0.0", "1.x", "*"):
        hallazgos = revisar_servidores(DONDE, _un_servidor(
            command="npx", args=[f"paquete-mcp@{rango}"]))
        assert _errores(hallazgos), f"no se rechazo el rango `{rango}`"


def test_una_referencia_sin_version_se_rechaza():
    hallazgos = revisar_servidores(DONDE, _un_servidor(command="uvx", args=["paquete-mcp"]))
    # Sin `@` no se reconoce como referencia: avisa en vez de bloquear, porque no se puede afirmar
    # que sea un paquete -- podria ser una bandera del lanzador.
    assert hallazgos
    assert not _errores(hallazgos)


# ── lo que NO debe bloquear ─────────────────────────────────────────────────────────────────
def test_una_version_fijada_pasa():
    assert not revisar_servidores(DONDE, _un_servidor(
        command="uvx", args=["ejemplo-catalogo-datos-mcp@0.4.1"]))


def test_una_precompilacion_fijada_tambien_pasa():
    # `1.0.0-rc.1` es una version concreta aunque lleve guion.
    assert not _errores(revisar_servidores(DONDE, _un_servidor(
        command="uvx", args=["paquete-mcp@1.0.0-rc.1"])))


def test_un_paquete_de_npm_con_ambito_pasa():
    """`@ambito/paquete@1.2.3` lleva dos `@` y el primero no separa la version: sin tratarlo aparte,
    un paquete con ambito legitimo se habria rechazado."""
    assert not _errores(revisar_servidores(DONDE, _un_servidor(
        command="npx", args=["@ejemplo/catalogo-mcp@1.2.3"])))


# ── el servidor remoto: no se puede fijar, y se dice ────────────────────────────────────────
def test_un_servidor_remoto_avisa_y_no_bloquea():
    """Un `http` no tiene version que fijar: su contenido puede cambiar en cualquier momento y no hay
    nada que comprobar en publicacion. Bloquearlo impediria usar servidores remotos legitimos;
    callarse daria a entender que esta gobernado. Avisa y nombra la unica defensa que queda."""
    hallazgos = revisar_servidores(DONDE, _un_servidor(
        type="http", url="https://knowledge-mcp.global.api.aws"))
    assert hallazgos
    assert not _errores(hallazgos)
    assert "digest de sus herramientas" in hallazgos[0].mensaje


# ── el archivo mal formado ──────────────────────────────────────────────────────────────────
def test_un_mcp_json_sin_mcpServers_es_error():
    # No le sirve a ningun cliente, asi que no es un `mcp` a medias: es un archivo inutil.
    for vacio in (None, {}, [], "texto"):
        assert _errores(revisar_servidores(DONDE, vacio)), f"no se detecto {vacio!r}"


# ── un `mcp` va SIEMPRE dentro de un plugin ─────────────────────────────────────────────────
def test_un_mcp_sin_plugin_es_ERROR():
    """Tecnicamente funciona suelto -- se comprobo: gate limpio, sello y ficha -- y se prohibe igual.

    Dos razones, y la segunda es la que decide: sin plugin no hay `enabledPlugins`, que es lo unico que
    apaga un servidor en todas las maquinas sin tocarlas; y con `strictPluginOnlyCustomization` -- un
    ajuste de empresa documentado, con `mcp` en la lista -- un servidor fuera de un plugin NO CARGA.
    Publicarlo seria sellar y catalogar algo que parece instalado y no esta.
    """
    hallazgos = revisar_que_esta_en_un_plugin(".mcp.json", hay_manifiesto=False)

    assert [h.severidad for h in hallazgos] == [Severidad.ERROR]
    assert "dentro de un PLUGIN" in hallazgos[0].mensaje


def test_un_mcp_dentro_de_un_plugin_no_produce_hallazgo():
    assert revisar_que_esta_en_un_plugin(".mcp.json", hay_manifiesto=True) == []


def test_el_mensaje_dice_QUE_hacer_y_la_convencion_medida():
    # Un error que solo prohibe obliga a adivinar. Este dice donde moverlo y cuantos servidores poner,
    # que es el dato que medimos: 18 de 18 archivos dentro de `plugins/` llevan un solo servidor.
    mensaje = revisar_que_esta_en_un_plugin(".mcp.json", hay_manifiesto=False)[0].mensaje

    assert "Muevelo a un plugin" in mensaje
    assert "UN servidor por plugin" in mensaje
