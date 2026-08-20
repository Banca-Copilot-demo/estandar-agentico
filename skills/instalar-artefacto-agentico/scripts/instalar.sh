#!/usr/bin/env bash
# Instala el artefacto YA VERIFICADO, con el alcance elegido de forma explicita.
#
# EL COMPROBANTE ES OBLIGATORIO. Si no existe el que escribe verificar-paquete.sh, este script se
# niega: el orden del que depende todo el skill -- descargar, verificar, instalar -- no puede quedar
# a merced de que alguien se salte un paso.
#
# EL ALCANCE NO SE ELIGE EN SILENCIO. `gh skill install` usa `project` por defecto, y `project` deja
# el archivo DENTRO del repositorio del consumidor, asi que afecta a todo el equipo; `user` va al
# home y solo afecta a quien instala. Aqui se pasa siempre. Los plugins de Copilot no tienen
# alcance de proyecto: son siempre de usuario.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly USO="instalar.sh <alcance:project|user> <directorio-verificado> <install_hint...>"

alcance="${1:-}"
directorio="${2:-}"
exigir_argumento "$alcance" "alcance" "$USO"
exigir_argumento "$directorio" "directorio-verificado" "$USO"
shift 2
if [ "$#" -eq 0 ]; then
  abortar "falta el install_hint de la ficha. uso: $USO"
fi

case "$alcance" in
  "$ALCANCE_PROYECTO"|"$ALCANCE_USUARIO") ;;
  *) abortar "alcance invalido: $alcance (validos: $ALCANCE_PROYECTO, $ALCANCE_USUARIO)" ;;
esac

comprobante="$directorio/$NOMBRE_COMPROBANTE"
if [ ! -f "$comprobante" ]; then
  echo "No encuentro el comprobante de verificacion en $comprobante." >&2
  echo "Ejecuta primero verificar-paquete.sh: instalar sin verificar es exactamente lo que" >&2
  echo "este skill existe para evitar." >&2
  exit 1
fi

comando=("$@")
if [ "${comando[0]}" = "copilot" ] && [ "$alcance" = "$ALCANCE_PROYECTO" ]; then
  abortar "copilot plugin install es SIEMPRE de alcance de usuario: no hay alcance de proyecto"
fi
if [ "${comando[0]}" = "gh" ]; then
  case " ${comando[*]} " in
    *" --scope "*) ;;
    *) comando+=(--scope "$alcance") ;;
  esac
fi

echo "Instalando con el comprobante de $comprobante"
printf 'comando:'
printf ' %q' "${comando[@]}"
printf '\n'
if ! salida="$("${comando[@]}" 2>&1)"; then
  traducir_fallo "$salida" >&2
  abortar "la instalacion fallo"
fi
echo "$salida"
echo "Instalado con alcance $alcance."
