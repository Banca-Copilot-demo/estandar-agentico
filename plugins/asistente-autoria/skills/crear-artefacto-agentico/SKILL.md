---
name: crear-artefacto-agentico
description: Crea un artefacto agentico conforme al estandar agentico -skill, agente, prompt, mcp o hooks- dentro del plugin del repositorio actual, rellena su metadata de gobierno, lo valida en local y abre el pull request. Usalo cuando alguien quiera crear, anadir, publicar o registrar un skill, un agente, un comando, una configuracion MCP o instrucciones para Copilot.
license: Proprietary
compatibility: Requiere git y gh (GitHub CLI) en el PATH
allowed-tools: Bash(git:*) Bash(gh:*) Read Write
metadata:
  id: demo.plataforma.crear-artefacto-agentico
  owner_team: plataforma-agentica
  owner_contact: plataforma-agentica@ejemplo.dev
  data_classification: internal
  status: draft
  version: "0.1.0"
  standard_version: "7.0.0"
---

# Crear un artefacto agentico conforme al estandar

Guia al desarrollador para crear un artefacto y dejarlo listo para revision. **No escribas
los archivos a mano: usa los scripts.** Lo mecanico es determinista; tu trabajo es el juicio.

## Paso 1 · Localiza el plugin

Ejecuta `scripts/detectar-plugin.sh`.

- Si encuentra `.claude-plugin/plugin.json`, **ese es el plugin**. El desarrollador no elige nada.
- Si no lo encuentra, ve al paso 1b.

### Paso 1b · No hay plugin aqui

Averigua primero si el desarrollador esta en el repositorio equivocado. Solo si de verdad es un
**dominio nuevo**, pregunta tres cosas —nombre del dominio, equipo dueno, descripcion en una
linea— y escribe con ellas `.claude-plugin/plugin.json` y `GOVERNANCE.json`. El manifiesto admite
SOLO los diez campos de Agent Plugins 1.0: cualquier otro lo rechaza el gate.

## Paso 2 · Determina el tipo

**La primera pregunta que de «si» decide.** No inventes tipos ni combines dos. El orden va de lo
mas especifico a lo mas general, y el criterio de cada pregunta es COMO SE ACTIVA el artefacto:

1. ¿Configura un servidor MCP para exponer herramientas? -> **mcp**
2. ¿Tiene que interceptar un evento del cliente? -> **hooks**
3. ¿Lo teclea la persona por su nombre, como un comando? -> **prompt**
4. ¿Delega una tarea completa con su propio contexto y sus handoffs? -> **agent**
5. Si ninguna: **skill** — el modelo lo elige cuando su `description` encaja.

**`instructions` NO está en esta lista, y no es un olvido.** Un archivo
`.instructions.md` se aplica solo a lo que casa con su `applyTo`, y **no hay forma de
distribuirlo**: la referencia de plugins de Claude Code dice que un `CLAUDE.md` en la raíz
de un plugin no se carga como contexto, y el conjunto de componentes de un plugin de
Copilot no las incluye. Así que la plataforma no puede publicarlas ni mantenerlas.

Si lo que buscas es *«esto tiene que aplicarse siempre a estos archivos»*, tienes dos
caminos y ninguno es un artefacto nuevo:

- **Si la regla la pone la organización** — «usa siempre arquitectura hexagonal» — el
  artefacto es un **skill** o un **prompt**, que sí viajan en el plugin. Pierdes la
  aplicación automática y ganas que exista de verdad en el repositorio de quien lo instale.
- **Si la regla es local del equipo**, escribe unas `instructions` en tu repositorio y ya
  está: es legítimo y así funciona el cliente. Queda fuera del catálogo, y el gate solo
  avisará de que existen y de su alcance.

Y si la regla **debe ser inviolable**, no puede vivir en una instrucción de ninguna forma:
las instrucciones se combinan sin orden definido y las de organización tienen la
precedencia más baja. Eso necesita un **gate**, no una sugerencia al modelo.

REGLA DE DESISTIMIENTO: si dudas entre `prompt` y `skill`, elige **skill**. Un skill porta en los
seis clientes y un prompt solo en dos, asi que un prompt es un skill con `user-invocable` que
ademas pierde portabilidad. Expresa como skill todo lo que se pueda.

## Paso 3 · Genera el esqueleto

Ejecuta `scripts/generar.sh <tipo> <nombre>`. El script copia el esqueleto de `assets/` y
**hereda el `id` y el `owner` del plugin**, asi que esos no se teclean.

### Cuando el artefacto NO va dentro de un plugin

Si el desarrollador quiere publicarlo **suelto** —porque no viaja con nadie y tiene su propio
ritmo de cambio— usa `scripts/generar.sh --unidad <tipo> <nombre>`. Crea el artefacto **con su
propio manifiesto**, asi que se publica como una unidad independiente: version, etiqueta, digesto y
entrada de catalogo propios.

**No es opcional si se quiere distribuir.** Un artefacto suelto sin manifiesto **no entra al
catalogo**, y esta medido contra los dos clientes: con el contenido en otro repositorio —que es la
topologia real— la instalacion falla con `No plugin.json found in repository`. Y lo que no esta en
el catalogo no lo gobierna el estado: se instalaria igual estuviera certificado, conforme o
suspendido.

Lo que el modo `--unidad` resuelve por su cuenta, y conviene no rehacerlo a mano:

- **El nombre de la unidad** sale del dominio declarado en el `GOVERNANCE.json` de la raiz mas el
  nombre del artefacto. Preguntarlo llevaria a que dos artefactos del mismo dominio acabaran con
  prefijos distintos.
- **La ubicacion.** El skill se queda donde ya vive; un prompt y un agente necesitan directorio
  propio, porque son archivos y no pueden alojar el manifiesto a su lado.
- **El componente declarado.** Un prompt declara `commands` en su manifiesto; skills y agentes no lo
  necesitan. `commands` es el unico componente **sin ruta por defecto** en Copilot, asi que sin
  declararlo el prompt se instala y no lo registra nadie: los archivos aterrizan y no los ve el
  cliente.

**El inventario del `GOVERNANCE.json` de la raiz no se toca**: la unidad no forma parte del conjunto
suelto, se publica sola y de la raiz solo hereda el dueno y el dominio.

## Paso 4 · Completa lo que solo el desarrollador sabe

Pidele `description` y `when_to_use`. Son los dos campos que ningun script puede deducir, y de
la `description` depende que el modelo sepa cuando usar el artefacto: sin ella, es codigo muerto
que ademas ocupa contexto en cada peticion.

## Paso 5 · Valida antes de abrir el PR

Ejecuta `scripts/validar.sh`. Si falla, corrige y repite. **No abras el PR en rojo**: el gate
va a rechazarlo igual y el ciclo es mas lento.

## Paso 6 · Abre el pull request

Abre el pull request con `gh pr create`, **con la identidad del desarrollador** y no con una
cuenta de servicio: la trazabilidad importa. Un pull request por artefacto: el gate rechaza mezclar
tipos que exigen firmantes distintos, porque la aprobacion dejaria de ser atribuible.

## Lo que no debes hacer

- No modifiques `GOVERNANCE.json` salvo para anadir el artefacto al inventario.
- No pongas credenciales en ningun archivo: se referencian (`${input:...}`, `oauth`).
- No declares `metadata.status` del artefacto distinto de `draft`: el estado lo derivan los gates.
  En `GOVERNANCE.json` no lo declares en absoluto — ese campo se retiro del estandar y se ignora.
