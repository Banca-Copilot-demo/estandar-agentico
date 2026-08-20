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
