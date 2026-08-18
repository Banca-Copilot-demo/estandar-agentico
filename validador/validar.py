#!/usr/bin/env python3
"""Validador de artefactos agenticos del estandar — gates G1, G3 y parte de G4.

QUE HACE Y QUE NO. Este validador EXTIENDE `gh skill publish --dry-run`, no lo reemplaza:
la herramienta oficial ya comprueba la conformidad con la especificacion Agent Skills
(nombres, coincidencia con el directorio, campos obligatorios, allowed-tools como cadena).
Aqui se comprueba lo que la herramienta NO puede saber: el manifiesto Agent Plugins 1.0, el
gobierno del estandar, el inventario declarado contra el arbol real y la higiene de contenido.

Salida: codigo 0 si todo pasa, 1 si hay algun error. Los avisos no bloquean.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Los UNICOS campos de primer nivel que la especificacion Agent Plugins 1.0 permite.
CAMPOS_PLUGIN = {
    "$schema", "name", "version", "description", "author",
    "homepage", "repository", "license", "keywords", "extensions",
}

# Campos obligatorios del manifiesto de gobierno del estandar.
CAMPOS_GOBIERNO = {
    "id", "domain", "owner", "status", "data_classification",
    "standard_version", "artifacts",
}

ESTADOS = {"draft", "conformant", "certified", "deprecated", "retired"}

# G3: patrones que delatan un secreto o un dato que no debe salir del banco.
# La credencial se REFERENCIA (${input:...}, ${env:...}, oauth), nunca se escribe.
PATRONES_G3 = [
    (r"gh[pousr]_[A-Za-z0-9]{16,}", "token de GitHub"),
    (r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}", "cabecera Authorization con token literal"),
    (r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{12,}", "credencial literal"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "clave privada"),
    (r"[A-Za-z]:\\Users\\[A-Za-z0-9._\-]+", "ruta absoluta de maquina Windows"),
    (r"/(?:home|Users)/[a-z0-9._\-]+/", "ruta absoluta de maquina Unix"),
]
# Excepciones: una referencia NO es un secreto.
REFERENCIA_OK = re.compile(r"\$\{(input|env|secrets|workspaceFolder):")

SEVERIDAD_ERROR, SEVERIDAD_AVISO = "error", "aviso"
hallazgos: list[tuple[str, str, str]] = []


def anotar(sev: str, donde: str, msg: str) -> None:
    hallazgos.append((sev, donde, msg))


def leer_frontmatter(ruta: Path) -> dict | None:
    """Extrae el frontmatter YAML sin depender de PyYAML: solo lo que necesitamos."""
    txt = ruta.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", txt, re.S)
    if not m:
        return None
    fm, bloque = {}, m.group(1)
    for linea in bloque.splitlines():
        if re.match(r"^\s", linea) or ":" not in linea:
            continue  # clave anidada: no hace falta para estas comprobaciones
        k, v = linea.split(":", 1)
        fm[k.strip()] = v.strip()
    # Detecta si allowed-tools viene como lista YAML (la trampa: debe ser CADENA).
    if re.search(r"^allowed-tools:\s*$", bloque, re.M) and re.search(r"^\s+-\s", bloque, re.M):
        fm["__allowed_tools_es_lista__"] = "si"
    return fm


# ─────────────────────────────────────────────────────────── G1 | plugin.json
def g1_manifiesto(raiz: Path) -> dict:
    candidatos = [raiz / ".claude-plugin" / "plugin.json", raiz / "plugin.json",
                  raiz / ".github" / "plugin" / "plugin.json", raiz / ".plugin" / "plugin.json"]
    ruta = next((c for c in candidatos if c.exists()), None)
    if ruta is None:
        anotar(SEVERIDAD_ERROR, "plugin.json", "no existe. Un artefacto no se publica fuera de un plugin")
        return {}
    try:
        man = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        anotar(SEVERIDAD_ERROR, str(ruta), f"JSON invalido: {e}")
        return {}

    rel = ruta.relative_to(raiz).as_posix()
    if rel != ".claude-plugin/plugin.json":
        anotar(SEVERIDAD_AVISO, rel,
               "esta ruta la reconoce Copilot pero NO Claude Code. Usa .claude-plugin/plugin.json "
               "para que el mismo plugin sirva a los dos clientes")

    for obligatorio in ("$schema", "name"):
        if obligatorio not in man:
            anotar(SEVERIDAD_ERROR, rel, f"falta el campo obligatorio `{obligatorio}`")
    sobrantes = set(man) - CAMPOS_PLUGIN
    if sobrantes:
        anotar(SEVERIDAD_ERROR, rel,
               f"campos de primer nivel no permitidos por la especificacion: {sorted(sobrantes)}. "
               "Lo especifico del estandar va en `extensions` bajo namespace DNS-inverso")
    if "version" in man and not re.fullmatch(r"\d+\.\d+\.\d+", str(man["version"])):
        anotar(SEVERIDAD_ERROR, rel, f"`version` no es SemVer: {man['version']}")
    return man


# ──────────────────────────────────────────────────── G4 | GOVERNANCE.json
def g4_gobierno(raiz: Path, manifiesto: dict) -> dict:
    ruta = raiz / "GOVERNANCE.json"
    if not ruta.exists():
        anotar(SEVERIDAD_ERROR, "GOVERNANCE.json", "no existe. Sin dueno declarado no hay a quien avisar")
        return {}
    try:
        gob = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        anotar(SEVERIDAD_ERROR, "GOVERNANCE.json", f"JSON invalido: {e}")
        return {}

    for f in sorted(CAMPOS_GOBIERNO - set(gob)):
        anotar(SEVERIDAD_ERROR, "GOVERNANCE.json", f"falta el campo obligatorio `{f}`")
    if gob.get("status") not in ESTADOS and "status" in gob:
        anotar(SEVERIDAD_ERROR, "GOVERNANCE.json", f"`status` invalido: {gob['status']}")
    if gob.get("status") not in (None, "draft"):
        anotar(SEVERIDAD_AVISO, "GOVERNANCE.json",
               f"`status` es `{gob['status']}`: el estado lo DERIVAN los gates, no se declara a mano")
    if manifiesto and gob.get("id") and gob["id"] != manifiesto.get("name"):
        anotar(SEVERIDAD_ERROR, "GOVERNANCE.json",
               f"`id` ({gob['id']}) no coincide con `name` de plugin.json ({manifiesto.get('name')})")
    dueno = gob.get("owner") or {}
    if not dueno.get("team"):
        anotar(SEVERIDAD_ERROR, "GOVERNANCE.json", "`owner.team` vacio: el dueno debe ser resoluble")
    return gob


# ─────────────────────────────────────────────── G1 | skills e inventario
def g1_skills(raiz: Path) -> int:
    dir_skills = raiz / "skills"
    if not dir_skills.is_dir():
        return 0
    n = 0
    for d in sorted(p for p in dir_skills.iterdir() if p.is_dir()):
        n += 1
        sk = d / "SKILL.md"
        if not sk.exists():
            anotar(SEVERIDAD_ERROR, d.name, "no tiene SKILL.md")
            continue
        fm = leer_frontmatter(sk)
        if fm is None:
            anotar(SEVERIDAD_ERROR, f"{d.name}/SKILL.md", "sin frontmatter: es indescubrible")
            continue
        if fm.get("__allowed_tools_es_lista__"):
            anotar(SEVERIDAD_ERROR, f"{d.name}/SKILL.md",
                   "`allowed-tools` es una lista YAML; la especificacion exige una CADENA separada por espacios")
        nombre = fm.get("name")
        if not nombre:
            anotar(SEVERIDAD_ERROR, f"{d.name}/SKILL.md", "falta `name`")
        elif nombre != d.name:
            anotar(SEVERIDAD_ERROR, f"{d.name}/SKILL.md",
                   f"`name` ({nombre}) no coincide con el directorio ({d.name}): el skill no cargara")
        desc = fm.get("description", "")
        if not desc:
            anotar(SEVERIDAD_ERROR, f"{d.name}/SKILL.md",
                   "falta `description`: es el mecanismo de seleccion del modelo")
        elif len(desc) > 1024:
            anotar(SEVERIDAD_ERROR, f"{d.name}/SKILL.md", f"`description` excede 1024 caracteres ({len(desc)})")
        lineas = sk.read_text(encoding="utf-8").count("\n")
        if lineas > 500:
            anotar(SEVERIDAD_AVISO, f"{d.name}/SKILL.md",
                   f"{lineas} lineas: la especificacion recomienda menos de 500. "
                   "Mueve el material de referencia a references/")
    return n


def g1_inventario(gob: dict, reales: dict[str, int]) -> None:
    decl = (gob or {}).get("artifacts") or {}
    for tipo, n_real in reales.items():
        n_decl = decl.get(tipo, 0)
        if n_decl != n_real:
            anotar(SEVERIDAD_ERROR, "GOVERNANCE.json",
                   f"inventario: declara {n_decl} `{tipo}` y el arbol real tiene {n_real}")


# ──────────────────────────────────────────────── G3 | higiene de contenido
def g3_higiene(raiz: Path) -> None:
    for f in sorted(raiz.rglob("*")):
        if not f.is_file() or ".git" in f.parts:
            continue
        if f.suffix.lower() not in {".md", ".json", ".yaml", ".yml", ".sh", ".py", ".txt", ""}:
            continue
        try:
            txt = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        rel = f.relative_to(raiz).as_posix()
        if rel.startswith("validador/"):
            continue  # este archivo contiene los patrones a proposito
        for patron, que in PATRONES_G3:
            for m in re.finditer(patron, txt):
                if REFERENCIA_OK.search(txt[max(0, m.start() - 40):m.end() + 10]):
                    continue  # es una referencia, no un secreto
                linea = txt[:m.start()].count("\n") + 1
                anotar(SEVERIDAD_ERROR, f"{rel}:{linea}", f"posible {que}")


def main() -> int:
    raiz = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(f"Validando {raiz.name}\n")

    manifiesto = g1_manifiesto(raiz)
    gobierno = g4_gobierno(raiz, manifiesto)
    n_skills = g1_skills(raiz)
    n_agents = len(list((raiz / "agents").glob("*.agent.md"))) if (raiz / "agents").is_dir() else 0
    n_prompts = len(list((raiz / "commands").glob("*.prompt.md"))) if (raiz / "commands").is_dir() else 0
    g1_inventario(gobierno, {"skills": n_skills, "agents": n_agents, "prompts": n_prompts})
    g3_higiene(raiz)

    errores = [h for h in hallazgos if h[0] == SEVERIDAD_ERROR]
    avisos = [h for h in hallazgos if h[0] == SEVERIDAD_AVISO]
    for sev, donde, msg in errores + avisos:
        marca = "ERROR" if sev == SEVERIDAD_ERROR else "aviso"
        print(f"{marca:5}  {donde}  {msg}")

    print(f"\nInventario real: {n_skills} skills | {n_agents} agentes | {n_prompts} prompts")
    if errores:
        print(f"\nVeredicto: NO CONFORME — {len(errores)} error(es), {len(avisos)} aviso(s)")
        return 1
    print(f"\nVeredicto: CONFORME — 0 errores, {len(avisos)} aviso(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
