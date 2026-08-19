#!/usr/bin/env python3
"""Validador de artefactos agenticos del estandar — gates G1, G3 y G4.

QUE HACE Y QUE NO. Este validador EXTIENDE `gh skill publish --dry-run`, no lo reemplaza:
la herramienta oficial ya comprueba la conformidad con la especificacion Agent Skills
(nombres, coincidencia con el directorio, campos obligatorios, allowed-tools como cadena).
Aqui se comprueba lo que la herramienta NO puede saber: el envelope de gobierno del estandar, el
manifiesto Agent Plugins 1.0 cuando existe, el inventario declarado contra el arbol real,
la higiene de contenido y las condiciones de los hooks.

EL ARTEFACTO ES LA UNIDAD DE GOBIERNO; EL PLUGIN ES OPCIONAL. El envelope
(id, owner_team, owner_contact, status, version, data_classification, standard_version) vive
en el campo `metadata` del PROPIO artefacto, que la especificacion define como mapa
string->string. Verificado el 18-ago-2026: `gh skill install` PRESERVA esas claves y anade
las suyas (github-repo, github-ref, github-tree-sha) al lado. Un artefacto suelto es por
tanto auditable sin plugin, y este validador NO exige que exista uno.

Salida: 0 si todo pasa, 1 si hay algun error. Los avisos no bloquean.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Los UNICOS campos de primer nivel que permite Agent Plugins 1.0.
CAMPOS_PLUGIN = {
    "$schema", "name", "version", "description", "author",
    "homepage", "repository", "license", "keywords", "extensions",
}

# Envelope de gobierno del estandar, dentro de `metadata` del artefacto.
ENVELOPE = {
    "id", "owner_team", "owner_contact", "status",
    "version", "data_classification", "standard_version",
}

ESTADOS = {"draft", "conformant", "certified", "deprecated", "retired"}
CLASIFICACIONES = {"public", "internal", "confidential", "restricted"}

# Un plugin es OPCIONAL salvo para estos casos, donde hace falta poder bloquearlo
# centralmente con enabledPlugins: mcp, hooks, y datos sensibles.
EXIGE_PLUGIN = {"confidential", "restricted"}

TECHO_TIMEOUT_S = 10          # techo del `timeoutSec` de un hook
EVENTO_SENSIBLE = "userPromptSubmitted"   # ve TODO lo que el desarrollador escribe

# G3: patrones que delatan un secreto o un dato que no debe salir del banco.
PATRONES_G3 = [
    (r"gh[pousr]_[A-Za-z0-9]{16,}", "token de GitHub"),
    (r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}", "cabecera Authorization con token literal"),
    (r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{12,}", "credencial literal"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "clave privada"),
    (r"[A-Za-z]:\\Users\\[A-Za-z0-9._\-]+", "ruta absoluta de maquina Windows"),
    (r"/(?:home|Users)/[A-Za-z0-9._\-]+/", "ruta absoluta de maquina Unix"),
]
REFERENCIA_OK = re.compile(r"\$\{(input|env|secrets|workspaceFolder):")

ERROR, AVISO = "error", "aviso"
hallazgos: list[tuple[str, str, str]] = []


def anotar(sev: str, donde: str, msg: str) -> None:
    hallazgos.append((sev, donde, msg))


# ───────────────────────────────────────────────────────── frontmatter
def frontmatter(ruta: Path) -> dict | None:
    """Extrae el frontmatter sin depender de PyYAML: planos + el bloque `metadata`."""
    txt = ruta.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", txt, re.S)
    if not m:
        return None
    bloque = m.group(1)
    fm: dict = {"metadata": {}}
    en_metadata = False
    for linea in bloque.splitlines():
        if re.match(r"^metadata:\s*$", linea):
            en_metadata = True
            continue
        if en_metadata and re.match(r"^\s+\S", linea) and ":" in linea:
            k, v = linea.split(":", 1)
            fm["metadata"][k.strip()] = v.strip().strip('"\'')
            continue
        if not re.match(r"^\s", linea):
            en_metadata = False
            if ":" in linea:
                k, v = linea.split(":", 1)
                fm[k.strip()] = v.strip()
    # `allowed-tools` como lista YAML es la trampa: la especificacion exige CADENA.
    if re.search(r"^allowed-tools:\s*$", bloque, re.M) and re.search(r"^\s+-\s", bloque, re.M):
        fm["__allowed_tools_lista__"] = True
    # `model` como array de nombres fijos: hallazgo 10 del activo del cliente.
    if re.search(r"^model:\s*\[", bloque, re.M):
        fm["__model_array__"] = True
    if re.search(r"^skillsReference:", bloque, re.M):
        fm["__skills_reference__"] = True
    return fm


# ──────────────────────────────────────── G1 G4 · envelope del artefacto
def envelope(donde: str, meta: dict) -> str | None:
    """Comprueba el envelope de gobierno. Devuelve la clasificacion de datos si la declara."""
    for campo in sorted(ENVELOPE - set(meta)):
        anotar(ERROR, donde, f"`metadata.{campo}` falta: es parte del envelope de gobierno")
    estado = meta.get("status")
    if estado and estado not in ESTADOS:
        anotar(ERROR, donde, f"`status` invalido: {estado}")
    elif estado and estado != "draft":
        anotar(AVISO, donde, f"`status` es `{estado}`: el estado lo DERIVAN los gates, no se declara")
    clasif = meta.get("data_classification")
    if clasif and clasif not in CLASIFICACIONES:
        anotar(ERROR, donde, f"`data_classification` invalida: {clasif}")
    for campo in ("version", "standard_version"):
        v = meta.get(campo)
        if v and not re.fullmatch(r"\d+\.\d+\.\d+", str(v)):
            anotar(ERROR, donde, f"`{campo}` no es SemVer: {v}")
    if meta.get("owner_contact") and "@" not in meta["owner_contact"]:
        anotar(AVISO, donde, "`owner_contact` no parece un correo o canal")
    return clasif


# ─────────────────────────────────────────────── G1 · manifiesto (opcional)
def manifiesto(raiz: Path) -> dict | None:
    candidatos = [raiz / ".claude-plugin" / "plugin.json", raiz / "plugin.json",
                  raiz / ".github" / "plugin" / "plugin.json", raiz / ".plugin" / "plugin.json"]
    ruta = next((c for c in candidatos if c.exists()), None)
    if ruta is None:
        return None          # el plugin es OPCIONAL: su ausencia no es un error
    rel = ruta.relative_to(raiz).as_posix()
    try:
        man = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        anotar(ERROR, rel, f"JSON invalido: {e}")
        return None
    if rel != ".claude-plugin/plugin.json":
        anotar(AVISO, rel, "esta ruta la reconoce Copilot pero NO Claude Code. "
                           "Usa .claude-plugin/plugin.json para que sirva a los dos")
    for obligatorio in ("$schema", "name"):
        if obligatorio not in man:
            anotar(ERROR, rel, f"falta el campo obligatorio `{obligatorio}`")
    sobrantes = set(man) - CAMPOS_PLUGIN
    if sobrantes:
        anotar(ERROR, rel, f"campos de primer nivel no permitidos: {sorted(sobrantes)}. "
                           "Lo del estandar va en `extensions` con namespace DNS-inverso")
    if "version" in man and not re.fullmatch(r"\d+\.\d+\.\d+", str(man["version"])):
        anotar(ERROR, rel, f"`version` no es SemVer: {man['version']}")
    return man


# ────────────────────────────────────────────────────────── artefactos
def revisar_skills(raiz: Path) -> tuple[int, set[str]]:
    d = raiz / "skills"
    if not d.is_dir():
        return 0, set()
    n, clasifs = 0, set()
    for sk_dir in sorted(p for p in d.iterdir() if p.is_dir()):
        n += 1
        sk = sk_dir / "SKILL.md"
        if not sk.exists():
            anotar(ERROR, sk_dir.name, "no tiene SKILL.md")
            continue
        donde = f"skills/{sk_dir.name}/SKILL.md"
        fm = frontmatter(sk)
        if fm is None:
            anotar(ERROR, donde, "sin frontmatter: es indescubrible")
            continue
        if fm.get("__allowed_tools_lista__"):
            anotar(ERROR, donde, "`allowed-tools` es lista YAML; la especificacion exige CADENA")
        nombre = fm.get("name")
        if not nombre:
            anotar(ERROR, donde, "falta `name`")
        elif nombre != sk_dir.name:
            anotar(ERROR, donde, f"`name` ({nombre}) no coincide con el directorio "
                                 f"({sk_dir.name}): el skill no cargara")
        desc = fm.get("description", "")
        if not desc:
            anotar(ERROR, donde, "falta `description`: es el mecanismo de seleccion del modelo")
        elif len(desc) > 1024:
            anotar(ERROR, donde, f"`description` excede 1024 caracteres ({len(desc)})")
        c = envelope(donde, fm["metadata"])
        if c:
            clasifs.add(c)
        lineas = sk.read_text(encoding="utf-8").count("\n")
        if lineas > 500:
            anotar(AVISO, donde, f"{lineas} lineas: la especificacion recomienda menos de 500. "
                                 "Mueve el material de referencia a references/")
    return n, clasifs


def revisar_prompts(raiz: Path) -> int:
    d = raiz / "commands"
    if not d.is_dir():
        return 0
    n = 0
    for pr in sorted(d.glob("*.prompt.md")):
        n += 1
        donde = f"commands/{pr.name}"
        fm = frontmatter(pr)
        if fm is None:
            anotar(ERROR, donde, "sin frontmatter")
            continue
        if fm.get("__model_array__"):
            anotar(ERROR, donde, "`model` es un array de nombres fijos. Declara un modelo y "
                                 "deja la lista en el `model_allowlist` del plugin: si no, cada "
                                 "rotacion del catalogo obliga a tocar todos los archivos")
        if fm.get("__skills_reference__"):
            anotar(ERROR, donde, "`skillsReference` no es un campo estandar. Usa `dependencies` "
                                 "por `id`: una ruta de sistema de archivos no resuelve en otra maquina")
        if not fm.get("description"):
            anotar(ERROR, donde, "falta `description`")
        envelope(donde, fm["metadata"])
    return n


def revisar_hooks(raiz: Path, inventario: dict) -> int:
    ruta = next((p for p in (raiz / "hooks.json", raiz / "hooks" / "hooks.json") if p.exists()), None)
    if ruta is None:
        return 0
    rel = ruta.relative_to(raiz).as_posix()
    try:
        cfg = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        anotar(ERROR, rel, f"JSON invalido: {e}")
        return 1
    # Un hook no puede aparecer por sorpresa: se declara.
    if not inventario.get("hooks"):
        anotar(ERROR, rel, "existe pero el inventario de GOVERNANCE.json no declara `hooks`. "
                           "Un componente que EJECUTA CODIGO no entra sin declararse")
    eventos = cfg.get("hooks") or {}
    for evento, entradas in eventos.items():
        for e in entradas if isinstance(entradas, list) else []:
            t = e.get("timeoutSec")
            if t is None:
                anotar(ERROR, f"{rel}:{evento}", "sin `timeoutSec`: un hook sin tope puede colgar el cliente")
            elif t > TECHO_TIMEOUT_S:
                anotar(ERROR, f"{rel}:{evento}", f"`timeoutSec` {t}s supera el techo de {TECHO_TIMEOUT_S}s")
            for k, v in (e.get("env") or {}).items():
                if str(v).lower() == "false" and re.search(r"(?i)block|deny|enforce|strict|secure", k):
                    anotar(AVISO, f"{rel}:{evento}", f"`env.{k}` viene en `false`: parece un control "
                                                     "de seguridad desactivado por defecto")
        if evento == EVENTO_SENSIBLE:
            anotar(AVISO, f"{rel}:{evento}", "este evento ve TODO lo que el desarrollador escribe. "
                                             "Revisa si el script accede a la red antes de aprobarlo")
    return 1


# ─────────────────────────────────────── G4 · gobierno del plugin
def gobierno(raiz: Path, man: dict | None) -> dict:
    ruta = raiz / "GOVERNANCE.json"
    if not ruta.exists():
        if man is not None:
            anotar(ERROR, "GOVERNANCE.json", "el repositorio declara un plugin pero no su gobierno")
        return {}
    try:
        gob = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        anotar(ERROR, "GOVERNANCE.json", f"JSON invalido: {e}")
        return {}
    if man and gob.get("id") and gob["id"] != man.get("name"):
        anotar(ERROR, "GOVERNANCE.json",
               f"`id` ({gob['id']}) no coincide con `name` de plugin.json ({man.get('name')})")
    if not (gob.get("owner") or {}).get("team"):
        anotar(ERROR, "GOVERNANCE.json", "`owner.team` vacio: el dueno debe ser resoluble")
    return gob


def inventario(gob: dict, reales: dict[str, int]) -> None:
    decl = (gob or {}).get("artifacts") or {}
    for tipo, n_real in reales.items():
        if decl.get(tipo, 0) != n_real:
            anotar(ERROR, "GOVERNANCE.json",
                   f"inventario: declara {decl.get(tipo, 0)} `{tipo}` y el arbol real tiene {n_real}")


# ───────────────────────────────────────────── G3 · higiene de contenido
def higiene(raiz: Path) -> None:
    for f in sorted(raiz.rglob("*")):
        if not f.is_file() or ".git" in f.parts:
            continue
        if f.suffix.lower() not in {".md", ".json", ".yaml", ".yml", ".sh", ".py", ".txt", ""}:
            continue
        rel = f.relative_to(raiz).as_posix()
        if rel.startswith("validador/"):
            continue          # este archivo contiene los patrones a proposito
        try:
            txt = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue
        for patron, que in PATRONES_G3:
            for m in re.finditer(patron, txt):
                if REFERENCIA_OK.search(txt[max(0, m.start() - 40):m.end() + 10]):
                    continue  # es una referencia, no un secreto
                anotar(ERROR, f"{rel}:{txt[:m.start()].count(chr(10)) + 1}", f"posible {que}")


def main() -> int:
    raiz = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    print(f"Validando {raiz.name}\n")

    man = manifiesto(raiz)
    gob = gobierno(raiz, man)
    n_skills, clasifs = revisar_skills(raiz)
    n_prompts = revisar_prompts(raiz)
    n_agents = len(list((raiz / "agents").glob("*.agent.md"))) if (raiz / "agents").is_dir() else 0
    n_hooks = revisar_hooks(raiz, (gob or {}).get("artifacts") or {})
    n_mcp = 1 if (raiz / ".mcp.json").exists() else 0

    if gob:
        inventario(gob, {"skills": n_skills, "agents": n_agents, "prompts": n_prompts})
    higiene(raiz)

    # El plugin es OPCIONAL, salvo cuando hace falta poder bloquearlo centralmente.
    if man is None:
        motivos = []
        if n_mcp:
            motivos.append("contiene un `mcp`")
        if n_hooks:
            motivos.append("contiene `hooks`")
        if clasifs & EXIGE_PLUGIN:
            motivos.append(f"clasificacion {sorted(clasifs & EXIGE_PLUGIN)}")
        if motivos:
            anotar(ERROR, "plugin.json",
                   "no existe, y aqui es obligatorio porque " + " y ".join(motivos) +
                   ": hace falta poder bloquearlo con enabledPlugins")
        else:
            anotar(AVISO, "plugin.json",
                   "sin plugin: los artefactos quedan gobernados por su propia metadata, pero "
                   "NO entran al marketplace ni se pueden bloquear centralmente")

    errores = [h for h in hallazgos if h[0] == ERROR]
    avisos = [h for h in hallazgos if h[0] == AVISO]
    for sev, donde, msg in errores + avisos:
        print(f"{'ERROR' if sev == ERROR else 'aviso':5}  {donde}  {msg}")

    print(f"\nInventario real: {n_skills} skills | {n_agents} agentes | {n_prompts} prompts | "
          f"{n_mcp} mcp | {n_hooks} hooks | plugin: {'si' if man else 'no'}")
    if errores:
        print(f"\nVeredicto: NO CONFORME - {len(errores)} error(es), {len(avisos)} aviso(s)")
        return 1
    print(f"\nVeredicto: CONFORME - 0 errores, {len(avisos)} aviso(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
