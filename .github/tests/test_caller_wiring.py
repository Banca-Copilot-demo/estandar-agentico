"""El cableado del llamador: que un repositorio de dominio invoque los gates como el ruleset espera.

POR QUE ESTAS PRUEBAS VIVEN EN EL ESTANDAR Y NO EN CADA REPOSITORIO DE DOMINIO (Y1). Lo que fijan es
identico en todos: los ids de job de los que se componen las comprobaciones requeridas, el
`if: always()` que evita el atasco, el `needs:` que conserva el orden por coste, y los secretos sin
los que una regla degrada en silencio. Copiadas en cada repositorio, la septima copia ya no diria lo
mismo que la primera.

LA DIRECCION ESTA INVERTIDA respecto a una prueba normal, y es a proposito: el codigo que se
comprueba esta en el LLAMADOR, no aqui. `CALLER_WORKFLOWS` trae la ruta de sus workflows, y el
workflow reutilizable `check-caller-wiring.yml` es quien la pone. Sin esa variable el modulo se salta
entero -- asi el propio estandar puede recogerlo en su CI y detectar que este archivo no importa o no
parsea, sin necesitar un llamador de verdad --.

LOS NOMBRES QUE SE COMPRUEBAN SIGUEN EN ESPAÑOL, y no es un olvido (G3b): `conformidad`,
`comportamiento` y `validar` son comprobaciones requeridas del ruleset, emparejadas por texto exacto.
Traducirlas dejaria TODAS las solicitudes de cambio bloqueadas para siempre.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

_CALLER_WORKFLOWS = os.environ.get("CALLER_WORKFLOWS")

pytestmark = pytest.mark.skipif(
    not _CALLER_WORKFLOWS,
    reason="sin CALLER_WORKFLOWS no hay llamador que comprobar; lo pone check-caller-wiring.yml")

# El workflow del llamador que cablea los dos gates, y los del estandar a los que llama.
_CALLER_GATE_WORKFLOW = "validar.yml"
_EVALUATION_WORKFLOW = "workflows/evaluar.yml"
_CONFORMANCE_WORKFLOW = "workflows/validar.yml"

# Los ids de job de los que se componen las comprobaciones REQUERIDAS del ruleset. No se traducen.
_CONFORMANCE_JOB_ID = "conformidad"
_EVALUATION_JOB_ID = "comportamiento"


def _jobs() -> dict:
    path = Path(_CALLER_WORKFLOWS) / _CALLER_GATE_WORKFLOW
    assert path.is_file(), (
        f"no existe `{path}`: el llamador no tiene el workflow que cablea los gates, o "
        "`CALLER_WORKFLOWS` no apunta a su directorio de workflows")
    return yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]


def _job_calling(reusable_workflow: str) -> tuple[str, dict]:
    for job_id, job in _jobs().items():
        if reusable_workflow in str(job.get("uses", "")):
            return job_id, job
    raise AssertionError(
        f"ningun job de `{_CALLER_GATE_WORKFLOW}` llama a `{reusable_workflow}`: o se retiro ese "
        "gate, o el `uses:` cambio de forma y esta prueba dejo de mirar nada")


def _evaluation_job() -> tuple[str, dict]:
    return _job_calling(_EVALUATION_WORKFLOW)


def _conformance_job() -> tuple[str, dict]:
    return _job_calling(_CONFORMANCE_WORKFLOW)


def test_el_brazo_de_evaluacion_sigue_llamandose_comportamiento():
    """LA OTRA MITAD DEL NOMBRE REQUERIDO. `comportamiento / Veredicto de comportamiento` se compone
    del ID de ESE job y del `name:` del agregador del reutilizable; el ruleset lo exige por
    coincidencia EXACTA. Renombrar el job -- tentador ahora que el canal tambien valida -- deja la
    comprobacion requerida sin nadie que la emita, y el pull request se atasca en «Expected — waiting
    for status» en vez de rechazarse. MEDIDO: ese atasco ya ocurrio dos veces en este proyecto."""
    job_id, _ = _evaluation_job()

    assert job_id == _EVALUATION_JOB_ID, (
        f"el job que llama a la evaluacion se llama `{job_id}`: la comprobacion pasaria a ser "
        f"`{job_id} / Veredicto de comportamiento` y el ruleset seguiria esperando la de "
        f"`{_EVALUATION_JOB_ID}`")


def test_el_brazo_de_evaluacion_arranca_aunque_la_conformidad_falle():
    """SIN ESTO EL GATE SE ATASCA, no se pone en rojo. Un job saltado al menos reporta algo; una
    LLAMADA saltada no reporta nada, y la comprobacion requerida espera para siempre.

    MEDIDO en el commit `f6e00a1a` de `agentes-sdlc`: con `conformidad` en `failure` los check-runs
    eran `failure conformidad / validar` y `skipped comportamiento`, y ninguna linea de veredicto.
    """
    job_id, job = _evaluation_job()

    assert "always()" in str(job.get("if", "")), (
        f"el job `{job_id}` no lleva `if: always()` (if={job.get('if')!r}): con la conformidad en "
        "rojo se salta, y con el se salta la llamada entera, asi que `Veredicto de comportamiento` "
        "-- comprobacion requerida -- no se emite y el pull request queda en «Expected — waiting "
        "for status» en vez de rechazado")


def test_el_orden_frente_a_la_conformidad_se_conserva():
    """LA MITAD QUE NO SE PUEDE PERDER AL ANADIR LA OTRA. `always()` desactiva la condicion, no la
    dependencia: sin el `needs:` la evaluacion correria EN PARALELO con el gate determinista, que es
    pagar inferencia sin esperar a saber si el formato del artefacto es siquiera valido -- el orden
    por COSTE CRECIENTE que estos controles defienden --."""
    job_id, job = _evaluation_job()
    depends_on = job.get("needs") or []
    depends_on = [depends_on] if isinstance(depends_on, str) else depends_on

    assert _CONFORMANCE_JOB_ID in depends_on, (
        f"el job `{job_id}` ya no depende de `{_CONFORMANCE_JOB_ID}` (needs={depends_on!r}): la "
        "evaluacion arrancaria en paralelo al gate determinista y gastaria modelo sin saber si el "
        "artefacto esta bien formado")


def test_el_trabajo_de_conformidad_sigue_llamandose_validar():
    """EL NOMBRE DE LA COMPROBACION REQUERIDA ES `conformidad / validar`, Y SE COMPONE DE DOS MITADES
    QUE VIVEN EN ARCHIVOS DISTINTOS: el ID de ESE job y el `name:` del job del reutilizable. El
    ruleset la exige por coincidencia EXACTA de texto, asi que si cualquiera de las dos cambia, la
    comprobacion deja de emitirse con ese nombre y TODAS las solicitudes de cambio quedan bloqueadas
    para siempre en «Expected — waiting for status», esperando un estado que ya nadie enviara.

    MEDIDO: ese atasco ya ocurrio dos veces en este proyecto, y no se lee como un rechazo -- parece un
    fallo de la plataforma --. Aqui se fija la mitad que el repositorio de dominio controla.
    """
    job_id, _ = _conformance_job()

    assert job_id == _CONFORMANCE_JOB_ID, (
        f"el job del gate determinista se llama `{job_id}` y no `{_CONFORMANCE_JOB_ID}`: la "
        f"comprobacion pasaria a llamarse `{job_id} / validar` y el ruleset seguiria esperando "
        f"`{_CONFORMANCE_JOB_ID} / validar`")


def test_la_conformidad_solo_corre_las_reglas_de_repositorio_en_una_solicitud_de_cambio():
    """LA MITAD QUE NO SE VE AL REPARTIR EL GATE. Las reglas de cada unidad se mudaron al canal de su
    unidad, que solo existe en una solicitud de cambio. Si ese job pidiera `repositorio` tambien en el
    push a `main`, las unidades se quedarian SIN VALIDAR en la rama publicada -- en verde, porque nadie
    las estaria mirando --. Y si no pidiera nada, cada unidad se validaria DOS veces en cada pull
    request: en la conformidad y en su canal."""
    _, job = _conformance_job()
    scope = str((job.get("with") or {}).get("alcance", ""))

    assert "repositorio" in scope and "pull_request" in scope, (
        f"el alcance del gate determinista es {scope!r}: tiene que pedir `repositorio` en una "
        "solicitud de cambio -- donde cada unidad tiene su canal -- y el recorrido completo fuera de "
        "ella, donde no hay canales que validen las unidades")


def test_la_evaluacion_recibe_los_secretos_que_necesita_para_comprobar_el_dueno():
    """LA REGLA QUE SE DEBILITA EN SILENCIO AL MUDAR LA VALIDACION. G4 exige que el `owner_team`
    declarado EXISTA en la organizacion, y el `GITHUB_TOKEN` de Actions no puede leer los equipos --
    responde 403, MEDIDO --: sin un token de la App, el validador no comprueba y degrada a AVISO.

    Ahora que la validacion por unidad corre dentro de los canales, olvidarlos no rompe nada visible:
    el gate sigue en verde y un artefacto con un dueño inexistente se publica igual. Es exactamente la
    clase de fallo que este proyecto persigue -- un control en verde que no protege nada --."""
    job_id, job = _evaluation_job()
    secrets = job.get("secrets") or {}

    for secret in ("app-id", "app-key"):
        assert secret in secrets, (
            f"el job `{job_id}` no le pasa `{secret}` a la evaluacion (secrets={sorted(secrets)}): "
            "la validacion de cada unidad corre alli y no podria resolver los equipos de la "
            "organizacion, asi que un `owner_team` inexistente pasaria de ERROR a aviso")
