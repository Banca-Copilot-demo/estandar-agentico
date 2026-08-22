# Esquemas EXTERNOS — copia fijada, no editar

Lo que hay aqui **no es nuestro**: son esquemas publicados por una especificacion de terceros,
copiados literalmente para poder validar **sin red y de forma reproducible**.

## Por que fijados y no referenciados en vivo

Cuatro razones, y la segunda es la que manda:

1. **El gate no necesitaria red.** La descarga tardo 2,6 s medidos. Un runner sin salida a internet
   —o ese host caido— convertiria una validacion en un fallo ajeno al cambio que se revisa, y
   bloquearia un merge.
2. **Atestamos el veredicto.** Un veredicto que depende de un archivo remoto **no es reproducible**:
   el mismo commit validado hoy y en seis meses podria dar resultados distintos, y la atestacion
   dejaria de probar algo verificable.
3. **Es la misma cadena de suministro que ya rechazamos.** Prohibimos `version_pin: latest` en los
   `mcp` por esto exacto. Aceptar un esquema remoto sin fijar seria incoherente: quien controle esa
   URL controlaria el veredicto del gate.
4. **El fallo llegaria en bloque.** Si endurecen el esquema, todos los repositorios empiezan a
   fallar a la vez sin que nadie haya tocado nada. Fijado, el cambio entra con su pull request.

## Como se mantiene al dia

Un job programado descarga el oficial y **avisa si difiere de esta copia**. No bloquea: solo nos
entera. Asi la copia no envejece a ciegas y la red se queda fuera del camino critico.

## Contenido

| Archivo | Origen | sha256 | Copiado |
|---|---|---|---|
| `plugin.schema.json` | https://agent-plugins.org/schemas/1.0.0/plugin.schema.json | `0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883` | 20-ago-2026 |

### Una contradiccion del oficial que conviene conocer

`plugin.schema.json` declara `additionalProperties: false`, pero **la prosa de Agent Plugins dice
que los clientes deben ignorar los campos desconocidos**. Se contradicen.

Validar contra el oficial tal cual seria **mas estricto que la propia especificacion**: rechazaria
un campo que un cliente conforme deberia tolerar. Por eso el gate trata el campo desconocido como
**aviso y no como error** — alineado con la prosa, y coherente con el criterio que ya aplicamos:
estricto donde se bloquea, permisivo donde se avisa.
