# Unidad publicable: CONJUNTO SUELTO

Los artefactos de la **raíz** del repositorio, los que no están dentro de ningún plugin. Copia este
`GOVERNANCE.json` a la raíz del repositorio de dominio y añade los artefactos desde
`plantillas/artefactos/`.

## Dónde va cada tipo en la raíz

```
<repositorio>/
├── GOVERNANCE.json                ← este archivo, con `version`
├── skills/<<NOMBRE>>/SKILL.md
├── agents/<<NOMBRE>>.agent.md
└── commands/<<NOMBRE>>.prompt.md
```

**No hay `.mcp.json` ni `hooks/` en esta lista, y no es un olvido:** esos dos tipos van **siempre dentro
de un plugin**. Un `mcp` suelto pierde la posibilidad de revocarse por artefacto, y unos `hooks` sueltos
**se suman** a los demás sin que ninguna capa superior los pueda quitar. El gate los rechaza aquí.

## La diferencia que importa: aquí `version` SÍ va

Es lo contrario que en un plugin. Sin manifiesto no hay otro sitio donde declarar con qué versión se
publica el conjunto — y **sin `version` los artefactos de la raíz no se empaquetan**: quedan huérfanos,
sin etiqueta, sin sello y sin ficha en el catálogo. El gate avisa de eso explícitamente.

## Lo único que un conjunto suelto no puede tener

**Entrada en el catálogo instalable.** Las entradas de un marketplace son plugins. Todo lo demás lo
conserva: dueño, versión, estado, etiqueta, paquete, atestación y ficha en el catálogo de metadata.

Y se instala igual de bien: un skill suelto tiene comando nativo de instalación fijable a una versión.
