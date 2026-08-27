"""Lo que se le exige al `.mcp.json`: que sus referencias esten FIJADAS. Regla pura sobre datos.

EL ATAQUE QUE CIERRA. Se llama *rug pull* y esta catalogado -- CVE-2025-54136, taxonomia MCP-38 --:
un servidor MCP nace util y de confianza, y despues cambia. Le cambian la descripcion de una
herramienta, o su esquema de entrada, o le redirigen el endpoint. Y como la descripcion de una
herramienta es una INSTRUCCION PARA EL MODELO, cambiarla es inyeccion de prompt sin tocar una linea
de codigo nuestro.

POR QUE EL PROTOCOLO NO AYUDA. MCP no ofrece ninguna primitiva de integridad para las definiciones de
herramientas: sin firma, sin version que el cliente deba fijar, y sin notificacion que los clientes
honren. Ademas, ningun cliente avisa al usuario cuando la definicion de una herramienta cambia.

LO QUE SI PODEMOS EXIGIR: que la referencia del servidor no sea movil. Con `@latest`, el codigo que
se aprobo y el que se ejecuta pueden ser distintos y nadie lo nota -- ni hay release nuevo, ni
revision, ni atestacion --. Medido en los plugins oficiales de AWS, que usan exactamente
`awslabs.aws-iac-mcp-server@latest`.

LO QUE ESTA REGLA NO PUEDE HACER, y conviene no prometerlo: un servidor `http` remoto no tiene
version que fijar, y su contenido puede cambiar en cualquier momento. Ahi la unica defensa posible es
comparar periodicamente el digest de sus herramientas, que es otra pieza.
"""
from __future__ import annotations

import re

from validador_agentico.dominio import declaracion_mcp, forma_mcp, gobierno_mcp
from validador_agentico.dominio.especificacion import RUTA_GOBIERNO
from validador_agentico.dominio.gobierno_mcp import GobiernoMcp
from validador_agentico.dominio.hallazgo import Hallazgo, aviso, error

# Etiquetas moviles habituales de los registros de paquetes. Ninguna fija nada: el mismo nombre
# devuelve contenido distinto en dos momentos distintos.
ETIQUETAS_MOVILES = ("latest", "main", "master", "next", "edge", "stable", "dev", "beta", "canary")

# Rangos de SemVer: fijan un LIMITE, no una version. `^1.2.0` acepta cualquier 1.x posterior.
_MARCAS_DE_RANGO = ("^", "~", ">", "<", "*", "||", " - ")

# Comodines por COMPONENTE: `1.x` y `1.0.X` no fijan la ultima parte. Se comprueba componente a
# componente y no como subcadena, porque una version legitima puede contener esas letras -- rechazar
# cualquier `x` habria descartado versiones validas.
_COMODINES_DE_COMPONENTE = ("x", "X", "*")

# Una referencia fijada acaba en `@<version>`: `paquete@0.4.1`, `paquete@1.0.0-rc.1`. El `@` inicial
# opcional cubre los paquetes con ambito de npm, `@ambito/paquete@1.2.3`.
_REFERENCIA_CON_VERSION = re.compile(r"^@?[^@\s]+@(?P<version>[^@\s]+)$")

_TRANSPORTES_SIN_VERSION = ("http", "sse")
_CLAVE_ARGUMENTOS = "args"
_CLAVE_TRANSPORTE = "type"
_CLAVE_URL = "url"


def _referencias_de(configuracion: dict) -> tuple[str, ...]:
    """Los argumentos que parecen una referencia a un paquete.

    Se miran los `args` y no el `command`: el comando es el LANZADOR -- `uvx`, `npx` -- y lo que
    identifica al servidor va en los argumentos.
    """
    argumentos = configuracion.get(_CLAVE_ARGUMENTOS) or []
    if not isinstance(argumentos, (list, tuple)):
        return ()
    return tuple(str(a) for a in argumentos if "@" in str(a))


def _defecto_de_la_referencia(referencia: str) -> str | None:
    """Por que esta referencia no fija una version, o `None` si la fija."""
    coincidencia = _REFERENCIA_CON_VERSION.match(referencia)
    if coincidencia is None:
        return "no declara version"
    version = coincidencia.group("version")
    if version.lower() in ETIQUETAS_MOVILES:
        return f"`{version}` es una etiqueta MOVIL"
    if any(marca in version for marca in _MARCAS_DE_RANGO):
        return f"`{version}` es un rango, no una version"
    if any(parte in _COMODINES_DE_COMPONENTE for parte in version.split(".")):
        return f"`{version}` lleva un comodin, no fija la version"
    return None


def revisar_declaracion(donde: str, configuracion: object,
                         servidores_declarados: object) -> list[Hallazgo]:
    """El gobierno declara EXACTAMENTE los servidores que la configuracion ejecuta.

    Se coteja por lo que IDENTIFICA a cada servidor -- la URL para un remoto, la referencia con version
    para un `stdio` -- y no por su nombre: la plataforma documenta que un `serverName` no es un control
    de seguridad, porque es la etiqueta que asigna el usuario y puede llamar `github` a cualquier cosa.
    """
    configurados = forma_mcp.servidores_de(configuracion)
    if configurados is None or not isinstance(servidores_declarados, list):
        # Sin una de las dos partes no hay nada que cotejar, y las reglas que las validan por separado
        # ya habran dicho lo suyo. Afirmar aqui una discrepancia seria inventarsela.
        return []

    sin_declarar, sin_configurar = declaracion_mcp.cotejar(configurados, servidores_declarados)
    hallazgos: list[Hallazgo] = []
    if sin_declarar:
        hallazgos.append(error(
            donde,
            f"se ejecuta un servidor que el GOVERNANCE.json no declara: {', '.join(sin_declarar)}. "
            f"La aprobacion no lo cubre, no tiene `tools_digest` con el que detectar deriva y no "
            f"recibe ficha: se ejecutaria sin gobierno. Declaralo, o quitalo de la configuracion"))
    if sin_configurar:
        hallazgos.append(error(
            donde,
            f"el GOVERNANCE.json declara un servidor que la configuracion NO tiene: "
            f"{', '.join(sin_configurar)}. La aprobacion cubre algo que no existe -- suele ser un "
            f"renombrado a medias -- y deja al aprobador creyendo que reviso lo que se ejecuta"))
    return hallazgos


def revisar_aprobacion_por_servidor(donde: str, configuracion: object,
                                     gobierno: GobiernoMcp) -> list[Hallazgo]:
    """Cada servidor de `mcpServers` tiene SU entrada de aprobacion, y al reves.

    LAS DOS DERIVAS QUE ESTO DETECTA Y LA FORMA ANTERIOR NO PODIA. Con el gobierno como LISTA
    posicional, el cotejo se hacia por lo que IDENTIFICA a cada servidor -- su URL, su
    `paquete@version` --, que responde «¿se ejecuta lo aprobado?» pero no «¿quien aprobo ESTE?». Al
    indexar el gobierno por el mismo nombre que usa `mcpServers`, cada entrada apunta a una entrada
    exacta de la configuracion y aparecen:

      1. UN SERVIDOR CONFIGURADO SIN APROBACION. Se ejecuta, sale por la red y nadie lo reviso.
         Error: es la via de acceso abierta.

      2. UNA APROBACION QUE SOBREVIVE A SU SERVIDOR. El servidor ya no esta y el bloque de aprobacion
         sigue ahi con su `review_by` y su `security_review: true`. Tambien error, y no por
         pedanteria: quien audite el gobierno vera un servidor aprobado que cree en ejecucion, y quien
         vuelva a anadir uno con ese nombre lo encontrara «ya aprobado» sin que nadie lo haya mirado.
         Es el sintoma tipico de un renombrado a medias.

    EL NOMBRE SIRVE PARA ESTO aunque la plataforma documente que un `serverName` NO ES UN CONTROL DE
    SEGURIDAD. Las dos cosas son ciertas y no chocan: el nombre no decide si algo es de fiar -- eso lo
    sigue decidiendo la identidad, en `revisar_declaracion` --, sino que EMPAREJA dos declaraciones del
    mismo repositorio que un mismo autor escribe a la vez.
    """
    configurados = forma_mcp.servidores_de(configuracion)
    if configurados is None:
        # Sin poder leer los servidores no hay nada que emparejar, y `revisar_servidores` ya dijo que
        # el archivo no tiene forma reconocible. Afirmar aqui una deriva seria inventarsela.
        return []
    if gobierno.forma_antigua:
        # La forma vieja no indexa por nombre, asi que este emparejamiento no aplica: su cotejo es el
        # de identidad, que sigue corriendo. El aviso de migracion lo emite `revisar_forma_del_bloque`.
        return []

    aprobados = set(gobierno.servidores)
    hallazgos = [
        error(donde,
              f"el servidor `{nombre}` esta configurado y el `GOVERNANCE.json` no lo aprueba. Se "
              f"ejecutaria sin aprobacion, sin `tools_digest` con el que detectar que cambio su "
              f"superficie de herramientas y sin ficha en el catalogo. Anade su entrada bajo `mcp`, o "
              f"quitalo de la configuracion")
        for nombre in sorted(set(configurados) - aprobados)
    ]
    hallazgos += [
        error(RUTA_GOBIERNO,
              f"`mcp.{nombre}` aprueba un servidor que el `.mcp.json` YA NO configura. La aprobacion "
              f"sobrevivio al servidor: quien audite el gobierno vera un servidor aprobado que cree "
              f"en ejecucion, y quien vuelva a anadir uno con ese nombre lo encontrara «ya aprobado» "
              f"sin que nadie lo haya mirado. Suele ser un renombrado a medias")
        for nombre in sorted(aprobados - set(configurados))
    ]
    return hallazgos


def revisar_forma_del_bloque(gobierno: GobiernoMcp) -> list[Hallazgo]:
    """La forma vieja del bloque `mcp` se acepta con AVISO mientras dure la transicion.

    POR QUE AVISO Y NO ERROR, que es lo que decide si esto se puede desplegar. El gate es comprobacion
    REQUERIDA en los repositorios de dominio: si la forma vieja bloqueara, todos los repositorios que
    aun no se han migrado se pondrian rojos a la vez y ninguno podria mergear NI SIQUIERA el pull
    request que viene a migrarlos, porque ese PR tambien pasa por el gate. Ya paso al retirar `status`.

    CUANDO SE PUEDE ENDURECER: cuando ningun `GOVERNANCE.json` de un repositorio de dominio declare
    `mcp.servers`. El aviso nombra los campos exactos a borrar para que la migracion sea mecanica.
    """
    if not gobierno.forma_antigua:
        return []
    derivados = gobierno_mcp.campos_derivados_declarados(gobierno)
    sobran = (f" Borra ademas {', '.join(f'`{c}`' for c in derivados)}: repiten o derivan lo que ya "
              f"esta en `.mcp.json`, y una copia que nada obliga a sincronizar se queda atras -- el "
              f"gate acabaria comparando la configuracion contra una copia rancia." if derivados
              else "")
    return [aviso(RUTA_GOBIERNO,
                  "`mcp.servers` es la forma ANTIGUA del bloque de gobierno y se acepta solo durante "
                  "la transicion. La forma vigente indexa por el NOMBRE del servidor -- la misma clave "
                  "que `mcpServers` usa en `.mcp.json` --, que es lo que permite detectar un servidor "
                  "configurado y no aprobado, y una aprobacion que sobrevive a su servidor. Con la "
                  f"lista posicional esas dos derivas pasan en verde.{sobran}")]


def revisar_que_esta_en_un_plugin(donde: str, hay_manifiesto: bool) -> list[Hallazgo]:
    """Un `mcp` va SIEMPRE dentro de un plugin. Error, no aviso.

    TECNICAMENTE FUNCIONA SUELTO -- se comprobo: un `.mcp.json` en la raiz con su bloque en el
    `GOVERNANCE.json` de la raiz da gate limpio, se sella y recibe ficha --. Se prohibe por dos
    razones, y la segunda es la que lo decide:

      1. Sin plugin no hay `enabledPlugins`, que es lo UNICO que permite apagar un servidor en todas
         las maquinas sin tocarlas. Y el `mcp` es uno de los dos tipos que cruzan una frontera de
         control: es justo el que algun dia habra que apagar rapido.

      2. Existe `strictPluginOnlyCustomization` con `mcp` en la lista, un ajuste de empresa
         documentado que hace que los servidores SOLO puedan venir de plugins. Bajo ese ajuste, un
         `mcp` suelto NO CARGA. Publicarlo seria gobernar, sellar y catalogar algo muerto -- y peor
         aun, algo que parece instalado y no esta.

    Y LA INDUSTRIA LO HACE ASI: de 18 archivos de configuracion MCP dentro de `plugins/` medidos en el
    marketplace oficial y en `awesome-copilot`, los 18 estan en un plugin. La guia del proveedor para
    distribuir un catalogo aprobado es exactamente esa: «distribuye los servidores como plugins a
    traves de un marketplace gestionado».
    """
    if hay_manifiesto:
        return []
    return [error(donde,
                  "un `mcp` va dentro de un PLUGIN, y esta unidad no tiene `plugin.json`. Suelto se "
                  "gobierna y se sella, pero pierde `enabledPlugins` -- lo unico que permite apagarlo "
                  "centralmente -- y con `strictPluginOnlyCustomization` activado NO CARGA, asi que se "
                  "publicaria algo que parece instalado y no esta. Muevelo a un plugin: la convencion "
                  "medida en los catalogos publicos es UN servidor por plugin")]


def revisar_servidores(donde: str, configuracion: object) -> list[Hallazgo]:
    """`configuracion` es el archivo MCP ENTERO, no un bloque suyo.

    Antes recibia ya extraido el `mcpServers`, y eso obligaba al llamador a saber en que clave estan
    los servidores -- cuando resulta que hay TRES formas en uso --. Ahora la forma la resuelve
    `forma_mcp`, que es donde vive el conocimiento de las variantes, y esta regla se ocupa de lo suyo.
    """
    servidores = forma_mcp.servidores_de(configuracion)
    if servidores is None:
        return [error(donde, "no se reconocen servidores en el archivo. Se admiten las tres formas en "
                             "uso -- un objeto `mcpServers`, un objeto `servers`, o los servidores "
                             "como claves de primer nivel -- y ninguna encaja: sin servidores no hay "
                             "`mcp` que gobernar, y el archivo no le sirve a ningun cliente")]
    if not servidores:
        return [error(donde, "declara cero servidores: el archivo no le sirve a ningun cliente. Si la "
                             "intencion es no tener MCP, borra el archivo en vez de dejarlo vacio")]

    hallazgos: list[Hallazgo] = []
    # `definicion` y no `configuracion`: la variable del bucle tapaba el parametro del mismo nombre.
    # Funcionaba por accidente -- los servidores ya estaban extraidos -- y dejaba una trampa para quien
    # añadiera despues cualquier uso del archivo completo tras el bucle.
    for nombre, definicion in servidores.items():
        if not isinstance(definicion, dict):
            hallazgos.append(error(donde, f"el servidor `{nombre}` no es un objeto"))
            continue

        if str(definicion.get(_CLAVE_TRANSPORTE, "")).lower() in _TRANSPORTES_SIN_VERSION:
            hallazgos.append(aviso(
                donde,
                f"el servidor `{nombre}` es REMOTO ({definicion.get(_CLAVE_URL, 'sin url')}): no "
                f"hay version que fijar y su contenido puede cambiar en cualquier momento. Lo unico "
                f"que lo detecta es comparar periodicamente el digest de sus herramientas"))
            continue

        referencias = _referencias_de(definicion)
        if not referencias:
            hallazgos.append(aviso(
                donde, f"no se reconoce la referencia del servidor `{nombre}`: no se puede "
                       "comprobar que este fijada a una version"))
            continue

        for referencia in referencias:
            defecto = _defecto_de_la_referencia(referencia)
            if defecto is not None:
                hallazgos.append(error(
                    donde,
                    f"el servidor `{nombre}` apunta a `{referencia}` y {defecto}: el codigo que se "
                    f"aprobo y el que se ejecuta pueden ser distintos sin release, sin revision y "
                    f"sin atestacion. Es el ataque conocido como *rug pull*"))
    return hallazgos
