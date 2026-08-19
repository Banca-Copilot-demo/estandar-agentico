---
name: crear-artefacto-agentico
description: Crea un artefacto agentico conforme al estandar agentico -skill, agente, prompt, mcp o instructions- dentro del plugin del repositorio actual, rellena su metadata de gobierno, lo valida en local y abre el pull request. Usalo cuando alguien quiera crear, anadir, publicar o registrar un skill, un agente, un comando, una configuracion MCP o instrucciones para Copilot.
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
linea— y ejecuta `scripts/crear-plugin.sh`.

## Paso 2 · Determina el tipo

Aplica el arbol de `references/arbol-de-decision.md`. **La primera pregunta que de «si» decide.**
No inventes tipos ni combines dos.

## Paso 3 · Genera el esqueleto

Ejecuta `scripts/generar.sh <tipo> <nombre>`. El script copia el esqueleto de `assets/` y
**hereda el `id` y el `owner` del plugin**, asi que esos no se teclean.

## Paso 4 · Completa lo que solo el desarrollador sabe

Pidele `description` y `when_to_use`. Son los dos campos que ningun script puede deducir, y de
la `description` depende que el modelo sepa cuando usar el artefacto: sin ella, es codigo muerto
que ademas ocupa contexto en cada peticion.

## Paso 5 · Valida antes de abrir el PR

Ejecuta `scripts/validar.sh`. Si falla, corrige y repite. **No abras el PR en rojo**: el gate
va a rechazarlo igual y el ciclo es mas lento.

## Paso 6 · Abre el pull request

Ejecuta `scripts/abrir-pr.sh`. El PR se abre **con la identidad del desarrollador**, no con una
cuenta de servicio: la trazabilidad importa.

## Lo que no debes hacer

- No modifiques `GOVERNANCE.json` salvo para anadir el artefacto al inventario.
- No pongas credenciales en ningun archivo: se referencian (`${input:...}`, `oauth`).
- No declares `status` distinto de `draft`: el estado lo derivan los gates.
