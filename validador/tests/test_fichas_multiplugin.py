"""Las fichas de un repositorio con VARIOS plugins: que la `ruta` publicada sirva de verdad.

QUE DEFECTO CUBRE, y se midio ejecutando el recorrido de instalacion contra lo publicado. La `ruta` de
cada ficha se publicaba RELATIVA AL PLUGIN -- `commands/x.prompt.md` -- y todos sus consumidores la
resuelven contra la RAIZ DEL REPOSITORIO: la pista de verificacion de la ficha descarga
`<repo>/<ruta>` fijado al sha, y el humo hace lo mismo.

Con un plugin en la raiz las dos rutas COINCIDEN, asi que el defecto era invisible. Con el plugin en
`plugins/referencia/` el consumidor pedia un archivo que no existe, y el sintoma fue «el sha256 del
prompt no coincide con lo firmado»: una alarma de INTEGRIDAD por un problema de RUTA. Es el peor tipo
de mensaje, porque manda a investigar la cadena de firma cuando lo que falla es una concatenacion.

Y UN SEGUNDO SINTOMA, PEOR QUE EL PRIMERO: la `ruta` dejaba de ser UNICA. Los dos `mcp` del
repositorio de demo publicaban `.mcp.json` los dos, asi que dos fichas de Port con ids distintos
apuntaban al mismo archivo y no habia forma de saber a que se referia cada una.

POR QUE NO LO VIO NINGUNA PRUEBA: no habia ni una que ejercitara `listar_artefactos`, y ninguna montaba
un repositorio con varios plugins para mirar lo que se PUBLICA. Las 235 pasaban con el defecto dentro.
"""
from __future__ import annotations

import json
from pathlib import Path

from validador_agentico.aplicacion.validar_repositorio import validar

_ENVELOPE_BASE = """  owner_team: squad-sdlc
  owner_contact: squad-sdlc@ejemplo.dev
  status: draft
  version: 1.0.0
  data_classification: internal
  standard_version: 8.0.0"""


def _skill(raiz_plugin: Path, nombre: str, identificador: str) -> None:
    directorio = raiz_plugin / "skills" / nombre
    directorio.mkdir(parents=True)
    (directorio / "SKILL.md").write_text(
        f"---\nname: {nombre}\n"
        f"description: Hace algo concreto y se usa cuando alguien lo pide por su nombre.\n"
        f"metadata:\n  id: {identificador}\n{_ENVELOPE_BASE}\n---\n\n# {nombre}\n",
        encoding="utf-8")


def _plugin_con_mcp(raiz: Path, nombre: str, identificador: str) -> Path:
    """Un plugin completo en `plugins/<nombre>/`, con su skill y su `.mcp.json` gobernado."""
    raiz_plugin = raiz / "plugins" / nombre
    manifiesto = raiz_plugin / ".claude-plugin"
    manifiesto.mkdir(parents=True)
    (manifiesto / "plugin.json").write_text(json.dumps({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": identificador, "version": "1.0.0", "description": "Plugin de prueba."}),
        encoding="utf-8")
    (raiz_plugin / "GOVERNANCE.json").write_text(json.dumps({
        "id": identificador, "domain": "sdlc",
        "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
        "status": "draft", "data_classification": "internal", "standard_version": "8.0.0",
        "artifacts": {"skills": 1, "mcps": 1},
        "mcp": {
            "servers": [{
                "name": "remoto", "transport": "http",
                "endpoint": "https://ejemplo.dev/mcp",
                "source": {"kind": "remote", "ref": "https://ejemplo.dev/mcp",
                           "version_pin": "sin-version"},
                "write_operations": False,
                "tools_digest": "0" * 64, "tools_digest_date": "2026-08-23"}],
            "credentials": {"mechanism": "none"},
            "approval": {"approved_by": "squad-seguridad", "date": "2026-08-23",
                         "review_by": "2027-02-23", "security_review": True}}}),
        encoding="utf-8")
    (raiz_plugin / ".mcp.json").write_text(json.dumps({
        "mcpServers": {"remoto": {"type": "http", "url": "https://ejemplo.dev/mcp"}}}),
        encoding="utf-8")
    _skill(raiz_plugin, f"skill-de-{nombre}", f"{identificador}.skill")
    return raiz_plugin


def _fichas(raiz: Path) -> dict[str, str]:
    """Las fichas publicadas, como `id -> ruta`."""
    veredicto = validar(raiz)
    return {a.id: a.ruta for a in veredicto.artefactos}


def test_la_ruta_publicada_es_relativa_al_REPOSITORIO_y_el_archivo_existe(tmp_path):
    # La comprobacion decisiva: la ruta que va en la ficha tiene que resolver desde la RAIZ, porque es
    # ahi donde la resuelve quien la consume.
    _plugin_con_mcp(tmp_path, "uno", "demo.sdlc.uno")
    _plugin_con_mcp(tmp_path, "dos", "demo.sdlc.dos")

    for identificador, ruta in _fichas(tmp_path).items():
        assert (tmp_path / ruta).is_file(), f"{identificador} publica {ruta}, que no existe en la raiz"


def test_dos_plugins_con_mcp_no_publican_la_MISMA_ruta(tmp_path):
    # MEDIDO en el repositorio de demo: los dos `mcp` publicaban `.mcp.json` los dos. Dos fichas con
    # ids distintos apuntando al mismo archivo hacen imposible saber a que se refiere cada una.
    _plugin_con_mcp(tmp_path, "uno", "demo.sdlc.uno")
    _plugin_con_mcp(tmp_path, "dos", "demo.sdlc.dos")

    fichas = _fichas(tmp_path)
    rutas_de_mcp = [r for i, r in fichas.items() if i.endswith(".mcp")]

    assert len(rutas_de_mcp) == 2, fichas
    assert len(set(rutas_de_mcp)) == 2, f"los dos mcp publican la misma ruta: {rutas_de_mcp}"


def test_todas_las_rutas_publicadas_son_distintas(tmp_path):
    _plugin_con_mcp(tmp_path, "uno", "demo.sdlc.uno")
    _plugin_con_mcp(tmp_path, "dos", "demo.sdlc.dos")

    rutas = list(_fichas(tmp_path).values())

    assert len(rutas) == len(set(rutas)), f"hay rutas repetidas entre fichas: {sorted(rutas)}"


def test_un_plugin_en_la_RAIZ_publica_su_ruta_sin_prefijo(tmp_path):
    """El caso que ocultaba el defecto: con el plugin en la raiz no hay prefijo que añadir, y la ruta
    tiene que quedarse tal cual -- sin un `./` delante ni nada que la rompa."""
    _skill(tmp_path, "solo", "demo.sdlc.solo")

    fichas = _fichas(tmp_path)

    assert fichas == {"demo.sdlc.solo": "skills/solo/SKILL.md"}, fichas
