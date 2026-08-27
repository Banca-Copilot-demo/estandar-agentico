"""Reglas de los hooks — el unico artefacto que EJECUTA CODIGO PROPIO automaticamente.

Y el unico que NO se instala: los hooks de repositorio viven en `.github/hooks/*.json` y, una vez
mergeados a la rama por defecto, se ejecutan en cada sesion del agente. Eso hace del pull request
el UNICO punto de control — no hay paso de instalacion donde intervenir— y es la razon por la que
el `CODEOWNERS` de seguridad sobre el archivo no es opcional.

Lo que este modulo comprueba es lo estatico. Lo que NO puede comprobar —si el script exfiltra lo
que el desarrollador escribe— es exactamente lo que revisa la persona.

PURAS (G5): reciben la configuracion ya parseada y devuelven hallazgos.
"""
from __future__ import annotations

import re

from validador_agentico.dominio import scripts_de_hooks
from validador_agentico.dominio.especificacion import (
    CAMPO_TIMEOUT_HOOK,
    CAMPO_TIMEOUT_HOOK_RETIRADO,
    EVENTOS_HOOK_SENSIBLES,
    PATRON_DESCARGA_EN_EJECUCION,
    PATRON_INTERRUPTOR_SEGURIDAD,
    TECHO_TIMEOUT_HOOK_S,
    TIMEOUT_HOOK_POR_DEFECTO_S,
    TIPO_HOOK_A_REVISAR,
    TIPO_HOOK_DOMINANTE,
)
from validador_agentico.dominio.hallazgo import Hallazgo, aviso, error

_CLAVE_ACCIONES = "hooks"
_CLAVE_TIPO = "type"
_CLAVE_COMANDO = "command"
_CLAVE_ARGUMENTOS = "args"


def revisar_hooks(ruta_relativa: str, configuracion: dict,
                  aprobacion_declarada: dict,
                  scripts_presentes: frozenset[str] = frozenset()) -> list[Hallazgo]:
    """`scripts_presentes` son las rutas de script que EXISTEN en el artefacto, relativas a su raiz.

    Llega como dato y no se lee aqui porque esta regla es de dominio. Por defecto vacio para que las
    pruebas que miden otra cosa no tengan que construir el arbol.

    `aprobacion_declarada` es el bloque `hooks` del `GOVERNANCE.json`. SUSTITUYE al inventario: los
    hooks salieron de `artifacts` porque NO TIENEN IDENTIDAD INDIVIDUAL -- se distinguen por evento y
    `matcher`, no llevan `id` en ninguna parte --, asi que declarar «hay 1 hooks» no enumeraba nada y
    el numero no podia ser otra cosa que 0 o 1. El control «un componente que EJECUTA CODIGO no entra
    por sorpresa» no se pierde: cambia de campo, y mejora, porque un numero se pone sin mirar y una
    aprobacion lleva nombre, fecha y fecha de caducidad.
    """
    hallazgos = _revisar_aprobacion(ruta_relativa, aprobacion_declarada)
    hallazgos += _revisar_scripts_externos(ruta_relativa, configuracion)
    hallazgos += _revisar_scripts_ausentes(ruta_relativa, configuracion, scripts_presentes)
    for evento, entradas in (configuracion.get("hooks") or {}).items():
        donde = f"{ruta_relativa}:{evento}"
        for entrada in entradas if isinstance(entradas, list) else []:
            if not isinstance(entrada, dict):
                continue
            hallazgos += _revisar_timeout_retirado(donde, entrada)
            hallazgos += _revisar_entorno(donde, entrada.get("env") or {})
            # SI EL GRUPO TRAE `timeoutSec`, la accion no se reprocha por no declarar `timeout`. Es
            # la condicion de la transicion: quien escribio la forma vieja SI declaro una intencion de
            # tope -- estaba siguiendo lo que este mismo gate le exigia --, y convertir eso en error
            # pondria rojos de golpe todos los `hooks.json` existentes, el nuestro incluido. El aviso
            # de `timeoutSec` ya dice que hay que mover.
            heredado = CAMPO_TIMEOUT_HOOK_RETIRADO in entrada
            for accion in entrada.get(_CLAVE_ACCIONES) or []:
                if isinstance(accion, dict):
                    hallazgos += _revisar_accion(donde, accion, en_transicion=heredado)
        if evento in EVENTOS_HOOK_SENSIBLES:
            hallazgos.append(aviso(donde,
                                   "este evento ve TODO lo que el desarrollador escribe: es un "
                                   "canal de salida de datos por diseno. Revisa si el script "
                                   "accede a la red antes de aprobarlo"))
    return hallazgos


def revisar_que_esta_en_un_plugin(donde: str, hay_manifiesto: bool) -> list[Hallazgo]:
    """Unos `hooks` van SIEMPRE dentro de un plugin. Error, no aviso.

    ES EL MISMO ARGUMENTO QUE PARA EL `mcp`, con la MISMA clave: existe
    `strictPluginOnlyCustomization.hooks` -- «Lock hooks to plugin and managed sources», ambito
    Managed -- hermana literal de `strictPluginOnlyCustomization.mcp`. Bajo ese ajuste, unos hooks
    fuera de un plugin no se ejecutan.

    Y AQUI EL ARGUMENTO ES MAS FUERTE QUE PARA EL `mcp`, por como se combinan las capas de ajustes:

        «Hook entries merge across settings levels rather than replacing each other: user, project,
         and local settings add their own hooks without removing managed ones, and the
         `disableAllHooks` setting can't disable managed hooks from outside managed settings.»

    O sea que un hook suelto NO lo quita ninguna capa superior: SE SUMA. Para un `mcp` suelto queda al
    menos `allowedMcpServers` como plan B; para unos hooks sueltos, el unico control por artefacto es
    `enabledPlugins`, y solo alcanza a los que estan DENTRO de un plugin. Lo demas es
    `disableAllHooks`, que es todo o nada. Un hook fuera de un plugin es, en la practica, irrevocable
    de forma granular.

    MEDIDO en los catalogos publicos: 6 de 6 archivos `hooks.json` de `claude-plugins-official` estan
    dentro de `plugins/`, y CERO artefactos de los dos catalogos declaran hooks en un `settings.json`
    o en frontmatter -- sobre 135 manifiestos --. Y el contraejemplo confirma el patron: los 8 hooks de
    `awesome-copilot` viven fuera de todo plugin porque Copilot no admite otra cosa, y se distribuyen
    copiando una carpeta a mano, sin version efectiva y sin revocacion.
    """
    if hay_manifiesto:
        return []
    return [error(donde,
                  "unos `hooks` van dentro de un PLUGIN, y esta unidad no tiene `plugin.json`. Un hook "
                  "suelto SE SUMA a los demas y no lo quita ninguna capa superior: el unico control por "
                  "artefacto es `enabledPlugins`, que solo alcanza a los hooks de un plugin, y lo que "
                  "queda es `disableAllHooks`, que apaga TODOS. Ademas, con "
                  "`strictPluginOnlyCustomization.hooks` activado no se ejecutan. Muevelos a un plugin")]


def _revisar_scripts_externos(ruta_relativa: str, configuracion: dict) -> list[Hallazgo]:
    """Un hook NO ejecuta scripts de fuera del artefacto. Error, no aviso.

    POR QUE ES LO MAS GRAVE QUE PUEDE TENER UN HOOK. Con `${CLAUDE_PROJECT_DIR}` el script vive en el
    repositorio del CONSUMIDOR: no viaja en el paquete, no entra en el digesto y nadie lo reviso al
    aprobar. El `hooks.json` pasaria cualquier verificacion -- su firma seria perfecta -- y lo que se
    ejecuta no existia cuando se firmo. La firma diria mucho menos de lo que aparenta, que es peor que
    no tener firma: la que no existe no engana a nadie.

    No es un caso hipotetico que convenga permitir «por flexibilidad»: si un artefacto necesita un
    script, ese script es parte del artefacto y va dentro.
    """
    externas = scripts_de_hooks.referencias_externas(configuracion)
    if not externas:
        return []
    return [error(ruta_relativa,
                  f"ejecuta un script de FUERA del artefacto "
                  f"({scripts_de_hooks.VARIABLE_RAIZ_DEL_CONSUMIDOR}): {comando}. Ese archivo vive en "
                  f"el repositorio de quien instala, asi que no viaja en el paquete, no entra en el "
                  f"digesto y nadie lo reviso al aprobar -- la firma cubriria el JSON y no lo que se "
                  f"ejecuta --. Si el script es parte del artefacto, muevelo dentro y referencialo "
                  f"con {scripts_de_hooks.VARIABLE_RAIZ_DEL_ARTEFACTO}")
            for comando in externas]


def _revisar_scripts_ausentes(ruta_relativa: str, configuracion: dict,
                               presentes: frozenset[str]) -> list[Hallazgo]:
    """Un script referenciado que no existe en el arbol: el hook falla al ejecutarse, no al aprobarse.

    Mismo razonamiento que la regla de recursos de un skill: el paquete se publicaria sellado y el
    fallo aparece en la maquina de otro, cuando ya es tarde.

    `presentes` son las rutas REFERENCIADAS que existen, o sea un subconjunto de las referencias. La
    primera version tenia una guarda `if not presentes: return []` con el argumento de que sin
    inventario no se puede afirmar que falte nada -- y era un error que la propia prueba destapo: si
    la unica referencia del hook no existe, `presentes` sale VACIO y la guarda desactivaba la regla
    EXACTAMENTE en el caso para el que existe. Un hook con un solo script, y ese ausente, pasaba en
    verde.
    """
    return [error(ruta_relativa,
                  f"referencia el script `{ruta}` y no existe en el artefacto: el hook fallaria al "
                  f"ejecutarse en la maquina de quien lo instale, no aqui")
            for ruta in scripts_de_hooks.referencias_propias(configuracion)
            if ruta not in presentes]


def _revisar_aprobacion(ruta_relativa: str, aprobacion_declarada: dict) -> list[Hallazgo]:
    """Un componente que ejecuta codigo no entra por sorpresa: alguien lo aprueba, con nombre y fecha.

    ANTES SE EXIGIA EL INVENTARIO -- `artifacts.hooks` --, y eso pedia un NUMERO. Un numero se pone
    sin mirar, y ademas no podia ser otro que 0 o 1: hay como mucho un `hooks.json` por unidad. La
    aprobacion es el mismo control mejor puesto, porque lo que hay que saber de un componente que
    ejecuta codigo en la maquina del desarrollador es quien se hizo responsable y hasta cuando.
    """
    if (aprobacion_declarada or {}).get("approval"):
        return []
    return [error(ruta_relativa,
                  "existe y el `GOVERNANCE.json` no declara `hooks.approval`. Un componente que "
                  "EJECUTA CODIGO en la maquina de quien instala no entra sin que alguien se haga "
                  "responsable, con nombre, fecha y fecha de revision")]


def _revisar_timeout_retirado(donde: str, objeto: dict) -> list[Hallazgo]:
    """`timeoutSec`, este donde este: se acepta con aviso y NO acota nada.

    ES EL DEFECTO QUE ESTE CAMBIO CORRIGE, y viene de nuestro propio gate: exigia este campo, que NO
    EXISTE en el formato. El cliente lo ignora, asi que el hook corria con el timeout POR DEFECTO de
    su tipo mientras quien lo escribio creia haber puesto cinco segundos.

    AVISO Y NO ERROR: hay 908 repositorios publicos que arrastran la misma grafia, y el gate es
    comprobacion requerida -- un error de golpe impediria mergear hasta el PR que viene a corregirlo.
    Se endurece cuando ningun `hooks.json` de un repositorio de dominio lo lleve.
    """
    if CAMPO_TIMEOUT_HOOK_RETIRADO not in objeto:
        return []
    return [aviso(donde,
                  f"`{CAMPO_TIMEOUT_HOOK_RETIRADO}` NO EXISTE en el formato y el cliente lo IGNORA: "
                  f"el hook corre con el timeout por defecto de su tipo, asi que este campo no acota "
                  f"nada aunque lo parezca. El real es `{CAMPO_TIMEOUT_HOOK}`, en segundos y dentro "
                  f"de cada accion de `hooks[]`. Renombralo y muevelo ahi")]


def _revisar_timeout(donde: str, accion: dict, tipo: str) -> list[Hallazgo]:
    """El tope REAL, `timeout`, en la accion. Sin el, el hook corre con el default de su tipo.

    EL MENSAJE DICE CUANTO SE ESPERARIA DE VERDAD y no solo «falta el timeout»: seiscientos segundos
    de cliente bloqueado es un argumento, y «falta un campo» es burocracia. Lo primero se corrige y lo
    segundo se ignora.
    """
    if CAMPO_TIMEOUT_HOOK not in accion:
        # Con `timeoutSec` presente ya se avisa en el grupo. Anadir aqui el error seria dar dos
        # hallazgos por un solo defecto, y ademas el peor de los dos: el que dice que falta algo que
        # la persona cree haber escrito.
        return []
    timeout_s = accion.get(CAMPO_TIMEOUT_HOOK)
    if not isinstance(timeout_s, (int, float)) or isinstance(timeout_s, bool):
        return [error(donde, f"`{CAMPO_TIMEOUT_HOOK}` no es un numero de segundos: {timeout_s!r}")]
    if timeout_s > TECHO_TIMEOUT_HOOK_S:
        return [error(donde, f"`{CAMPO_TIMEOUT_HOOK}` de {timeout_s}s supera el techo de "
                             f"{TECHO_TIMEOUT_HOOK_S}s")]
    return []


def _revisar_accion(donde: str, accion: dict, *, en_transicion: bool) -> list[Hallazgo]:
    """Lo que se le exige a UNA accion: su tope, y lo suyo segun el tipo.

    `en_transicion` es «el grupo declaro el `timeoutSec` que este gate exigia»: entonces no se reprocha
    la falta de `timeout`, porque el autor SI declaro una intencion de tope y lo unico que hizo fue
    seguir lo que se le pedia. Reprocharselo como error seria cobrarle nuestro propio defecto.
    """
    tipo = str(accion.get(_CLAVE_TIPO, ""))
    hallazgos = _revisar_timeout(donde, accion, tipo)
    hallazgos += _revisar_timeout_retirado(donde, accion)
    if (CAMPO_TIMEOUT_HOOK not in accion and CAMPO_TIMEOUT_HOOK_RETIRADO not in accion
            and not en_transicion):
        por_defecto = TIMEOUT_HOOK_POR_DEFECTO_S.get(tipo)
        hallazgos.append(error(
            donde,
            f"la accion no declara `{CAMPO_TIMEOUT_HOOK}`: correra con el default de su tipo"
            + (f" -- {por_defecto} s" if por_defecto else "")
            + f", y el estandar acota los hooks a {TECHO_TIMEOUT_HOOK_S} s. Un hook sin tope "
              f"efectivo puede dejar el cliente colgado, y quien lo instala no sabe por que"))
    if tipo == TIPO_HOOK_DOMINANTE:
        hallazgos += _revisar_comando(donde, accion)
    if tipo == TIPO_HOOK_A_REVISAR:
        hallazgos.append(aviso(
            donde,
            f"hook de tipo `{TIPO_HOOK_A_REVISAR}` hacia `{accion.get('url', 'sin url')}`: manda el "
            f"evento a un servicio EXTERNO con cabeceras propias, o sea una salida de datos que no "
            f"pasa por ningun otro control del estandar. NO hay regla de gobierno para el porque no "
            f"se encontro ni un uso real, y gobernar una hipotesis es inventarse un control que "
            f"nadie ejercita: revisalo a mano, y si esto se repite ese es el momento de escribirla"))
    return hallazgos


def _revisar_comando(donde: str, accion: dict) -> list[Hallazgo]:
    """Las dos reglas de gobierno del tipo DOMINANTE -- 27008 de 33472 archivos medidos, ~81 %.

    1. EL COMANDO APUNTA DENTRO DE LA UNIDAD. Un `${CLAUDE_PLUGIN_ROOT}/...` viaja en el paquete,
       entra en el digesto y se reviso al aprobar. Una ruta absoluta de una maquina -- `/home/ana/...`,
       `C:\\Users\\...` -- no existe en la maquina de nadie mas, y un binario suelto del sistema
       (`./limpiar.sh`, `python scripts/x.py`) se resuelve contra un directorio de trabajo que aqui no
       se controla: en los dos casos, lo que se ejecuta no es lo que se firmo.

    2. NO SE DESCARGA NADA EN EJECUCION. Un `curl ... | bash` se salta el sello POR COMPLETO: el JSON
       iria firmado con un digesto perfecto y lo que corre se baja de internet en ese momento. La
       firma diria muchisimo menos de lo que aparenta, que es peor que no tenerla.

    La primera se comprueba con la referencia a la raiz DEL ARTEFACTO y no con una lista de rutas
    prohibidas: una lista de prohibiciones siempre deja fuera un caso, y aqui el caso que se escapa se
    ejecuta con los permisos del desarrollador.
    """
    textos = [t for t in (accion.get(_CLAVE_COMANDO), *(accion.get(_CLAVE_ARGUMENTOS) or []))
              if isinstance(t, str)]
    comando = " ".join(textos)
    if not comando.strip():
        return [error(donde, f"una accion de tipo `{TIPO_HOOK_DOMINANTE}` sin `command`: no ejecuta "
                             f"nada, y el gate no puede decir que ejecutaria")]

    hallazgos: list[Hallazgo] = []
    if re.search(PATRON_DESCARGA_EN_EJECUCION, comando):
        hallazgos.append(error(
            donde,
            f"el comando DESCARGA Y EJECUTA en tiempo de ejecucion: `{comando}`. Eso se salta el "
            f"sello por completo -- el `hooks.json` iria firmado con un digesto perfecto y lo que "
            f"corre se baja de internet en ese momento, no existia cuando se aprobo y puede ser "
            f"distinto en cada maquina. Si el script es parte del artefacto, muevelo dentro"))
    if scripts_de_hooks.VARIABLE_RAIZ_DEL_ARTEFACTO not in comando:
        hallazgos.append(error(
            donde,
            f"el comando no apunta dentro de la unidad: `{comando}`. Referencialo con "
            f"{scripts_de_hooks.VARIABLE_RAIZ_DEL_ARTEFACTO}/... -- asi viaja en el paquete, entra en "
            f"el digesto y es lo que se reviso al aprobar --. Una ruta absoluta de una maquina no "
            f"existe en la de nadie mas, y un binario suelto se resuelve contra un directorio de "
            f"trabajo que aqui no se controla: en los dos casos se ejecuta algo que no se firmo"))
    return hallazgos


def _revisar_entorno(donde: str, entorno: dict) -> list[Hallazgo]:
    """Un control de seguridad apagado por defecto, en un archivo que nadie abre."""
    return [
        aviso(donde, f"`env.{clave}` viene en `false`: parece un control de seguridad desactivado "
                     "por defecto")
        for clave, valor in entorno.items()
        if str(valor).lower() == "false" and re.search(PATRON_INTERRUPTOR_SEGURIDAD, clave)
    ]
