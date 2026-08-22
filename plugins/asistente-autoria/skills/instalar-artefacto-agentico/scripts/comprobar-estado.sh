#!/usr/bin/env bash
# Responde una sola pregunta: el `status` de la ficha permite instalar este artefacto.
#
# POR QUE ANTES DE DESCARGAR. Un artefacto `retired` no se instala aunque su atestacion sea
# perfecta: la firma dice quien lo publico, no si sigue vigente. Ese dato solo esta en la ficha.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly USO="comprobar-estado.sh <status> [superseded_by] [sunset_date]"
readonly SALIDA_RETIRADO=3

estado="${1:-}"
sucesor="${2:-}"
fecha_fin="${3:-}"
exigir_argumento "$estado" "status" "$USO"

if [ "$estado" = "$ESTADO_RETIRADO" ]; then
  echo "RETIRADO: este artefacto esta fuera de servicio y no se instala." >&2
  if [ -n "$sucesor" ]; then
    echo "Sustituto declarado en la ficha: $sucesor" >&2
  fi
  exit "$SALIDA_RETIRADO"
fi

if [ "$estado" = "$ESTADO_DEPRECADO" ]; then
  echo "AVISO: la ficha declara el artefacto como deprecado."
  echo "  sustituto:      ${sucesor:-no declarado en la ficha}"
  echo "  fin de soporte: ${fecha_fin:-no declarado en la ficha}"
  echo "Se puede instalar, pero tiene fecha de caducidad: confirmalo con quien lo pide."
  exit 0
fi

echo "Estado $estado: se puede continuar con la descarga y la verificacion."
