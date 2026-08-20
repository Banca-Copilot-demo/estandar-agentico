#!/usr/bin/env bash
# Trae un archivo suelto FIJADO AL SHA y comprueba su sha256 contra el de la ficha.
#
# POR QUE NO VIENE COMO PAQUETE. Un `prompt` y unas `instructions` no viajan en un plugin: ni Agent
# Plugins v1 ni los cinco componentes de Copilot los incluyen. La unica forma de traerlos es el
# contenido crudo fijado al sha, y entonces la integridad la da el `sha256_archivo` de la ficha, no
# una atestacion de paquete.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly USO="verificar-archivo.sh <repo> <sha> <ruta-en-el-repo> <sha256> <destino>"
readonly BASE_CRUDA="https://raw.githubusercontent.com"

repo="${1:-}"
sha="${2:-}"
ruta="${3:-}"
sha256_esperado="${4:-}"
destino="${5:-}"
exigir_argumento "$repo" "repo" "$USO"
exigir_argumento "$sha" "sha" "$USO"
exigir_argumento "$ruta" "ruta-en-el-repo" "$USO"
exigir_argumento "$sha256_esperado" "sha256-esperado" "$USO"
exigir_argumento "$destino" "destino" "$USO"

url="$BASE_CRUDA/$repo/$sha/$ruta"

# `destino` admite un DIRECTORIO o un archivo, y no es indulgencia: su script hermano
# `verificar-paquete.sh` recibe un directorio. Que este exigiera un archivo hacia que pasarle un
# directorio fallara con `curl: (23) client returned ERROR on write` -- un error de ESCRITURA que
# parece de red y manda a mirar la URL.
if [ -d "$destino" ]; then
  destino="$destino/$(basename "$ruta")"
fi
mkdir -p "$(dirname "$destino")"
echo "Descargando $url"
if ! salida="$(curl --fail --silent --show-error --location "$url" --output "$destino" 2>&1)"; then
  traducir_fallo "$salida" >&2
  abortar "no se pudo descargar $ruta fijado a $sha"
fi

sha256_real="$(sha256sum "$destino" | cut -d ' ' -f 1)"
if [ "$sha256_real" != "$sha256_esperado" ]; then
  rm -f "$destino"
  traducir_fallo "sha256 distinto: esperado $sha256_esperado, obtenido $sha256_real" >&2
  abortar "integridad NO verificada: el archivo descargado se ha borrado"
fi

echo "El sha256 coincide con el de la ficha: $sha256_real"
echo "Archivo verificado en $destino"
