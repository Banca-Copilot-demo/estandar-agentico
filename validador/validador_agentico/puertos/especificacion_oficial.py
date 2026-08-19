"""Puerto de la comprobacion oficial de la especificacion Agent Skills.

POR QUE AQUI SI HAY PUERTO Y EN EL RESTO DEL PAQUETE NO. La regla del proyecto es que un puerto se
introduce cuando hay -- o se anticipa -- mas de una implementacion, o se necesita un doble de test.
Las dos condiciones se cumplen: la implementacion real invoca `gh` como proceso externo, y las
pruebas necesitan sustituirla para poder cubrir los tres resultados sin red ni CLI instalado.

Para el resto de la I/O del paquete -- leer el repositorio, escribir el informe -- hay una sola
implementacion y no se inventa puerto: una interfaz con un unico implementador es indireccion sin
beneficio.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from validador_agentico.dominio.comprobacion import Comprobacion

# Parte del contrato y no del adaptador: la aplicacion nombra la comprobacion sin conocer quien la
# implementa. Si viviera en el adaptador, `aplicacion` tendria que importarlo solo para el nombre.
NOMBRE_COMPROBACION_OFICIAL = "especificacion Agent Skills (oficial)"


class ComprobadorOficial(Protocol):
    """Comprueba un repositorio contra la especificacion oficial de Agent Skills.

    Devuelve SIEMPRE una `Comprobacion`, nunca lanza: el gate tiene que poder agregar su resultado
    junto al de las demas. Que la herramienta no este instalada es un resultado, no una excepcion.
    """

    def comprobar(self, raiz: Path) -> Comprobacion: ...
