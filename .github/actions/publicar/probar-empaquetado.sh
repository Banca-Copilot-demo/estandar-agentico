#!/usr/bin/env bash
# Prueba de regresion del empaquetado determinista (T3, T6).
#
# El defecto que cubre: un empaquetado que cambia de digest cuando cambia el reloj o el orden de
# lectura del sistema de archivos. Se medio en la fase 4: sin `--mtime`, el mismo contenido daba
# un digest distinto en cada ejecucion, y la atestacion no habria sido verificable por nadie.
#
# Comprueba tres propiedades, cada una con su mensaje: si falla, el mensaje dice cual se rompio.
set -euo pipefail

readonly RAIZ="${1:?falta la raiz del repositorio a empaquetar}"
readonly AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TRABAJO="$(mktemp -d)"
trap 'rm -rf "$TRABAJO"' EXIT

fallos=0
comprobar() {  # comprobar <descripcion> <esperado> <obtenido>
  if [ "$2" = "$3" ]; then
    echo "  ok    $1"
  else
    echo "  FALLO $1"
    echo "        esperado: $2"
    echo "        obtenido: $3"
    fallos=$((fallos + 1))
  fi
}

primero="$("$AQUI/empaquetar.sh" "$RAIZ" "$TRABAJO/a.tar.gz")"
segundo="$("$AQUI/empaquetar.sh" "$RAIZ" "$TRABAJO/b.tar.gz")"
comprobar "dos empaquetados seguidos dan el mismo digest" "$primero" "$segundo"

# Toca las fechas de todo lo versionado: el contenido no cambio, el digest no debe cambiar.
git -C "$RAIZ" ls-files -z | tr '\0' '\n' | while read -r archivo; do
  touch -d '2001-02-03 04:05:06' "$RAIZ/$archivo"
done
tras_tocar="$("$AQUI/empaquetar.sh" "$RAIZ" "$TRABAJO/c.tar.gz")"
comprobar "cambiar las fechas de modificacion no cambia el digest" "$primero" "$tras_tocar"

# Cambiar un byte del contenido SI debe cambiar el digest: si no, el sello no probaria nada.
copia="$TRABAJO/copia"
git -C "$RAIZ" ls-files -z | tr '\0' '\n' > "$TRABAJO/versionados"
git clone --quiet --no-hardlinks "$RAIZ" "$copia"
primer_archivo="$(head -1 "$TRABAJO/versionados")"
printf '\n<byte de mas>\n' >> "$copia/$primer_archivo"
git -C "$copia" add -A && git -C "$copia" -c user.email=p@p -c user.name=p commit --quiet -m x
tras_editar="$("$AQUI/empaquetar.sh" "$copia" "$TRABAJO/d.tar.gz")"
if [ "$primero" = "$tras_editar" ]; then
  echo "  FALLO editar el contenido debe cambiar el digest (no cambio)"
  fallos=$((fallos + 1))
else
  echo "  ok    editar el contenido cambia el digest"
fi

echo
if [ "$fallos" -ne 0 ]; then
  echo "empaquetado: $fallos propiedad(es) rota(s)" >&2
  exit 1
fi
echo "empaquetado determinista: 3 propiedades comprobadas | digest $primero"
