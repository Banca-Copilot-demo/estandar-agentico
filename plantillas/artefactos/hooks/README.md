# Hooks

**Van SIEMPRE dentro de un plugin, y son UNOS por plugin.** Es el tipo con el control más estricto, y por
una razón concreta: **es el único que ejecuta código propio sin que nadie lo invoque**. No hay paso de
instalación donde intervenir ni momento en que alguien decida usarlo.

Y el argumento para exigir plugin es aquí **más fuerte** que en el `mcp`: las entradas de hook **se suman
entre capas de configuración** en vez de reemplazarse, así que unos hooks fuera de un plugin **no los
quita ninguna capa superior**. Lo único que queda es apagarlos todos, que es todo o nada.

## Dos archivos, dos sitios

| Archivo | Dónde va |
|---|---|
| `hooks/hooks.json` | dentro del plugin |
| El bloque `hooks` de aprobación | se **pega** en el `GOVERNANCE.json` del plugin |

```json
"hooks": {
  "approval": {
    "approved_by": "<<EQUIPO_DE_SEGURIDAD>>",
    "date": "<<FECHA>>",
    "review_by": "<<FECHA_DE_REVISION>>",
    "security_review": true
  }
}
```

## Los scripts van DENTRO del artefacto

`${CLAUDE_PLUGIN_ROOT}` apunta a la raíz del plugin, así que el script viaja en el paquete, entra en el
digesto y se revisa al aprobar.

**Lo contrario es el error más grave que puede tener un hook:** referenciar un script del repositorio de
quien instala. Ese archivo **no viaja en el paquete, no entra en el digesto y nadie lo revisó**. La firma
cubriría el JSON y no lo que se ejecuta — y una firma que dice menos de lo que aparenta es peor que
ninguna. El gate lo rechaza.

## Lo que el gate exige

**`timeoutSec` siempre**, y por debajo del techo del estándar. Un hook sin tope puede colgar el cliente de
quien lo instale.

**Declararse en el inventario del gobierno.** Un componente que ejecuta código no entra por sorpresa.

**Aprobación de seguridad**, con fecha y fecha de revisión.

## Dos avisos que da el gate y conviene entender

**El evento que ve todo lo que se escribe.** Hay un evento de ciclo de vida que recibe **cada mensaje del
desarrollador**. Es un canal de salida de datos por diseño, así que si el script accede a la red hay que
mirarlo dos veces. El gate avisa; la decisión es de la persona que aprueba.

**Un interruptor de seguridad apagado por defecto.** Una variable de entorno del tipo `BLOCK_ON_THREAT` en
`false` es un control desactivado en un archivo que nadie abre.

## Y un tipo de hook que el estándar NO admite sin excepción

Existen manejadores que **deciden con un modelo** en lugar de ejecutar un comando. Son útiles, pero rompen
la premisa de que un hook es determinista: su decisión es probabilística y **nadie en la industria sabe
todavía cómo evaluarlos**. Requieren excepción explícita con aprobación de seguridad. Los que sí se
admiten sin excepción son los de comando, los de petición HTTP y los que invocan una herramienta MCP.
