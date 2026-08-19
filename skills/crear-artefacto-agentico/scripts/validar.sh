#!/usr/bin/env bash
# Corre el gate en local. Es EL MISMO comando que corre CI, y eso es el punto: un pull request que
# nace en verde no rebota.
#
# No se pasa `--organizacion` ni `--rama-base`: el primero exige una credencial que la maquina del
# desarrollador no tiene por que tener, y el segundo solo aplica dentro de un pull request. Los dos
# los anade CI. Aqui se corre lo que se puede correr sin credenciales, que es la mayor parte.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly MODULO="validador_agentico.cli"

raiz="$(raiz_del_plugin)" || abortar "no estoy dentro de un repositorio con $RUTA_MANIFIESTO"

if ! python -c "import validador_agentico" 2>/dev/null; then
  echo "El validador no esta instalado. Instalandolo a la version de este asistente..."
  bash "$(dirname "${BASH_SOURCE[0]}")/instalar-validador.sh"
fi

python -m "$MODULO" "$raiz" "$@"
