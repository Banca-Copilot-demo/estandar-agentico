"""Constantes de las especificaciones y del estandar agentico.

Todos los umbrales son constantes NOMBRADAS y no literales dispersos (P11): el nombre dice que
controla cada numero, y hay un solo sitio donde ajustarlo cuando la especificacion cambie.

Puro: sin I/O y sin imports del proyecto fuera de `dominio/`.
"""
from __future__ import annotations

from enum import Enum

# ── Agent Plugins 1.0 ──────────────────────────────────────────────────────────────────────
# Los UNICOS campos de primer nivel que la especificacion permite en `plugin.json`. Lo especifico
# de un cliente va bajo `extensions` con namespace DNS-inverso.
CAMPOS_PLUGIN_PERMITIDOS = frozenset({
    "$schema", "name", "version", "description", "author",
    "homepage", "repository", "license", "keywords", "extensions",
})
CAMPOS_PLUGIN_OBLIGATORIOS = ("$schema", "name")

# Rutas donde los clientes descubren el manifiesto, en orden de preferencia. La primera es la
# UNICA que reconocen Copilot Y Claude Code: poniendola ahi, un mismo plugin sirve a los dos.
RUTAS_MANIFIESTO = (
    ".claude-plugin/plugin.json",
    "plugin.json",
    ".github/plugin/plugin.json",
    ".plugin/plugin.json",
)
RUTA_MANIFIESTO_UNIFICADA = RUTAS_MANIFIESTO[0]

# ── Agent Skills ───────────────────────────────────────────────────────────────────────────
MAX_CARACTERES_DESCRIPCION = 1024
"""Limite de `description` en la especificacion Agent Skills."""

MAX_LINEAS_SKILL = 500
"""Longitud recomendada de `SKILL.md`. Por encima, el material de referencia deberia estar en
`references/`: el cuerpo entero se carga cuando el skill se activa."""

# ── Envelope de gobierno del estandar ────────────────────────────────────────────────────────────
# Vive en el campo `metadata` del PROPIO artefacto, que la especificacion define como mapa
# string->string. Verificado el 18-ago-2026: `gh skill install` PRESERVA estas claves y anade las
# suyas (`github-repo`, `github-ref`, `github-tree-sha`) al lado. Por eso un artefacto suelto es
# auditable sin plugin.
CAMPOS_ENVELOPE = frozenset({
    "id", "owner_team", "owner_contact", "status",
    "version", "data_classification", "standard_version",
})


class Estado(str, Enum):
    """Estados del ciclo de vida. Los DERIVAN los gates; no se declaran a mano."""

    DRAFT = "draft"
    CONFORMANT = "conformant"
    CERTIFIED = "certified"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


ESTADO_EN_AUTORIA = Estado.DRAFT


class Clasificacion(str, Enum):
    """Clasificacion del dato mas sensible que el artefacto toca o transporta."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# ── Hooks ──────────────────────────────────────────────────────────────────────────────────
TECHO_TIMEOUT_HOOK_S = 10
"""Techo del `timeoutSec` de un hook. Sin tope, un hook lento vuelve el cliente inusable; el
ejemplo de referencia de la industria usa 5 y 10 segundos."""

EVENTOS_HOOK_SENSIBLES = frozenset({"userPromptSubmitted", "UserPromptSubmit"})
"""Los eventos que ven TODO lo que el desarrollador escribe: son un canal de salida de datos por
diseno y merecen revision humana explicita.

LAS DOS GRAFIAS, y era un fallo ABIERTO tener solo una. Los dos ecosistemas nombran el mismo evento
distinto: Copilot usa `userPromptSubmitted` en camelCase y Claude Code `UserPromptSubmit` en
PascalCase. La constante tenia solo la primera, asi que el aviso NO disparaba en la forma que usan los
plugins de Claude -- la del catalogo oficial, con dos apariciones medidas, y la que usan nuestros
propios plugins --. O sea que el evento mas sensible pasaba sin avisar justo en el ecosistema en el que
trabajamos."""

PATRON_INTERRUPTOR_SEGURIDAD = r"(?i)block|deny|enforce|strict|secure"
"""Nombres de variables de entorno que parecen un control de seguridad. Si vienen en `false`, es
un interruptor apagado por defecto en un archivo que nadie abre."""

RUTAS_HOOKS = ("hooks.json", "hooks/hooks.json")

# ── G3 · higiene de contenido ──────────────────────────────────────────────────────────────
# Patrones que delatan un secreto o un dato que no debe salir del banco. La credencial se
# REFERENCIA (`${input:...}`, `${env:...}`, `oauth`), nunca se escribe.
PATRONES_HIGIENE: tuple[tuple[str, str], ...] = (
    (r"gh[pousr]_[A-Za-z0-9]{16,}", "token de GitHub"),
    (r"(?i)\bBearer\s+[A-Za-z0-9._\-]{20,}", "cabecera Authorization con token literal"),
    (r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{12,}", "credencial literal"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "clave privada"),
    (r"[A-Za-z]:\\Users\\[A-Za-z0-9._\-]+", "ruta absoluta de maquina Windows"),
    (r"/(?:home|Users)/[A-Za-z0-9._\-]+/", "ruta absoluta de maquina Unix"),
)

PATRON_REFERENCIA_SEGURA = r"\$\{(input|env|secrets|workspaceFolder):"
"""Una referencia no es un secreto: el archivo solo dice COMO obtener la credencial."""

VENTANA_CONTEXTO_REFERENCIA = 40
"""Caracteres antes de la coincidencia donde se busca una referencia segura."""

EXTENSIONES_ESCANEABLES = frozenset({".md", ".json", ".yaml", ".yml", ".sh", ".py", ".txt", ""})

# ── SemVer ─────────────────────────────────────────────────────────────────────────────────
PATRON_SEMVER = r"\d+\.\d+\.\d+"
"""SemVer se valida como STRING. Verificado: al instalar, `version: "1.0.0"` pierde las comillas;
con `1.10` el valor se interpretaria como numero y perderia el cero."""
