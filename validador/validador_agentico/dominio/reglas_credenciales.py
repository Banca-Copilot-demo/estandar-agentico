"""Quien custodia la credencial de un `mcp` tiene que estar declarado.

EL DEFECTO QUE CIERRA. El artefacto `mcp` viaja SIN secreto -- G3 rechaza cualquier token literal --,
asi que lleva solo una referencia. Al instalar, el cliente muestra un prompt pidiendo el valor, y el
desarrollador se queda ahi: **el `owner_team` del artefacto es quien lo PUBLICO, y el token lo da
quien ADMINISTRA el servicio.** Son dos duenos distintos, y sin declarar el segundo el flujo termina
en un correo a ciegas.

NO EXISTE CONVENCION EN LA INDUSTRIA PARA ESTO, y conviene saberlo: el `server.json` del registro
oficial de MCP declara QUE credencial hace falta y que es secreta -- `isRequired`, `isSecret` -- pero
no su dueno. Tampoco Backstage tiene una anotacion de «como se solicita el acceso». Lo unico que se
toma prestado de ahi es la regla del dueno: SIEMPRE un grupo, nunca una persona, porque un dueno
individual deja la entrada huerfana en cuanto cambia de puesto.

POR QUE SOLO SE EXIGE CON `secret-ref`. Con `oauth` o `workload-identity` el desarrollador se
autentica con su propia identidad y no hay nada que pedirle a nadie; con `none` no hay credencial. El
unico caso en que alguien tiene que CONCEDER algo a mano es la referencia a un secreto.
"""
from __future__ import annotations

from enum import Enum

from validador_agentico.dominio import variables_mcp
from validador_agentico.dominio.gobierno_mcp import GobiernoMcp
from validador_agentico.dominio.hallazgo import Hallazgo, aviso, error


class MecanismoCredencial(str, Enum):
    NINGUNO = "none"
    REFERENCIA_A_SECRETO = "secret-ref"
    OAUTH = "oauth"
    IDENTIDAD_DE_CARGA = "workload-identity"


# Solo este mecanismo obliga a que alguien conceda un acceso a mano.
_EXIGE_DUENO = MecanismoCredencial.REFERENCIA_A_SECRETO
_CAMPOS_OBLIGATORIOS = ("credential_owner", "access_request_url")
# Un dueno con arroba es una persona, y una persona deja la entrada huerfana al cambiar de puesto.
_MARCA_DE_PERSONA = "@"


def revisar_credenciales(donde: str, credenciales: dict | None) -> list[Hallazgo]:
    """Revisa el bloque `credentials` de un artefacto `mcp`."""
    if not credenciales:
        return [error(donde, "un `mcp` tiene que declarar `credentials`: sin eso no se sabe si "
                             "necesita secreto ni quien lo concede")]

    mecanismo = credenciales.get("mechanism")
    if mecanismo not in {m.value for m in MecanismoCredencial}:
        return [error(donde, f"`credentials.mechanism` invalido: {mecanismo!r}. Validos: "
                             f"{', '.join(m.value for m in MecanismoCredencial)}")]

    if mecanismo != _EXIGE_DUENO.value:
        return []

    propiedad = credenciales.get("ownership") or {}
    hallazgos = [
        error(donde, f"`credentials.ownership.{campo}` falta: con `secret-ref` alguien tiene que "
                     "conceder el acceso, y el desarrollador necesita saber quien")
        for campo in _CAMPOS_OBLIGATORIOS if not propiedad.get(campo)
    ]

    dueno = propiedad.get("credential_owner", "")
    if dueno and _MARCA_DE_PERSONA in dueno:
        hallazgos.append(aviso(
            donde, f"`credential_owner` parece una persona ({dueno}): declara un EQUIPO. Un dueno "
                   "individual deja la entrada sin dueno en cuanto cambia de puesto"))
    return hallazgos


# ── La lista VERIFICABLE de credenciales ────────────────────────────────────────────────────────
_CLAVE_NOMBRE = "name"
_CLAVE_SITIO = "kind"


def revisar_credenciales_declaradas(donde: str, gobierno: GobiernoMcp,
                                     servidores_configurados: dict) -> list[Hallazgo]:
    """Lo declarado en `credentials` contra las `${VAR}` que el `.mcp.json` usa de verdad.

    ESTA ES LA COMPROBACION QUE ANTES NO EXISTIA, y su ausencia es lo que hacia inutil al campo. Con
    `{"mechanism": "none"}` el gobierno AFIRMABA que no habia credencial y el gate se lo creia, porque
    no habia nada contra que contrastarlo. Declarar cero credenciales y traer una cabecera
    `Authorization: ${API_TOKEN}` salia CONFORME -- y ese es justo el caso en que un aprobador cree
    haber revisado «un servidor publico sin credencial».

    SE COTEJA EN LAS DOS DIRECCIONES, por el mismo motivo que el cotejo de servidores:

      - una `${VAR}` que se USA y no se declara: es una credencial que nadie aprobo, que no tiene
        custodio conocido y que el desarrollador va a tener que conseguir sin saber a quien pedirsela.
        ERROR.
      - una credencial DECLARADA que el archivo no usa: el aprobador reviso un acceso que no se pide.
        AVISO y no error, y la diferencia esta razonada: sobra permiso declarado, que es un problema
        de higiene, no una via de acceso abierta. Ademas hay un caso legitimo -- una credencial que el
        servidor pide por su cuenta al arrancar y que no aparece en el archivo --, y convertirlo en
        error obligaria a mentir en el gobierno para pasar el gate.

    El `kind` tambien se coteja: declarar como `env` lo que viaja en una cabecera cambia quien lo ve
    -- una cabecera sale por la red a un tercero -- y quien la aprueba necesita saberlo.
    """
    if gobierno.forma_antigua:
        # La forma vieja no tiene lista que cotejar. Su aviso de migracion ya lo dice todo, y anadir
        # aqui «no declaras credenciales» seria un segundo hallazgo por el mismo defecto.
        return []

    observadas = variables_mcp.observadas(servidores_configurados)
    declaradas = {
        (servidor.nombre, str(credencial.get(_CLAVE_NOMBRE, ""))): str(credencial.get(_CLAVE_SITIO, ""))
        for servidor in gobierno.servidores.values()
        for credencial in servidor.credenciales
    }

    hallazgos: list[Hallazgo] = []
    for credencial in observadas:
        clave = (credencial.servidor, credencial.nombre)
        if clave not in declaradas:
            hallazgos.append(error(
                donde,
                f"el servidor `{credencial.servidor}` usa `${{{credencial.nombre}}}` en "
                f"`{credencial.sitio.value}` y el gobierno no lo declara en `credentials`. Es una "
                f"credencial que nadie aprobo y de la que no consta custodio: quien instale el plugin "
                f"tendra que conseguirla sin saber a quien pedirsela"))
            continue
        if declaradas[clave] and declaradas[clave] != credencial.sitio.value:
            hallazgos.append(error(
                donde,
                f"el servidor `{credencial.servidor}` declara `{credencial.nombre}` como "
                f"`{declaradas[clave]}` y el `.mcp.json` la usa como `{credencial.sitio.value}`. No "
                f"es un matiz: una cabecera SALE POR LA RED al servidor del tercero y una variable de "
                f"entorno se queda en el proceso, asi que quien aprueba esta valorando otra cosa"))

    usadas = {(c.servidor, c.nombre) for c in observadas}
    hallazgos += [
        aviso(donde,
              f"el servidor `{servidor}` declara la credencial `{nombre}` y el `.mcp.json` no la usa "
              f"en ningun `env` ni cabecera: o sobra en el gobierno, o el servidor la pide por su "
              f"cuenta al arrancar -- y entonces conviene decirlo en las notas de la aprobacion")
        for (servidor, nombre) in sorted(declaradas)
        if (servidor, nombre) not in usadas
    ]
    return hallazgos
