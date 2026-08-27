# Unidad publicable: PLUGIN

Envoltorio de un plugin. Copia esta carpeta a `plugins/<<NOMBRE>>/` del repositorio de dominio y añade
dentro los artefactos que necesites desde `plantillas/artefactos/`.

## Dónde va cada tipo dentro del plugin

```
plugins/<<NOMBRE>>/
├── .claude-plugin/plugin.json     identidad y version del PAQUETE
├── GOVERNANCE.json                dueño, estado, inventario y aprobaciones
├── skills/<<NOMBRE>>/SKILL.md     un directorio por skill
├── agents/<<NOMBRE>>.agent.md     un archivo por agente
├── commands/<<NOMBRE>>.prompt.md  un archivo por prompt
├── .mcp.json                      UNO por plugin — no varios
├── hooks/hooks.json               UNO por plugin
└── evals/promptfooconfig.yaml     suite, co-localizada con lo que evalúa
```

## Tres reglas que el gate comprueba y conviene saber de antemano

**1. `version` va en el manifiesto y NO en el gobierno.** Con `plugin.json` presente, declarar `version`
en `GOVERNANCE.json` es un error: dos declaraciones de lo mismo divergen en cuanto alguien toque una. La
del paquete es la del manifiesto.

**2. El inventario enumera IDS, no cuenta.** `artifacts` lleva la lista de `metadata.id` de cada skill,
agente y prompt, y el gate la compara con el árbol real. Un contador tenía un falso negativo: borrar un
artefacto y añadir otro deja el número igual, así que el gate no veía nada mientras el catálogo publicaba
una lista que ya no existía.

**3. Un `mcp` o unos `hooks` obligan a declarar su bloque de aprobación** en el gobierno. Copia el bloque
correspondiente desde `plantillas/artefactos/mcp/` o `plantillas/artefactos/hooks/`, que lo traen con la
forma exacta. El del `mcp` va **indexado por el nombre del servidor** — la misma clave que `mcpServers` —,
que es lo que permite al gate ver un servidor configurado y no aprobado, o una aprobación que sobrevive a
un servidor que ya no está.

## Sobre `keywords` y los diez campos del manifiesto

La especificación de plugins permite **exactamente diez campos de primer nivel**, y rechaza cualquier otro.
Lo que el estándar necesite añadir va dentro de `extensions`, nunca al nivel raíz — el gate lo comprueba y
el cliente rechazaría el plugin si no.

**La excepción es `mcpServers`.** No está en esos diez, pero es una clave que el **cliente** define y lee:
admite los servidores MCP **inline** en el manifiesto como alternativa al `.mcp.json`. El gate ya no la
rechaza como campo inventado — la **gobierna igual** que si viniera del archivo, con las mismas reglas de
fijado, aprobación y credenciales — y avisa sólo de que **porta a menos sitios** que el archivo. Antes, un
plugin que la usara se llevaba **cero** reglas del `mcp` y salía en verde.

## Y no, no hace falta un `metadata.json`

**No existe** como archivo, ni en este proyecto ni en el ecosistema. Lo que existe es un campo `metadata`
**dentro de `marketplace.json`**, y la documentación oficial lo describe como *«free-form object for your
own fields, such as entitlement or catalog data»* y dice explícitamente que **«Claude Code doesn't read
it»** — es decir, un campo libre que nadie interpreta.

Poner ahí el gobierno sería ponerlo en un sitio donde:

- **nada lo valida**, porque es libre por definición;
- **nada lo lee**, así que no cambia ningún comportamiento;
- **no viaja con la unidad**, porque vive en el repositorio del marketplace y no en el plugin, de modo
  que quedaría fuera del digesto y de la atestación.

El gobierno vive en **`GOVERNANCE.json`**, que sí se valida contra un esquema, sí lo lee el gate, y sí
viaja sellado dentro de la unidad. Crear un archivo nuevo no añadiría ni una comprobación: añadiría un
segundo sitio donde mirar.

*(Única salvedad conocida: `metadata.pluginRoot` en `marketplace.json` sí lo lee el cliente, para resolver
nombres de origen. Es configuración de distribución, no gobierno.)*
