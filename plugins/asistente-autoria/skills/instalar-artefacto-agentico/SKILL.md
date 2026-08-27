---
name: instalar-artefacto-agentico
description: "Instala un artefacto agentico publicado -skill, agente, prompt o mcp- invirtiendo el orden del cliente. Descarga el release del sha, verifica la atestacion y solo entonces instala, con el alcance elegido de forma explicita. Usalo cuando alguien quiera instalar, anadir, consumir o traerse a su repositorio un artefacto del catalogo, cuando quiera comprobar la firma o el sha256 de un artefacto ya publicado, o cuando una instalacion haya fallado con un mensaje que no explica su causa."
license: Proprietary
compatibility: Requiere gh (GitHub CLI), copilot, curl y sha256sum en el PATH
allowed-tools: Bash(gh:*) Bash(copilot:*) Bash(sha256sum:*) Read
metadata:
  id: demo.plataforma.instalar-artefacto-agentico
  owner_team: plataforma-agentica
  owner_contact: plataforma-agentica@ejemplo.dev
  data_classification: internal
  status: draft
  version: "0.3.0"
  standard_version: "7.0.0"
---

# Instalar un artefacto agentico verificando antes de instalar

Los clientes no verifican. Esta medido: el `--help` de `gh skill install` no menciona verificacion
y la documentacion de `copilot plugin install` tampoco. Y el comando es **atomico** -- resuelve,
descarga e instala de una vez --, asi que un desarrollador solo puede *instalar y luego verificar*,
y desinstalar si algo no cuadra. **El valor de este skill es invertir ese orden:** descargar,
verificar, y solo entonces instalar. **No teclees los comandos a mano: usa los scripts.**

## Paso 1 · Pide la ficha de Port

Todo lo que hace falta esta en la ficha del artefacto en el catalogo, y el desarrollador puede
leerla: `install_hint`, `verify_hint`, `sha256_archivo`, `status`, `tipo`, `repo`, `ref`, `sha`,
`digest`, `superseded_by`, `sunset_date`. **No adivines ninguno de esos valores** ni los deduzcas
mirando GitHub: la ficha la escribe el CI con lo que salio del sello.

## Paso 2 · Comprueba el estado antes de descargar

Ejecuta `bash scripts/comprobar-estado.sh <status> <superseded_by> <sunset_date>`.

- `retired`: **no se instala**. El script sale con codigo 3 y no hay excepcion; ofrece el sustituto.
- `deprecated`: se puede instalar, pero avisa con `superseded_by` y `sunset_date` y **confirma con
  quien lo pide** antes de seguir.

Una firma valida dice quien publico el artefacto, no si sigue vigente. Ese dato solo esta aqui.

## Paso 3 · Pregunta el alcance, no lo elijas tu

- **skill**: `gh skill install` acepta `--scope {project|user}` y por defecto es **`project`**.
  `project` deja el archivo **dentro del repositorio del consumidor**, asi que afecta a todo el
  equipo; `user` va al home y solo afecta a quien instala. Es la decision que afecta a otros:
  **preguntala siempre en voz alta.**
- **plugin de Copilot**: `copilot plugin install` es **siempre de alcance de usuario**. No existe
  alcance de proyecto para plugins, asi que aqui no hay nada que preguntar.

## Paso 4 · Descarga y verifica

Ejecuta `bash scripts/verificar-paquete.sh <repo> <ref> <sha> <directorio-destino>`.

El script anade `--signer-repo Banca-Copilot-demo/estandar-agentico` a `gh attestation verify`.
**Sin esa opcion la verificacion falla** con `Error: verifying with issuer "sigstore.dev"`, un
mensaje que no nombra al firmante: el paquete sale del repositorio del dominio, pero lo firma el
workflow reutilizable del estandar.

Si la verificacion falla, **no se instala**. No hay atajo.

### Prompts e instructions no viajan en el paquete

Un `prompt` y unas `instructions` no van dentro de un plugin -- ni Agent Plugins v1 ni los cinco
componentes de Copilot los incluyen --. Se traen fijados al `sha` y se comprueban contra el
`sha256_archivo` de la ficha:

`bash scripts/verificar-archivo.sh <repo> <sha> <ruta-en-el-repo> <sha256_archivo> <destino>`

## Paso 5 · Si es un mcp, di quien da la credencial ANTES de instalar

Ejecuta `scripts/decir-quien-da-la-credencial.sh <mecanismo> <dueno> <url> <entitlement>` con lo que
la ficha declara en `credential_owner` y `access_request_url`.

**El orden es el punto.** El cliente va a pedir un token en cuanto el mcp se active, y el
`owner_team` de la ficha es quien PUBLICO el artefacto, no quien custodia la credencial. Si el dato
llega despues del prompt, el desarrollador ya esta bloqueado.

Con `oauth` no hay nada que pedir: se autentica con su propia identidad.

## Paso 6 · Instala

Ejecuta `bash scripts/instalar.sh <alcance> <directorio-verificado> <install_hint...>`, con el
`install_hint` **tal cual** viene en la ficha. El script exige el comprobante que escribio el paso
4: sin el, se niega a instalar.

## Paso 7 · Si algo falla, traduce el mensaje

Ejecuta `bash scripts/explicar-fallo.sh "<texto pegado>"`. Los tres fallos conocidos son opacos por
si mismos:

- Rechazo con `strictKnownMarketplaces`: es una **politica administrada** de la organizacion, y el
  mensaje no dice que lo sea. No se arregla en la maquina del desarrollador.
- `verifying with issuer "sigstore.dev"`: falta `--signer-repo`; el mensaje no nombra al firmante.
- `sha256` que no coincide: el contenido **no es el que se sello**. No se instala ni se copia al
  repositorio del consumidor.

## Lo que no debes hacer

- No instales antes de verificar, ni "para probar": el comando de instalacion es atomico y lo que
  entra ya esta dentro.
- No elijas el alcance en silencio, y menos el que por defecto toca a todo el equipo.
- No inventes valores que estan en la ficha: `repo`, `ref`, `sha`, `digest` y `sha256_archivo`
  vienen del sello.
- No invoques los scripts por su bit de ejecucion: usa `bash <ruta>`. El bit no sobrevive a un
  checkout desde Windows y da `Permission denied` con codigo 126.
