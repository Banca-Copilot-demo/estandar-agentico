"""Las TRES formas en que un archivo MCP declara sus servidores, y los dos nombres de archivo.

EL DEFECTO QUE CIERRA, medido sobre los catalogos publicos. El gate asumia UNA forma -- un objeto
`mcpServers` -- y el comentario del codigo afirmaba que «los plugins reales lo llevan con una sola
clave». Se conto y es falso:

  archivo       clave de primer nivel                     observados
  .mcp.json     mcpServers                                        10
  .mcp.json     ninguna: los servidores en la RAIZ                10
  mcp.json      servers (1) y mcpServers (4)                       5

DIEZ DE LOS QUINCE plugins del marketplace OFICIAL usan la forma sin clave, entre ellos `github`,
`terraform`, `linear` y `playwright`.

Y producia dos fallos OPUESTOS:

  - CERRADO PERO EN FALSO: la forma desnuda se rechazaba con «no declara `mcpServers`». Habriamos
    rechazado la forma mayoritaria del catalogo oficial, igual que el patron del `name` del agente
    rechazaba a los cinco agentes de `.github-private`.

  - ABIERTO: un `mcp.json` -- sin punto, como los de `awesome-copilot` -- no se leia siquiera.
    Inventario 0, ninguna ficha, ningun error, veredicto CONFORME. Comprobado con un servidor fijado a
    `@latest`, que es el defecto que la regla del rug pull existe para cazar.
"""
from __future__ import annotations

import pytest

from validador_agentico.dominio.forma_mcp import servidores_de

# Copiados TAL CUAL de los plugins del marketplace oficial y de awesome-copilot, para que la prueba
# falle si alguna de esas formas deja de reconocerse.
_COMO_CONTEXT7 = {"mcpServers": {"context7": {"type": "http", "url": "https://mcp.context7.com/mcp"}}}
_COMO_GITHUB = {"github": {"type": "http", "url": "https://api.githubcopilot.com/mcp/",
                           "headers": {"Authorization": "Bearer ${TOKEN}"}}}
_COMO_TERRAFORM = {"terraform": {"command": "docker",
                                 "args": ["run", "hashicorp/terraform-mcp-server:0.4.0"]}}
_COMO_AWESOME_COPILOT = {"servers": {"github-agentic-workflows": {"command": "gh",
                                                                  "args": ["aw", "mcp-server"]}}}


@pytest.mark.parametrize("nombre,configuracion,esperados", [
    ("mcpServers (context7)", _COMO_CONTEXT7, ["context7"]),
    ("raiz, remoto (github)", _COMO_GITHUB, ["github"]),
    ("raiz, stdio (terraform)", _COMO_TERRAFORM, ["terraform"]),
    ("servers (awesome-copilot)", _COMO_AWESOME_COPILOT, ["github-agentic-workflows"]),
])
def test_las_formas_REALES_de_los_catalogos_se_reconocen(nombre, configuracion, esperados):
    """En bucle con el nombre en el id: cuando falla, dice QUE forma dejo de reconocerse (T5)."""
    assert list(servidores_de(configuracion) or {}) == esperados, nombre


def test_un_objeto_VACIO_no_es_la_forma_desnuda():
    """`{}` no declara servidores y tampoco es «no reconozco la forma»: son dos cosas distintas y el
    llamador da mensajes distintos."""
    assert servidores_de({}) is None


def test_un_mcpServers_VACIO_se_distingue_de_no_reconocer_la_forma():
    # `{"mcpServers": {}}` es un archivo que declara EXPLICITAMENTE que no hay servidores -- es como se
    # desactiva MCP en la configuracion gestionada --. No reconocer la forma es no saber que hay.
    assert servidores_de({"mcpServers": {}}) == {}


def test_un_objeto_que_no_parece_servidores_no_se_interpreta_como_tal():
    """Sin esto, cualquier JSON con un objeto dentro se leeria como una lista de servidores, y el gate
    gobernaria el conjunto equivocado."""
    assert servidores_de({"version": 1, "descripcion": {"texto": "algo"}}) is None


def test_se_exige_que_TODOS_los_valores_parezcan_servidor():
    # Con «alguno» basta, un archivo con una clave suelta junto a los servidores se leeria mal. Y
    # equivocarse aqui significa aprobar y sellar un conjunto que no es el que se ejecuta.
    mezclado = {"servidor": {"command": "uvx", "args": ["x@1.0.0"]}, "otraCosa": {"a": 1}}

    assert servidores_de(mezclado) is None


@pytest.mark.parametrize("valor", [None, [], "texto", 42])
def test_lo_que_no_es_un_objeto_no_revienta(valor):
    assert servidores_de(valor) is None


def test_el_envoltorio_manda_sobre_la_forma_desnuda():
    """Si un archivo trae `mcpServers` Y claves que parecen servidores al lado, gana el envoltorio: es
    la forma que la especificacion documenta, y adivinar la otra gobernaria lo que no se ejecuta."""
    ambiguo = {"mcpServers": {"elBueno": {"command": "uvx", "args": ["a@1.0.0"]}},
               "elOtro": {"command": "uvx", "args": ["b@2.0.0"]}}

    assert list(servidores_de(ambiguo)) == ["elBueno"]
