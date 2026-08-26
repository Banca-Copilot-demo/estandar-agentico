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
