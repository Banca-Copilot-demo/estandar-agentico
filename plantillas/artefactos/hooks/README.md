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

## La estructura, que es donde más se falla

`hooks` → **evento** → lista de **grupos**; y cada grupo, con su `matcher` opcional, lleva una lista
`hooks[]` de **acciones**. El grupo decide **cuándo** corre; la acción, **qué** corre y con qué tope.

Los cinco tipos de acción son `command`, `http`, `mcp_tool`, `prompt` y `agent`. `command` es el dominante
con diferencia: **27008 de 33472** archivos medidos en GitHub, un 81 %, tres veces el siguiente.

### `timeout`, no `timeoutSec` — y va en la ACCIÓN

Este estándar **exigía `timeoutSec` a nivel de grupo, y ese campo no existe**. El cliente lo ignora, así
que el hook corría con el timeout **por defecto** de su tipo mientras quien lo escribió creía haber puesto
un tope de cinco segundos:

| tipo | por defecto |
|---|---|
| `command`, `http`, `mcp_tool` | 600 s |
| `prompt` | 30 s |
| `agent` | 60 s |

Diez minutos de cliente bloqueado. El campo real es **`timeout`**, en segundos, **dentro de cada acción**.
`timeoutSec` se sigue aceptando con aviso mientras dure la migración — hay 908 repositorios públicos que
arrastran el mismo error, así que va a llegar de fuera — y pasará a error cuando ningún `hooks.json` de un
repositorio de dominio lo declare.

### Los eventos son una lista cerrada de 31

Y el motivo es que **un evento mal escrito no falla: simplemente no dispara nunca**. `PostToolUSe` instala
bien, ejecuta bien y no hace nada, y el autor cree que su hook está activo. Sólo el esquema puede
atraparlo. Ojo con las dos grafías del ecosistema: Copilot llama `userPromptSubmitted` a lo que aquí es
`UserPromptSubmit`, y **no son intercambiables**.

## Lo que el gate exige

**`timeout` en cada acción**, y por debajo del techo del estándar. Un hook sin tope efectivo puede colgar
el cliente de quien lo instale.

**Que el comando apunte dentro de la unidad**, con `${CLAUDE_PLUGIN_ROOT}/…`. Una ruta absoluta de una
máquina no existe en la de nadie más, y un binario suelto se resuelve contra un directorio de trabajo que
el artefacto no controla: en los dos casos se ejecuta algo que no se firmó.

**Que el comando no descargue nada en ejecución.** Un `curl … | bash` se salta el sello por completo: el
JSON iría firmado con un digesto perfecto y lo que corre se baja de internet en ese momento.

**Aprobación de seguridad** en el `GOVERNANCE.json`, con fecha y fecha de revisión. Sustituye a la
declaración en el inventario: los hooks **no tienen identidad individual** — se distinguen por evento y
`matcher`, no llevan `id` —, así que enumerarlos no enumeraba nada y el número no podía ser otro que 0 o
1. Un componente que ejecuta código sigue sin entrar por sorpresa; lo que cambia es que ahora entra con un
nombre y una fecha detrás en vez de con un número.

## Tres avisos que da el gate y conviene entender

**Un hook `http`.** Manda el evento a un servicio **externo** con cabeceras propias, o sea una salida de
datos que no pasa por ningún otro control del estándar. No se le añade campo de gobierno **a propósito**:
no encontramos ni un uso real, y gobernar una hipótesis es inventarse un control que nadie ejercita. El
gate avisa para que se revise a mano; si esto se repite, ése será el momento de escribir la regla.

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
