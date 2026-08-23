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
from validador_agentico.dominio.hallazgo import (
    ArtefactoPublicado,
    Inventario,
    PluginPublicado,
)

# Que colecciones del contenido se publican como ficha, y con que `tipo` en el predicado firmado.
TIPO_POR_COLECCION = (("skills", "skill"), ("prompts", "prompt"))
# El `mcp` no esta en esa tabla porque no es una coleccion de artefactos con frontmatter: es UN
# archivo de configuracion mas su `METADATA.json` hermano. Se proyecta aparte.
TIPO_MCP = "mcp"



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
                         raiz: Path) -> ArtefactoPublicado | None:
    """`None` cuando el envelope no esta completo: un artefacto sin gobierno no tiene ficha que
    publicar, y el gate ya lo habra marcado como error."""
    metadata = frontmatter.get("metadata") or {}
    identificador = metadata.get("id")
    if not identificador:
        return None
    return ArtefactoPublicado(
        id=identificador,
        tipo=tipo,
        ruta=ruta,
        owner_team=metadata.get("owner_team", ""),
        owner_contact=metadata.get("owner_contact", ""),
        version=str(metadata.get("version", "")),
        data_classification=metadata.get("data_classification", ""),
        standard_version=str(metadata.get("standard_version", "")),
        sha256=digesto.sha256_de(raiz / ruta),
    )


def listar_artefactos(contenido: ContenidoRepositorio,
                       raiz: Path) -> tuple[ArtefactoPublicado, ...]:
    publicados: list[ArtefactoPublicado] = []
    for coleccion, tipo in TIPO_POR_COLECCION:
        for artefacto in getattr(contenido, coleccion):
            if artefacto.frontmatter is None:
                continue
            publicado = artefacto_publicado(tipo, artefacto.ruta_relativa,
                                             artefacto.frontmatter, raiz)
            if publicado is not None:
                publicados.append(publicado)
    del_mcp = mcp_publicado(contenido, raiz)
    if del_mcp is not None:
        publicados.append(del_mcp)
    return tuple(publicados)


def mcp_publicado(contenido: ContenidoRepositorio, raiz: Path) -> ArtefactoPublicado | None:
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
        ruta=contenido.mcp.ruta_relativa,
        owner_team=dueno.get("team", ""),
        owner_contact=dueno.get("contact", ""),
        version=str(gobierno.get("standard_version", "")),
        data_classification=gobierno.get("data_classification", ""),
        standard_version=str(gobierno.get("standard_version", "")),
        sha256=digesto.sha256_de(raiz / contenido.mcp.ruta_relativa),
        tools_digest=_digest_de_herramientas_declarado(bloque),
    )


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
