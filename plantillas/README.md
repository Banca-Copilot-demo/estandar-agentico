# Plantillas del estándar agéntico

Esqueletos para crear artefactos y unidades publicables que **nacen conformes**. Están pensadas para que
las use el asistente de autoría, y también para copiarlas a mano.

> **La propiedad que las hace útiles: se validan.** Una prueba del validador instancia cada plantilla,
> sustituye los marcadores y **corre el gate sobre el resultado**. Una plantilla que produjera un
> artefacto no conforme sería peor que no tener plantilla: enseñaría a hacerlo mal y con la autoridad de
> venir del repositorio del estándar. Si el estándar cambia y una plantilla se queda atrás, la prueba
> falla.

---

## Cómo se organiza, y por qué así

```
plantillas/
├── unidad-plugin/      el envoltorio de un PLUGIN: manifiesto + gobierno
├── unidad-suelta/      el envoltorio del CONJUNTO SUELTO: solo gobierno, con version
└── artefactos/         UNA plantilla por tipo, se copia dentro de la unidad que sea
    ├── skill/
    ├── agente/
    ├── prompt/
    ├── mcp/
    ├── hooks/
    └── evals/
```

**Los artefactos están separados de los envoltorios a propósito.** Un `SKILL.md` es idéntico dentro de un
plugin o suelto: lo que cambia es **dónde vive y qué lo declara**. Si hubiera una copia de cada tipo por
cada envoltorio, serían diez plantillas para cinco tipos, y divergirían en la primera corrección que
alguien hiciera con prisa.

## Los marcadores

Todos tienen la forma `<<NOMBRE>>`, en mayúsculas y con dobles ángulos. No es decorativo: hace que sean
**buscables con una expresión regular trivial** y que ninguna plantilla se pueda publicar por descuido —
un `<<` en un artefacto real es un error visible, no un valor plausible.

| Marcador | Qué es | Ejemplo |
|---|---|---|
| `<<DOMINIO>>` | El dominio al que pertenece | `sdlc` |
| `<<ID>>` | Identidad completa del artefacto | `demo.sdlc.revisar-jql` |
| `<<NOMBRE>>` | Nombre corto, en minúsculas y guiones | `revisar-jql` |
| `<<EQUIPO>>` | Slug del equipo dueño, **que debe existir en la organización** | `squad-sdlc` |
| `<<CONTACTO>>` | Correo del equipo | `squad-sdlc@ejemplo.dev` |
| `<<VERSION>>` | SemVer, **entre comillas** | `"1.0.0"` |
| `<<DESCRIPCION>>` | Qué hace y **cuándo usarlo** | ver más abajo |

## Cuál elegir: plugin o suelto

La decisión no es estética — determina si se puede **revocar de forma centralizada**:

| Si el artefacto es… | Va en |
|---|---|
| Una configuración **MCP** o unos **hooks** | **`unidad-plugin/` — obligatorio.** Son los dos tipos que cruzan una frontera de control |
| Un skill, prompt o agente que **viaja junto a otros** porque cambia con ellos | `unidad-plugin/` |
| Un skill, prompt o agente **independiente** | `unidad-suelta/` |

Un repositorio puede tener las dos cosas a la vez: plugins en `plugins/` y artefactos sueltos en la raíz.

### Un suelto que se publica **solo** usa el envoltorio de plugin

Cuando un artefacto suelto lleva su propio `.claude-plugin/plugin.json` deja de formar parte del
conjunto suelto: **es una unidad publicable por sí misma**, con etiqueta, paquete y ficha propios. Su
envoltorio es entonces el de `unidad-plugin/` — manifiesto **y gobierno**, y sin `version` en el
gobierno — aunque viva en `skills/<nombre>/` y no en `plugins/`. No hay una tercera plantilla porque
no hay una tercera forma: un plugin de un solo artefacto es un plugin.

**Cada unidad publicable declara su propio `GOVERNANCE.json`, y el gate lo exige.** No se hereda el de
la raíz del repositorio: si se heredara, todos los sueltos de un repositorio acabarían con el mismo
`owner.team` por el mero hecho de vivir ahí, y **en silencio**. El dueño es a quien se le pide la
aprobación y a quien se le abre el issue — atribuirlo por vecindad es justo lo que este marco existe
para impedir. El asistente de autoría lo genera junto al manifiesto, así que declararlo no cuesta nada.

**Dónde va:** en la raíz de la unidad, **hermano de `.claude-plugin/` y nunca dentro**. Ese directorio
lo lee el cliente y su contenido lo fija una especificación que no controlamos; además todo lo que
cuelga de la unidad viaja en el paquete sellado hasta la máquina de quien instala, y el gobierno lleva
equipo dueño, contacto y clasificación del dato.

## Lo que ninguna plantilla puede rellenar por ti

Tres cosas, y son las que deciden si el artefacto sirve:

1. **La `description`.** Es el mecanismo por el que el modelo decide usar el artefacto — o no usarlo. Tiene
   que decir **qué hace y cuándo usarlo**, en tercera persona. Una descripción vaga hace que el artefacto
   se active en tareas ajenas, o que no se active nunca.
2. **El equipo dueño.** Tiene que **existir** en la organización. El gate lo comprueba, y sin dueño
   resoluble no hay a quien avisar cuando el artefacto falle.
3. **La aprobación**, para `mcp` y `hooks`. La firma un equipo de seguridad, con fecha y con fecha de
   revisión. No es un campo que se rellene solo.
