"""Pedir la rama base y no poder resolverla NO puede salir en verde.

EL DEFECTO, MEDIDO en el registro de una solicitud de cambio real -- no leyendo el codigo --:

    DEBUG   cambios_git - listando cambios frente a origin/main
    WARNING cambios_git - no se pudieron listar los cambios frente a origin/main:
            fatal: origin/main...HEAD: no merge base

La accion hacia `git fetch --depth=1` de la base sobre un checkout que ya era superficial: dos
historias inconexas, sin ningun ancestro comun, asi que `base...HEAD` no tiene contra que comparar.
Sin lista de cambios, las reglas que dependen de la base se declaran «no aplica» y CALLAN.

Consecuencia: la regla de mezcla de firmantes llevaba desde el principio sin ejecutarse **ni una
sola vez** en CI, y el gate salia CONFORME. Es la peor forma de fallar, porque un gate que no
comprueba y calla es indistinguible de uno que comprobo y aprobo.

La causa se arregla en la accion (`--unshallow`). Esta prueba fija la OTRA mitad: que el proximo
fallo de la misma clase -- sea cual sea su causa -- no vuelva a pasar en silencio.
"""
from __future__ import annotations

from pathlib import Path

from validador_agentico import cli


def test_pedir_la_rama_base_y_no_poder_resolverla_NO_es_conforme(tmp_path, monkeypatch):
    # Un directorio que no es un repositorio git: `archivos_cambiados` devuelve `None`, exactamente
    # como cuando no hay merge base.
    (tmp_path / "skills").mkdir()
    monkeypatch.chdir(tmp_path)

    salida = cli.main([str(tmp_path), "--rama-base", "origin/main",
                       "--sin-comprobacion-oficial"])

    assert salida == cli.SALIDA_NO_CONFORME


def test_sin_rama_base_el_mismo_repositorio_SI_puede_ser_conforme(tmp_path, monkeypatch):
    """El corte anterior solo aplica cuando la base se PIDIO. Fuera de una solicitud de cambio no hay
    contra que comparar y la regla no aplica de verdad: si esta prueba fallara, el arreglo habria
    convertido toda validacion local en no conforme."""
    (tmp_path / "skills").mkdir()
    monkeypatch.chdir(tmp_path)

    salida = cli.main([str(tmp_path), "--sin-comprobacion-oficial"])

    assert salida == cli.SALIDA_CONFORME


def test_la_accion_de_validar_NO_usa_un_fetch_superficial_de_la_base():
    """REGRESION de la causa raiz, y se comprueba sobre el YAML porque es donde vive: un
    `fetch --depth=1` de la base deja dos historias inconexas y anula todas las reglas de solicitud
    de cambio. Sin esta prueba, cualquiera lo reintroduce por ahorrarse unos segundos de clonado.
    """
    accion = (Path(__file__).resolve().parents[2]
              / ".github" / "actions" / "validar" / "action.yml")
    # Solo lo EJECUTABLE: el comentario que explica el defecto cita `--depth=1` a proposito, y
    # mirarlo tambien haria fallar la prueba por el texto que documenta su propia razon de ser.
    ejecutable = "\n".join(linea for linea in accion.read_text(encoding="utf-8").splitlines()
                           if not linea.lstrip().startswith("#"))

    assert "--depth=1" not in ejecutable, "la base vuelve a traerse superficial: no habra merge base"
    assert "--unshallow" in ejecutable
