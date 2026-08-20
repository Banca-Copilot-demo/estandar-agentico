#!/usr/bin/env bash
# Traduce un fallo de gh o de copilot a una frase que diga QUE hacer. Nada mas.
#
# Existe como entrada suelta para el caso en que el desarrollador ya se choco con el error por su
# cuenta y solo trae el texto pegado.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly USO="explicar-fallo.sh <texto-del-fallo>"

texto="${1:-}"
exigir_argumento "$texto" "texto-del-fallo" "$USO"
traducir_fallo "$texto"
