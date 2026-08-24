"""El gobierno declara EXACTAMENTE los servidores que la configuracion ejecuta.

EL DEFECTO QUE CIERRA, medido. Un servidor presente en el `.mcp.json` y ausente del `GOVERNANCE.json`
pasaba en verde si estaba fijado. Se probo con un gobierno que declaraba un servidor de documentacion
de solo lectura y una configuracion que ademas traia uno apuntando a un host interno de produccion:
veredicto CONFORME, y el segundo no aparecia en ningun hallazgo. La aprobacion cubria un subconjunto de
lo que se ejecuta.

Y POR QUE NO SE COTEJA POR EL NOMBRE. La documentacion de la plataforma es explicita: «un `serverName`
NO ES UN CONTROL DE SEGURIDAD. El nombre es la etiqueta que asigna el usuario, no el servidor
subyacente, asi que un usuario puede llamar `github` a cualquier servidor». Sus propios allowlists
emparejan por `serverUrl` o `serverCommand`.
"""
from __future__ import annotations

import pytest

from validador_agentico.dominio.declaracion_mcp import (
    cotejar,
    identidad_configurada,
    identidad_declarada,
)
from validador_agentico.dominio.hallazgo import Severidad
from validador_agentico.dominio.reglas_mcp import revisar_declaracion

# Las formas REALES de nuestro `catalogo-datos`: un `stdio` con paquete fijado y un remoto.
_CONFIG_STDIO = {"type": "stdio", "command": "uvx", "args": ["ejemplo-catalogo-datos-mcp@0.4.1"]}
_DECLARADO_STDIO = {"name": "catalogo-datos", "transport": "stdio", "write_operations": False,
                    "source": {"kind": "pypi", "ref": "ejemplo-catalogo-datos-mcp",
                               "version_pin": "0.4.1"}}
_CONFIG_REMOTO = {"type": "http", "url": "https://knowledge-mcp.global.api.aws"}
_DECLARADO_REMOTO = {"name": "aws-knowledge", "transport": "http",
                     "endpoint": "https://knowledge-mcp.global.api.aws",
                     "write_operations": False,
                     "source": {"kind": "remote", "ref": "https://knowledge-mcp.global.api.aws",
                                "version_pin": "sin-version"}}


def _mensajes(hallazgos) -> str:
    return " | ".join(h.mensaje for h in hallazgos)


# ── la identidad: lo que se ejecuta, no como se llama ───────────────────────────────────────
def test_un_stdio_se_identifica_por_su_paquete_con_version():
    assert identidad_configurada(_CONFIG_STDIO) == "ejemplo-catalogo-datos-mcp@0.4.1"
    assert identidad_declarada(_DECLARADO_STDIO) == "ejemplo-catalogo-datos-mcp@0.4.1"


def test_un_remoto_se_identifica_por_su_url():
    assert identidad_configurada(_CONFIG_REMOTO) == "https://knowledge-mcp.global.api.aws"
    assert identidad_declarada(_DECLARADO_REMOTO) == "https://knowledge-mcp.global.api.aws"


def test_las_formas_REALES_de_catalogo_datos_cotejan_sin_hallazgos():
    """Copiadas tal cual del repositorio: si el emparejamiento se rompe, esta prueba lo dice antes de
    que el gate bloquee un artefacto que siempre fue correcto."""
    sin_declarar, sin_configurar = cotejar(
        {"catalogo-datos": _CONFIG_STDIO, "aws-knowledge": _CONFIG_REMOTO},
        [_DECLARADO_STDIO, _DECLARADO_REMOTO])

    assert (sin_declarar, sin_configurar) == ((), ())


@pytest.mark.parametrize("una,otra", [
    ("https://x.dev/mcp", "https://x.dev/mcp/"),
    ("https://X.DEV/mcp", "https://x.dev/mcp"),
    ("  https://x.dev/mcp  ", "https://x.dev/mcp"),
])
def test_urls_equivalentes_no_producen_una_discrepancia_falsa(una, otra):
    # Sin normalizar, una barra final o una mayuscula en el host bloquearia un artefacto correcto. La
    # plataforma documenta que el host es insensible a mayusculas.
    assert (identidad_configurada({"url": una})
            == identidad_configurada({"url": otra}))


def test_la_RUTA_si_distingue_dos_servidores():
    """La plataforma dice que «las rutas siguen siendo sensibles a mayusculas». Dos rutas distintas son
    dos servidores, y tratarlas como una dejaria pasar uno sin aprobar."""
    assert (identidad_configurada({"url": "https://x.dev/Mcp"})
            != identidad_configurada({"url": "https://x.dev/mcp"}))


# ── el cotejo en las dos direcciones ────────────────────────────────────────────────────────
def test_un_servidor_CONFIGURADO_y_no_declarado_es_ERROR():
    # EL CASO MEDIDO: el gobierno declara el de documentacion y la configuracion trae ademas uno
    # apuntando a produccion. Antes: CONFORME y sin mencionarlo.
    hallazgos = revisar_declaracion(
        ".mcp.json",
        {"docs": {"type": "http", "url": "https://docs.ejemplo.dev/mcp"},
         "produccion": {"type": "http", "url": "https://prod-interno.bcp.com.pe/mcp"}},
        [{"name": "docs", "transport": "http", "endpoint": "https://docs.ejemplo.dev/mcp",
          "source": {"kind": "remote", "ref": "https://docs.ejemplo.dev/mcp",
                     "version_pin": "sin-version"}}])

    assert [h.severidad for h in hallazgos] == [Severidad.ERROR]
    assert "prod-interno.bcp.com.pe" in _mensajes(hallazgos)


def test_un_servidor_DECLARADO_y_no_configurado_tambien_es_ERROR():
    """La aprobacion cubre un fantasma. Suele ser un renombrado a medias, y deja al aprobador creyendo
    que reviso lo que se ejecuta."""
    hallazgos = revisar_declaracion(
        ".mcp.json", {"docs": _CONFIG_REMOTO}, [_DECLARADO_REMOTO, _DECLARADO_STDIO])

    assert [h.severidad for h in hallazgos] == [Severidad.ERROR]
    assert "NO tiene" in _mensajes(hallazgos)


def test_el_nombre_NO_hace_que_coincidan():
    """El corazon de la regla: dos servidores con el mismo nombre y distinta URL son dos servidores.
    Si el cotejo fuera por nombre, esto pasaria en verde -- y es exactamente el escenario que la
    plataforma describe: «un usuario puede llamar `github` a cualquier servidor»."""
    hallazgos = revisar_declaracion(
        ".mcp.json",
        {"github": {"type": "http", "url": "https://impostor.ejemplo.dev/mcp"}},
        [{"name": "github", "transport": "http", "endpoint": "https://api.githubcopilot.com/mcp",
          "source": {"kind": "remote", "ref": "https://api.githubcopilot.com/mcp",
                     "version_pin": "sin-version"}}])

    assert len(hallazgos) == 2, "el impostor no esta declarado, y el declarado no esta configurado"
    assert "impostor" in _mensajes(hallazgos)


def test_cambiar_la_VERSION_de_un_stdio_lo_convierte_en_otro_servidor():
    # Es lo que hace util fijar la version: `paquete@0.4.1` y `paquete@0.5.0` son codigo distinto, y la
    # aprobacion del primero no cubre al segundo.
    hallazgos = revisar_declaracion(
        ".mcp.json",
        {"catalogo": {"command": "uvx", "args": ["ejemplo-catalogo-datos-mcp@0.5.0"]}},
        [_DECLARADO_STDIO])

    assert hallazgos, "una version distinta tiene que romper el cotejo"
    assert "0.5.0" in _mensajes(hallazgos)


# ── no inventar discrepancias ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("declarados", [None, "texto", 42, {}])
def test_sin_bloque_de_gobierno_no_se_inventa_una_discrepancia(declarados):
    """Que falte el gobierno del `mcp` ya lo dice otra regla. Añadir aqui un error por lo mismo daria
    dos hallazgos por un solo hecho."""
    assert revisar_declaracion(".mcp.json", {"x": _CONFIG_REMOTO}, declarados) == []


def test_un_servidor_cuya_referencia_no_se_reconoce_no_se_declara_ausente():
    """No se puede afirmar que algo no este declarado si no se sabe QUE es. La regla de fijado ya avisa
    de que su referencia no se reconoce."""
    hallazgos = revisar_declaracion(
        ".mcp.json", {"raro": {"command": "servidor-local-sin-args"}}, [])

    assert hallazgos == []
