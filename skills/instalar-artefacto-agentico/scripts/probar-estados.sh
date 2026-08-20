#!/usr/bin/env bash
# Prueba de regresion de los codigos de salida (T6): este script decide si algo se INSTALA, asi que
# tiene que estar probado y no comprobado a ojo.
#
# EL DEFECTO QUE FIJA es de medicion, no de codigo. Se comprobo con
# `bash comprobar-estado.sh retired | head -1; echo $?` y salio 0 -- porque `$?` era el de `head` y
# no el del script --. Parecia que un retirado no bloqueaba. Aqui se mide sin tuberia.
set -euo pipefail

readonly AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ESPERADO_RETIRADO=3
readonly ESPERADO_CONTINUA=0

fallos=0
comprobar() {  # comprobar <descripcion> <esperado> <estado> [sucesor] [fecha]
  local descripcion="$1" esperado="$2"
  shift 2
  local obtenido=0
  bash "$AQUI/comprobar-estado.sh" "$@" >/dev/null 2>&1 || obtenido=$?
  if [ "$obtenido" = "$esperado" ]; then
    echo "  ok    $descripcion (codigo $obtenido)"
  else
    echo "  FALLO $descripcion: esperado $esperado, obtenido $obtenido"
    fallos=$((fallos + 1))
  fi
}

comprobar "retired BLOQUEA" "$ESPERADO_RETIRADO" retired demo.sdlc.sucesor
comprobar "retired bloquea aunque no haya sucesor" "$ESPERADO_RETIRADO" retired
comprobar "deprecated deja continuar" "$ESPERADO_CONTINUA" deprecated s 2027-01-01
comprobar "conformant deja continuar" "$ESPERADO_CONTINUA" conformant
comprobar "certified deja continuar" "$ESPERADO_CONTINUA" certified

# Sin argumentos tiene que fallar: instalar sin saber el estado es lo que la fase 1 evita.
sin_estado=0
bash "$AQUI/comprobar-estado.sh" >/dev/null 2>&1 || sin_estado=$?
if [ "$sin_estado" -ne 0 ]; then
  echo "  ok    sin estado NO continua (codigo $sin_estado)"
else
  echo "  FALLO sin estado deberia fallar y devolvio 0"
  fallos=$((fallos + 1))
fi

echo
if [ "$fallos" -ne 0 ]; then
  echo "estados: $fallos comprobacion(es) rota(s)" >&2
  exit 1
fi
echo "estados: 6 comprobaciones, todas correctas"
