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
    diciendo `conformant` y `en_marketplace: false` -- Port y el marketplace contando cosas distintas
    del mismo artefacto --.

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


_EXPRESION = re.compile(r"\$\{\{.*?\}\}")


def _plantilla_del_nombre(texto: str) -> str:
    """El texto fijo del nombre de la comprobacion, con la parte variable sustituida por un hueco.

    Las dos mitades se escriben en archivos distintos y una lleva `matrix.unidad` mientras la otra
    lleva la subruta que se publica: comparar los textos literales seria comparar dos expresiones que
    NUNCA pueden ser iguales. Lo que tiene que coincidir es el molde.
    """
    return _EXPRESION.sub("<unidad>", texto).strip()


def _nombres_buscados_por_el_guardian() -> list[str]:
    return [
        valor
        for _, paso in _pasos_de(yaml.safe_load(_PUBLICAR.read_text(encoding="utf-8")))
        for clave, valor in (paso.get("env") or {}).items()
        if "NOMBRE_DE_LA_COMPROBACION" in clave
    ]


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
    emitido = _plantilla_del_nombre(_jobs_de(_EVALUAR)["evaluar"]["name"])
    buscados = [_plantilla_del_nombre(b) for b in _nombres_buscados_por_el_guardian()]

    assert buscados, ("publicar.yml no declara el nombre de la comprobacion que busca en un `env` "
                      "nombrado, asi que esta prueba no puede vigilar que coincida")
    assert all(b == emitido for b in buscados), (
        f"publicar.yml busca {buscados} y `evaluar.yml` emite {emitido!r}. Si no coinciden, la "
        "busqueda no encuentra la comprobacion, se lee como «no existe» y ningun artefacto se "
        "certifica jamas -- sin un solo error en rojo")


# --- Un trabajo de evaluacion POR UNIDAD, y un guardian que pregunta por la suya ----------------
#
# EL DEFECTO QUE FIJA ESTE BLOQUE, medido en el run 33040368778 de `agentes-sdlc`: mientras hubo UN
# trabajo de evaluacion para todo el repositorio, su unica conclusion se contagiaba. `revisar-jql`
# con 3 de 3 y `referencia` con 3 de 3 se quedaron en Conforme porque la suite de `migracion` estaba
# en 2 de 3 -- dos artefactos que cumplian, sin certificar por una unidad que sus equipos no habian
# tocado --. El arreglo tiene dos mitades que solo sirven juntas: que cada unidad EMITA su propia
# comprobacion, y que el guardian PREGUNTE por la de su unidad. Con una sola, el defecto sigue vivo.

def test_la_evaluacion_abre_un_trabajo_por_unidad_y_no_uno_para_todo_el_repositorio():
    """La mitad que EMITE. Sin matriz solo hay una conclusion, y una conclusion compartida no puede
    decir nada de una unidad concreta por mucho que el guardian afine la pregunta."""
    evaluar = _jobs_de(_EVALUAR)["evaluar"]
    matriz = (evaluar.get("strategy") or {}).get("matrix")

    assert matriz, ("el job `evaluar` no declara `strategy.matrix`: vuelve a haber una sola "
                    "conclusion para todo el repositorio, y una suite roja se contagia a las demas")
    assert any("fromJSON" in str(v) for v in matriz.values()), (
        f"la matriz de `evaluar` no sale de un `fromJSON` de la deteccion: {matriz!r}. Una lista "
        "escrita a mano es una segunda definicion de «que unidades hay» y divergiria de la que "
        "decide que suites corren")


def test_el_nombre_del_trabajo_de_evaluacion_lleva_la_unidad():
    """Es lo que hace la comprobacion LOCALIZABLE por unidad -- GitHub nombra el check-run
    `<job del llamador> / <nombre del job llamado>` -- y, de paso, lo que el portal muestra para
    saber que artefacto corre y cual fallo sin abrir un log. Con un nombre fijo, las N celdas
    emitirian N comprobaciones indistinguibles y el guardian no podria elegir la suya."""
    nombre = _jobs_de(_EVALUAR)["evaluar"]["name"]
    variable = (_jobs_de(_EVALUAR)["evaluar"].get("strategy") or {}).get("matrix") or {}

    assert _EXPRESION.search(nombre), (
        f"el `name:` del job de evaluacion es fijo ({nombre!r}): todas las celdas emitirian la misma "
        "comprobacion y el guardian no podria distinguir la de su unidad")
    assert any(f"matrix.{clave}" in nombre for clave in variable), (
        f"el `name:` {nombre!r} no interpola ninguna clave de la matriz {sorted(variable)}: el "
        "nombre varia por algo que no es la unidad que se evalua")


def test_el_guardian_pregunta_por_la_comprobacion_de_SU_unidad():
    """La mitad que PREGUNTA, y la que faltaba cuando se midio el defecto. El acotado por `subruta`
    ya se aplicaba a «¿esta unidad trae suites?», pero «¿su suite paso?» seguia leyendo una senal de
    repositorio. La mitad acotada no sirve de nada si la otra no lo esta."""
    buscados = _nombres_buscados_por_el_guardian()

    assert buscados, "publicar.yml no declara el nombre de la comprobacion que busca"
    culpables = [b for b in buscados if "outputs.subruta" not in b]
    assert not culpables, (
        f"el guardian busca {culpables}, que no lleva la subruta de la unidad publicada: esta "
        "preguntando por una comprobacion de REPOSITORIO, asi que la suite roja de un vecino vuelve "
        "a impedir que se promocione un artefacto que cumple")


def test_la_matriz_esta_guardada_contra_el_caso_vacio():
    """`fromJSON('[]')` NO produce una matriz que se salte: tumba la corrida al arrancar. Y si se
    dejara correr, el `result` de una matriz que no se abre es `skipped`, que leido a la ligera pasa
    por verde -- el mismo modo de fallo del trabajo saltado que reporta «Success», ya medido aqui --.

    Por eso la guarda es un `if:` sobre el booleano de la deteccion, y no una comparacion contra el
    texto del array: cualquier diferencia de serializacion la romperia en silencio.
    """
    condicion = str(_jobs_de(_EVALUAR)["evaluar"].get("if", ""))

    assert "hay-suites" in condicion, (
        f"el job de matriz no esta guardado por `hay-suites` (if={condicion!r}): con cero unidades, "
        "`fromJSON('[]')` tumba la corrida entera al arrancar y no se reporta ninguna comprobacion")


def test_el_tope_de_paralelismo_de_la_matriz_coincide_con_su_constante_nombrada():
    """MEDIDO en el run 33067070476 de `agentes-sdlc`, y el modo de fallo es de los peores que hemos
    visto: `strategy` NO admite expresiones en `max-parallel`. Con
    `max-parallel: ${{ needs.<job>.outputs.<x> }}` el job de matriz NO LLEGA A EXISTIR -- no aparece
    en la lista de trabajos y no emite ninguna comprobacion -- y sin embargo su `result` vale
    `failure`. El agregador entonces anuncia «alguna unidad esta en rojo» cuando no se evaluo
    ninguna, y en el portal no hay ningun job que abrir para descubrirlo.

    Asi que el numero tiene que ser literal. Esta prueba es lo que impide que eso se convierta en un
    segundo sitio donde vive el mismo umbral (P11): la constante `UNIDADES_EN_PARALELO` sigue siendo
    donde esta escrito QUE controla y por que, y aqui se exige que el literal la siga.
    """
    documento = yaml.safe_load(_EVALUAR.read_text(encoding="utf-8"))
    constante = str((documento.get("env") or {}).get("UNIDADES_EN_PARALELO", ""))
    tope = (documento["jobs"]["evaluar"].get("strategy") or {}).get("max-parallel")

    assert constante, ("`evaluar.yml` ya no declara la constante `UNIDADES_EN_PARALELO`: el tope de "
                       "la matriz quedaria como un numero magico sin nada que explique que controla")
    assert "${{" not in str(tope), (
        f"`max-parallel` es una expresion ({tope!r}): `strategy` no la expande, el job de matriz no "
        "llega a existir y su `result` sale `failure` sin haber evaluado nada")
    assert str(tope) == constante, (
        f"`max-parallel: {tope}` no coincide con `UNIDADES_EN_PARALELO: {constante}`. El motor "
        "obliga a repetir el numero; que no divergan es lo unico que mantiene una sola fuente de "
        "verdad para el umbral")


def _agregador_de(jobs: dict) -> tuple[str, dict]:
    salida = str((yaml.safe_load(_EVALUAR.read_text(encoding="utf-8")).get("on")
                  or yaml.safe_load(_EVALUAR.read_text(encoding="utf-8")).get(True))
                 ["workflow_call"]["outputs"]["resultado"]["value"])
    nombre = salida.split("jobs.", 1)[1].split(".", 1)[0]
    return nombre, jobs[nombre]


def test_el_veredicto_que_consume_el_llamador_lo_emite_un_agregador_que_corre_siempre():
    """Con matriz hay N conclusiones y el llamador consume UNA, asi que hace falta un job que las
    combine. Y ese job necesita `if: always()`: sin el, una celda roja lo deja en `skipped`, un job
    saltado reporta «Success» y el gate del pull request se pondria VERDE justo cuando una suite
    acaba de fallar -- ademas de emitir el `resultado` vacio --."""
    jobs = _jobs_de(_EVALUAR)
    nombre, agregador = _agregador_de(jobs)

    assert "always()" in str(agregador.get("if", "")), (
        f"el job `{nombre}` emite el veredicto del workflow sin `if: always()`: una celda roja lo "
        "deja saltado, y un job saltado reporta «Success»")
    depende = agregador.get("needs") or []
    assert "evaluar" in depende, (
        f"el job `{nombre}` no depende de `evaluar` (needs={depende!r}): estaria emitiendo un "
        "veredicto sin mirar el resultado de ninguna unidad")


def test_el_agregador_distingue_el_caso_vacio_de_que_pasaran_todas():
    """UNO CERTIFICA Y EL OTRO NO, asi que colapsarlos es el defecto. Una matriz que no se abre deja
    `needs.evaluar.result` en `skipped`; leerlo como verde certificaria artefactos que nadie evaluo,
    y leerlo como rojo dejaria sin publicar a los repositorios que legitimamente no traen suites. La
    distincion tiene que venir de la senal EXPLICITA de la deteccion, no del `result`."""
    nombre, agregador = _agregador_de(_jobs_de(_EVALUAR))
    guion = "\n".join(str(paso.get("run", "")) for paso in (agregador.get("steps") or []))
    entorno = {c: str(v) for paso in (agregador.get("steps") or [])
               for c, v in (paso.get("env") or {}).items()}

    assert "sin_suites" in guion and "superada" in guion and "fallida" in guion, (
        f"el job `{nombre}` no emite los tres veredictos distintos: colapsarlos hace que «no habia "
        "nada que medir» y «paso todo» se lean igual")
    assert any("hay-suites" in v for v in entorno.values()), (
        f"el job `{nombre}` no recibe `hay-suites` de la deteccion ({sorted(entorno)}): solo le "
        "queda el `result` de la matriz para decidir, y ahi el caso vacio es `skipped`, "
        "indistinguible de un trabajo que se salto por cualquier otro motivo")


def test_el_agregador_detiene_el_cambio_cuando_una_unidad_esta_en_rojo():
    """EL GATE DEL PULL REQUEST TIENE QUE SEGUIR BLOQUEANDO. Con la matriz, la celda roja es un job
    HERMANO del que emite el veredicto, no un antecesor del llamador: sin un `exit 1` explicito en el
    agregador, el workflow reutilizable terminaria en VERDE con una suite en rojo dentro."""
    nombre, agregador = _agregador_de(_jobs_de(_EVALUAR))

    detiene = [paso for paso in (agregador.get("steps") or [])
               if "exit 1" in str(paso.get("run", ""))]

    assert detiene, (
        f"ningun paso de `{nombre}` sale con error: la evaluacion terminaria en verde aunque una "
        "unidad tenga su suite en rojo, y el pull request se podria mergear")
    assert any("fallida" in str(paso.get("if", "")) for paso in detiene), (
        f"el paso que detiene el cambio en `{nombre}` no esta condicionado al veredicto `fallida`: "
        "o detiene siempre, o detiene por algo que no es el veredicto")


# --- La suite se ejecuta UNA sola vez, y la publicacion recupera aquella medicion ---------------

def test_la_evaluacion_no_corre_fuera_de_una_solicitud_de_cambio():
    """LA SEGUNDA PASADA QUE SOBREVIVIO SIN QUE NADIE LA MIRARA. Los repositorios de dominio disparan
    su validacion con `pull_request` Y `push: branches: [main]`, asi que todo cambio se evaluaba DOS
    veces: duplicaba el gasto del unico token de inferencia de la organizacion y multiplicaba las
    ocasiones de que el veredicto se contradijera a si mismo -- MEDIDO sobre el MISMO contenido: 3 de
    3, luego 2 de 3, luego verde --.

    LA GUARDA VA EN EL PRIMER JOB, no en el de la matriz: puesta abajo, la deteccion se pagaria igual
    en cada push a main.
    """
    jobs = _jobs_de(_EVALUAR)
    primero = next(iter(jobs.values()))

    assert "pull_request" in str(primero.get("if", "")), (
        f"el primer job de `evaluar.yml` corre fuera de una solicitud de cambio (if="
        f"{primero.get('if')!r}): el push a main volveria a evaluar lo mismo con otro sha, gastando "
        "una segunda vez el token de inferencia sobre contenido ya medido")


def test_el_guardian_resuelve_de_que_commit_colgaba_la_medicion():
    """EL NUDO QUE ESTO CIERRA. La suite corre en la rama; el merge con squash crea un commit NUEVO
    en `main` -- otro sha -- y es ese el que se etiqueta. Preguntar por las comprobaciones del commit
    etiquetado es preguntar por un commit que nadie evaluo, y solo funcionaba porque el push a main
    lo reevaluaba todo: la respuesta llegaba de la pasada que sobraba.

    No se transporta el veredicto -- un check-run no caduca --: se pregunta de que pull request nacio
    el commit, que es una sola llamada y ningun permiso de escritura.
    """
    guardian = _guardian_de_la_promocion(_jobs_de(_PUBLICAR))
    consultas = "\n".join(str(paso.get("run", ""))
                          for paso in (_jobs_de(_PUBLICAR)[guardian].get("steps") or []))

    assert "/pulls" in consultas, (
        f"el guardian `{guardian}` no resuelve de que pull request nacio el commit etiquetado: "
        "busca la comprobacion en un sha que, tras un merge con squash, nadie evaluo. O eso, o se "
        "esta apoyando otra vez en una segunda evaluacion en el push a main")


def test_el_guardian_no_lee_una_medicion_irrecuperable_como_verde():
    """EL FALLO QUE RECORRE TODA ESTA CADENA: leer «no se sabe» como «paso». Un commit que no llego
    por un pull request no tiene medicion recuperable, y eso no certifica -- pero se dice con su
    motivo, para que el artefacto no se quede en Conforme sin que nadie sepa por que --."""
    guardian = _guardian_de_la_promocion(_jobs_de(_PUBLICAR))
    pasos = _jobs_de(_PUBLICAR)[guardian].get("steps") or []
    decisor = [p for p in pasos if "promociona=" in str(p.get("run", ""))]

    assert decisor, f"el guardian `{guardian}` ya no escribe `promociona`: la prueba quedo obsoleta"
    guion = str(decisor[-1]["run"])

    assert re.search(r'promociona=false', guion), (
        "el guardian no arranca desde `promociona=false`: cualquier camino que no llegue a decidir "
        "dejaria el output vacio, y un output vacio no puede distinguirse de una decision tomada")
    assert guion.index("promociona=false") < guion.index('promociona=true'), (
        "el guardian escribe `promociona=true` antes que el `false` por defecto: si la consulta "
        "muriera entre las dos escrituras, la ausencia de medicion se leeria como verde")


# --- D2: el veredicto del juez se conserva, y sobre todo cuando la suite falla ------------------
#
# EL DEFECTO QUE ESTAS PRUEBAS FIJAN: `promptfoo eval` sin `-o` deja los resultados en el
# `~/.promptfoo` del runner, que muere con el. Del log solo sobrevive la tabla -- respuestas truncadas
# a ~5 lineas y un `[PASS]`/`[FAIL]` pelado --, o sea que EL MOTIVO QUE DIO LA RUBRICA se pierde.
#
# LO QUE COSTO, medido: una suite dio 3/3, luego 2/3 y luego verde sobre EL MISMO CONTENIDO, y se
# lleva toda la sesion llamando a eso «azar del modelo» sin que nadie pueda mirar por que. Esta medido
# ademas que el caso que falla CUMPLE su ancla determinista (`icontains: bloqueante`), asi que lo que
# falla es la rubrica. Hay una decision de politica pendiente -- repetir N veces y votar por mayoria,
# con coste x3 o x5 de inferencia -- que no se puede tomar informadamente a ciegas.
#
# ES UNA PRUEBA DE FORMA SOBRE EL YAML y no puede ser otra cosa: comprobarlo de verdad exigiria una
# corrida de CI con cuota de inferencia. Lo que se vigila es que el cableado no se deshaga.

def _paso_llamado(ruta: Path, fragmento: str) -> dict:
    coincidencias = [paso for _, paso in _pasos_de(yaml.safe_load(ruta.read_text(encoding="utf-8")))
                     if fragmento in str(paso.get("name", ""))]
    assert len(coincidencias) == 1, (
        f"se esperaba exactamente un paso cuyo nombre contenga {fragmento!r} en {_identificador(ruta)}, "
        f"y hay {len(coincidencias)}: la prueba dejaria de vigilar lo que cree vigilar")
    return coincidencias[0]


def test_la_evaluacion_escribe_el_informe_del_juez_con_o_y_no_lo_deja_morir_en_el_runner():
    """Sin `-o`, el motivo de la rubrica no existe en ninguna parte una vez apagado el runner."""
    paso = _paso_llamado(_EVALUAR, "Ejecutar las suites")
    guion = str(paso.get("run", "")).replace("\\\n", " ")

    assert re.search(r"\beval\b.*\s-o\s", guion), (
        "`promptfoo eval` corre sin `-o`: los resultados quedan en el `~/.promptfoo` del runner y "
        "mueren con el, y con ellos el motivo que dio la rubrica")


def test_el_informe_de_cada_suite_lleva_un_nombre_derivado_de_SU_RUTA_y_no_del_archivo():
    """EL DEFECTO QUE EVITA: todas las suites del estandar se llaman igual -- `evals/suite.yaml` dentro
    de cada artefacto --, asi que un informe nombrado por el archivo haria que la segunda suite pisara
    a la primera EN SILENCIO. Se conservaria un solo informe y seria el de otro artefacto: peor que no
    conservar ninguno, porque parece completo."""
    guion = str(_paso_llamado(_EVALUAR, "Ejecutar las suites").get("run", ""))

    definicion = [linea for linea in guion.splitlines() if re.match(r"\s*informe=", linea)]

    assert definicion, "no se ve donde se compone la ruta del informe"
    assert "suite" in definicion[0], (
        f"la ruta del informe no se deriva de la ruta de la suite: {definicion[0].strip()!r}. "
        "Con un nombre fijo, la ultima suite pisa a las anteriores sin decirlo")


def test_el_informe_se_sube_TAMBIEN_cuando_las_suites_fallan():
    """LA MITAD DEL ARREGLO, y la que se olvida: el paso que corre las suites sale con 1 cuando alguna
    no pasa, asi que un `upload-artifact` sin `always()` sube el informe SOLO en las corridas verdes --
    aquellas en las que a nadie le hace falta -- y lo pierde en la unica que interesa. Subirlo solo
    cuando pasa es no subirlo."""
    paso = _paso_llamado(_EVALUAR, "Conservar el informe del juez")

    assert "upload-artifact" in str(paso.get("uses", "")), "el informe no se sube a ninguna parte"
    assert "always()" in str(paso.get("if", "")), (
        "el informe solo se sube si la corrida va bien; la corrida que hay que diagnosticar es "
        "justamente la que falla")


def test_la_ruta_que_escribe_el_informe_y_la_que_lo_sube_son_LA_MISMA_expresion():
    """Y5 en su forma mas cara: `upload-artifact` es una accion y no hereda el directorio de trabajo
    del `run` que escribio los archivos. Con dos expresiones distintas -- o con una relativa -- el
    directorio existe, esta vacio, y el artefacto se sube sin nada dentro SIN UN SOLO ERROR."""
    documento = yaml.safe_load(_EVALUAR.read_text(encoding="utf-8"))
    variable = "DIRECTORIO_DE_INFORMES"

    declarada = (documento.get("env") or {}).get(variable, "")
    escritura = str(_paso_llamado(_EVALUAR, "Ejecutar las suites").get("run", ""))
    subida = str((_paso_llamado(_EVALUAR, "Conservar el informe del juez").get("with") or {}).get("path", ""))

    assert declarada.startswith("${{ github.workspace }}"), (
        f"{variable} no es absoluta ({declarada!r}): un relativo significa cosas distintas en cada paso")
    assert variable in escritura, "el paso que corre las suites no escribe en la variable declarada"
    assert variable in subida, (
        f"el paso que sube el informe usa {subida!r} en vez de la variable: dos expresiones que hoy "
        "coinciden y manana divergen sin que nada lo detecte")


# --- El brazo de evaluacion ARRANCA y RECHAZA; nunca se salta dejando la comprobacion esperando ----
#
# MEDIDO en el commit `f6e00a1a` de `agentes-sdlc`: con `conformidad` en `failure`, el job
# `comportamiento` del llamador se salto por su `needs:`, y al saltarse el LLAMADOR los jobs de
# `evaluar.yml` NO SE MATERIALIZARON -- ni siquiera como `skipped`: no existieron --. El contexto
# `comportamiento / Veredicto de comportamiento`, comprobacion REQUERIDA del ruleset, se quedo en
# «Expected — waiting for status» esperando un estado que ya nadie iba a emitir.

# CADA DESENLACE, CLASIFICADO A MANO Y EN UN SOLO SITIO. La clave es el veredicto; el valor dice si
# DETIENE el cambio. Anadir uno nuevo obliga a decidir aqui de que lado cae, que es exactamente la
# decision que no se puede tomar por descuido: `no_procede` es verde porque no evaluar fuera de un
# pull request es legitimo, y reutilizarlo para «no se pudo evaluar» dejaria el control en verde
# protegiendo nada.
_DESENLACES_DEL_VEREDICTO = {
    "superada": False,
    "sin_suites": False,
    "no_procede": False,
    "fallida": True,
    "no_evaluable": True,
}


def _desenlaces_emitidos() -> set[str]:
    _, agregador = _agregador_de(_jobs_de(_EVALUAR))
    guion = "\n".join(str(paso.get("run", "")) for paso in (agregador.get("steps") or []))
    return set(re.findall(r"resultado=([a-z_]+)", guion))


def _desenlaces_que_detienen() -> set[str]:
    _, agregador = _agregador_de(_jobs_de(_EVALUAR))
    condiciones = " ".join(str(paso.get("if", "")) for paso in (agregador.get("steps") or [])
                           if "exit 1" in str(paso.get("run", "")))
    return {clave for clave in _DESENLACES_DEL_VEREDICTO if clave in condiciones}


def test_todo_desenlace_del_veredicto_esta_clasificado_como_bloqueante_o_no():
    """UN DESENLACE SIN CLASIFICAR ES UN VERDE POR DESCUIDO. El paso que detiene el cambio pregunta
    por veredictos concretos, asi que cualquier valor nuevo que nadie anada a esa condicion pasa el
    gate en silencio. Esta prueba obliga a decidir de que lado cae antes de poder emitirlo."""
    emitidos = _desenlaces_emitidos()

    assert emitidos == set(_DESENLACES_DEL_VEREDICTO), (
        f"`evaluar.yml` emite {sorted(emitidos)} y la tabla de esta prueba clasifica "
        f"{sorted(_DESENLACES_DEL_VEREDICTO)}. Clasifica el desenlace nuevo -- ¿detiene el cambio o "
        "no? -- en vez de dejar que el paso que bloquea decida por omision")


def test_ningun_desenlace_que_no_llego_a_medir_deja_pasar_el_cambio():
    """EL VEREDICTO NUNCA DEBE DECIR QUE SI SIN HABER MEDIDO. `fallida` y `no_evaluable` significan
    las dos que no hay medicion que certifique -- una porque la suite salio mal, otra porque no se
    llego a ejecutar --, y las dos tienen que salir con error. Si `no_evaluable` no detuviera, un
    artefacto sin evaluar pasaria en cuanto alguien quitara la conformidad de las requeridas."""
    detienen = _desenlaces_que_detienen()

    for desenlace, bloquea in _DESENLACES_DEL_VEREDICTO.items():
        assert (desenlace in detienen) is bloquea, (
            f"el desenlace `{desenlace}` "
            f"{'no detiene' if bloquea else 'detiene'} el cambio y deberia "
            f"{'detenerlo' if bloquea else 'dejarlo pasar'}: pasos que salen con error "
            f"condicionados a {sorted(detienen)}")


def test_la_conformidad_rota_no_abre_ninguna_celda_de_matriz():
    """CERO INFERENCIA SOBRE UN ARTEFACTO CUYO FORMATO YA SE SABE ROTO. Es el orden por COSTE
    CRECIENTE que este workflow defiende: el gate determinista tarda segundos y no consume modelo;
    una suite tarda minutos y gasta la unica cuota de inferencia de la organizacion. Si el
    cortocircuito se cayera, el brazo arrancaria -- que es el arreglo -- pero pagando por descubrir
    lo que el gate ya dijo."""
    deteccion = next(iter(_jobs_de(_EVALUAR).values()))

    assert "inputs.conformidad" in str(deteccion.get("if", "")), (
        f"la deteccion de suites no mira el resultado del gate del llamador (if="
        f"{deteccion.get('if')!r}): con la conformidad en rojo se abriria la matriz igualmente y se "
        "gastaria inferencia en un artefacto que ya se sabe mal formado")


def test_el_veredicto_no_confunde_no_haber_medido_con_no_proceder():
    """LOS DOS DEJAN LA DETECCION EN `skipped`, Y SOLO UNO ES LEGITIMO. Con el cortocircuito, «no es
    un pull request» y «la conformidad esta rota» son indistinguibles por `needs.unidades.result`: la
    causa solo la conserva el input. Y el orden de las preguntas es parte del arreglo -- si
    `no_procede` se preguntara primero, la conformidad rota saldria VERDE diciendo que no se evaluo --.
    """
    _, agregador = _agregador_de(_jobs_de(_EVALUAR))
    guion = "\n".join(str(paso.get("run", "")) for paso in (agregador.get("steps") or []))
    entorno = {c: str(v) for paso in (agregador.get("steps") or [])
               for c, v in (paso.get("env") or {}).items()}

    assert any("inputs.conformidad" in v for v in entorno.values()), (
        f"el agregador no recibe el resultado del gate del llamador ({sorted(entorno)}): solo le "
        "queda el `result` de una deteccion que el cortocircuito deja en `skipped`, el mismo valor "
        "que fuera de un pull request")
    assert guion.index("resultado=no_evaluable") < guion.index("resultado=no_procede"), (
        "el veredicto decide `no_procede` antes de mirar la conformidad: la conformidad rota saldria "
        "en VERDE -- «no se invoco desde una solicitud de cambio» -- en vez de en rojo")
