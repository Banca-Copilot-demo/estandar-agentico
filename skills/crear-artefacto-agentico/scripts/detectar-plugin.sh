#!/usr/bin/env bash
# Responde una sola pregunta: en que plugin estoy. Codigo de salida 1 si en ninguno, y ese caso NO
# es un error -- es el paso 1b del asistente, que decide si de verdad hace falta un plugin nuevo.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

if raiz="$(raiz_del_plugin)"; then
  echo "plugin: $(campo_del_manifiesto "$raiz/$RUTA_MANIFIESTO" name)"
  echo "raiz:   $raiz"
  exit 0
fi
echo "Aqui no hay plugin: no encontre $RUTA_MANIFIESTO subiendo desde $(pwd)."
echo "Comprueba primero que estas en el repositorio correcto."
exit 1
