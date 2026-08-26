"""Pruebas del descubrimiento de UNIDADES PUBLICABLES.

EL PRIMER DEFECTO QUE CUBREN se midio ejecutando el gate sobre un repositorio con dos plugins bajo
`plugins/`: respondio «0 skills, 0 agentes, plugin: no» y veredicto CONFORME. Tres artefactos reales,
y el gate no vio ninguno.

EL SEGUNDO se midio despues, y era del mismo tipo: en un repositorio con plugins Y un skill en la
raiz, el skill de la raiz DESAPARECIA del veredicto -- sin ficha, sin error, sin aviso --. La funcion
devolvia «o los plugins O la raiz», nunca las dos, asi que la raiz no era una unidad y su contenido no
se leia como artefacto. Los dos defectos fallan igual: en verde.
"""
from __future__ import annotations

from validador_agentico.dominio.reglas_layout import (
    es_multiunidad,
    raices_de_artefacto_individual,
    raices_de_plugin,
    tiene_artefactos_propios,
    unidades_publicables,
)

RUTAS = (".claude-plugin/plugin.json", "plugin.json")
_DIRECTORIOS = ("skills", "agents", "commands")
_ARCHIVOS = (".mcp.json",)


def _crear_plugin(directorio, ruta_manifiesto=".claude-plugin/plugin.json"):
    destino = directorio / ruta_manifiesto
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("{}", encoding="utf-8")
    return directorio


def _crear_skill(directorio, nombre="x"):
    destino = directorio / "skills" / nombre
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")


def _unidades(raiz):
    return unidades_publicables(raiz, RUTAS, _DIRECTORIOS, _ARCHIVOS)


# ── plugins anidados: el primer defecto ─────────────────────────────────────────────────────
def test_dos_plugins_bajo_plugins_dan_DOS_unidades(tmp_path):
    for nombre in ("contratos", "migracion"):
        _crear_plugin(tmp_path / "plugins" / nombre)

    unidades = _unidades(tmp_path)

    assert [r.name for r in unidades] == ["contratos", "migracion"]
    assert es_multiunidad(unidades, tmp_path)


def test_el_orden_es_ESTABLE_entre_ejecuciones(tmp_path):
    # Sin orden estable, el veredicto cambia de forma entre corridas y el digesto que se atesta
    # deja de ser reproducible.
    for nombre in ("zeta", "alfa", "media"):
        _crear_plugin(tmp_path / "plugins" / nombre)

    assert [r.name for r in _unidades(tmp_path)] == ["alfa", "media", "zeta"]


# ── el repositorio MIXTO: el segundo defecto ────────────────────────────────────────────────
def test_plugins_MAS_artefactos_en_la_raiz_dan_una_unidad_de_mas(tmp_path):
    # El defecto: aqui se devolvia solo el plugin, y el skill de la raiz no lo leia nadie.
    _crear_plugin(tmp_path / "plugins" / "contratos")
    _crear_skill(tmp_path)

    unidades = _unidades(tmp_path)

    assert unidades[-1] == tmp_path, "el conjunto suelto tiene que ser una unidad"
    assert [r.name for r in unidades[:-1]] == ["contratos"]


def test_la_raiz_va_AL_FINAL_para_que_los_mensajes_se_agrupen(tmp_path):
    # El orden no es cosmetico: los hallazgos salen agrupados por unidad, y con la raiz en medio
    # quedarian intercalados con los de los plugins.
    for nombre in ("uno", "dos"):
        _crear_plugin(tmp_path / "plugins" / nombre)
    _crear_skill(tmp_path)

    assert _unidades(tmp_path)[-1] == tmp_path


def test_plugins_SIN_nada_en_la_raiz_no_añaden_la_raiz(tmp_path):
    # Si se añadiera siempre, un repositorio multiplugin normal tendria una unidad vacia de mas, y
    # el etiquetado crearia una etiqueta para un paquete sin contenido.
    _crear_plugin(tmp_path / "plugins" / "contratos")
    _crear_skill(tmp_path / "plugins" / "contratos")

    assert _unidades(tmp_path) == (tmp_path / "plugins" / "contratos",)


def test_un_directorio_de_artefactos_VACIO_en_la_raiz_no_cuenta(tmp_path):
    # Un `skills/` vacio que alguien dejo tras mover su contenido no debe crear una unidad.
    _crear_plugin(tmp_path / "plugins" / "contratos")
    (tmp_path / "skills").mkdir()

    assert _unidades(tmp_path) == (tmp_path / "plugins" / "contratos",)


def test_un_mcp_en_la_raiz_tambien_hace_que_haya_conjunto_suelto(tmp_path):
    # Un `.mcp.json` es un artefacto por si mismo, no un directorio: si solo se miraran los
    # directorios, un mcp en la raiz seguiria siendo invisible.
    _crear_plugin(tmp_path / "plugins" / "contratos")
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")

    assert _unidades(tmp_path)[-1] == tmp_path


# ── lo que NO debe cambiar ──────────────────────────────────────────────────────────────────
def test_un_plugin_en_la_raiz_sigue_dando_UNA_unidad(tmp_path):
    _crear_plugin(tmp_path)
    _crear_skill(tmp_path)

    assert _unidades(tmp_path) == (tmp_path,)
    assert not es_multiunidad(_unidades(tmp_path), tmp_path)


def test_un_repositorio_de_artefactos_SUELTOS_sigue_siendo_una_unidad(tmp_path):
    """Sin manifiesto no hay plugin, pero el repositorio SI se valida y SI se publica: devolver una
    tupla vacia lo dejaria sin revisar, que es el defecto que esta regla vino a cerrar."""
    _crear_skill(tmp_path)

    assert _unidades(tmp_path) == (tmp_path,)


def test_un_repositorio_sin_nada_sigue_siendo_revisable(tmp_path):
    assert _unidades(tmp_path) == (tmp_path,)


# ── un plugin se reconoce por su MANIFIESTO, no por su carpeta ───────────────────────────────
def test_una_carpeta_bajo_plugins_SIN_manifiesto_no_es_una_unidad(tmp_path):
    # Si contara como unidad, una carpeta de material compartido se validaria como plugin vacio.
    _crear_plugin(tmp_path / "plugins" / "real")
    (tmp_path / "plugins" / "compartido").mkdir(parents=True)

    assert [r.name for r in _unidades(tmp_path)] == ["real"]


def test_el_manifiesto_en_la_RAIZ_del_plugin_tambien_cuenta(tmp_path):
    """Copilot lee `plugin.json` en la raiz del plugin y Claude Code `.claude-plugin/plugin.json`:
    las dos formas identifican una unidad, o el gate solo veria los plugins de un cliente."""
    _crear_plugin(tmp_path / "plugins" / "para-copilot", "plugin.json")

    assert [r.name for r in _unidades(tmp_path)] == ["para-copilot"]


def test_sin_carpeta_plugins_no_se_inventan_unidades(tmp_path):
    (tmp_path / "otra-cosa" / "x").mkdir(parents=True)

    assert _unidades(tmp_path) == (tmp_path,)


# ── las dos preguntas son distintas y se responden aparte ───────────────────────────────────
def test_raices_de_plugin_responde_SOLO_por_los_plugins(tmp_path):
    """`raices_de_plugin` contesta «que plugins hay» -- lo que el marketplace necesita -- y
    `unidades_publicables` contesta «que se publica», que incluye el conjunto suelto. Mezclarlas
    haria que el conjunto suelto apareciera en el marketplace, y sus entradas SON plugins."""
    _crear_plugin(tmp_path / "plugins" / "contratos")
    _crear_skill(tmp_path)

    assert raices_de_plugin(tmp_path, RUTAS) == (tmp_path / "plugins" / "contratos",)
    assert len(_unidades(tmp_path)) == 2


def test_tiene_artefactos_propios_distingue_vacio_de_ausente(tmp_path):
    assert not tiene_artefactos_propios(tmp_path, _DIRECTORIOS, _ARCHIVOS, RUTAS)
    (tmp_path / "skills").mkdir()
    assert not tiene_artefactos_propios(tmp_path, _DIRECTORIOS, _ARCHIVOS, RUTAS)
    _crear_skill(tmp_path)
    assert tiene_artefactos_propios(tmp_path, _DIRECTORIOS, _ARCHIVOS, RUTAS)


# ── artefactos sueltos con manifiesto propio ────────────────────────────────────────────────
#
# EL DEFECTO QUE CUBREN, medido contra los DOS clientes: un artefacto suelto sin manifiesto no se
# puede instalar desde el catalogo cuando el contenido vive en otro repositorio -- que es la
# topologia real --. Falla con «No plugin.json found in repository», asi que el suelto quedaba fuera
# del catalogo y, por tanto, fuera del control de estado: se instalaba igual estuviera certificado,
# conforme o suspendido.
def test_un_skill_con_manifiesto_propio_es_su_propia_unidad(tmp_path):
    _crear_skill(tmp_path, "revisar-jql")
    _crear_plugin(tmp_path / "skills" / "revisar-jql")

    assert _unidades(tmp_path) == (tmp_path / "skills" / "revisar-jql",)


def test_el_conjunto_suelto_NO_reempaqueta_lo_que_ya_es_unidad(tmp_path):
    """Si el conjunto suelto siguiera existiendo, cada artefacto viajaria en DOS paquetes con dos
    digestos, y el catalogo tendria dos punteros al mismo contenido."""
    _crear_skill(tmp_path, "revisar-jql")
    _crear_plugin(tmp_path / "skills" / "revisar-jql")

    assert tmp_path not in _unidades(tmp_path)


def test_conviven_el_que_tiene_manifiesto_y_el_que_no(tmp_path):
    """Poner manifiesto es opcional y gradual: quien no lo pone sigue en el conjunto suelto, asi que
    anadir la regla no rompe ningun repositorio existente."""
    _crear_skill(tmp_path, "con-manifiesto")
    _crear_plugin(tmp_path / "skills" / "con-manifiesto")
    _crear_skill(tmp_path, "sin-manifiesto")

    unidades = _unidades(tmp_path)

    assert tmp_path / "skills" / "con-manifiesto" in unidades
    assert tmp_path in unidades, "el que no tiene manifiesto sigue publicandose con el conjunto"


def test_un_directorio_de_artefacto_SIN_manifiesto_no_es_unidad(tmp_path):
    _crear_skill(tmp_path, "x")

    assert raices_de_artefacto_individual(tmp_path, RUTAS, _DIRECTORIOS) == ()


def test_cada_tipo_suelto_puede_ser_unidad_propia(tmp_path):
    """No solo los skills: un prompt o un agente con manifiesto tambien se publican por separado, que
    es lo que les da version y digesto propios."""
    for contenedor in ("skills", "commands", "agents"):
        _crear_plugin(tmp_path / contenedor / "uno")

    encontradas = raices_de_artefacto_individual(tmp_path, RUTAS, _DIRECTORIOS)

    assert len(encontradas) == 3, f"faltan tipos: {encontradas}"


def test_los_plugins_anidados_y_los_individuales_conviven(tmp_path):
    _crear_plugin(tmp_path / "plugins" / "contratos")
    _crear_skill(tmp_path, "revisar-jql")
    _crear_plugin(tmp_path / "skills" / "revisar-jql")

    unidades = _unidades(tmp_path)

    assert tmp_path / "plugins" / "contratos" in unidades
    assert tmp_path / "skills" / "revisar-jql" in unidades


def test_un_artefacto_individual_NO_aparece_como_plugin_anidado(tmp_path):
    """`raices_de_plugin` alimenta el marketplace con «que plugins hay». Un artefacto individual se
    publica igual, pero se descubre por otra via: mezclarlos haria que un cambio en una de las dos
    preguntas moviera la otra sin querer."""
    _crear_skill(tmp_path, "revisar-jql")
    _crear_plugin(tmp_path / "skills" / "revisar-jql")

    assert raices_de_plugin(tmp_path, RUTAS) == ()
