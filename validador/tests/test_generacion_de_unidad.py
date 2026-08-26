"""El asistente de autoria genera una unidad suelta que NACE CONFORME, gobierno incluido.

POR QUE ESTA PRUEBA SOSTIENE AL RESTO. El gate exige ahora un `GOVERNANCE.json` por unidad
publicable, y esa exigencia solo es razonable si el archivo se GENERA. El argumento con el que el
gate acabo heredando el gobierno de la raiz estaba escrito en el propio validador -- «obligaria a
escribir un archivo de gobierno por cada skill del inventario, decenas, para repetir los mismos tres
campos» -- y decae exactamente aqui: si el generador deja de escribirlo, el coste vuelve y la
presion por reintroducir la herencia con el.

Se ejecuta el script DE VERDAD y se le corre el gate al resultado, que es la unica forma de que el
desfase entre el generador y las reglas sea un fallo de CI en vez de una sorpresa en la maquina de
quien escribe el artefacto.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from validador_agentico.aplicacion.validar_repositorio import validar
from validador_agentico.dominio.hallazgo import Severidad

_RAIZ_DEL_ESTANDAR = Path(__file__).resolve().parents[2]
_ESQUEMAS = _RAIZ_DEL_ESTANDAR / "schemas"
_GENERAR = (_RAIZ_DEL_ESTANDAR / "plugins" / "asistente-autoria" / "skills"
            / "crear-artefacto-agentico" / "scripts" / "generar.sh")

# Donde aterriza la unidad de cada tipo. Lo decide el propio script, y tenerlo aqui como dato deja
# que las pruebas recorran los tres en bucle en vez de repetir el caso tres veces (T5).
_UNIDAD_DE = {"skill": "skills/revisar-jql", "agent": "agents/revisar-jql",
              "prompt": "commands/revisar-jql"}

_GOBIERNO_DE_LA_RAIZ = {
    "id": "demo.sdlc.sueltos",
    "domain": "sdlc",
    "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
    "status": "draft",
    "data_classification": "internal",
    "version": "1.0.0",
    "standard_version": "8.0.0",
    "artifacts": {"skills": 0, "agents": 0, "prompts": 0},
}


def _repositorio_de_dominio(raiz: Path) -> Path:
    """Un repositorio git con el gobierno de la raiz: es lo que `--unidad` exige para arrancar."""
    subprocess.run(["git", "init", "-q", str(raiz)], check=True)
    (raiz / "GOVERNANCE.json").write_text(json.dumps(_GOBIERNO_DE_LA_RAIZ, indent=2),
                                          encoding="utf-8")
    return raiz


def _generar(raiz: Path, tipo: str) -> Path:
    """Corre el generador dentro del repositorio y devuelve la raiz de la unidad creada."""
    # LA RUTA DEL SCRIPT VA RELATIVA A `cwd`, y no absoluta, porque una ruta absoluta obliga a saber
    # que forma entiende el bash que resuelva `PATH`. Medido en Windows: ahi puede ser el de WSL, que
    # monta el disco en `/mnt/c` y no reconoce ni `C:\...` ni `C:/...`; el script «no existe» y la
    # prueba falla por el entorno y no por lo que mide. Una ruta relativa no tiene ese problema en
    # ningun bash.
    relativa = Path(os.path.relpath(_GENERAR, raiz)).as_posix()
    subprocess.run(["bash", relativa, "--unidad", tipo, "revisar-jql"],
                   cwd=raiz, check=True, capture_output=True, text=True)
    return raiz / _UNIDAD_DE[tipo]


def _falta_el_entorno_del_generador() -> bool:
    """El generador es un script de bash que necesita `git` y `python` DENTRO de ese bash.

    SE COMPRUEBA EJECUTANDOLO y no con `shutil.which`, que responde por el PATH de Windows: medido en
    una maquina de desarrollo, el `bash` que resuelve el PATH es el de WSL, con su propio PATH y sin
    `python` -- solo `python3` --, asi que `which` decia que si y el script moria con 127. En CI, que
    es donde esta prueba tiene que correr de verdad, las tres estan.
    """
    if shutil.which("bash") is None or shutil.which("git") is None:
        return True
    sonda = subprocess.run(["bash", "-c", "command -v git && command -v python"],
                           capture_output=True, text=True)
    return sonda.returncode != 0


pytestmark = pytest.mark.skipif(
    _falta_el_entorno_del_generador(),
    reason="el generador necesita bash con `git` y `python` dentro")


@pytest.mark.parametrize("tipo", sorted(_UNIDAD_DE), ids=sorted(_UNIDAD_DE))
def test_la_unidad_generada_trae_su_GOBIERNO_y_no_hereda_el_de_la_raiz(tipo, tmp_path):
    """REGRESION del defecto de la herencia, por el lado del generador.

    El asistente ya escribia el manifiesto de la unidad y no su gobierno, asi que cada suelto que
    generaba nacia dependiendo del `owner.team` de la raiz -- medido en `agentes-sdlc` con
    `skills/revisar-jql` --. Si alguien quita la generacion, esta prueba falla antes de que el hueco
    llegue a un repositorio de dominio.
    """
    unidad = _generar(_repositorio_de_dominio(tmp_path), tipo)

    gobierno = json.loads((unidad / "GOVERNANCE.json").read_text(encoding="utf-8"))

    assert gobierno["owner"]["team"] == "squad-sdlc"
    assert gobierno["id"] == "demo.sdlc.revisar-jql", "el id de la unidad, no el de la raiz"


@pytest.mark.parametrize("tipo", sorted(_UNIDAD_DE), ids=sorted(_UNIDAD_DE))
def test_el_gobierno_NO_se_escribe_dentro_del_directorio_que_lee_el_cliente(tipo, tmp_path):
    """`.claude-plugin/` lo define una especificacion ajena y lo lee el cliente; ademas todo lo que
    cuelga de la unidad viaja en el paquete sellado hasta la maquina de quien instala, y el gobierno
    lleva equipo dueno, correo y clasificacion del dato. Ahi dentro seria contenido interno metido en
    un directorio publico."""
    unidad = _generar(_repositorio_de_dominio(tmp_path), tipo)

    assert (unidad / "GOVERNANCE.json").is_file()
    assert not (unidad / ".claude-plugin" / "GOVERNANCE.json").exists()


@pytest.mark.parametrize("tipo", sorted(_UNIDAD_DE), ids=sorted(_UNIDAD_DE))
def test_el_gate_no_reclama_NADA_del_gobierno_de_lo_generado(tipo, tmp_path):
    """Se le corre el gate de verdad y se mira SOLO lo que sale de `GOVERNANCE.json`: si el generador
    se desincroniza de las reglas -- un campo nuevo, otro nombre, el inventario descuadrado --, sale
    aqui y no en el repositorio de un equipo.

    ACOTADO AL GOBIERNO A PROPOSITO. El esqueleto trae `PENDIENTE` donde hace falta una persona, asi
    que exigirle CONFORME entero convertiria esta prueba en la de otra cosa.
    """
    raiz = _repositorio_de_dominio(tmp_path)
    _generar(raiz, tipo)

    errores = [f"{h.donde}: {h.mensaje}" for h
               in validar(raiz, directorio_de_esquemas=_ESQUEMAS,
                          equipos_conocidos=frozenset({"squad-sdlc"})).hallazgos
               if h.severidad is Severidad.ERROR]

    assert not [e for e in errores if "GOVERNANCE.json" in e], errores
