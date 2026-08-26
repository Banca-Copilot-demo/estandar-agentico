"""Reglas del plugin: manifiesto Agent Plugins 1.0, gobierno del conjunto e inventario.

EL PLUGIN ES OPCIONAL, SIEMPRE. Es una decision de EMPAQUETADO, no de riesgo: ningun tipo lo
exige por ser peligroso, porque el riesgo de cada uno lo cubre otro control que funciona con
plugin o sin el — `allowedMcpServers` y los `scopes` de la credencial para `mcp`, el `CODEOWNERS`
de seguridad para `hooks`, y G3 mas los permisos del repositorio para los datos sensibles.

PURAS (G5): reciben datos ya parseados y devuelven hallazgos.
"""
from __future__ import annotations

import re

from validador_agentico.dominio.especificacion import (
    CAMPOS_PLUGIN_OBLIGATORIOS,
    CAMPOS_PLUGIN_PERMITIDOS,
    PATRON_SEMVER,
    RUTA_MANIFIESTO_UNIFICADA,
)
from validador_agentico.dominio.hallazgo import Hallazgo, Inventario, aviso, error


def revisar_manifiesto(ruta_relativa: str, manifiesto: dict) -> list[Hallazgo]:
    """El `plugin.json` conforme a Agent Plugins 1.0, cuando el repositorio declara uno."""
    hallazgos: list[Hallazgo] = []
    if ruta_relativa != RUTA_MANIFIESTO_UNIFICADA:
        hallazgos.append(aviso(ruta_relativa,
                               f"esta ruta la reconoce Copilot pero NO Claude Code. Usa "
                               f"`{RUTA_MANIFIESTO_UNIFICADA}` para que el mismo plugin sirva "
                               "a los dos clientes"))
    hallazgos += [
        error(ruta_relativa, f"falta el campo obligatorio `{campo}`")
        for campo in CAMPOS_PLUGIN_OBLIGATORIOS if campo not in manifiesto
    ]
    sobrantes = sorted(set(manifiesto) - CAMPOS_PLUGIN_PERMITIDOS)
    if sobrantes:
        hallazgos.append(error(ruta_relativa,
                               f"campos de primer nivel no permitidos por la especificacion: "
                               f"{sobrantes}. Lo especifico del estandar va en `extensions` bajo "
                               "namespace DNS-inverso"))
    version = manifiesto.get("version")
    if version and not re.fullmatch(PATRON_SEMVER, str(version)):
        hallazgos.append(error(ruta_relativa, f"`version` no es SemVer: {version}"))
    return hallazgos


def revisar_gobierno(gobierno: dict, manifiesto: dict | None) -> list[Hallazgo]:
    """El `GOVERNANCE.json` de la unidad, con plugin o sin el.

    SIEMPRE ES EL DE ESTA UNIDAD. Hubo un modo `heredado` que omitia `id` y `version` porque el
    gobierno podia ser el del repositorio que aloja al artefacto suelto; se retiro con la herencia,
    asi que los dos campos describen lo que se publica aqui y se comprueban sin excepcion.
    """
    donde = "GOVERNANCE.json"
    hallazgos: list[Hallazgo] = []
    if not (gobierno.get("owner") or {}).get("team"):
        hallazgos.append(error(donde, "`owner.team` vacio: el dueno debe ser RESOLUBLE contra la "
                                      "organizacion. Un artefacto sin dueno real no se puede "
                                      "deprecar, corregir ni retirar"))
    # EL AVISO DEL `status` RETIRADO YA NO SE CONDICIONA A NADA, y antes si: vivia detras de un
    # `if heredado` que retornaba temprano, para no repetirlo una vez por cada artefacto suelto que
    # compartia el gobierno de la raiz. Sin herencia no hay nada que compartir -- cada unidad trae el
    # suyo --, asi que cada aviso corresponde a un archivo distinto y ninguno se duplica.
    hallazgos += _revisar_estado_retirado(donde, gobierno)
    identificador = gobierno.get("id")
    nombre_plugin = (manifiesto or {}).get("name")
    if identificador and nombre_plugin and identificador != nombre_plugin:
        hallazgos.append(error(donde, f"`id` ({identificador}) no coincide con `name` de "
                                      f"plugin.json ({nombre_plugin})"))
    hallazgos += _revisar_version_del_paquete(donde, gobierno, manifiesto)
    return hallazgos


CAMPO_ESTADO_RETIRADO = "status"
"""El campo de estado que el gobierno declaraba y que ya no forma parte del estandar."""


def _revisar_estado_retirado(donde: str, gobierno: dict) -> list[Hallazgo]:
    """`status` en el gobierno: se ACEPTA, se DESCARTA y se avisa. Nunca bloquea.

    POR QUE SE RETIRO. El estado del ciclo de vida se DERIVA de hechos —gates superados, etiqueta,
    atestacion— y lo publica la ficha del catalogo. Este campo era EDITABLE y decia `draft` mientras
    el catalogo decia `certified` del mismo artefacto: no se contradicen, significan cosas distintas,
    pero comparten nombre y quien lo leia podia creer que editandolo movia el estado real. Un campo
    que parece una palanca y no lo es es peor que no tenerlo.

    POR QUE AVISO Y NO ERROR, que es la parte que decide si esto se puede desplegar. El gate es
    comprobacion REQUERIDA en los repositorios de dominio: si la presencia del campo bloqueara, todos
    los repositorios que aun no se han actualizado se pondrian rojos a la vez y —peor— ninguno podria
    mergear NI SIQUIERA el PR que lo quita, porque ese PR tambien pasa por el gate. El estandar no
    puede exigir un cambio que el propio gate impide realizar. El aviso empuja sin cerrar la puerta.

    Y POR QUE HACE FALTA ESTA REGLA ADEMAS DE QUITARLO DEL ESQUEMA: el esquema del gobierno declara
    `additionalProperties: false`, asi que borrar la propiedad convertiria su presencia en ERROR
    automaticamente —justo el bloqueo que hay que evitar—. Por eso el esquema la conserva marcada
    `deprecated` y es esta regla la que emite la senal.

    NO ES el `metadata.status` del frontmatter de un artefacto: ese vive en `envelope.schema.json`,
    lo revisa `reglas_artefacto.revisar_envelope` y sigue vigente.
    """
    if CAMPO_ESTADO_RETIRADO not in gobierno:
        return []
    return [aviso(donde, f"`{CAMPO_ESTADO_RETIRADO}` ya no forma parte del gobierno y se IGNORA: el "
                         "estado del ciclo de vida se DERIVA de los gates y lo publica la ficha del "
                         "catalogo, asi que editarlo aqui no cambiaba nada. Quitalo del archivo; "
                         "para el veredicto de la ultima corrida mira `certification.verdict`")]


def _revisar_version_del_paquete(donde: str, gobierno: dict,
                                  manifiesto: dict | None) -> list[Hallazgo]:
    """`version` en el gobierno: OBLIGATORIA sin plugin, PROHIBIDA con plugin.

    De donde sale la etiqueta es lo unico que decide si un repositorio tiene cadena de publicacion.
    Con plugin sale del `plugin.json`, que es lo que el marketplace resuelve; sin plugin no hay otro
    sitio, y sin ella el repositorio no se etiqueta -- asi que no hay release, ni atestacion, ni ficha,
    y el consumidor no puede verificar nada antes de instalar. Ese era exactamente el estado del
    camino del artefacto suelto: el lineamiento prometia catalogo y sello, y no habia de donde sacar
    la version.

    Y PROHIBIDA CUANDO HAY MANIFIESTO por el motivo de siempre: dos declaraciones de la misma cosa
    divergen, y aqui la divergencia produciria una etiqueta que no corresponde al paquete.
    """
    declarada = gobierno.get("version")
    if manifiesto is not None:
        if declarada:
            return [error(donde, f"declara `version` ({declarada}) y ademas hay un `plugin.json`: "
                                 f"la version del paquete es la del manifiesto, que es lo que el "
                                 f"marketplace resuelve. Dos declaraciones divergen, y la etiqueta "
                                 f"saldria de una de las dos sin saber cual")]
        return []
    if not declarada:
        return [error(donde, "sin `version` y sin `plugin.json`: no hay de donde derivar la etiqueta, "
                             "asi que este repositorio NO se publica -- sin release no hay atestacion "
                             "ni ficha, y quien lo instale no podra verificar que es lo aprobado. "
                             "Declara `version` en SemVer para publicar los artefactos sueltos")]
    return []


def revisar_gobierno_ausente(unidad: str, que_publica: str) -> list[Hallazgo]:
    """Una unidad publicable que no declara su `GOVERNANCE.json`.

    ES UN ERROR Y NO UN SILENCIO, y el silencio era el defecto. Antes esto solo se reclamaba cuando
    la unidad traia `plugin.json`; un artefacto suelto con manifiesto propio se quedaba sin gobierno
    y el gate lo suplia con el de la raiz del repositorio. Medido en `agentes-sdlc`: seis unidades
    publicables y `skills/revisar-jql` acababa con el `owner.team` de la raiz sin declararlo nadie.
    Heredar el dueno por vecindad es exactamente lo que este marco existe para impedir: el dueno es a
    quien se le pide la aprobacion y a quien se le abre el issue.

    `unidad` y `que_publica` van en el mensaje porque el hallazgo se lee en un repositorio con varias
    unidades, y «falta el gobierno» a secas no dice cual ni por que le toca declararlo.
    """
    return [error("GOVERNANCE.json",
                  f"la unidad `{unidad}` se publica por separado -- {que_publica} -- y no declara su "
                  "GOVERNANCE.json. Cada unidad publicable declara el suyo: el dueno, el estado y la "
                  "clasificacion NO se heredan del repositorio que la aloja, o todos los artefactos "
                  "de un repositorio acabarian con el mismo dueno por vecindad")]


def revisar_inventario(declarado: dict, inventario: Inventario) -> list[Hallazgo]:
    """Lo declarado contra el arbol real. Un catalogo que publica un inventario inexistente da
    falsa confianza, que es peor que no publicar nada."""
    return [
        error("GOVERNANCE.json",
              f"inventario: declara {declarado.get(tipo, 0)} `{tipo}` y el arbol real tiene {real}")
        for tipo, real in inventario.como_declarado().items()
        if declarado.get(tipo, 0) != real
    ]


def revisar_ausencia_de_plugin() -> list[Hallazgo]:
    """Sin plugin no hay error: los artefactos quedan gobernados por su propia metadata. Lo que se
    pierde es la ENTRADA AL MARKETPLACE, y conviene que el autor lo sepa.

    El mensaje decia antes que sin plugin no hay distribucion, y era impreciso: un repositorio de
    sueltos SI se publica -- etiqueta, paquete, atestacion y ficha -- si declara su `version` en el
    `GOVERNANCE.json`. Lo unico que no puede tener es entrada de marketplace, porque las entradas de
    un marketplace SON plugins. Decirlo mal empujaba a empaquetar en un plugin para conseguir algo que
    no hacia falta.
    """
    return [aviso(RUTA_MANIFIESTO_UNIFICADA,
                  "sin plugin: los artefactos se gobiernan por su propia metadata y el repositorio se "
                  "publica como paquete suelto -- con atestacion y ficha -- si su GOVERNANCE.json "
                  "declara `version`. Lo que NO puede tener es entrada en el marketplace, ni "
                  "instalarse o bloquearse como conjunto")]
