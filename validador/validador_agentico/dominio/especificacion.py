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

# ── Gobierno del estandar ──────────────────────────────────────────────────────────────────
RUTA_GOBIERNO = "GOVERNANCE.json"
"""El archivo de gobierno, en la raiz DE LA UNIDAD publicable -- que no siempre es la del repositorio.

VIVE AQUI Y NO EN EL ADAPTADOR, que es donde estaba. El nombre del archivo es un hecho del ESTANDAR y
no un detalle de como se lee el disco, y las reglas de dominio necesitan nombrarlo para decir DONDE
esta el defecto. Importarlo de `adaptadores/repositorio.py` habria puesto a `dominio/` a depender de
un adaptador -- la flecha apuntando hacia afuera, que es justo lo que G5 prohibe -- y volver a
escribir la cadena en el dominio habria dejado dos definiciones del mismo valor (G2). El adaptador lo
reexporta, asi que quien ya lo importaba de alli sigue funcionando."""

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
    """Estados del ciclo de vida. Los DERIVAN los gates; no se declaran a mano.

    EL ORDEN ES EL DEL CICLO DE VIDA, no alfabetico, y se replica igual en
    `schemas/envelope.schema.json` y en `port/blueprint-artefacto-agentico.json`.
    `tests/test_contrato_de_port.py` falla si los tres dejan de coincidir.

    `SUSPENDED` es la unica salida REVERSIBLE: el artefacto deja de distribuirse -- el release
    vuelve a prelanzamiento -- sin que nadie declare todavia que se retira. Por eso NO exige el
    bloque `deprecation`, que `DEPRECATED` y `RETIRED` si exigen: suspender no anuncia un plazo,
    solo detiene la distribucion mientras se decide.
    """

    DRAFT = "draft"
    CONFORMANT = "conformant"
    CERTIFIED = "certified"
    SUSPENDED = "suspended"
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
CAMPO_TIMEOUT_HOOK = "timeout"
"""El campo REAL del tope de ejecucion de un hook: `timeout`, en SEGUNDOS y en la ACCION.

Verificado contra la documentacion oficial y contra plugins reales -- los de AWS instalados en
Copilot usan `"timeout": 30` dentro de la accion --."""

CAMPO_TIMEOUT_HOOK_RETIRADO = "timeoutSec"
"""El campo que el gate EXIGIA y que NO EXISTE en el formato.

EL DEFECTO, y no era cosmetico. El gate pedia `timeoutSec` a nivel de GRUPO. El cliente ignora ese
campo por completo, asi que el hook corria con el timeout POR DEFECTO de su tipo -- 600 s para
`command`, 30 s para `prompt` -- mientras quien lo escribio creia haber puesto un tope de 5 segundos.
Un control que parece un control y no lo es es peor que no tener ninguno: el que no existe no engana
a nadie.

SE SIGUE ACEPTANDO CON AVISO. Hay 908 repositorios publicos que arrastran el mismo error, asi que
alguien lo traera de fuera; y el gate es comprobacion REQUERIDA, de modo que convertirlo en error de
golpe bloquearia todos los repositorios de dominio a la vez e impediria mergear hasta el pull request
que viene a corregirlo. Se endurece cuando ningun `hooks.json` de un repositorio de dominio lo lleve.
"""

TECHO_TIMEOUT_HOOK_S = 10
"""Techo del `timeout` de un hook, en segundos. Sin tope, un hook lento vuelve el cliente inusable; el
ejemplo de referencia de la industria usa 5 y 10 segundos."""

TIMEOUT_HOOK_POR_DEFECTO_S = {
    "command": 600, "http": 600, "mcp_tool": 600, "prompt": 30, "agent": 60,
}
"""Lo que el cliente aplica cuando la accion no declara `timeout`, por tipo.

Esta aqui para que el mensaje del gate pueda decir CUANTO se va a esperar de verdad. «Falta el
timeout» invita a ignorarlo; «se bloqueara hasta 600 s» no."""

TIPO_HOOK_DOMINANTE = "command"
"""El tipo con reglas de gobierno propias. Medido en GitHub: 27008 de 33472 archivos, ~81 %, tres
veces el siguiente. Es donde se concentra el riesgo, y por eso es el unico con reglas propias."""

TIPO_HOOK_A_REVISAR = "http"
"""Un hook `http` manda el evento a un servicio EXTERNO con cabeceras propias.

NO SE LE ANADE CAMPO DE GOBIERNO a proposito: no se encontro ni un uso real -- muestra pequena -- y un
campo de gobierno para un caso que nadie tiene es sobre-ingenieria, que ademas envejece sin que nadie
lo ejercite. Lo que se hace en su lugar es AVISAR cuando aparezca uno, para decidir con un caso
delante en vez de con una hipotesis."""

PATRON_DESCARGA_EN_EJECUCION = (
    r"(?i)\b(curl|wget|iwr|invoke-webrequest)\b[^\n|]*\|[^\n]*\b(bash|sh|zsh|python\d?|node)\b"
)
"""Un comando que DESCARGA Y EJECUTA en tiempo de ejecucion.

POR QUE ES LO MAS GRAVE que puede llevar un hook, junto con el script de fuera del artefacto: se salta
el sello POR COMPLETO. El `hooks.json` iria firmado y su digesto seria perfecto, y lo que se ejecuta
se baja de internet en el momento -- no existia cuando se firmo, no lo reviso nadie y puede ser
distinto en cada maquina. La firma diria muchisimo menos de lo que aparenta."""

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
