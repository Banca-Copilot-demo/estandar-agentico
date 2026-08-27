"""Lo que la ficha de Port dice de un artefacto SEGUN SU ESTADO. Regla pura: sin I/O.

POR QUE ESTO ES UNA REGLA Y NO TRES LINEAS EN EL SCRIPT QUE ESCRIBE LA FICHA. La pregunta «¿este
artefacto se distribuye?» tiene hoy DOS escritores -- la publicacion, que escribe la ficha entera, y
las transiciones de estado, que solo tocan lo que el estado cambia -- y manana tendra cinco mas
(suspension, reactivacion, obsolescencia, retirada). Si cada uno la respondiera por su cuenta,
tendriamos siete formas de decir lo mismo y divergirian en la primera correccion.

EL DEFECTO QUE CIERRA, medido en Port real: una ficha en estado `conformant` -- que por
politica NO se distribuye -- declaraba `en_marketplace: True` y una pista de instalacion
`copilot plugin install <plugin>@<marketplace>`. Ese comando NO RESUELVE, porque el artefacto no esta
en el marketplace. La ficha de Port prometia algo que el marketplace no puede cumplir.

La causa era que `en_marketplace` significaba «es un componente que un plugin transporta», que es una
propiedad del TIPO. Desde que publicar y distribuir son dos actos distintos, lo que decide si algo se
distribuye es el ESTADO combinado con la politica de promocion, y el tipo es solo una condicion
necesaria.
"""
from __future__ import annotations

from validador_agentico.dominio.politica import Promocion, entra_al_marketplace
from validador_agentico.dominio.reglas_layout import RAIZ_DEL_REPOSITORIO, unidad_de

# `name` del marketplace: el que resuelve `<plugin>@<marketplace>`.
MARKETPLACE = "agentico"

# Donde espera cada cliente un prompt traido a mano. `commands/` en el origen; en el destino lo fija
# el cliente, no nosotros.
DESTINO_PROMPT = ".github/prompts"

# Los tipos que un plugin TRANSPORTA. Es condicion NECESARIA para distribuirse por el marketplace, pero
# ya no suficiente: hace falta ademas que el estado lo permita.
#
# `prompt` SE AÑADIO DESPUES, y el comentario anterior decia lo contrario: que ni `prompt` ni
# `instructions` estaban en ninguna lista de componentes y por eso «viajan por otro canal». Estaba
# incompleto, y se vio MIDIENDO en vez de leyendo:
#
#   - la referencia de plugins de Copilot SI lista `commands` como componente, con un matiz que lo
#     explica todo: es el unico SIN RUTA POR DEFECTO. Por eso un prompt dentro de un plugin se
#     instalaba sin registrarse -- los archivos aterrizaban y no los veia nadie --;
#   - al declarar `commands` en el manifiesto, el comportamiento CAMBIA de forma observable: Copilot
#     copia SOLO el directorio declarado en vez de copiarlo todo a ciegas, lo que prueba que lee la
#     declaracion. En Claude Code `commands/` si es ruta por defecto y se registra sin declararla.
#
# CONSECUENCIA PARA QUIEN GENERE EL MANIFIESTO: una unidad de tipo `prompt` tiene que declarar
# `commands`; skills y agentes no lo necesitan porque sus rutas SI son las de por defecto.
#
# `instructions` esta fuera a proposito: dejo de ser un tipo gobernado porque no hay canal que la
# distribuya.
TIPOS_QUE_UN_PLUGIN_TRANSPORTA = frozenset({"skill", "agent", "prompt", "mcp", "hooks"})

TIPO_SKILL = "skill"
TIPO_PROMPT = "prompt"

# La subruta de la unidad que ocupa el repositorio entero, o -- en un repositorio mixto -- del
# conjunto de artefactos sueltos que no pertenece a ningun plugin.
#
# NO SE REDECLARA EL VALOR: es el mismo `.` que emite `listar_plugins` y con el que `reglas_layout`
# nombra esa unidad. Escribirlo dos veces es tener dos sitios donde cambiarlo y uno donde olvidarlo
# (G2). El alias se conserva porque este modulo lo exporta y hay quien lo importa por este nombre.
SUBRUTA_RAIZ = RAIZ_DEL_REPOSITORIO

# Un skill vive en su propia carpeta -- `.../<nombre>/SKILL.md` --, y su nombre ES esa carpeta. Con
# menos separadores la ruta no puede nombrar un skill.
_PROFUNDIDAD_MINIMA_DE_SKILL = 2


def _unidad_que_contiene(ruta_del_artefacto: str, unidades: list[dict]) -> dict | None:
    """La unidad publicable dentro de la que vive el artefacto, o `None` si ninguna lo contiene.

    QUIEN DECIDE LA PERTENENCIA ES `reglas_layout.unidad_de`, Y ESTE MODULO NO LA REIMPLEMENTA.
    Tenia su propia copia -- misma regla, mismo desempate por la coincidencia mas larga, misma
    excepcion para `.` -- escrita contra `startswith` en vez de contra segmentos de ruta. Dos
    definiciones de «a que unidad pertenece este archivo» son dos cosas que divergen en el primer
    arreglo que alguien haga con prisa: el gate exigiria subir la version de una unidad y la ficha
    sellaria otra (G2/P9).

    LO UNICO QUE APORTA ESTA FUNCION es traducir entre los dos portadores del mismo dato: aqui la
    unidad viaja como `dict` del veredicto -- con `subruta` y `nombre` --, y la regla pura habla de
    subrutas. Resuelve la subruta con la regla y devuelve el registro que la lleva.

    LA COMPARACION POR SEGMENTOS ES ADEMAS MAS ESTRICTA que el `startswith` que sustituye:
    `plugins/referencia-vieja/...` no cuelga de `plugins/referencia`.
    """
    por_subruta = {u["subruta"]: u for u in unidades if u.get("subruta")}
    elegida = unidad_de(ruta_del_artefacto, list(por_subruta))
    return por_subruta.get(elegida) if elegida is not None else None


def plugin_que_contiene(ruta_del_artefacto: str, plugins: list[dict]) -> str:
    """El nombre del plugin dentro del que vive `ruta_del_artefacto`, o cadena vacia si ninguno.

    EL DEFECTO QUE ESTO ARREGLA, visto mirando Port real y no el codigo: la pista de
    instalacion se construia con `inventario.nombre_plugin`, que es UN nombre a nivel de
    REPOSITORIO. En un repositorio con varios plugins ese unico nombre se aplicaba a TODOS los
    artefactos, asi que cuatro de los cinco quedaban apuntando al plugin equivocado.

    No era un error cosmetico: quien siguiera la pista instalaba OTRO plugin y no obtenia el
    artefacto que buscaba -- y el comando no falla, porque el plugin al que apunta si existe --.
    """
    unidad = _unidad_que_contiene(ruta_del_artefacto, plugins)
    return str(unidad.get("nombre", "")) if unidad else ""


def es_de_la_unidad(ruta_del_artefacto: str, subruta_publicada: str,
                    unidades: list[dict]) -> bool:
    """Si el artefacto pertenece a la unidad que ESTA publicacion sella.

    EL DEFECTO QUE CIERRA, medido en Port real: la publicacion de UNA unidad reescribia la
    ficha de TODOS los artefactos del repositorio, porque el predicado firmado es del repositorio
    entero. Consecuencia: publicar un skill le ponia a los artefactos vecinos -- sin tocarlos, sin
    volver a sellarlos -- la etiqueta, el sha y el digest de una version que no es la suya. La ficha
    de un vecino apuntaba a un paquete que no lo contiene.

    LA PERTENENCIA ES POR UNIDAD Y NO POR PREFIJO, y la diferencia importa en el repositorio MIXTO.
    Al publicar el conjunto suelto -- subruta `.` -- todo el repositorio empieza por el prefijo,
    incluidos los artefactos de los plugins anidados, que tienen su propia etiqueta. Comparando la
    unidad RESUELTA en vez del prefijo, cada artefacto cuenta para una sola publicacion.
    """
    unidad = _unidad_que_contiene(ruta_del_artefacto, unidades)
    subruta_del_artefacto = unidad["subruta"] if unidad else SUBRUTA_RAIZ
    return str(subruta_del_artefacto) == subruta_publicada


def esta_distribuido(estado: str, promocion: Promocion, pertenece_a_un_plugin: bool,
                     tipo: str) -> bool:
    """Si el artefacto esta HOY en el marketplace, y por tanto se instala por nombre.

    TRES CONDICIONES, y las tres hacen falta:

      - que su TIPO sea de los que un plugin transporta -- un `instructions` no lo es --;
      - que PERTENEZCA a un plugin: las entradas de un marketplace son plugins, y un artefacto
        suelto sin manifiesto propio no tiene entrada;
      - que su ESTADO lo permita segun la politica. Es la condicion que faltaba y la que hacia mentir
        a la ficha.
    """
    if tipo not in TIPOS_QUE_UN_PLUGIN_TRANSPORTA or not pertenece_a_un_plugin:
        return False
    return entra_al_marketplace(estado, promocion)


def pista_de_instalacion(tipo: str, ruta: str, distribuido: bool, repositorio: str,
                         sha: str, etiqueta: str, nombre_plugin: str) -> str:
    """El COMANDO exacto que el consumidor ejecuta, coherente con si el artefacto se distribuye.

    SIEMPRE UN COMANDO. Una descripcion en prosa obliga al consumidor a averiguar como se instala,
    que es justo lo que la ficha existe para evitar.

    Y SIEMPRE FIJADO. Cuando no se distribuye, el consumidor sigue pudiendo traerselo por su cuenta
    -- un piloto, el propio equipo --, pero de la VERSION PUBLICADA y no de la rama: por eso cada
    rama de abajo lleva la etiqueta o el sha sellado. Una pista sin fijar instalaria algo que nadie
    reviso.
    """
    if distribuido:
        # Se instala el PLUGIN, no el artefacto: un plugin se instala completo. Poner aqui el id del
        # artefacto daba un comando que no resuelve contra ninguna entrada del marketplace.
        return f"copilot plugin install {nombre_plugin}@{MARKETPLACE}"

    # LAS DOS RAMAS DE ABAJO NECESITAN LA RUTA, y una ficha ya escrita puede no traerla: `ruta` se
    # anadio a la ficha de Port justo para que las transiciones de estado pudieran reconstruir la
    # pista, asi que las fichas anteriores a ese cambio la tienen vacia. Sin esta guarda, una
    # promocion sobre una ficha vieja reventaria al partir una cadena vacia -- y reventar en una
    # transicion de estado es peor que dar la pista generica, porque deja Port a medio actualizar.
    if tipo == TIPO_SKILL and ruta.count("/") >= _PROFUNDIDAD_MINIMA_DE_SKILL:
        # La forma es `gh skill install <repo> <skill[@version]>`, MEDIDO ejecutandolo: el nombre del
        # skill es un argumento aparte, no parte del repositorio. Concatenar la ruta al repositorio
        # produce un comando que falla con «must specify a skill name». El nombre es el DIRECTORIO
        # del skill, que la especificacion obliga a que coincida con su `name`.
        return f"gh skill install {repositorio} {ruta.rsplit('/', 2)[-2]}@{etiqueta}"

    if tipo == TIPO_PROMPT and ruta:
        # UN PROMPT SIN MARKETPLACE. Es el unico camino que no pasa por un canal gobernado: quien lo
        # siga se traera el archivo este certificado, conforme o suspendido. La salida es publicarlo
        # como su propia unidad -- con manifiesto que declare `commands` --, no mejorar esta pista.
        #
        # Se trae el archivo FIJADO AL SHA -- no a la etiqueta -- porque el sha es lo que quedo
        # sellado, y el nombre del destino lo fija el cliente.
        destino = f"{DESTINO_PROMPT}/{ruta.rsplit('/', 1)[-1]}"
        return (f"curl -fsSL https://raw.githubusercontent.com/{repositorio}/{sha}/"
                f"{ruta} -o {destino}")

    # AGENTE, MCP Y HOOKS SIN DISTRIBUIR. No hay comando de cliente que los instale sueltos, asi que
    # la pista honesta es traerse el PAQUETE PUBLICADO -- el mismo que lleva la atestacion -- y
    # continuar por el camino manual: descargar, verificar e instalar. La verificacion la dice el
    # otro campo de la ficha.
    return (f"gh release download {etiqueta} --repo {repositorio}"
            "  # aun no distribuido: verifica el paquete antes de instalarlo")
