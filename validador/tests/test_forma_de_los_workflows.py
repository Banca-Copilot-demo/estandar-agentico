"""Los workflows y composite actions del estandar son YAML valido.

EL DEFECTO QUE FIJA, medido en esta sesion: al anadir un paso a `publicar/action.yml` se metio codigo
Python MULTILINEA dentro de un bloque `run:`. Las lineas quedaron a columna cero, que es donde el
escalar de bloque termina, y el archivo dejo de ser YAML valido.

POR QUE HACIA FALTA UNA PRUEBA Y NO BASTABA CON MIRARLO. El fallo no lo detecta nada del repositorio:
ni el gate, ni las pruebas, ni el editor. Lo habria descubierto GitHub al intentar ejecutar el
workflow -- es decir, al publicar --, y la publicacion es justo el momento en el que un fallo cuesta
mas: la etiqueta ya existe y, con releases inmutables, no se puede rehacer.

Es ademas una clase de defecto que se repite: `run:` acepta cualquier texto, asi que invita a pegar
scripts dentro. Por eso la comprobacion es sobre TODOS los archivos y no sobre el que se rompio.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

_RAIZ = Path(__file__).resolve().parents[2]
_WORKFLOWS = sorted((_RAIZ / ".github" / "workflows").glob("*.yml"))
_ACTIONS = sorted((_RAIZ / ".github" / "actions").glob("*/action.yml"))
_TODOS = _WORKFLOWS + _ACTIONS


def _identificador(ruta: Path) -> str:
    return f"{ruta.parent.name}/{ruta.name}"


def test_hay_workflows_y_actions_que_comprobar():
    """Si los globs dejaran de encontrar archivos -- por una reorganizacion de carpetas -- las
    pruebas de abajo pasarian sin comprobar nada, que es peor que fallar."""
    assert _WORKFLOWS, "no se encontro ningun workflow: el glob quedo obsoleto"
    assert _ACTIONS, "no se encontro ninguna composite action: el glob quedo obsoleto"


@pytest.mark.parametrize("ruta", _TODOS, ids=[_identificador(r) for r in _TODOS])
def test_es_yaml_valido(ruta):
    try:
        documento = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as fallo:
        pytest.fail(f"{_identificador(ruta)} no es YAML valido: {fallo}")
    assert isinstance(documento, dict), f"{_identificador(ruta)} no define un mapa en la raiz"


def _pasos_de(documento: dict) -> list[tuple[str, dict]]:
    """Todos los pasos del archivo, con el nombre de su job o `runs` para poder senalarlos."""
    pasos = []
    for nombre, job in (documento.get("jobs") or {}).items():
        pasos += [(nombre, paso) for paso in (job.get("steps") or [])]
    pasos += [("runs", paso) for paso in ((documento.get("runs") or {}).get("steps") or [])]
    return pasos


@pytest.mark.parametrize("ruta", _TODOS, ids=[_identificador(r) for r in _TODOS])
def test_ningun_paso_consulta_secrets_en_su_if(ruta):
    """REGRESION del defecto mas caro encontrado en los workflows, y llevaba tiempo activo.

    `if: ${{ secrets.app-id != '' }}` a nivel de PASO no es sintaxis valida: el contexto `secrets` no
    existe ahi. GitHub lo rechaza al ARRANCAR con «Unrecognized named-value: 'secrets'», antes de
    ejecutar nada.

    LO QUE COSTO: el gate de conformidad llevaba fallando en `startup_failure` en TODOS los pull
    requests, asi que no corria ninguna comprobacion y los cambios se mergeaban sin validar. Y falla
    de la peor forma imaginable -- en 0 segundos, sin jobs, sin anotaciones y sin log --. La unica
    señal era que la lista de workflows mostraba el NOMBRE DEL ARCHIVO en lugar del nombre declarado,
    porque GitHub ni siquiera habia podido leerlo.

    La forma correcta es pasar el secreto por `env` del job y consultar `env` en el `if`.
    """
    documento = yaml.safe_load(ruta.read_text(encoding="utf-8"))

    culpables = [
        f"{job}: {paso.get('name', '(sin nombre)')}"
        for job, paso in _pasos_de(documento)
        if "secrets." in str(paso.get("if", ""))
    ]

    assert not culpables, (
        f"{_identificador(ruta)} consulta `secrets` en el `if` de un paso: {culpables}. "
        "El contexto `secrets` no existe ahi y GitHub rechaza el workflow AL ARRANCAR. "
        "Pasa el secreto por `env` del job y comprueba `env` en el `if`")


def _workflow_llamado(usa: str) -> str:
    """El nombre de archivo del workflow reutilizable de ESTE repositorio que un job invoca, o "".

    Solo se resuelven los de este repositorio: de un workflow ajeno no se puede leer que secretos
    declara, asi que sobre esos no hay nada que comprobar.
    """
    if ".github/workflows/" not in usa or "estandar-agentico" not in usa:
        return ""
    return usa.split(".github/workflows/", 1)[1].split("@", 1)[0]


def _secretos_declarados_por(nombre: str) -> set[str]:
    ruta = _RAIZ / ".github" / "workflows" / nombre
    if not ruta.is_file():
        return set()
    documento = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    # `on` es la clave literal del disparador, pero YAML 1.1 la lee como el booleano True.
    disparadores = documento.get("on") or documento.get(True) or {}
    return set((disparadores.get("workflow_call") or {}).get("secrets") or {})


@pytest.mark.parametrize("ruta", _WORKFLOWS, ids=[_identificador(r) for r in _WORKFLOWS])
def test_quien_llama_a_un_workflow_del_repo_nombra_todos_sus_secretos(ruta):
    """Un workflow reutilizable NO hereda los secretos de quien lo llama: hay que pasarlos.

    MEDIDO en una publicacion real. `publicar.yml` invocaba a `promocionar.yml` pasando solo la
    etiqueta, asi que la promocion se quedaba sin credenciales de Port. Resultado:
    `demo.sdlc.revisar-jql--v0.1.2` quedo promocionado y distribuido mientras su ficha seguia
    diciendo `conformant` y `en_marketplace: false` -- los dos catalogos contando cosas distintas del
    mismo artefacto --.

    NO FALLA RUIDOSAMENTE, que es lo que lo hace caro: los secretos son opcionales, asi que la
    publicacion termina en VERDE y lo unico que queda es un aviso dentro del log de un job.

    LA REGLA ES NOMBRARLOS, no pasarlos siempre. Omitir un secreto a proposito sigue siendo legitimo
    -- se pasa vacio --; lo que deja de ser posible es omitirlo sin enterarse.
    """
    documento = yaml.safe_load(ruta.read_text(encoding="utf-8"))

    culpables = []
    for nombre_job, job in (documento.get("jobs") or {}).items():
        llamado = _workflow_llamado(str(job.get("uses", "")))
        if not llamado:
            continue
        pasados = job.get("secrets")
        if pasados == "inherit":
            continue
        faltan = _secretos_declarados_por(llamado) - set(pasados or {})
        if faltan:
            culpables.append(f"{nombre_job} -> {llamado}: {sorted(faltan)}")

    assert not culpables, (
        f"{_identificador(ruta)} invoca workflows sin nombrar todos sus secretos: {culpables}. "
        "Un workflow reutilizable no los hereda: pasalos, o pasalos vacios si la omision es "
        "deliberada. Sin ellos el trabajo se degrada en silencio y la publicacion termina en verde")


def test_todo_find_de_la_evaluacion_poda_el_clon_del_estandar():
    """El workflow de evaluacion clona el estandar DENTRO del workspace: sus `find` tienen que saltarselo.

    MEDIDO, y en dos sitios distintos con danos distintos:

    - La BUSQUEDA DE SUITES se tragaba `.estandar/plantillas/artefactos/evals/promptfooconfig.yaml` y
      dejaba en rojo a un repositorio de dominio por una plantilla que no controla (run 33016050350 de
      `agentes-sdlc`).
    - El COLOCADO DE ARTEFACTOS copiaba al cliente los skills del asistente de autoria y el `SKILL.md`
      de `plantillas/` (run 33018092035, `skill disponible: skill`). Este es peor: no pone en rojo algo
      ajeno, CONTAMINA el entorno donde se mide el artefacto propio, y el cliente elige que skill
      cargar por su `description`.

    LA PRUEBA ES SOBRE TODOS LOS `find`, NO SOBRE LOS DOS CONOCIDOS. Arreglar los dos y no fijar la
    regla deja el tercero para el proximo que anada un paso que recorra el workspace, y ese descubrira
    el mismo defecto desde cero.

    SE MIRA CADA `find`, NO CADA PASO, y la primera version de esta prueba no lo hacia: el paso que
    coloca los artefactos tiene DOS -- uno para skills y otro para agentes -- y comprobar el texto del
    paso entero dejaba que el segundo tapara al primero. Comprobado desconectando la poda del `find`
    de skills: la prueba seguia pasando.
    """
    ruta = _RAIZ / ".github" / "workflows" / "evaluar.yml"
    documento = yaml.safe_load(ruta.read_text(encoding="utf-8"))

    culpables = []
    for _, paso in _pasos_de(documento):
        # Las continuaciones de linea se unen: un `find` partido en varias lineas es un solo comando.
        guion = str(paso.get("run", "")).replace("\\\n", " ")
        for comando in re.findall(r"find .*", guion):
            if "DIRECTORIO_DEL_ESTANDAR" not in comando:
                culpables.append(f"{paso.get('name', '(sin nombre)')}: {comando.strip()[:80]}")

    assert not culpables, (
        f"estos `find` recorren el workspace sin podar el clon del estandar: {culpables}. "
        "Ese directorio lo crea este mismo workflow y no pertenece al repositorio evaluado: "
        "recorrerlo mete plantillas y artefactos ajenos en la evaluacion")


@pytest.mark.parametrize("ruta", _TODOS, ids=[_identificador(r) for r in _TODOS])
def test_declara_lo_minimo_para_ejecutarse(ruta):
    """Un YAML valido puede seguir sin ser un workflow. Un archivo sin `jobs` ni `runs` es sintaxis
    correcta que GitHub ignora, y eso vuelve a fallar en silencio."""
    documento = yaml.safe_load(ruta.read_text(encoding="utf-8"))

    assert "jobs" in documento or "runs" in documento, \
        f"{_identificador(ruta)} no declara `jobs` ni `runs`: no lo ejecutaria nadie"


# --- La suite de evaluacion se ejecuta UNA sola vez por artefacto -------------------------------

_PUBLICAR = _RAIZ / ".github" / "workflows" / "publicar.yml"
_EVALUAR = _RAIZ / ".github" / "workflows" / "evaluar.yml"


def _jobs_de(ruta: Path) -> dict:
    return yaml.safe_load(ruta.read_text(encoding="utf-8")).get("jobs") or {}


def test_publicar_no_vuelve_a_ejecutar_la_suite_de_evaluacion():
    """MEDIDO, y es la razon de que la segunda corrida se retirara: el veredicto de la suite NO es
    reproducible. La MISMA suite sobre el MISMO contenido dio 3 de 3 en el pull request, 2 de 3 al
    certificar y verde al reejecutar.

    Con un juez asi, evaluar dos veces no confirma nada: solo anade una segunda tirada de dado sobre
    un artefacto ya revisado, y gasta otra vez el UNICO token de inferencia de la organizacion. Y en
    la practica salen mas de dos, porque cada push al pull request reejecuta.

    El contenido es ademas literalmente el mismo: el etiquetado es automatico justo tras el merge,
    asi que la etiqueta apunta al commit del merge.
    """
    culpables = [
        nombre for nombre, job in _jobs_de(_PUBLICAR).items()
        if "workflows/evaluar.yml" in str(job.get("uses", ""))
    ]

    assert not culpables, (
        f"publicar.yml vuelve a invocar la evaluacion en {culpables}. La suite se ejecuta UNA vez, "
        "en la solicitud de cambio: una segunda corrida de un juez no reproducible no confirma la "
        "primera, solo duplica el gasto del token y las ocasiones de contradecirse")


def test_promocionar_depende_de_un_job_que_comprueba_la_certificacion():
    """REGRESION del defecto que aparece si se quita la segunda evaluacion sin poner nada en su sitio.

    `promocionar` colgaba de `certificar` y de su veredicto. Al retirar esa corrida, la tentacion es
    dejar `promocionar` con `needs: publicar` y sin condicion -- y entonces TODO lo que se publica se
    certifica, incluido lo que nadie evaluo --. Esta prueba exige que siga habiendo un job entre
    medias y que su salida siga condicionando la promocion.
    """
    jobs = _jobs_de(_PUBLICAR)
    promocionar = jobs.get("promocionar")
    assert promocionar, "publicar.yml ya no tiene job `promocionar`"

    assert _guardian_de_la_promocion(jobs), (
        f"`promocionar` no esta condicionado por la salida de ningun job guardian "
        f"(needs={promocionar.get('needs')!r}, if={promocionar.get('if')!r}). Sin el, se promociona todo lo que se publica: "
        "un artefacto SIN suites tambien queda en verde, porque un trabajo saltado reporta «Success»")


def _guardian_de_la_promocion(jobs: dict) -> str | None:
    """El job que se interpone entre publicar y promocionar y cuya salida condiciona la promocion."""
    promocionar = jobs.get("promocionar") or {}
    depende = promocionar.get("needs")
    depende = [depende] if isinstance(depende, str) else list(depende or [])
    condicion = str(promocionar.get("if", ""))
    return next((j for j in depende if j != "publicar" and f"needs.{j}.outputs" in condicion), None)


def test_el_guardian_de_la_promocion_comprueba_que_haya_suites_y_no_solo_el_color():
    """EL FALLO MAS FACIL DE COMETER AQUI, y esta MEDIDO: un artefacto sin suites sale VERDE. El
    trabajo de comportamiento se salta, y un trabajo saltado reporta «Success» -- el pull request
    queda CLEAN --. Un guardian que solo mirase el color certificaria artefactos que nadie evaluo,
    que es lo contrario del proposito del estado.

    Por eso se exige que el guardian use la MISMA deteccion de suites que la evaluacion, y no una
    tercera definicion escrita a mano de «que es una suite» (G2/P9).
    """
    jobs = _jobs_de(_PUBLICAR)
    guardian = _guardian_de_la_promocion(jobs)
    assert guardian, "no hay ningun job guardian entre `publicar` y `promocionar`"

    acciones = [str(paso.get("uses", "")) for paso in (jobs[guardian].get("steps") or [])]
    assert any("actions/detectar-suites" in a for a in acciones), (
        f"el job `{guardian}` no usa la accion `detectar-suites`: no sabe si la unidad publicada "
        "trae suites, asi que promocionaria lo que nadie evaluo -- o traeria una segunda definicion "
        f"de que es una suite. Pasos con `uses`: {acciones}")


def test_el_guardian_no_confunde_un_fallo_de_la_consulta_con_una_comprobacion_ausente():
    """MEDIDO ejecutando el bloque `run:` del guardian contra un `gh` que devuelve 1: sin
    `set -o pipefail` el veredicto era «ausente», no «no se pudo consultar».

    La consulta es una tuberia (`gh ... | tail -1`) y el estado de una tuberia es el de su ULTIMO
    comando, que aqui es `tail` y siempre vale 0. Sin `pipefail`, un 403 por falta de `checks: read`
    se leeria como «este commit no tiene comprobacion» y el aviso mandaria a mirar la suite en vez
    del bloque de permisos. Es el mismo modo de fallo que ya costo una medicion en este repositorio,
    donde `comprobar-estado.sh | head` devolvia el codigo de `head`.
    """
    jobs = _jobs_de(_PUBLICAR)
    guardian = _guardian_de_la_promocion(jobs)
    consultas = [
        paso for paso in (jobs[guardian].get("steps") or [])
        if "gh api" in str(paso.get("run", ""))
    ]

    assert consultas, f"el job `{guardian}` ya no consulta la API: esta prueba quedo obsoleta"
    culpables = [p.get("name") for p in consultas if "set -o pipefail" not in p["run"]]
    assert not culpables, (
        f"{culpables} consulta la API a traves de una tuberia sin `set -o pipefail`: el fallo de "
        "`gh` se pierde tras el codigo de salida del ultimo comando, y un 403 se leeria como que "
        "el commit no tiene comprobacion")


def test_el_guardian_busca_la_comprobacion_por_el_nombre_que_le_da_quien_la_emite():
    """El guardian localiza el check-run del commit por su NOMBRE, y ese nombre lo declara el job de
    `evaluar.yml`. Son dos archivos distintos, asi que el texto puede divergir -- y su divergencia NO
    hace ruido: la busqueda simplemente no encuentra nada, se lee como «no existe comprobacion» y
    NADA se certifica nunca. Un estado inalcanzable en silencio es justo el defecto que la promocion
    existe para cerrar.

    Se compara por sufijo a proposito: GitHub nombra el check-run de un workflow reutilizable
    `<job del llamador> / <nombre del job llamado>`, y el prefijo lo elige cada repositorio de
    dominio. Lo unico que el estandar controla es la segunda mitad.
    """
    emitido = _jobs_de(_EVALUAR)["evaluar"]["name"]

    buscados = [
        valor
        for _, paso in _pasos_de(yaml.safe_load(_PUBLICAR.read_text(encoding="utf-8")))
        for clave, valor in (paso.get("env") or {}).items()
        if "NOMBRE_DE_LA_COMPROBACION" in clave
    ]

    assert buscados, ("publicar.yml no declara el nombre de la comprobacion que busca en un `env` "
                      "nombrado, asi que esta prueba no puede vigilar que coincida")
    assert all(b == emitido for b in buscados), (
        f"publicar.yml busca {buscados} y `evaluar.yml` emite {emitido!r}. Si no coinciden, la "
        "busqueda no encuentra la comprobacion, se lee como «no existe» y ningun artefacto se "
        "certifica jamas -- sin un solo error en rojo")
