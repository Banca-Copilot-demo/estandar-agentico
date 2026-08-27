# Recorrido de publicación y certificación

Tres pruebas de punta a punta contra la organización real. Comprueban lo que BCP exige: **un artefacto
Conforme no se distribuye masivamente, y uno Certificado sí** — y que la frontera entre ambos la decide
únicamente si sus evaluaciones pasan.

Ejecutadas por última vez el **2026-08-27**. Los resultados de esa ejecución están en
[Línea base medida](#línea-base-medida); una reejecución que se desvíe de ahí es una señal, no un ruido.

> **Esta carpeta tiene dos mitades.** Este documento cubre el camino de **publicación**: cómo un cambio
> llega a ser instalable y con qué estado. `camino-instalacion.sh` cubre el de **instalación**: descarga
> el release real, verifica su atestación y comprueba los casos negativos. Ninguna de las dos sustituye
> a la otra.

---

## Antes de empezar

**Lo que hace falta:**

| | |
|---|---|
| `gh` autenticado | con permiso de `--admin` sobre `Banca-Copilot-demo` |
| `copilot` y `claude` | los dos clientes; las pruebas verifican la instalación en ambos |
| Credenciales de Port | `PORT_CLIENT_ID` y `PORT_CLIENT_SECRET` en `C:\PROYECTO_TRACK_AGENTICO_BCP\.env` |

```bash
set -a; . /c/PROYECTO_TRACK_AGENTICO_BCP/.env; set +a
```

Cárgalas así, como variables. **Nunca las imprimas** ni las pases por línea de comandos: un
`clientSecret` en un argumento queda en el historial del shell y en la tabla de procesos.

### Tres reglas que ahorran tiempo

**Se reutilizan artefactos que ya existen; no se crean nuevos.** Cada prueba sube la versión de un
artefacto vivo de `agentes-sdlc`. Crear artefactos de usar y tirar llena la organización de basura que
**no se puede limpiar**: las etiquetas están protegidas por *ruleset* y `gh release delete --cleanup-tag`
responde `HTTP 422: Cannot delete this tag`. Es la protección funcionando — las etiquetas anclan las
atestaciones — pero significa que cada prueba deja rastro permanente.

| Prueba | Artefacto | Por qué ese |
|---|---|---|
| Caso 1 y 3 | una unidad **sin suites** | el 1 la deja así; el 3 se las añade |
| Caso 2 | una unidad **con suite verde** | mide el camino hasta `certified` sin escribir nada nuevo |

**Qué unidad toca cada vez cambia, y por eso la tabla no las nombra.** Cuando el caso 3 le añade
evaluaciones a una unidad, ésa deja de servir para el caso 1 en la siguiente ejecución: ya no está sin
suites. En la ejecución del 2026-08-27 se usó `plugins/contratos` para los casos 1 y 3 y
`skills/revisar-jql` para el 2, porque `plugins/migracion` había recibido su suite en la anterior.
Antes de empezar, mira qué unidades tienen suites:

```bash
cd /c/PROYECTO_TRACK_AGENTICO_BCP/demo-bcp-copilot/agentes-sdlc
for d in plugins/*/ skills/*/; do
  echo "$d $(grep -h '\"version\"' $d.claude-plugin/plugin.json) suites=$(find $d -name promptfooconfig.yaml | wc -l)"
done
```

**Los merges necesitan `--admin`.** La política de rama exige revisión de *code owner* y nadie aprueba
su propio PR:

```bash
gh pr merge <n> --repo Banca-Copilot-demo/agentes-sdlc --squash --delete-branch --admin
```

**Si un `push` no dispara nada, ciérra y reabre el PR.** Está medido: un commit llegó al remoto y GitHub
no generó el evento. Comprueba primero que el commit está arriba; si está y no hay ejecución, fuerza el
evento con `gh pr close <n> && gh pr reopen <n>`.

### Cómo se lee una ficha del catálogo de metadata

```bash
python /c/PROYECTO_TRACK_AGENTICO_BCP/demo-bcp-copilot/estandar-agentico/pruebas-e2e/leer_ficha.py demo.sdlc.planificar-migracion
```

```
FICHA_STATUS="certified"
FICHA_REF="demo.sdlc.migracion--v0.1.3"
FICHA_MARKETPLACE="True"
```

Dos cosas que confunden si no se avisan: el campo del *blueprint* se llama **`status`**, no `estado`; y
**no existen `version` ni `etiqueta`** — la versión se lee dentro de `ref`. `FICHA_MARKETPLACE` vale
`"True"` o `"False"` con mayúscula, porque sale de `str()` de Python: comparar contra `"true"` no
coincide nunca.

### Cómo se lee el catálogo instalable

```bash
gh api repos/Banca-Copilot-demo/marketplace/contents/.claude-plugin/marketplace.json --jq '.content' \
  | base64 -d | python -c "import json,sys; d=json.load(sys.stdin); [print(p['name'], p['version']) for p in d['plugins']]"
```

---

## Caso 1 · Sin evaluaciones termina en Conforme y no se distribuye

**Qué comprueba:** que un artefacto sin suites se publica, se sella y **no llega al catálogo**.

**Por qué importa:** es el requisito de BCP. Publicar no se bloquea; **distribuir sí**. Un artefacto cuyo
comportamiento nadie ha medido no puede repartirse por la organización.

### Pasos

1. Rama desde `main` de `agentes-sdlc`. Cambia algo real en
   `plugins/migracion/skills/planificar-migracion/SKILL.md`.
2. Abre el PR **sin subir la versión**, a propósito.
3. Sube la versión en `plugins/migracion/.claude-plugin/plugin.json`.
4. Mergea con `--admin`. La cadena `Etiquetar → Publicar` arranca sola.

### Criterios de aprobación

| # | Comprobación | Aprueba si |
|---|---|---|
| 1 | Gate sin subir versión | **falla**, y el mensaje nombra la unidad y su versión actual **sin proponer un número** |
| 2 | Evaluación tras el fallo | `comportamiento` sale **`skipping`** — no se gasta inferencia sobre algo que ya se sabe que no avanza |
| 3 | Gate con la versión subida | los dos checks en verde |
| 4 | Acotado de la evaluación | dice `sin suites de evaluacion: se publicara como Conforme` **aunque el repositorio tenga suites de otras unidades** |
| 5 | Release | `gh release list` lo muestra marcado **`Pre-release`** |
| 6 | Catálogo instalable | **sigue mostrando la versión anterior** |
| 7 | Ficha | `FICHA_STATUS="conformant"`, `FICHA_MARKETPLACE="False"`, `FICHA_REF` = **su propia etiqueta** |
| 8 | Fichas ajenas | las de `revisar-jql` y `contratos` **no cambian** — regresión del defecto 1 |
| 9 | Instalación | instala la versión **anterior**, y el contenido nuevo **no aparece** en el disco |

La comprobación 9 es la que de verdad demuestra el requisito. No basta con que el comando falle: hay que
verificar que **el contenido conforme no llega al cliente**.

```bash
cd /c/PROYECTO_TRACK_AGENTICO_BCP/demo-bcp-copilot/consumidor-prueba
copilot plugin install demo.sdlc.migracion@agentico
grep '"version"' /c/Users/hvidalsi/.copilot/installed-plugins/agentico/demo.sdlc.migracion/.claude-plugin/plugin.json
grep -c "<frase que solo esta en la version nueva>" /c/Users/hvidalsi/.copilot/installed-plugins/agentico/demo.sdlc.migracion/SKILL.md
```

Aprueba con la versión **anterior** y un conteo de **0**.

---

## Caso 2 · Con evaluaciones que pasan termina en Certificado y sí se distribuye

**Qué comprueba:** el camino completo hasta `certified`, y que el artefacto se instala en **los dos
clientes**.

**Por qué importa:** es la otra mitad del requisito. Si certificar no abriera la distribución, el estado
no significaría nada.

### Pasos

Igual que el caso 1, sobre `skills/revisar-jql` — que ya trae su suite — subiendo a la versión siguiente.

### Criterios de aprobación

| # | Comprobación | Aprueba si |
|---|---|---|
| 1 | Evaluación en el PR | **`Successes: 3, Failures: 0`**, y el log dice `unidades tocadas por el cambio: skills/revisar-jql` |
| 2 | Acotado por unidad | **no corre** la suite de `plugins/referencia` |
| 3 | Descubrimiento del artefacto | el log dice `skill disponible: revisar-jql` — sin esto se estaría midiendo el modelo base, no el artefacto |
| 4 | Guardián de la promoción | **no vuelve a evaluar**: comprueba que la unidad trae suites y que la comprobación de comportamiento del commit quedó en verde |
| 5 | Promoción | se encadena sola y el release queda **sin marca de prelanzamiento** |
| 6 | Ficha | `FICHA_STATUS="certified"`, `FICHA_MARKETPLACE="True"` |
| 7 | Catálogo instalable | muestra la versión **nueva** |
| 8 | Instalación en Copilot | llega la versión nueva **con** el contenido nuevo |
| 9 | Instalación en Claude Code | ídem, bajo `~/.claude/plugins/cache/agentico/<nombre>/<version>/` |

```bash
# LOS TRES PASOS, y los tres hacen falta si el artefacto ya estaba instalado. Con `install` a secas el
# cliente responde «is already installed» y deja la version VIEJA en cache, sin error ni aviso.
claude plugin uninstall demo.sdlc.revisar-jql@agentico
claude plugin marketplace update agentico
claude plugin install demo.sdlc.revisar-jql@agentico

# La cache guarda una carpeta por version: comprueba en la NUEVA, y que la vieja siga sin el contenido.
find /c/Users/hvidalsi/.claude/plugins/cache/agentico/demo-sdlc-revisar-jql -name SKILL.md \
  -exec sh -c 'echo "$(basename $(dirname "$1")): $(grep -c "<frase nueva>" "$1")"' _ {} \;
```

En Copilot, borra antes el directorio de la instalación anterior o falla con `Access is denied`:

```bash
rm -rf /c/Users/hvidalsi/.copilot/installed-plugins/agentico/demo.sdlc.revisar-jql
copilot plugin install demo.sdlc.revisar-jql@agentico
```

> **Si el catálogo no recoge la versión promocionada**, regenera el índice a mano y vuelve a mirar:
> `gh workflow run regenerar-indice.yml --repo Banca-Copilot-demo/marketplace`. Que haga falta es el
> defecto 6; si ya está corregido, no debería hacer falta.

---

## Caso 3 · Añadir evaluaciones lleva de Conforme a Certificado

**Qué comprueba:** que un artefacto ya publicado en Conforme puede certificarse después, y que lo que
antes no se instalaba pasa a instalarse.

**Por qué importa:** es el camino que recorrerá la mayoría. Casi nadie escribe las evaluaciones a la vez
que el artefacto.

### Pasos

1. Añade la suite en `plugins/migracion/skills/planificar-migracion/evals/promptfooconfig.yaml`.
2. Abre el PR **sin subir la versión**.
3. Sube la versión y mergea con `--admin`.

### Criterios de aprobación

| # | Comprobación | Aprueba si |
|---|---|---|
| 1 | Gate sin subir versión | **falla**, y el cambio está **solo dentro de `evals/`** |
| 2 | Evaluación de la suite nueva | pasa, y corre **solo** la de esa unidad |
| 3 | Ficha antes de promocionar | `conformant` / `False`, con la etiqueta nueva |
| 4 | Ficha después | **`certified`** / **`True`**, y `install_hint` pasa a `copilot plugin install …@agentico` |
| 5 | Catálogo instalable | muestra la versión nueva |
| 6 | Instalación | llega la versión nueva **con** el cuerpo que en el caso 1 era inalcanzable |

La comprobación 1 es la razón de ser de este caso. **Añadir evaluaciones obliga a una versión nueva** —
no es burocracia: la suite viaja dentro del paquete sellado, así que el digesto cambia. Y certificar la
versión anterior sería emitir un veredicto sobre unos bytes distintos de los que se firmaron.

> **Si `copilot plugin install` falla con `Access is denied (os error 5)`**, es el directorio de la
> instalación anterior, no el catálogo. `copilot plugin uninstall` falla igual; bórralo a mano:
> `rm -rf /c/Users/hvidalsi/.copilot/installed-plugins/agentico/<nombre>`.

---

## Línea base medida

Ejecución del **2026-08-27** contra `Banca-Copilot-demo`, ya con una sola evaluación por artefacto.

| Etapa | Duración | Referencia |
|---|---|---|
| `conformidad / validar` | 11–16 s | no consume modelo |
| `comportamiento` sin suites | ~11 s | run [33041435193](https://github.com/Banca-Copilot-demo/agentes-sdlc/actions/runs/33041435193) |
| `comportamiento` con suite de 3 casos y juez | 1 m 29 s – 1 m 34 s | runs [33041718421](https://github.com/Banca-Copilot-demo/agentes-sdlc/actions/runs/33041718421) y [33042368836](https://github.com/Banca-Copilot-demo/agentes-sdlc/actions/runs/33042368836) |
| `publicar` (sellar, atestar, ficha) | 16–28 s | run [33042515392](https://github.com/Banca-Copilot-demo/agentes-sdlc/actions/runs/33042515392) |
| `certificable` (el guardián) | 9 s sin suites · **2 m 34 s – 2 m 54 s** con ellas | mismo run |
| `promocionar` | 13–18 s | mismo run |

> **El guardián tarda minutos aunque no evalúe nada, y no es un defecto.** Espera a que la comprobación
> de comportamiento del commit etiquetado termine — la publicación arranca casi a la vez que ella —,
> así que su duración es la de la evaluación que está esperando, no trabajo suyo. Sin suites resuelve
> en 9 s.

Resultados finales de la ejecución:

| | Caso 1 | Caso 2 | Caso 3 |
|---|---|---|---|
| Artefacto | `demo.sdlc.contratos` 0.2.1 | `demo.sdlc.revisar-jql` 0.2.1 | `demo.sdlc.contratos` 0.2.2 |
| Release | Pre-release | promocionado | promocionado |
| Ficha | `conformant` / `False` | `certified` / `True` | `certified` / `True` |
| Marketplace | se quedó en 0.1.2 | subió a 0.2.1 | subió a 0.2.2 |
| Instalación en Copilot | llegó la **0.1.2**, sin el cuerpo nuevo | llegó la 0.2.1 con él | llegó la 0.2.2 con él |
| Instalación en Claude Code | — | llegó la 0.2.1 con él | llegó la 0.2.2 con él |

El caso 1 y el caso 3 son el **mismo artefacto y el mismo contenido**: la frase `Paginacion declarada`
se contó **0 veces** cuando estaba en Conforme y **1 vez** tras certificarse. Mismo comando de
instalación, resultado opuesto, decidido únicamente por si sus evaluaciones pasaron.

**Una desviación de tiempo importa.** Si la evaluación tarda mucho menos de lo esperado y además falla,
sospecha del agotamiento de la cuota de inferencia antes que del artefacto: no se manifiesta como un
error de cuota sino **como casos en rojo**. En esta ejecución, la corrida que dio 2/3 duró 39 s frente a
los 82 s de la que dio 3/3.

---

## Lo que estas pruebas destaparon

Seis defectos. **Los seis terminaban en verde** — ninguno rompía nada visible, y por eso ninguno se
había detectado antes.

| # | Defecto | Síntoma |
|---|---|---|
| 1 | Publicar una unidad reescribía las fichas de **todas** | `revisar-jql` mostraba la etiqueta, el sha y el digesto de `contratos`: el campo que sirve para **verificar integridad** apuntaba a bytes que no eran los suyos |
| 2 | `en_marketplace` era un literal, no un hecho | decía `true` de artefactos que el índice excluía |
| 3 | `promocionar` no recibía las credenciales de Port | el release quedaba distribuido y la ficha seguía diciendo `conformant`: los dos catálogos contando cosas distintas del mismo artefacto |
| 4 | Se evaluaban suites ajenas al repositorio | un repositorio de dominio se ponía rojo por una **plantilla** del estándar, que por construcción no puede pasar |
| 5 | Se colocaban artefactos ajenos en el cliente | mientras se medía un artefacto, el cliente tenía cargados los del asistente de autoría y una plantilla: **contaminaba el entorno de medición** |
| 6 | `promocionar` no avisaba al índice | artefacto **certificado y no instalable** hasta la pasada programada del índice, que es diaria |
| 7 | una suite roja **en una unidad** impedía promocionar **todas las demás** | `revisar-jql` y `referencia`, con 3/3 cada una, se quedaron en Conforme porque la suite de `migracion` estaba roja. Abierto como [estandar-agentico#28](https://github.com/Banca-Copilot-demo/estandar-agentico/issues/28) |

**El defecto 7 se midió en esta ejecución y sigue abierto.** El guardián de la promoción pregunta si la
comprobación `Evaluacion de comportamiento` del commit está en verde, y esa comprobación es **una sola
para todo el repositorio**: el trabajo recorre todas las suites y emite una conclusión. Es el mismo
defecto que el acotado por `subruta` cerró para la pregunta «¿esta unidad trae suites?» pero no para
«¿su suite pasó?». Tiene tres arreglos posibles con costes distintos, y elegir entre ellos es decisión
de BCP: están en el issue.

En la ejecución del 2026-08-27 no bloqueó, pero **por casualidad**: la suite de `migracion` pasó esa
vez. Es decir que hoy la promoción de una unidad depende de que las suites de las demás tengan un buen
día.

### El veredicto de certificación no es reproducible

Es el hallazgo más importante, y **no se arregla con código**: es una decisión de política.

La misma suite, sobre el mismo contenido, sin cambiar el motor:

| Momento | Resultado | Duración |
|---|---|---|
| En el pull request | **3/3** | 82 s |
| En la certificación, ~10 min después | **2/3** | 39 s |
| Reejecutando la certificación | **pasa** | |

El sistema reaccionó correctamente las tres veces — evaluación en rojo, no promociona — pero el estado
final de un artefacto dependió de la tirada.

**Esta medición provocó un cambio de diseño, y por eso la tabla ya no se puede reproducir.** La suite
se ejecutaba dos veces por artefacto: una en el pull request y otra al publicar, sobre el commit
etiquetado. Evaluar dos veces el mismo contenido no daba más garantía — **duplicaba las ocasiones de
que el azar dijera cosas distintas del mismo artefacto**, y gastaba el doble del único token de
inferencia de la organización. La segunda pasada se retiró: hoy **la suite corre una sola vez, en el
pull request**, y la promoción se limita a comprobar que la unidad trae suites y que su veredicto fue
verde. Al reejecutar estas pruebas se verá una sola corrida, no dos.

Lo que el cambio **no** arregla es la causa: una única ejecución tampoco es reproducible. Si cae en un
mal día, el artefacto se queda en Conforme. La diferencia es que ahora el problema está en un solo
sitio, y cualquier remedio se aplica una vez.

**El riesgo no es que un artefacto bueno falle una vez.** Es lo que la gente hará al descubrirlo:
reintentar hasta que salga verde. Y en cuanto reintentar sea la práctica normal, «Certificado» deja de
significar *este artefacto se comporta como promete* y pasa a significar *alguien tuvo paciencia*.

Las tres salidas posibles, sin recomendación porque la decisión es de BCP:

| Opción | Gana | Cuesta |
|---|---|---|
| N corridas impares, gana la mayoría | veredicto estable, y N es una palanca explícita | ×3 o ×5 la inferencia, que ya es el recurso escaso |
| Más ancla determinista y menos juez | reproducible y barato | deja de medir lo que solo un juez alcanza |
| Umbral por debajo del 100 % | trivial de implementar | «pasa» pasa a significar «pasa casi siempre» |

---

## Hallazgos operativos del entorno

Dos cosas que no son defectos del código pero cuestan horas si no se saben.

**`gh run rerun` no recoge los cambios de un workflow referenciado con `@main`.** Usa la definición del
run original. Medido: tras corregir la propagación de credenciales, reejecutar el job siguió fallando
igual, con el mismo aviso palabra por palabra. Para verificar un arreglo en un workflow reutilizable hace
falta **una ejecución nueva**, no una reejecución.

**GitHub puede perder el evento de un `push`.** El commit llegó al remoto —verificado por API— y no se
generó ninguna ejecución. Se fuerza cerrando y reabriendo el PR. Ocurrió dos veces en la organización.
Con un check requerido deja el PR bloqueado sin diagnóstico; **con el push de una etiqueta significaría
no publicar sin que nadie se entere.**

**Certificar una versión nueva NO llega a quien ya tenía instalada una anterior.** Medido en el caso 2:
con `demo.sdlc.revisar-jql 0.2.1` ya certificada y en el catálogo, el comando de instalación respondió

```
✔ Plugin "demo.sdlc.revisar-jql@agentico" is already installed (scope: user)
```

y la caché del cliente seguía teniendo **sólo la 0.1.2**. No hubo error, no hubo aviso: el cliente
consideró la petición satisfecha. Para que llegara la versión certificada hicieron falta tres pasos:

```bash
claude plugin uninstall demo.sdlc.revisar-jql@agentico
claude plugin marketplace update agentico     # sin esto, reinstalar vuelve a traer la vieja
claude plugin install demo.sdlc.revisar-jql@agentico
```

En Copilot el síntoma es distinto y más honesto: reinstalar sobre una instalación previa falla con
`Access is denied (os error 5)` —hay que borrar el directorio a mano—, así que al menos no se queda
callado.

**La consecuencia de gobierno es la que importa, y no es del código.** El estado dice «Certificado y
distribuido», el catálogo ofrece la versión nueva, y sin embargo **el parque instalado se queda donde
estaba**. Distribuir no es adoptar. Cualquier cosa que dependa de que una corrección llegue de verdad
—retirar una versión con un defecto, cerrar una capacidad externa— necesita un mecanismo de
actualización que hoy no existe en el marco: los estados gobiernan lo que el catálogo **ofrece**, no lo
que las máquinas **tienen**.

---

## Pendientes conocidos

**El enum `status` del blueprint de Port no tiene `suspended`.** Sus valores son `draft`, `conformant`,
`certified`, `deprecated` y `retired`. No afecta a estas tres pruebas, pero **bloquea los flujos 4 a 10**
del ciclo de vida en cuanto se implementen.

**`evals/` viaja dentro del paquete sellado.** El gate lo avisa: `la carpeta evals/ existe y el artefacto
no la referencia: viaja en el paquete y no se usa`. Es aviso y no error, así que no bloquea. Tiene una
consecuencia buscada —añadir evaluaciones cambia el digesto, y por eso exige versión nueva— y otra no
buscada: el consumidor se descarga unas pruebas que no va a ejecutar.

**Hay una ficha rezagada en Port, de antes de que la ficha fuera por artefacto.** `demo.sdlc.catalogo-datos`
declara `ref: demo.sdlc.catalogo-datos--v0.1.0` y `en_marketplace: True`, mientras el artefacto real de
esa unidad —`demo.sdlc.catalogo-datos.mcp`— va por `--v0.3.0`. No es una regresión de estas pruebas: es
una entidad de nivel de plugin que dejó de escribirse cuando la unidad de la ficha pasó a ser la
capacidad. Conviene decidir si se borra o se rellena, porque hoy el catálogo de metadata tiene dos
fichas de la misma unidad contando versiones distintas.
