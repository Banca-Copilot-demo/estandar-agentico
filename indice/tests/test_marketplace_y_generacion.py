"""Pruebas del marketplace generado y del caso de uso.

El caso de uso se prueba con DOBLES INYECTADOS, no parcheando `subprocess` (T4): los adaptadores son
argumentos con valor por defecto, asi que la prueba pasa los suyos y no toca red, ni `gh`, ni disco.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from indice_agentico.adaptadores import github, marketplace
from indice_agentico.adaptadores.paquete import LecturaManifiesto
from indice_agentico.aplicacion.generar import generar
from indice_agentico.dominio.candidato import Descarte, Entrada, Indice, Motivo
from indice_agentico import cli

PROPIETARIO = {"name": "Plataforma Agentica (demo)", "email": "plataforma-agentica@ejemplo.dev"}
# Ruta explicita y no la de por defecto: una prueba que dependa del directorio de trabajo pasa o
# falla segun desde donde se invoque a pytest.
ESQUEMAS = Path(__file__).resolve().parents[2] / "schemas"
CLAUDE = marketplace.Proyeccion.CLAUDE_CODE


def _entrada(name: str, version: str = "0.2.0", subruta: str | None = None) -> Entrada:
    extra = {"subruta": subruta} if subruta else {}
    return Entrada(name=name, description="d", version=version,
                   repositorio=f"organizacion/agentes-{name}", etiqueta=f"v{version}",
                   sha="c" * 40, **extra)


# ── marketplace ────────────────────────────────────────────────────────────────────────────
def test_toda_entrada_del_marketplace_lleva_sha():
    """Sin `sha` el puntero es movil: la etiqueta se puede reescribir si el repositorio no tiene
    releases inmutables, y entonces `ref` no fija nada."""
    generado = json.loads(marketplace.render(Indice((_entrada("a"), _entrada("b")), ()),
                                             "agentico", PROPIETARIO, "0.1.0", CLAUDE))
    assert generado["plugins"]
    for plugin in generado["plugins"]:
        assert len(plugin["source"]["sha"]) == 40, plugin["name"]


def test_source_se_emite_como_objeto_y_no_como_cadena():
    # La forma abreviada de `source` es una cadena y NO admite `sha`.
    generado = json.loads(marketplace.render(Indice((_entrada("a"),), ()), "agentico", PROPIETARIO,
                                             "0.1", CLAUDE))
    assert isinstance(generado["plugins"][0]["source"], dict)


def test_los_plugins_salen_ordenados_por_nombre():
    # Sin orden fijo, cada regeneracion produce un diff distinto sin que nada haya cambiado.
    generado = json.loads(marketplace.render(Indice((_entrada("z"), _entrada("a")), ()),
                                             "agentico", PROPIETARIO, "0.1", CLAUDE))
    assert [p["name"] for p in generado["plugins"]] == ["a", "z"]


def test_el_marketplace_avisa_de_que_esta_generado():
    generado = json.loads(marketplace.render(Indice((), ()), "agentico", PROPIETARIO, "0.1",
                                             CLAUDE))
    assert "no editar a mano" in generado["metadata"]["description"]


# ── borradores y prelanzamientos NO entran al marketplace ───────────────────────────────────
def test_un_prelanzamiento_no_entra_al_marketplace(monkeypatch):
    """Es el mecanismo para RETIRAR del marketplace un release cuyo plugin ya no se mantiene: un
    release publicado no se puede borrar sin romper las atestaciones que cuelgan de el, y
    `prerelease` es la senal nativa de GitHub para «esto no es para consumo general».

    Defecto MEDIDO contra la organizacion real: el marketplace listaba `demo.sdlc.migracion-cnf
    0.3.0`, de cuando el repositorio era un plugin unico. Ese plugin ya no existe en el arbol -- hoy
    hay dos bajo `plugins/` -- pero su release seguia siendo el mas nuevo de su grupo, asi que la
    vitrina anunciaba algo que nadie mantiene.

    Se parchea `_gh` y no el adaptador porque lo que se prueba ES el filtrado del adaptador (T4 pide
    inyectar dobles para probar OTRA cosa a traves de un adaptador; aqui el adaptador es el sujeto).
    """
    respuesta = json.dumps([
        {"tagName": "vigente--v1.0.0", "publishedAt": "2026-01-02", "isDraft": False,
         "isPrerelease": False},
        {"tagName": "retirado--v9.9.9", "publishedAt": "2026-01-03", "isDraft": False,
         "isPrerelease": True},
        {"tagName": "borrador--v9.9.9", "publishedAt": "2026-01-04", "isDraft": True,
         "isPrerelease": False},
    ])
    monkeypatch.setattr(github, "_gh", lambda *argumentos: respuesta)

    assert github.etiquetas_publicadas("org/repo") == ("vigente--v1.0.0",)


# ── caso de uso, con dobles ────────────────────────────────────────────────────────────────
class GithubFalso:
    """Doble del adaptador de GitHub. `sellado` decide si la atestacion verifica."""

    def __init__(self, repositorios: list[str], *, sellado: bool = True, con_release: bool = True,
                 con_paquete: bool = True, etiquetas: tuple[str, ...] = ("v0.2.0",)):
        self._repositorios = repositorios
        self._sellado = sellado
        self._con_release = con_release
        self._con_paquete = con_paquete
        self._etiquetas = etiquetas

    def repositorios_del_dominio(self, organizacion, topico):
        return self._repositorios

    def etiquetas_publicadas(self, repositorio):
        return () if not self._con_release else self._etiquetas

    def release(self, repositorio, etiqueta):
        if not self._con_release:
            return None
        return etiqueta, "d" * 40, "paquete.tar.gz" if self._con_paquete else None

    def descargar_paquete(self, repositorio, etiqueta, paquete, destino):
        return Path(destino) / paquete

    def verificar_atestacion(self, ruta, repositorio):
        return self._sellado

    def veredicto_atestado(self, ruta, repositorio):
        return {"conforme": True} if self._sellado else None


class LectorFalso:
    """Doble del lector del paquete. `lleva_plugin=False` simula un artefacto SUELTO, que es el caso
    que el marketplace omite en vez de rechazar."""

    def __init__(self, *, lleva_plugin: bool = True):
        self._lleva_plugin = lleva_plugin

    def digest(self, ruta):
        return "e" * 64

    def leer_manifiesto(self, ruta):
        if not self._lleva_plugin:
            return LecturaManifiesto(presente=False)
        return LecturaManifiesto(
            presente=True,
            contenido={"name": "migracion-cnf", "description": "d", "version": "0.2.0"})


def test_un_dominio_sellado_entra_al_indice():
    indice = generar("org", "agent-skills",
                     github=GithubFalso(["org/agentes-sdlc"]), lector=LectorFalso())
    assert [e.name for e in indice.entradas] == ["migracion-cnf"]
    assert indice.rechazos == ()


def test_un_dominio_sin_sellar_se_rechaza_sin_tumbar_la_generacion():
    """El defecto que cubre: si un rechazo abortara, un solo dominio mal publicado congelaria el
    indice de TODOS los demas."""
    indice = generar("org", "agent-skills",
                     github=GithubFalso(["org/agentes-sdlc"], sellado=False),
                     lector=LectorFalso())
    assert indice.entradas == ()
    assert indice.rechazos == (Descarte("org/agentes-sdlc", Motivo.SIN_ATESTACION),)


def test_un_repositorio_sin_releases_se_rechaza_por_ese_motivo_y_no_por_otro():
    indice = generar("org", "agent-skills",
                     github=GithubFalso(["org/agentes-sdlc"], con_release=False),
                     lector=LectorFalso())
    assert indice.rechazos[0].motivo is Motivo.SIN_RELEASE


def test_un_release_sin_paquete_no_se_confunde_con_no_tener_release():
    """Defecto medido al ejecutar el generador contra la organizacion real: los dos casos daban el
    mismo motivo, y el equipo del dominio habria buscado un release que si existia."""
    indice = generar("org", "agent-skills",
                     github=GithubFalso(["org/agentes-sdlc"], con_paquete=False),
                     lector=LectorFalso())
    assert indice.rechazos[0].motivo is Motivo.SIN_PAQUETE


def test_un_artefacto_suelto_se_omite_y_no_cuenta_como_rechazo(tmp_path):
    """Lo que motivo la distincion: el plugin es opcional, asi que un artefacto suelto NO es un
    error de publicacion. Si contara como rechazo, el resumen del indice reportaria defectos
    inexistentes cada vez que un dominio publica un skill suelto."""
    indice = generar("org", "agent-skills",
                     github=GithubFalso(["org/skill-suelto"]),
                     lector=LectorFalso(lleva_plugin=False))
    assert indice.entradas == ()
    assert indice.rechazos == ()
    assert indice.omisiones == (Descarte("org/skill-suelto", Motivo.SIN_PLUGIN),)


def test_un_suelto_y_un_plugin_conviven_en_la_misma_pasada():
    """El caso realista: la organizacion tiene de los dos. El plugin entra al marketplace y el
    suelto se omite, sin que ninguno afecte al otro."""
    class LectorMixto:
        def digest(self, ruta):
            return "e" * 64

        def leer_manifiesto(self, ruta):
            lleva = "con-plugin" in str(ruta)
            return LecturaManifiesto(
                presente=lleva,
                contenido={"name": "migracion-cnf", "description": "d",
                           "version": "0.2.0"} if lleva else None)

    class GithubMixto(GithubFalso):
        def descargar_paquete(self, repositorio, etiqueta, paquete, destino):
            return Path(destino) / f"{repositorio.split('/')[-1]}.tar.gz"

    indice = generar("org", "agent-skills",
                     github=GithubMixto(["org/con-plugin", "org/suelto"]),
                     lector=LectorMixto())
    assert [e.name for e in indice.entradas] == ["migracion-cnf"]
    assert [o.repositorio for o in indice.omisiones] == ["org/suelto"]
    assert indice.rechazos == ()


def test_sin_repositorios_el_indice_sale_vacio_y_no_falla():
    indice = generar("org", "agent-skills", github=GithubFalso([]), lector=LectorFalso())
    assert indice == Indice((), (), ())


# ── el guardarail de escritura ─────────────────────────────────────────────────────────────
def test_un_indice_vacio_no_sobreescribe_el_marketplace_existente(tmp_path):
    """Defecto que cubre: sobreescribir con `plugins: []` desinstalaria todo de golpe. Toca disco
    porque lo que se prueba ES el efecto en disco -- no es una regla de dominio (T1)."""
    previo = tmp_path / marketplace.Proyeccion.CLAUDE_CODE.ruta
    previo.parent.mkdir(parents=True)
    previo.write_text('{"plugins": ["algo"]}', encoding="utf-8")

    codigo = cli.escribir(Indice((), ()), tmp_path, {CLAUDE: "{}"})

    assert codigo == cli.SALIDA_ERROR
    assert "algo" in previo.read_text(encoding="utf-8")


def test_un_indice_con_entradas_si_se_escribe(tmp_path):
    indice = Indice((_entrada("a"),), ())
    contenido = marketplace.render(indice, "agentico", PROPIETARIO, "0.1.0", CLAUDE)

    codigo = cli.escribir(indice, tmp_path, {CLAUDE: contenido}, ESQUEMAS)

    assert codigo == cli.SALIDA_OK
    escrito = tmp_path / marketplace.Proyeccion.CLAUDE_CODE.ruta
    assert escrito.read_text(encoding="utf-8") == contenido


def test_se_escriben_LAS_DOS_proyecciones_en_la_misma_llamada():
    """Defecto que cubre: la proyeccion de Copilot no se generaba -- se escribio a mano durante una
    prueba de instalacion -- asi que se habria quedado rancia sin que nada lo indicara. Si una se
    puede actualizar sin la otra, los usuarios de un cliente ven un marketplace mas viejo en
    silencio."""
    assert {p.ruta for p in marketplace.Proyeccion} == {
        ".claude-plugin/marketplace.json",
        ".github/plugin/marketplace.json",
    }


def test_las_dos_proyecciones_se_escriben_en_una_sola_llamada(tmp_path):
    indice = Indice((_entrada("a"),), ())
    contenidos = {p: marketplace.render(indice, "agentico", PROPIETARIO, "0.1.0", p)
                  for p in marketplace.Proyeccion}

    cli.escribir(indice, tmp_path, contenidos, ESQUEMAS)

    for proyeccion in marketplace.Proyeccion:
        assert (tmp_path / proyeccion.ruta).exists(), proyeccion.ruta


# ── un plugin ANIDADO se direcciona distinto en cada cliente ────────────────────────────────
def _anidado(subruta: str = "plugins/contratos") -> Entrada:
    return Entrada(name="demo.sdlc.contratos", description="d", version="0.1.0",
                   repositorio="organizacion/agentes-sdlc",
                   etiqueta="demo.sdlc.contratos--v0.1.0", sha="c" * 40, subruta=subruta)


def test_un_plugin_anidado_usa_git_subdir_en_claude_code():
    """Claude Code acepta `github` con `path` y despues IGNORA el `path`: instalaria el repositorio
    entero sin dar error. `git-subdir` es su unica fuente que honra un subdirectorio."""
    generado = json.loads(marketplace.render(Indice((_anidado(),), ()), "agentico", PROPIETARIO,
                                             "0.1.0", marketplace.Proyeccion.CLAUDE_CODE))
    fuente = generado["plugins"][0]["source"]
    assert fuente["source"] == "git-subdir"
    assert fuente["path"] == "plugins/contratos"


def test_un_plugin_anidado_usa_github_mas_path_en_copilot():
    # Copilot RECHAZA `git-subdir`, y una entrada asi rompe el indice entero para ese cliente.
    generado = json.loads(marketplace.render(Indice((_anidado(),), ()), "agentico", PROPIETARIO,
                                             "0.1.0", marketplace.Proyeccion.COPILOT))
    fuente = generado["plugins"][0]["source"]
    assert fuente["source"] == "github"
    assert fuente["path"] == "plugins/contratos"


def test_un_plugin_que_ocupa_su_repositorio_se_direcciona_IGUAL_en_los_dos():
    fuentes = [json.loads(marketplace.render(Indice((_entrada("a"),), ()), "agentico", PROPIETARIO,
                                             "0.1.0", p))["plugins"][0]["source"]
               for p in marketplace.Proyeccion]
    assert fuentes[0] == fuentes[1]
    assert "path" not in fuentes[0]


def test_las_dos_proyecciones_de_un_anidado_CUMPLEN_cada_una_su_esquema(tmp_path):
    """Es la prueba que cierra el circulo: cada cliente recibe una fuente que el OTRO rechazaria,
    y las dos pasan su propia validacion."""
    indice = Indice((_anidado(),), ())
    contenidos = {p: marketplace.render(indice, "agentico", PROPIETARIO, "0.1.0", p)
                  for p in marketplace.Proyeccion}

    assert cli.escribir(indice, tmp_path, contenidos, ESQUEMAS) == cli.SALIDA_OK


# ── el marketplace se valida ANTES de escribirse ────────────────────────────────────────────
def test_un_marketplace_que_no_cumple_el_esquema_no_se_escribe(tmp_path):
    """Defecto que cubre: el indice emitia el marketplace sin comprobarlo contra el esquema, asi que
    una fuente que un cliente no sabe instalar se publicaba y solo se notaba al instalar."""
    indice = Indice((_entrada("a"),), ())
    invalido = json.dumps({"name": "agentico", "owner": PROPIETARIO,
                           "plugins": [{"name": "x"}]})

    codigo = cli.escribir(indice, tmp_path, {CLAUDE: invalido}, ESQUEMAS)

    assert codigo == cli.SALIDA_ERROR
    assert not list(tmp_path.rglob("marketplace.json")), "no debe escribirse ninguna proyeccion"


def test_la_combinacion_QUE_FALLA_EN_SILENCIO_se_rechaza(tmp_path):
    """`github` + `path`: Claude Code lo acepta y despues IGNORA el `path`, instalando el
    repositorio entero. No da error, da un plugin equivocado -- por eso lo para el esquema."""
    indice = Indice((_entrada("a"),), ())
    letal = json.dumps({
        "name": "agentico", "owner": PROPIETARIO,
        "plugins": [{"name": "a", "description": "d", "version": "0.2.0",
                     "source": {"source": "github", "repo": "org/repo",
                                "path": "plugins/a", "ref": "main"}}]})

    assert cli.escribir(indice, tmp_path, {CLAUDE: letal}, ESQUEMAS) == cli.SALIDA_ERROR


# ── el artefacto suelto publicado como su propia unidad ─────────────────────────────────────
@pytest.mark.parametrize("subruta", ["skills/revisar-jql", "commands/resumir", "agents/auditor"],
                         ids=["skill", "prompt", "agente"])
@pytest.mark.parametrize("proyeccion", list(marketplace.Proyeccion),
                         ids=[p.name.lower() for p in marketplace.Proyeccion])
def test_un_suelto_apunta_a_SU_subruta_en_las_dos_proyecciones(subruta, proyeccion):
    """LAS DOS PROYECCIONES O NINGUNA. Esta medido que los clientes no aceptan lo mismo: Copilot
    rechaza la fuente `git-subdir`, y Claude Code acepta `github` con `path` pero IGNORA el path e
    instala el repositorio ENTERO sin dar error. Una proyeccion correcta y la otra no no seria medio
    arreglo: seria una instalacion silenciosamente equivocada en uno de los dos clientes.

    Y el `sha` importa tanto como el `path`: es lo que ata lo que el marketplace instala con lo que
    la atestacion firmo. Comprobado que los dos clientes lo honran -- se fijo el marketplace a un
    commit, se movio la rama a otro posterior con un marcador y el marcador NO aparecio en lo
    instalado --.
    """
    entrada = _entrada("revisar-jql", version="0.1.0", subruta=subruta)
    generado = json.loads(marketplace.render(Indice((entrada,), ()), "agentico", PROPIETARIO,
                                             "0.1.0", proyeccion))

    fuente = generado["plugins"][0]["source"]

    assert fuente["path"] == subruta, fuente
    assert fuente["sha"] == "c" * 40, fuente
