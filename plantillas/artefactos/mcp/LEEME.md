# Configuración MCP

**Va SIEMPRE dentro de un plugin, y es UNA por plugin.** No es una convención: es el único tipo que
**añade capacidades ejecutables desde fuera de la organización**, y necesita poder revocarse por
artefacto. Suelto pierde esa posibilidad, y con la política de plataforma que restringe el origen de las
personalizaciones **no llega ni a cargar**.

## Dos archivos, dos sitios

| Archivo | Dónde va | Qué es |
|---|---|---|
| `.mcp.json` | raíz del plugin | La configuración que **lee el cliente** |
| `bloque-de-gobierno.json` | se **pega** dentro del `GOVERNANCE.json` del plugin | El gobierno: dueño de la credencial, aprobación, digesto |

**No se mezclan a propósito.** El `.mcp.json` es un archivo que consumen herramientas de terceros; meterle
claves nuestras nos haría depender de lo estricto que sea cada cliente, y ese fallo lo descubre quien
instala, no el gate.

## Un servidor por plugin

Aunque el formato admita varios en un archivo, **el estándar pide uno**. La razón es la revocación y el
perfil de riesgo: dos servidores en el mismo plugin comparten aprobación, plazo de revisión y suerte —
apagar uno apaga el otro. Con un servidor por plugin, cada uno se aprueba y se retira por su cuenta, y su
plazo de revisión sale de **su propio** perfil.

## Lo que el gate exige y suele fallar

**La referencia tiene que estar FIJADA.** Un `@latest` o una etiqueta móvil significa que el contenido
puede cambiar sin que nadie apruebe nada — es la vía del *rug pull*. Para un servidor remoto no hay
versión que fijar, y por eso se declara `version_pin: "sin-version"` y se acepta **a cambio** de vigilar
el digesto de sus herramientas.

**El `tools_digest` sale de preguntarle al servidor**, no de escribirlo a mano:

```
python -m validador_agentico.digest_mcp <ENDPOINT> --formato json
```

**La credencial va por referencia, nunca literal.** Si el servidor la necesita, se declara **cómo se
obtiene** — una variable de entorno, un secreto, una bóveda — y quién la custodia, que normalmente no es
quien publica el plugin.

**El plazo de revisión sale del riesgo del servidor**: seis meses si puede escribir, doce si sólo lee. Y
`write_operations` es el campo que lo justifica, así que declararlo mal no es un detalle.
