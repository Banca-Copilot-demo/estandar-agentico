"""El `mcpServers` declarado DENTRO del `plugin.json`, que es la alternativa que el formato admite.

EL HUECO QUE CUBREN, y es de los que no avisan de nada. El formato admite `mcpServers` inline en el
manifiesto -- `string | array | object` -- como ALTERNATIVA a `.mcp.json`. Nuestro validador asumia
el archivo: sin `.mcp.json`, el recorrido del `mcp` no se ejecutaba, asi que un repositorio que lo
declarara inline se llevaba CERO reglas -- ni fijado de version, ni cotejo contra el gobierno, ni
aprobacion, ni credenciales -- y el gate salia en VERDE. Un servidor MCP entero sin gobierno.

No es que se rechazara mal: es que NO SE MIRABA. Es el mismo tipo de fallo que el `mcp.json` sin
punto, y por eso estas pruebas van por el gate completo y no por una regla suelta -- lo que fallaba
era el CABLE, no la regla.

Cada prueba nombra el defecto que cubre (T2).
"""
from __future__ import annotations

import json
from pathlib import Path

from validador_agentico.aplicacion.validar_repositorio import validar

_ESQUEMAS = Path(__file__).resolve().parents[2] / "schemas"

_APROBACION = {"approved_by": "squad-seguridad", "date": "2026-08-23",
               "review_by": "2027-08-23", "security_review": True}

_SERVIDOR_FIJADO = {"type": "stdio", "command": "uvx",
                    "args": ["ejemplo-catalogo-mcp@0.4.1"]}


def _repositorio(tmp_path: Path, *, servidores: dict, gobierno_del_mcp=None) -> Path:
    raiz = tmp_path / "repo"
    manifiesto = raiz / ".claude-plugin"
    manifiesto.mkdir(parents=True)
    (manifiesto / "plugin.json").write_text(json.dumps({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": "demo.x.y", "version": "1.0.0",
        "description": "Plugin con el MCP declarado en el manifiesto.",
        "mcpServers": servidores,
    }), encoding="utf-8")
    gobierno = {
        "id": "demo.x.y", "domain": "x",
        "owner": {"team": "squad-x", "contact": "squad-x@ejemplo.dev"},
        "data_classification": "internal", "standard_version": "8.0.0",
        "artifacts": {"skills": [], "agents": [], "prompts": []},
    }
    if gobierno_del_mcp is not None:
        gobierno["mcp"] = gobierno_del_mcp
    (raiz / "GOVERNANCE.json").write_text(json.dumps(gobierno), encoding="utf-8")
    return raiz


def _errores(raiz: Path):
    return validar(raiz, directorio_de_esquemas=_ESQUEMAS).errores


def _mensajes(hallazgos):
    return " || ".join(h.mensaje for h in hallazgos)


def test_un_servidor_inline_sin_gobierno_del_mcp_es_error(tmp_path):
    # EL DEFECTO EXACTO: antes, sin `.mcp.json`, esto salia CONFORME. Un servidor que se ejecuta, sale
    # por la red, y no tiene aprobacion, ni dueno de la credencial, ni digesto con el que detectar que
    # su superficie de herramientas cambio.
    raiz = _repositorio(tmp_path, servidores={"catalogo": _SERVIDOR_FIJADO})
    assert "el gobierno no declara `mcp`" in _mensajes(_errores(raiz))


def test_un_servidor_inline_con_referencia_movil_es_error(tmp_path):
    # La regla de fijado NO CORRIA sobre esta forma. Medido en los plugins de AWS: usan exactamente
    # `awslabs.aws-iac-mcp-server@latest`, y con el MCP inline eso pasaba sin que nadie lo mirara.
    raiz = _repositorio(
        tmp_path,
        servidores={"aws": {"type": "stdio", "command": "uvx",
                            "args": ["awslabs.aws-iac-mcp-server@latest"]}},
        gobierno_del_mcp={"aws": {"write_operations": False, "credentials": [],
                                  "approval": _APROBACION}})
    assert "rug pull" in _mensajes(_errores(raiz))


def test_un_servidor_inline_no_aprobado_es_error(tmp_path):
    raiz = _repositorio(
        tmp_path,
        servidores={"catalogo": _SERVIDOR_FIJADO, "interno": {"type": "http",
                                                              "url": "https://interno/mcp"}},
        gobierno_del_mcp={"catalogo": {"write_operations": False, "credentials": [],
                                       "approval": _APROBACION}})
    assert "`interno`" in _mensajes(_errores(raiz))


def test_una_credencial_inline_sin_declarar_es_error(tmp_path):
    # Declarar cero credenciales y traer un `Authorization` sigue siendo error tambien por esta via:
    # el gobierno es el mismo, solo cambia de que archivo se leen los servidores.
    raiz = _repositorio(
        tmp_path,
        servidores={"remoto": {"type": "http", "url": "https://x/mcp",
                               "headers": {"Authorization": "Bearer ${API_TOKEN}"}}},
        gobierno_del_mcp={"remoto": {"write_operations": False, "credentials": [],
                                     "approval": _APROBACION}})
    assert "API_TOKEN" in _mensajes(_errores(raiz))


def test_un_mcp_inline_bien_gobernado_no_bloquea_pero_avisa_de_la_portabilidad(tmp_path):
    # `mcpServers` inline NO forma parte de Agent Plugins 1.0 -- diez campos de primer nivel, y este
    # no esta --, asi que porta a menos sitios que un `.mcp.json`. Es informacion que el autor
    # necesita, no un motivo para rechazarlo: el formato lo admite y el cliente lo lee.
    raiz = _repositorio(
        tmp_path,
        servidores={"catalogo": _SERVIDOR_FIJADO},
        gobierno_del_mcp={"catalogo": {"write_operations": False, "credentials": [],
                                       "approval": _APROBACION}})
    veredicto = validar(raiz, directorio_de_esquemas=_ESQUEMAS)
    assert veredicto.conforme, _mensajes(veredicto.errores)
    assert "porta a menos sitios" in _mensajes(veredicto.avisos)


def test_declararlo_inline_no_se_reprocha_como_campo_inventado(tmp_path):
    # Antes salia como «campo de primer nivel no permitido», que empuja a BORRARLO -- y borrarlo no
    # arregla nada, porque entonces el plugin deja de funcionar --. El mensaje mandaba al sitio
    # equivocado justo cuando el problema real era que no se gobernaba.
    raiz = _repositorio(
        tmp_path,
        servidores={"catalogo": _SERVIDOR_FIJADO},
        gobierno_del_mcp={"catalogo": {"write_operations": False, "credentials": [],
                                       "approval": _APROBACION}})
    todos = validar(raiz, directorio_de_esquemas=_ESQUEMAS).hallazgos
    assert "no permitidos por la especificacion" not in _mensajes(todos)
