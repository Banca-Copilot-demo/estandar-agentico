"""Validar UNA unidad publicable, para que cada celda de la matriz de CI valide lo suyo y nada mas.

EL DEFECTO QUE CIERRA, medido leyendo el cableado de `agentes-sdlc/.github/workflows/validar.yml` y
las duraciones reales del commit `8ef42e5`: la conformidad corria como UN solo trabajo que recorria el
repositorio ENTERO, asi que un defecto preexistente en el artefacto de otro equipo bloqueaba la
solicitud de quien no lo habia tocado. Con 86 artefactos repartidos en cuatro repositorios, el sintoma
seria el peor posible: alguien bloqueado sin entender por que, sobre codigo que no es suyo.

POR QUE EL FLAG ES LO QUE HACE POSIBLE LA MATRIZ, y no un adorno. Sin acotar, las N celdas ejecutarian
el recorrido completo: todas darian el MISMO veredicto y todas saldrian en rojo por el defecto de una
sola. Seria peor que un trabajo unico -- el mismo bloqueo, repetido N veces y pagando N recorridos --.

LAS REGLAS DE REPOSITORIO NO SE REPARTEN, y por eso el recorrido sin acotar sigue siendo obligatorio:
higiene, mezcla de aprobadores, huerfanos y subida de version se juzgan sobre el arbol entero.
Repartirlas daria N veces el mismo hallazgo o, en el caso de los huerfanos, NINGUNA vez: un artefacto
que no pertenece a ninguna unidad no lo encuentra ninguna celda por definicion.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from validador_agentico.aplicacion.validar_repositorio import Alcance, validar
from validador_agentico.dominio.hallazgo import Severidad

_PLANTILLA_SKILL = """---
name: {nombre}
description: Hace algo concreto y se usa cuando alguien lo pide por su nombre en una conversacion.
metadata:
  id: demo.sdlc.{nombre}
  owner_team: squad-sdlc
  owner_contact: squad-sdlc@ejemplo.dev
  status: draft
  version: "2.0.0"
  data_classification: internal
  standard_version: "8.0.0"
---

# {nombre}
"""


def _plugin(raiz: Path, nombre: str, *, skill_roto: bool = False) -> str:
    """Un plugin con un skill dentro. `skill_roto` le quita el frontmatter, que es un error de unidad.

    Devuelve la subruta con la que la matriz nombra a esa unidad.
    """
    base = raiz / "plugins" / nombre
    (base / ".claude-plugin").mkdir(parents=True)
    (base / ".claude-plugin" / "plugin.json").write_text(json.dumps({
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "name": f"demo.sdlc.{nombre}", "version": "2.0.0",
        "description": "Un plugin de prueba.",
    }), encoding="utf-8")
    (base / "GOVERNANCE.json").write_text(json.dumps({
        "id": f"demo.sdlc.{nombre}",
        "domain": "sdlc",
        "owner": {"team": "squad-sdlc", "contact": "squad-sdlc@ejemplo.dev"},
        "status": "draft",
        "data_classification": "internal",
        "standard_version": "8.0.0",
        "artifacts": {"skills": 1},
    }), encoding="utf-8")
    directorio = base / "skills" / nombre
    directorio.mkdir(parents=True)
    cuerpo = f"# {nombre}\n" if skill_roto else _PLANTILLA_SKILL.format(nombre=nombre)
    (directorio / "SKILL.md").write_text(cuerpo, encoding="utf-8")
    return f"plugins/{nombre}"


def _errores(raiz: Path, unidad: str | None = None) -> list[str]:
    veredicto = validar(raiz, solo_la_unidad=unidad)
    return [f"{h.donde}: {h.mensaje}" for h in veredicto.hallazgos
            if h.severidad is Severidad.ERROR]


def test_validar_una_unidad_no_reporta_los_errores_de_otra(tmp_path):
    # EL DEFECTO CENTRAL: hoy el gate es un solo recorrido, asi que el plugin sano hereda el rojo del
    # roto. Acotado, la celda del sano tiene que salir limpia.
    sano = _plugin(tmp_path, "sano")
    _plugin(tmp_path, "roto", skill_roto=True)

    assert _errores(tmp_path, sano) == [], "la unidad sana hereda errores de la unidad rota"


def test_validar_la_unidad_rota_si_reporta_su_propio_error(tmp_path):
    # El complemento del anterior: acotar no puede convertirse en no mirar. Si la celda del roto
    # tambien saliera limpia, el flag no estaria acotando, estaria silenciando.
    _plugin(tmp_path, "sano")
    roto = _plugin(tmp_path, "roto", skill_roto=True)

    assert _errores(tmp_path, roto), "la unidad rota no reporta su propio error"


def test_una_unidad_inexistente_es_error_y_no_un_pase_en_verde(tmp_path):
    # SIN ESTO LA MATRIZ PUEDE PUBLICAR SIN VALIDAR. Que quien construye la matriz y quien la recorre
    # discrepen sobre que unidades hay es un fallo real -- un renombrado, un filtro de diff que no
    # coincide --, y su sintoma seria una celda en verde que no valido nada, un agregado en verde, y
    # un artefacto publicado sin haber pasado el gate.
    _plugin(tmp_path, "sano")

    assert _errores(tmp_path, "plugins/no-existe"), "una unidad inexistente pasa en verde"


def test_al_acotar_no_se_repiten_las_reglas_de_repositorio(tmp_path):
    # Los hallazgos de unidad llevan la subruta de su plugin en `donde`; los de repositorio no. Si al
    # acotar apareciera alguno sin prefijo, se estaria repitiendo en cada celda el mismo hallazgo
    # sobre el arbol entero -- N veces el mismo mensaje apuntando al mismo sitio --.
    sano = _plugin(tmp_path, "sano")
    _plugin(tmp_path, "roto", skill_roto=True)

    ajenos = [h.donde for h in validar(tmp_path, solo_la_unidad=sano).hallazgos
              if not h.donde.startswith(sano)]
    assert ajenos == [], f"al acotar se colaron hallazgos ajenos a la unidad: {ajenos}"


def test_las_dos_mitades_del_reparto_cubren_el_recorrido_completo(tmp_path):
    # LA PROPIEDAD QUE HACE LEGITIMO REPARTIR EL GATE EN VARIOS TRABAJOS. Si la suma de las celdas
    # mas el trabajo de repositorio dejara fuera alguna regla, el reparto habria convertido un gate
    # en un gate mas debil sin que nadie lo notara -- y en verde --. Se compara el CONJUNTO de
    # hallazgos, no la cuenta: un duplicado tambien seria un defecto, pero de otro tipo.
    sano = _plugin(tmp_path, "sano")
    roto = _plugin(tmp_path, "roto", skill_roto=True)

    def _todos(veredicto):
        return {(h.donde, h.mensaje) for h in veredicto.hallazgos}

    repartido = (_todos(validar(tmp_path, solo_la_unidad=sano))
                 | _todos(validar(tmp_path, solo_la_unidad=roto))
                 | _todos(validar(tmp_path, alcance=Alcance.REPOSITORIO)))
    completo = _todos(validar(tmp_path))

    assert repartido == completo, (
        f"el reparto pierde o inventa hallazgos. Solo en el completo: {completo - repartido}. "
        f"Solo en el repartido: {repartido - completo}")


def test_pedir_alcance_de_unidad_sin_nombrarla_es_un_error_del_programador(tmp_path):
    # Las dos formas de escribirlo mal son simetricas, pero solo una pasaria callando: nombrar la
    # unidad ya implica el alcance, mientras que pedir el alcance sin nombre dejaria `raices` vacio
    # y produciria una celda en verde que no valido nada.
    _plugin(tmp_path, "sano")

    with pytest.raises(ValueError):
        validar(tmp_path, alcance=Alcance.UNIDAD)


def test_solo_repositorio_no_reporta_hallazgos_de_ninguna_unidad(tmp_path):
    # La otra mitad del reparto: si el trabajo de repositorio siguiera viendo los defectos de cada
    # unidad, volveria a bloquear a todos por el defecto de uno -- exactamente lo que la matriz
    # existe para eliminar --, y ademas los duplicaria con los de las celdas.
    _plugin(tmp_path, "sano")
    _plugin(tmp_path, "roto", skill_roto=True)

    de_unidades = [h.donde for h in validar(tmp_path, alcance=Alcance.REPOSITORIO).hallazgos
                   if h.donde.startswith("plugins/")]
    assert de_unidades == [], f"el trabajo de repositorio juzga unidades: {de_unidades}"


def test_sin_acotar_el_veredicto_sigue_viendo_todas_las_unidades(tmp_path):
    # RETROCOMPATIBILIDAD: el recorrido sin acotar es el que corre en la publicacion y en local, y el
    # flag no puede haberle cambiado el criterio. Con el plugin roto presente tiene que salir en rojo.
    _plugin(tmp_path, "sano")
    _plugin(tmp_path, "roto", skill_roto=True)

    assert _errores(tmp_path), "el recorrido completo dejo de ver el defecto de una unidad"
