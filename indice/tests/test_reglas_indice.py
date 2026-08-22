"""Pruebas de la regla del indice. Puras: la regla recibe un candidato y devuelve una decision.

Cada prueba cubre UNA forma de colarse en el indice sin estar probado. Son las pruebas mas
importantes del repositorio: si una de estas se rompe, el estandar deja de ser exigible aunque todo
lo demas siga en verde.
"""
from __future__ import annotations

from indice_agentico.dominio.candidato import Candidato, Destino, Motivo
from indice_agentico.dominio.reglas_indice import evaluar, version_de_la_etiqueta

MANIFIESTO = {"name": "migracion-cnf", "description": "Skills del dominio SDLC.",
              "version": "0.2.0"}
VEREDICTO_CONFORME = {"conforme": True, "errores": [], "avisos": []}


def _candidato(**cambios) -> Candidato:
    base = {"repositorio": "organizacion/agentes-sdlc", "etiqueta": "v0.2.0",
            "sha": "a" * 40, "digest": "b" * 64, "lleva_plugin": True,
            "manifiesto": MANIFIESTO, "atestacion_verificada": True,
            "veredicto": VEREDICTO_CONFORME}
    return Candidato(**{**base, **cambios})


def test_un_candidato_probado_y_conforme_se_indexa():
    decision = evaluar(_candidato())
    assert decision.destino is Destino.INDEXAR
    assert decision.entrada.name == "migracion-cnf"
    assert decision.entrada.version == "0.2.0"
    assert decision.entrada.sha == "a" * 40


def test_sin_atestacion_verificada_no_se_indexa():
    """El hueco que cierra: `publicar.yml` vive en el repo del dominio y es editable. Quitar el
    paso de atestacion NO debe servir para publicar contenido sin sellar."""
    decision = evaluar(_candidato(atestacion_verificada=False))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SIN_ATESTACION


def test_con_procedencia_pero_sin_veredicto_no_se_indexa():
    # La procedencia prueba de DONDE salio; no prueba que pasara ningun gate. Hacen falta las dos.
    decision = evaluar(_candidato(veredicto=None))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SIN_VEREDICTO


def test_un_veredicto_negativo_atestado_no_se_indexa():
    # Se puede firmar un veredicto que diga que no es conforme: firmar no es aprobar.
    decision = evaluar(_candidato(veredicto={"conforme": False, "errores": [{"mensaje": "x"}]}))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.NO_CONFORME


def test_sin_paquete_no_se_indexa():
    decision = evaluar(_candidato(digest=None))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SIN_PAQUETE


def test_version_del_manifiesto_distinta_de_la_etiqueta_no_se_indexa():
    """Si difieren, el puntero dice `v0.2.0` y el contenido se declara `0.1.0`: el consumidor no
    puede saber que instalo, y el numero de version deja de servir para nada."""
    decision = evaluar(_candidato(manifiesto={**MANIFIESTO, "version": "0.1.0"}))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.VERSION_DISCREPANTE


def test_la_etiqueta_sin_v_tambien_vale():
    decision = evaluar(_candidato(etiqueta="0.2.0"))
    assert decision.destino is Destino.INDEXAR
    assert decision.entrada.version == "0.2.0"


def test_un_manifiesto_sin_description_no_bloquea_pero_deja_rastro():
    decision = evaluar(_candidato(manifiesto={"name": "x", "version": "0.2.0"}))
    assert decision.destino is Destino.INDEXAR
    assert "sin descripcion" in decision.entrada.description


# ── el plugin decide DONDE se lista, no SI es instalable ────────────────────────────────────
def test_un_suelto_sellado_se_OMITE_y_no_se_rechaza():
    """El plugin es OPCIONAL en el estandar. Un skill suelto se gobierna por su metadata y se
    instala por su canal; lo unico que no tiene es entrada en `marketplace.json`, porque las
    entradas de un marketplace SON plugins. Rechazarlo hacia que el equipo del dominio buscase un
    defecto que no existe."""
    decision = evaluar(_candidato(lleva_plugin=False, manifiesto=None))
    assert decision.destino is Destino.OMITIR
    assert decision.motivo is Motivo.SIN_PLUGIN


def test_un_suelto_SIN_SELLAR_se_rechaza_y_no_se_omite():
    """El defecto medido: una version de esta regla preguntaba por el plugin ANTES del sello, y
    entonces un artefacto suelto publicado sin atestacion salia como omision limpia y llegaba a la
    ficha del catalogo. El sello se exige a todos; el plugin solo decide el canal."""
    decision = evaluar(_candidato(lleva_plugin=False, manifiesto=None,
                                  atestacion_verificada=False, veredicto=None))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SIN_ATESTACION


def test_un_suelto_con_veredicto_negativo_se_rechaza():
    # Mismo motivo: no llevar plugin no exime de haber pasado los gates.
    decision = evaluar(_candidato(lleva_plugin=False, manifiesto=None,
                                  veredicto={"conforme": False}))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.NO_CONFORME


def test_un_plugin_ILEGIBLE_si_se_rechaza():
    """Distinto de no llevarlo: aqui el paquete DECLARA un plugin y esta roto. Antes los dos casos
    daban `None` al leer el manifiesto y eran indistinguibles."""
    decision = evaluar(_candidato(manifiesto=None))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SIN_MANIFIESTO


def test_el_sha_de_la_entrada_es_un_commit_y_no_un_nombre_de_rama():
    """Defecto medido al indexar un release real: el generador tomaba `targetCommitish`, que para un
    release creado desde una etiqueta devuelve el NOMBRE DE LA RAMA. La entrada salia con
    `sha: main`, un puntero movil -- justo lo que el sha existe para evitar."""
    decision = evaluar(_candidato(sha="main"))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SHA_NO_RESUELTO


# ── etiquetas por plugin: `<nombre>--vX.Y.Z` ────────────────────────────────────────────────
def test_la_version_se_lee_igual_en_las_DOS_formas_de_etiqueta():
    """Defecto MEDIDO leyendo el codigo contra la cadena de publicacion: la version se sacaba con
    `etiqueta.removeprefix("v")`, asi que una etiqueta por plugin se comparaba ENTERA contra la
    version del manifiesto y el candidato se rechazaba por VERSION_DISCREPANTE -- mandando al equipo
    del dominio a buscar un desajuste de version que no existe."""
    for etiqueta in ("v0.2.0", "demo.sdlc.migracion--v0.2.0"):
        assert version_de_la_etiqueta(etiqueta) == "0.2.0", etiqueta


def test_un_plugin_anidado_se_rechaza_por_la_SUBRUTA_y_no_por_la_version():
    # El motivo importa tanto como el rechazo: `VERSION_DISCREPANTE` habria enviado a revisar el
    # manifiesto, que esta bien.
    decision = evaluar(_candidato(etiqueta="migracion-cnf--v0.2.0"))
    assert decision.destino is Destino.RECHAZAR
    assert decision.motivo is Motivo.SUBRUTA_NO_RESUELTA


def test_un_plugin_en_la_raiz_sigue_indexandose():
    # Lo que NO debe cambiar: el caso normal, un plugin por repositorio.
    assert evaluar(_candidato(etiqueta="v0.2.0")).destino is Destino.INDEXAR
