"""Proyecta el CONTENIDO leido del repositorio hacia las salidas del caso de uso.

Aqui no se aplica ninguna regla y no se produce ningun hallazgo: solo se transforma lo que el
adaptador entrego en las tres cosas que el veredicto necesita llevar -- el inventario, las fichas
de los artefactos publicados y los datos de custodia --.

POR QUE ES UN MODULO APARTE. El caso de uso hacia dos cosas distintas: aplicar las reglas del gate
a cada plugin Y proyectar su contenido hacia estas salidas. Son dos grupos tematicos (G1), y al
cruzar el nucleo el umbral de tamano la conjuncion se volvio evidente: «revisa las reglas Y
construye el inventario Y arma las fichas Y extrae la custodia».

Todas las funciones son PURAS salvo `artefacto_publicado`, que calcula el digesto del archivo y por
tanto lee disco: es el unico I/O de este modulo y esta acotado a esa funcion.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from validador_agentico.adaptadores import digesto
from validador_agentico.adaptadores.repositorio import ContenidoRepositorio
from validador_agentico.dominio import scripts_de_hooks
from validador_agentico.dominio.hallazgo import (
    ArtefactoPublicado,
    Inventario,
    PluginPublicado,
)

# Que colecciones del contenido se publican como ficha, y con que `tipo` en el predicado firmado.
TIPO_POR_COLECCION = (("skills", "skill"), ("prompts", "prompt"), ("agentes_leidos", "agent"))
# `agentes_leidos` FALTABA, y se descubrio al construir el primer plugin con los cinco tipos: el gate
# validaba el agente pero no llegaba al predicado, asi que no tenia ficha en el catalogo. Un artefacto
# con envelope, id y dueno que el catalogo no conoce es indistinguible de uno que no existe.

# El `mcp` no esta en esa tabla porque no es una coleccion de artefactos con frontmatter: es UN
# archivo de configuracion mas su bloque en el gobierno del plugin. Se proyecta aparte.
TIPO_MCP = "mcp"
TIPO_HOOKS = "hooks"



def sumar_inventarios(a: Inventario, b: Inventario) -> Inventario:
    """El inventario del repositorio es la suma del de sus plugins. `tiene_plugin` es un O: basta
    que uno lo tenga para que el repositorio publique al marketplace."""
    return Inventario(
        skills=a.skills + b.skills, agentes=a.agentes + b.agentes,
        prompts=a.prompts + b.prompts, mcps=a.mcps + b.mcps, hooks=a.hooks + b.hooks,
        tiene_plugin=a.tiene_plugin or b.tiene_plugin,
        nombre_plugin=a.nombre_plugin or b.nombre_plugin)


def construir_inventario(contenido: ContenidoRepositorio) -> Inventario:
    return Inventario(
        skills=len(contenido.skills),
        agentes=contenido.agentes,
        prompts=len(contenido.prompts),
        mcps=contenido.mcps,
        hooks=1 if contenido.hooks else 0,
        tiene_plugin=contenido.manifiesto is not None and contenido.manifiesto.es_legible,
        nombre_plugin=nombre_del_plugin(contenido),
    )


def plugin_publicado(contenido: ContenidoRepositorio, raiz_plugin: Path,
                     raiz_repositorio: Path) -> PluginPublicado | None:
    """El plugin de esta raiz con SU SUBRUTA, o `None` si aqui no hay manifiesto legible.

    La subruta se calcula respecto a la raiz del repositorio porque es lo que un cliente necesita
    para instalarlo, y es el unico sitio donde el dato sobrevive: el paquete publicado no lo lleva.
    `.` cuando el plugin es el repositorio entero.
    """
    if contenido.manifiesto is None or not contenido.manifiesto.es_legible:
        return None
    manifiesto = contenido.manifiesto.contenido
    nombre = manifiesto.get("name")
    if not nombre:
        return None
    return PluginPublicado(
        nombre=str(nombre),
        version=str(manifiesto.get("version", "")),
        subruta=raiz_plugin.relative_to(raiz_repositorio).as_posix() or ".",
    )


def nombre_del_plugin(contenido: ContenidoRepositorio) -> str:
    if contenido.manifiesto is None or not contenido.manifiesto.es_legible:
        return ""
    return contenido.manifiesto.contenido.get("name", "")


def equipos_declarados(contenido: ContenidoRepositorio) -> list[tuple[str, str]]:
    """Todos los `owner_team` del repositorio, con donde se declaro cada uno."""
    declarados: list[tuple[str, str]] = []
    if contenido.gobierno is not None and contenido.gobierno.es_legible:
        equipo = (contenido.gobierno.contenido.get("owner") or {}).get("team")
        if equipo:
            declarados.append((contenido.gobierno.ruta_relativa, equipo))
    for artefacto in (*contenido.skills, *contenido.prompts):
        metadata = (artefacto.frontmatter or {}).get("metadata") or {}
        equipo = metadata.get("owner_team")
        if equipo:
            declarados.append((artefacto.ruta_relativa, equipo))
    return declarados


def artefacto_publicado(tipo: str, ruta: str, frontmatter: dict,
                         raiz: Path, prefijo: str = "") -> ArtefactoPublicado | None:
    """`None` cuando el envelope no esta completo: un artefacto sin gobierno no tiene ficha que
    publicar, y el gate ya lo habra marcado como error.

    `ruta` llega relativa al PLUGIN -- es lo que el adaptador leyo -- y `prefijo` es la subruta del
    plugin dentro del repositorio. La ficha publica la suma de las dos, y el digesto se sigue
    calculando desde `raiz`, que es la raiz del plugin. Ver el porque en `listar_artefactos`.
    """
    metadata = frontmatter.get("metadata") or {}
    identificador = metadata.get("id")
    if not identificador:
        return None
    return ArtefactoPublicado(
        id=identificador,
        tipo=tipo,
        ruta=f"{prefijo}{ruta}",
        owner_team=metadata.get("owner_team", ""),
        owner_contact=metadata.get("owner_contact", ""),
        version=str(metadata.get("version", "")),
        data_classification=metadata.get("data_classification", ""),
        standard_version=str(metadata.get("standard_version", "")),
        sha256=digesto.sha256_de(raiz / ruta),
    )


def listar_artefactos(contenido: ContenidoRepositorio, raiz: Path,
                       prefijo: str = "") -> tuple[ArtefactoPublicado, ...]:
    """Las fichas de este plugin, con la `ruta` RELATIVA AL REPOSITORIO.

    POR QUE EL PREFIJO, y es un defecto MEDIDO en el recorrido de instalacion contra lo publicado. La
    `ruta` se publicaba relativa al PLUGIN -- `commands/x.prompt.md` -- y todos sus consumidores la
    resuelven contra la RAIZ DEL REPOSITORIO: la pista de verificacion de la ficha descarga
    `<repo>/<ruta>` fijado al sha, y el humo hace lo mismo. Con el plugin en la raiz las dos rutas
    coinciden y no se notaba; con el plugin en `plugins/referencia/` el consumidor pedia un archivo
    que no existe, y el sintoma era «el sha256 del prompt no coincide con lo firmado» -- una alarma de
    integridad por un problema de ruta.

    Y HABIA UN SEGUNDO SINTOMA PEOR: la `ruta` dejaba de ser UNICA. Los dos `mcp` del repositorio de
    demo publicaban `ruta=.mcp.json` los dos, asi que dos fichas distintas del catalogo apuntaban al
    mismo archivo y no habia forma de saber a que se referia cada una.

    El digesto se sigue calculando desde `raiz`, que es la raiz del PLUGIN: es donde el archivo esta
    de verdad. Lo que cambia es lo que se PUBLICA, no lo que se lee.
    """
    publicados: list[ArtefactoPublicado] = []
    for coleccion, tipo in TIPO_POR_COLECCION:
        for artefacto in getattr(contenido, coleccion):
            if artefacto.frontmatter is None:
                continue
            publicado = artefacto_publicado(tipo, artefacto.ruta_relativa,
                                             artefacto.frontmatter, raiz, prefijo)
            if publicado is not None:
                publicados.append(publicado)
    del_mcp = mcp_publicado(contenido, raiz, prefijo)
    if del_mcp is not None:
        publicados.append(del_mcp)
    de_hooks = hooks_publicado(contenido, raiz, prefijo)
    if de_hooks is not None:
        publicados.append(de_hooks)
    return tuple(publicados)


def mcp_publicado(contenido: ContenidoRepositorio, raiz: Path,
                   prefijo: str = "") -> ArtefactoPublicado | None:
    """El `mcp` como artefacto del predicado, o `None` si no hay o no esta gobernado.

    Va aparte de los demas porque su metadata NO esta en un frontmatter -- un `.mcp.json` es
    configuracion del cliente y no admite uno -- sino en el `GOVERNANCE.json` del plugin, bajo la
    clave `mcp`.

    HEREDA EL ENVELOPE DEL PLUGIN: dueno, clasificacion y version del estandar salen del gobierno, no
    de una declaracion propia. Un `mcp` es uno por plugin, asi que declararlos aparte serian cinco
    campos duplicados -- y duplicarlos es pedir que divergan. Lo unico que declara por su cuenta es la
    custodia de la CREDENCIAL, que es de otro equipo.

    EL `sha256` ES DEL `.mcp.json`, que es el archivo que puede cambiar sin que cambie nada mas. Y
    `tools_digest` se copia de lo declarado: es la referencia contra la que la comprobacion periodica
    detecta que el servidor cambio sus herramientas, y aqui viaja FIRMADA.
    """
    if contenido.mcp is None or contenido.gobierno is None:
        return None
    if not contenido.gobierno.es_legible:
        return None
    gobierno = contenido.gobierno.contenido
    bloque = gobierno.get("mcp")
    if not isinstance(bloque, dict) or not gobierno.get("id"):
        return None
    dueno = gobierno.get("owner") or {}
    return ArtefactoPublicado(
        # El `mcp` no tiene id propio: es una capacidad DEL plugin, asi que se identifica con el suyo
        # mas el tipo. Un id inventado aparte seria un segundo nombre para la misma cosa.
        id=f"{gobierno['id']}.{TIPO_MCP}",
        tipo=TIPO_MCP,
        # Con el prefijo del plugin: sin el, los dos `mcp` de un repositorio con varios plugins
        # publicaban `.mcp.json` los DOS, y dos fichas distintas apuntaban al mismo archivo.
        ruta=f"{prefijo}{contenido.mcp.ruta_relativa}",
        owner_team=dueno.get("team", ""),
        owner_contact=dueno.get("contact", ""),
        version=str(gobierno.get("standard_version", "")),
        data_classification=gobierno.get("data_classification", ""),
        standard_version=str(gobierno.get("standard_version", "")),
        sha256=digesto.sha256_de(raiz / contenido.mcp.ruta_relativa),
        tools_digest=_digest_de_herramientas_declarado(bloque),
        servidores=_servidores_publicados(bloque),
    )


def _servidores_publicados(gobierno_del_mcp: dict) -> tuple:
    """Un elemento por servidor con lo que la comprobacion de deriva necesita para funcionar.

    `nombre`, `endpoint` y `tools_digest`. El endpoint va porque sin el no hay a donde conectarse, y
    tiene que ir FIRMADO por el mismo motivo que el digesto: si saliera del `GOVERNANCE.json`, alguien
    podria apuntar la comprobacion a un servidor limpio mientras el cliente usa otro.

    Se publica el nombre aunque no sea un control de seguridad -- la plataforma lo dice -- porque es lo
    que una persona reconoce en el catalogo. Lo que identifica al servidor para cualquier decision es su
    endpoint.

    Los `stdio` se incluyen SIN endpoint: no se les puede consultar la superficie de herramientas, asi
    que la deriva los marcara «sin comprobar», que es un estado legitimo y visible. Omitirlos daria una
    lista de servidores que no coincide con la del gobierno.
    """
    servidores = gobierno_del_mcp.get("servers") or []
    return tuple(
        {"nombre": str(s.get("name", "")),
         "endpoint": str(s.get("endpoint", "")),
         "tools_digest": str(s.get("tools_digest", ""))}
        for s in servidores if isinstance(s, dict))


def hooks_publicado(contenido: ContenidoRepositorio, raiz: Path,
                     prefijo: str = "") -> ArtefactoPublicado | None:
    """El `hooks` como artefacto del predicado, con el digesto de sus SCRIPTS.

    POR QUE EXISTE. `hooks` era el unico de los cinco tipos sin ficha: se declaraba en el inventario y
    se aprobaba en el `GOVERNANCE.json`, pero no llegaba al catalogo ni llevaba digesto propio. O sea
    que el tipo que EJECUTA CODIGO era el unico cuyo contenido no se podia verificar archivo a archivo,
    y su integridad dependia solo del digesto del paquete completo.

    DOS NIVELES DE DIGESTO. `sha256` es el del `hooks.json`; `scripts` lleva el de CADA script que ese
    JSON manda ejecutar; y `scripts_digest` cubre el conjunto -- el JSON y todos sus scripts --. El
    primero y el tercero responden «cambio algo»; el segundo responde «que cambio». Firmar solo el JSON
    seria firmar el indice de un libro: el JSON declara comandos y los scripts son los que actuan.

    HEREDA EL ENVELOPE DEL PLUGIN, igual que el `mcp`, y por el mismo motivo: es uno por unidad, asi
    que declarar dueno y clasificacion aparte serian campos duplicados que acabarian divergiendo.
    """
    if contenido.hooks is None or not contenido.hooks.es_legible:
        return None
    if contenido.gobierno is None or not contenido.gobierno.es_legible:
        return None
    gobierno = contenido.gobierno.contenido
    if not isinstance(gobierno.get("hooks"), dict) or not gobierno.get("id"):
        return None
    dueno = gobierno.get("owner") or {}
    del_json = digesto.sha256_de(raiz / contenido.hooks.ruta_relativa)
    por_script = _digestos_de_scripts(contenido.hooks.contenido, raiz)
    return ArtefactoPublicado(
        # Como el `mcp`: no tiene id propio, es una capacidad DE la unidad. Un id inventado aparte
        # seria un segundo nombre para la misma cosa.
        id=f"{gobierno['id']}.{TIPO_HOOKS}",
        tipo=TIPO_HOOKS,
        ruta=f"{prefijo}{contenido.hooks.ruta_relativa}",
        owner_team=dueno.get("team", ""),
        owner_contact=dueno.get("contact", ""),
        version=str(gobierno.get("standard_version", "")),
        data_classification=gobierno.get("data_classification", ""),
        standard_version=str(gobierno.get("standard_version", "")),
        sha256=del_json,
        # Las rutas de los scripts se publican con el prefijo de la unidad, igual que la del JSON:
        # quien las consume las resuelve contra la raiz del REPOSITORIO.
        scripts={f"{prefijo}{ruta}": sha for ruta, sha in por_script.items()},
        scripts_digest=scripts_de_hooks.digest_del_conjunto(
            {contenido.hooks.ruta_relativa: del_json, **por_script}),
    )


def _digestos_de_scripts(configuracion: dict, raiz: Path) -> dict[str, str]:
    """`ruta -> sha256` de cada script que el hook ejecuta y que EXISTE en el arbol.

    Los ausentes se omiten en vez de publicarse con digesto vacio: la regla del gate ya los senala
    como error, y una ficha con un digesto en blanco invitaria a creer que se verifico algo.
    """
    digestos = {}
    for ruta in scripts_de_hooks.referencias_propias(configuracion):
        archivo = raiz / ruta
        if archivo.is_file():
            digestos[ruta] = digesto.sha256_de(archivo)
    return digestos


def _digest_de_herramientas_declarado(gobierno_del_mcp: dict) -> str:
    """El `tools_digest` declarado, cuando TODOS los servidores declaran el mismo.

    Con un solo servidor -- el caso normal -- es el suyo. Con varios, se concatenan en orden de
    nombre y se vuelve a hashear, para que el predicado lleve UN valor por artefacto: el `mcp` es un
    artefacto, no uno por servidor. Vacio si ninguno lo declara, que es legitimo cuando todos son
    descargables y fijados.
    """
    servidores = gobierno_del_mcp.get("servers") or []
    declarados = sorted(
        str(s.get("tools_digest")) for s in servidores
        if isinstance(s, dict) and s.get("tools_digest"))
    if not declarados:
        return ""
    if len(declarados) == 1:
        return declarados[0]
    return hashlib.sha256("".join(declarados).encode("utf-8")).hexdigest()


def custodia_declarada(contenido: ContenidoRepositorio) -> dict:
    """El bloque `ownership` del `.mcp.json`, si lo hay. Se propaga tal cual: la regla ya comprobo
    que este completo, y aqui solo se transporta hacia el predicado firmado."""
    if contenido.mcp is None or not contenido.mcp.es_legible:
        return {}
    return (contenido.mcp.contenido.get("credentials") or {}).get("ownership") or {}
