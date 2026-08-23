"""Pruebas del gate: la agregacion y su orquestacion.

POR QUE ESTAS PRUEBAS EXISTEN. Esta regla vivia en un `if` de bash dentro de una accion compuesta,
donde ninguna prueba la alcanzaba -- y es la regla que decide si un artefacto se publica. Al traerla
al dominio, los tres resultados quedan cubiertos.

La orquestacion se prueba con un DOBLE INYECTADO del comprobador oficial (T4): ni `gh` instalado, ni
red, ni parchear modulos.
"""
from __future__ import annotations

import json
from pathlib import Path

from validador_agentico.aplicacion.ejecutar_gate import NOMBRE_COMPROBACION_PROPIA, ejecutar
from validador_agentico.dominio.comprobacion import (
    Comprobacion,
    Resultado,
    ResultadoGate,
    agrega_conforme,
)
from validador_agentico.dominio.hallazgo import Inventario, Veredicto, aviso, error

# Se construye un repositorio MINIMO en disco en vez de apuntar a un repo hermano. Medido: la
# primera
# version de estas pruebas apuntaba a `../agentes-sdlc`, que NO EXISTE cuando solo esta clonado el
# repo del estandar -- como en CI --. Las tres pruebas pasaban contra un directorio inexistente, o
# sea por el motivo equivocado. Es la misma clase de falso verde que el gate existe para evitar.
_SKILL_CONFORME = """---
name: validar-algo
description: Comprueba algo concreto y se usa cuando alguien lo pide.
metadata:
  id: demo.sdlc.ejemplo
  owner_team: squad-sdlc
  owner_contact: squad-sdlc@ejemplo.dev
  status: draft
  version: 1.0.0
  data_classification: internal
  standard_version: 7.0.0
---

# Validar algo

Cuerpo del skill.
"""


def _repositorio_minimo(raiz: Path) -> Path:
    """Un repositorio con un unico skill conforme y sin plugin: el caso mas simple que el gate
    considera CONFORME (la ausencia de plugin es solo un aviso)."""
    directorio = raiz / "skills" / "validar-algo"
    directorio.mkdir(parents=True)
    (directorio / "SKILL.md").write_text(_SKILL_CONFORME, encoding="utf-8")
    return raiz


def _comprobacion(resultado: Resultado, nombre: str = "x") -> Comprobacion:
    return Comprobacion(nombre, resultado, "detalle")


# ── la agregacion, pura ────────────────────────────────────────────────────────────────────
def test_todas_conformes_agrega_conforme():
    assert agrega_conforme((_comprobacion(Resultado.CONFORME),
                            _comprobacion(Resultado.CONFORME, "y")))


def test_una_sola_no_conforme_tumba_el_gate():
    assert not agrega_conforme((_comprobacion(Resultado.CONFORME),
                                _comprobacion(Resultado.NO_CONFORME, "y")))


def test_no_aplica_no_bloquea():
    """El defecto que cubre: con dos estados en vez de tres, un dominio de SOLO PROMPTS quedaria
    rechazado porque la herramienta oficial falla con «no skills found» -- el motivo equivocado."""
    assert agrega_conforme((_comprobacion(Resultado.CONFORME),
                            _comprobacion(Resultado.NO_APLICA, "y")))


def test_no_aplica_sola_tambien_es_conforme():
    assert agrega_conforme((_comprobacion(Resultado.NO_APLICA),))


def test_sin_comprobaciones_no_hay_nada_que_bloquee():
    # Documenta el caso limite a proposito: si algun dia el gate se queda sin comprobaciones, la
    # funcion NO lo declara fallido -- quien construye la lista es responsable de que no este vacia.
    assert agrega_conforme(())


def test_solo_no_conforme_bloquea_y_los_otros_dos_no():
    for resultado, esperado in ((Resultado.CONFORME, False),
                                (Resultado.NO_APLICA, False),
                                (Resultado.NO_CONFORME, True)):
        assert _comprobacion(resultado).bloquea is esperado, resultado


# ── el resultado del gate ──────────────────────────────────────────────────────────────────
def test_el_gate_no_es_conforme_si_su_comprobacion_propia_falla():
    veredicto = Veredicto(hallazgos=(error("x", "falta description"),), inventario=Inventario())
    resultado = ResultadoGate(veredicto=veredicto,
                              comprobaciones=(_comprobacion(Resultado.NO_CONFORME),))
    assert not resultado.conforme


def test_un_aviso_no_tumba_el_gate():
    veredicto = Veredicto(hallazgos=(aviso("x", "el cuerpo es largo"),), inventario=Inventario())
    resultado = ResultadoGate(veredicto=veredicto,
                              comprobaciones=(_comprobacion(Resultado.CONFORME),))
    assert resultado.conforme


# ── la orquestacion, con doble inyectado ───────────────────────────────────────────────────
class ComprobadorFalso:
    """Doble del comprobador oficial. Registra si se le llamo, que es la mitad de lo que hay que
    comprobar: el gate no debe invocar la herramienta cuando esta desactivada."""

    def __init__(self, resultado: Resultado):
        self._resultado = resultado
        self.llamadas = 0

    def comprobar(self, raiz: Path) -> Comprobacion:
        self.llamadas += 1
        return Comprobacion("oficial", self._resultado, "detalle del doble")


def test_el_gate_lee_de_verdad_el_repositorio_que_recibe(tmp_path):
    """Ancla las demas: si el inventario no refleja el skill del fixture, el gate no leyo nada y
    cualquier otra asercion sobre el seria vacia."""
    resultado = ejecutar(_repositorio_minimo(tmp_path),
                         comprobador_oficial=ComprobadorFalso(Resultado.CONFORME))
    assert resultado.veredicto.inventario.skills == 1


def test_el_gate_agrega_las_dos_comprobaciones(tmp_path):
    doble = ComprobadorFalso(Resultado.CONFORME)
    resultado = ejecutar(_repositorio_minimo(tmp_path), comprobador_oficial=doble)
    assert [c.nombre for c in resultado.comprobaciones] == [NOMBRE_COMPROBACION_PROPIA, "oficial"]
    assert doble.llamadas == 1
    assert resultado.conforme


def test_si_la_oficial_falla_el_gate_falla_aunque_lo_nuestro_este_verde(tmp_path):
    doble = ComprobadorFalso(Resultado.NO_CONFORME)
    resultado = ejecutar(_repositorio_minimo(tmp_path), comprobador_oficial=doble)
    assert resultado.veredicto.conforme
    assert not resultado.conforme


def test_desactivarla_no_la_invoca_y_deja_su_motivo_escrito(tmp_path):
    """Desactivar no es dar por buena: queda como `no aplica` con el motivo, para que nadie lea el
    informe y crea que la comprobacion oficial paso."""
    doble = ComprobadorFalso(Resultado.NO_CONFORME)
    resultado = ejecutar(_repositorio_minimo(tmp_path), comprobador_oficial=doble,
                         con_comprobacion_oficial=False)
    assert doble.llamadas == 0
    oficial = resultado.comprobaciones[-1]
    assert oficial.resultado is Resultado.NO_APLICA
    assert "--sin-comprobacion-oficial" in oficial.detalle


_MCP_FIJADO = '{"mcpServers": {"catalogo": {"command": "uvx", "args": ["paquete-mcp@0.4.1"]}}}'


def _crear_mcp(raiz, credenciales: dict | None = None) -> None:
    """Un `mcp` se declara con DOS archivos: el `.mcp.json` que lee el CLIENTE -- al que no se le
    añade ninguna clave nuestra -- y el bloque `mcp` del `GOVERNANCE.json`, donde vive el gobierno.

    `credenciales=None` simula que el gobierno no declara el bloque `mcp`.
    """
    (raiz / ".mcp.json").write_text(_MCP_FIJADO, encoding="utf-8")
    # EL GOBIERNO SE ESCRIBE COMPLETO, no solo el bloque `mcp`. Al vivir el gobierno del mcp aqui, un
    # `GOVERNANCE.json` a medias activa las reglas del PLUGIN y la prueba fallaria por `owner.team`
    # vacio en vez de por lo que mide -- asi se descubrio, y por eso este helper es explicito.
    gobierno = {
        "id": "demo.x.y",
        "domain": "x",
        "owner": {"team": "squad-x", "contact": "squad-x@ejemplo.dev"},
        "status": "draft",
        "data_classification": "internal",
        "standard_version": "7.0.0",
        "artifacts": {"skills": 1, "agents": 0, "prompts": 0, "mcps": 1, "instructions": 0},
    }
    if credenciales is not None:
        gobierno["mcp"] = {"credentials": credenciales}
    (raiz / "GOVERNANCE.json").write_text(json.dumps(gobierno), encoding="utf-8")


def test_un_mcp_sin_custodia_declarada_bloquea_el_gate(tmp_path):
    """Defecto medido: ninguna prueba del arnes tenia un `.mcp.json`, asi que el cableado del
    adaptador no estaba cubierto y un fallo al leerlo pasaba las 84 pruebas en verde."""
    raiz = _repositorio_minimo(tmp_path)
    _crear_mcp(raiz, {"mechanism": "secret-ref"})

    resultado = ejecutar(raiz, comprobador_oficial=ComprobadorFalso(Resultado.CONFORME))

    assert not resultado.conforme
    motivos = " ".join(h.mensaje for h in resultado.veredicto.errores)
    assert "credential_owner" in motivos
    assert "access_request_url" in motivos


def test_un_mcp_con_oauth_no_pide_custodia(tmp_path):
    raiz = _repositorio_minimo(tmp_path)
    _crear_mcp(raiz, {"mechanism": "oauth"})

    resultado = ejecutar(raiz, comprobador_oficial=ComprobadorFalso(Resultado.CONFORME))

    assert resultado.conforme


def test_un_mcp_sin_su_bloque_en_el_gobierno_bloquea_el_gate(tmp_path):
    """Defecto MEDIDO con un `mcp` real: el gobierno se leia del propio `.mcp.json`. Ese archivo lo
    consume el CLIENTE -- los plugins reales lo llevan con una sola clave, `mcpServers` -- asi que
    meter campos nuestros nos haria depender de lo estricto que sea cada cliente. El gobierno vive en
    `GOVERNANCE.json`, y sin su bloque `mcp` el servidor no tiene dueno de credencial ni aprobacion."""
    raiz = _repositorio_minimo(tmp_path)
    _crear_mcp(raiz, credenciales=None)

    resultado = ejecutar(raiz, comprobador_oficial=ComprobadorFalso(Resultado.CONFORME))

    assert not resultado.conforme
    assert "GOVERNANCE.json" in " ".join(h.donde for h in resultado.veredicto.errores)


def test_un_mcp_con_referencia_movil_bloquea_el_gate(tmp_path):
    """El gate tiene que rechazar el *rug pull* de punta a punta, no solo en la regla suelta."""
    raiz = _repositorio_minimo(tmp_path)
    (raiz / ".mcp.json").write_text(
        '{"mcpServers": {"catalogo": {"command": "uvx", "args": ["paquete-mcp@latest"]}}}',
        encoding="utf-8")
    (raiz / "METADATA.json").write_text('{"credentials": {"mechanism": "oauth"}}', encoding="utf-8")

    resultado = ejecutar(raiz, comprobador_oficial=ComprobadorFalso(Resultado.CONFORME))

    assert not resultado.conforme
    assert "rug pull" in " ".join(h.mensaje for h in resultado.veredicto.errores)


_SKILL_CON_YAML_ROTO = """---
name: roto
description: Hace algo: y estos dos puntos rompen el YAML
---

Cuerpo.
"""


def test_un_frontmatter_que_no_es_yaml_valido_bloquea_el_gate(tmp_path):
    """Defecto MEDIDO en nuestro propio repositorio: un `description` con dos puntos sin entrecomillar
    dejaba el frontmatter ilegible. Los clientes SALTAN un skill con YAML invalido sin avisar, y
    nuestro gate lo daba por CONFORME -- porque la extraccion es por expresiones regulares y una
    expresion regular no ve un error de sintaxis. Un artefacto que ningun cliente puede cargar es
    justo lo que G1 existe para atrapar."""
    directorio = tmp_path / "skills" / "roto"
    directorio.mkdir(parents=True)
    (directorio / "SKILL.md").write_text(_SKILL_CON_YAML_ROTO, encoding="utf-8")

    resultado = ejecutar(tmp_path, comprobador_oficial=ComprobadorFalso(Resultado.CONFORME))

    assert not resultado.conforme
    assert any("no es YAML valido" in h.mensaje for h in resultado.veredicto.errores)


def test_un_frontmatter_valido_no_produce_ese_error(tmp_path):
    resultado = ejecutar(_repositorio_minimo(tmp_path),
                         comprobador_oficial=ComprobadorFalso(Resultado.CONFORME))
    assert not any("YAML" in h.mensaje for h in resultado.veredicto.errores)


# ── el gate CON los esquemas de verdad ─────────────────────────────────────────────────────
# Los esquemas del propio repositorio, no una copia: si divergen de lo que el gate espera, es un
# defecto real y estas pruebas tienen que verlo.
_ESQUEMAS_REALES = Path(__file__).resolve().parent.parent.parent / "schemas"


def test_el_gate_ejecuta_los_esquemas_cuando_se_le_pasan(tmp_path):
    # HUECO DE COBERTURA MEDIDO: TODAS las demas pruebas de este archivo omiten
    # `directorio_de_esquemas`, y con `None` la comprobacion de forma devuelve [] y no se ejecuta. O
    # sea que el camino que valida contra los esquemas -- el que decide si un artefacto publica -- no
    # tenia ninguna prueba de punta a punta. Se noto al mover una funcion de capa: 216 pruebas en
    # VERDE y el gate reventaba con AttributeError en esa misma funcion al correrlo de verdad.
    resultado = ejecutar(_repositorio_minimo(tmp_path),
                         comprobador_oficial=ComprobadorFalso(Resultado.CONFORME),
                         directorio_de_esquemas=_ESQUEMAS_REALES)
    assert resultado.conforme, [h.mensaje for h in resultado.veredicto.errores]


# Un skill cuyo unico defecto es de FORMA: `allowed-tools` como lista YAML cuando la especificacion
# exige una cadena separada por espacios (hallazgo 20 del activo). Es el canario de que los esquemas
# se ejecutan: si el camino del esquema estuviera muerto, este mensaje no aparece.
_SKILL_CON_ALLOWED_TOOLS_COMO_LISTA = """---
name: validar-algo
description: Comprueba algo concreto y se usa cuando alguien lo pide.
allowed-tools:
  - Read
  - Bash
metadata:
  id: demo.sdlc.ejemplo
  owner_team: squad-sdlc
  owner_contact: squad-sdlc@ejemplo.dev
  status: draft
  version: 1.0.0
  data_classification: internal
  standard_version: 7.0.0
---

# Validar algo
"""

# El prefijo con que el gate marca un defecto que vino del ESQUEMA y no de una regla. Se comprueba
# literalmente a proposito: la version anterior de esta prueba aceptaba «forma invalida» O
# «allowed-tools», y el segundo lo produce tambien la regla -- asi que habria pasado con el camino del
# esquema muerto, que es exactamente lo que esta prueba existe para detectar.
_MARCA_DE_DEFECTO_DE_ESQUEMA = "forma invalida"


def test_un_campo_del_tipo_equivocado_lo_atrapa_el_ESQUEMA(tmp_path):
    directorio = tmp_path / "skills" / "validar-algo"
    directorio.mkdir(parents=True)
    (directorio / "SKILL.md").write_text(_SKILL_CON_ALLOWED_TOOLS_COMO_LISTA, encoding="utf-8")

    resultado = ejecutar(tmp_path, comprobador_oficial=ComprobadorFalso(Resultado.CONFORME),
                         directorio_de_esquemas=_ESQUEMAS_REALES)

    mensajes = [h.mensaje for h in resultado.veredicto.errores]
    assert not resultado.conforme
    assert any(_MARCA_DE_DEFECTO_DE_ESQUEMA in m for m in mensajes), mensajes


# ── que el gate CABLEE de verdad las reglas que reciben contexto ────────────────────────────
# POR QUE ESTAS DOS PRUEBAS EXISTEN, y no es teorico: se comprobo por mutacion. Se comentaron las dos
# invocaciones -- `_revisar_duenos` y `_revisar_mezcla` -- dentro de `validar()`, o sea se
# DESCONECTARON las reglas del gate, y las 218 pruebas siguieron EN VERDE. Las reglas tienen sus
# pruebas propias en `test_reglas_aprobacion`, asi que lo que nadie comprobaba era el CABLE: que el
# gate las llame con el contexto que recibe. Es la misma forma del defecto que dejo sin probar la
# comprobacion contra esquemas -- parametro opcional, `None` apaga la regla, ninguna prueba lo pasa --
# y las dos reglas afectadas deciden si algo publica.
def test_el_gate_cablea_la_regla_de_dueno_resoluble(tmp_path):
    # `squad-sdlc` es el equipo que declara el skill del fixture; se le pasa un conjunto de equipos
    # que NO lo contiene, asi que si el cable existe el gate bloquea.
    resultado = ejecutar(_repositorio_minimo(tmp_path),
                         comprobador_oficial=ComprobadorFalso(Resultado.CONFORME),
                         equipos_conocidos=frozenset({"otro-squad"}))

    mensajes = [h.mensaje for h in resultado.veredicto.errores]
    assert not resultado.conforme
    assert any("NO existe en la organizacion" in m for m in mensajes), mensajes


def test_el_gate_cablea_la_regla_de_mezcla_de_firmantes(tmp_path):
    # Un cambio que toca un skill y un `.mcp.json`: dos clases de firmante en el mismo pull request.
    resultado = ejecutar(_repositorio_minimo(tmp_path),
                         comprobador_oficial=ComprobadorFalso(Resultado.CONFORME),
                         archivos_cambiados=("skills/validar-algo/SKILL.md", ".mcp.json"))

    mensajes = [h.mensaje for h in resultado.veredicto.errores]
    assert not resultado.conforme
    assert any("firmantes DISTINTOS" in m for m in mensajes), mensajes
