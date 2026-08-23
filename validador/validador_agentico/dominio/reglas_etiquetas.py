"""Como se llama la etiqueta de una unidad publicable. Regla pura: recibe datos, devuelve el nombre.

POR QUE ES UNA REGLA Y NO UN `if` DE BASH, que es donde estaba. La forma de la etiqueta es el contrato
mas caro de equivocar de toda la cadena: con releases inmutables una etiqueta mal puesta NO SE BORRA, y
seis sitios del pipeline dependen de poder leerla. Estaba decidida en tres lineas de bash dentro del
workflow de etiquetado, donde ninguna prueba la alcanzaba, y se equivoco en cuanto aparecio un caso
nuevo.

EL DEFECTO MEDIDO. La condicion era «si la subruta es `.`, forma corta `vX.Y.Z`». Eso valia cuando `.`
solo podia significar «el repositorio ENTERO es el paquete» -- un plugin en la raiz --. Al aparecer el
repositorio MIXTO, `.` pasa a significar tambien «el conjunto suelto de un repositorio que ademas
tiene plugins», y la forma corta se volvio ambigua: en `agentes-sdlc` se creo un release `v1.0.0`
conviviendo con cuatro etiquetas nombradas, y ahi `v1.0.0` significaba «todo excepto los plugins» --
una definicion por RESTA que nadie deduce leyendo la etiqueta --.

EL DISCRIMINADOR CORRECTO NO ES LA SUBRUTA, ES SI LA UNIDAD ESTA SOLA. Con una sola unidad la forma
corta es inequivoca: la etiqueta se refiere al repositorio, y da igual si ese repositorio es un plugin
o un conjunto de sueltos. Con varias, cada etiqueta tiene que decir CUAL publica.

LA CONVENCION LA PARSEA OTRO PAQUETE. `indice_agentico.dominio.reglas_etiquetas` hace el camino
inverso -- de la etiqueta al nombre y la version -- y comparte por tanto el separador. Son dos
paquetes instalables por separado, asi que la constante esta en los dos: si se toca aqui, hay que
tocarla alli.
"""
from __future__ import annotations

# Separa el nombre de la unidad de su version. Dos guiones y no uno porque los nombres de plugin
# LLEVAN guiones -- `catalogo-datos` -- y con un separador de un guion la etiqueta seria ambigua.
SEPARADOR_DE_ETIQUETA = "--v"
PREFIJO_DE_VERSION = "v"


def etiqueta_de(nombre: str, version: str, unidad_unica: bool) -> str:
    """El nombre de la etiqueta que publica esta unidad.

    `unidad_unica` es si el repositorio publica UNA sola cosa. Es un dato del repositorio y no de la
    unidad, y por eso lo recibe en vez de deducirlo: la misma unidad se etiqueta distinto segun tenga
    vecinas o no, y esa es justo la decision que el `if` de bash no sabia tomar.
    """
    if unidad_unica:
        return f"{PREFIJO_DE_VERSION}{version}"
    return f"{nombre}{SEPARADOR_DE_ETIQUETA}{version}"
