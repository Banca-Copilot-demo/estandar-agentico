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

**2. El inventario tiene que cuadrar con el árbol.** Los números de `artifacts` se comparan con lo que hay
de verdad. Si añades un skill y no subes el contador, el gate lo bloquea — y al revés.

**3. Un `mcp` o unos `hooks` obligan a declarar su bloque de aprobación** en el gobierno. Copia el bloque
correspondiente desde `plantillas/artefactos/mcp/` o `plantillas/artefactos/hooks/`, que lo traen con la
forma exacta.

## Sobre `keywords` y los diez campos del manifiesto

La especificación de plugins permite **exactamente diez campos de primer nivel**, y rechaza cualquier otro.
Lo que el estándar necesite añadir va dentro de `extensions`, nunca al nivel raíz — el gate lo comprueba y
el cliente rechazaría el plugin si no.
