#!/usr/bin/env bash
# Descarga el paquete del release y VERIFICA su atestacion. No instala nada.
#
# POR QUE ESTE SCRIPT EXISTE. Esta medido que ningun cliente verifica al instalar: ni el `--help`
# de `gh skill install` ni la documentacion de `copilot plugin install` mencionan verificacion, y el
# comando es ATOMICO -- resuelve, descarga e instala de una vez --. Asi que el desarrollador solo
# puede instalar y verificar despues. Aqui se invierte el orden: primero se baja, luego se verifica
# y solo entonces se instala.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly USO="verificar-paquete.sh <repo> <ref> <sha> <directorio-destino>"

repo="${1:-}"
ref="${2:-}"
sha="${3:-}"
destino="${4:-}"
exigir_argumento "$repo" "repo" "$USO"
exigir_argumento "$ref" "ref" "$USO"
exigir_argumento "$sha" "sha" "$USO"
exigir_argumento "$destino" "directorio-destino" "$USO"

mkdir -p "$destino"
echo "Descargando el release $ref de $repo (sellado en $sha) en $destino"
if ! salida="$(gh release download "$ref" --repo "$repo" --dir "$destino" --clobber 2>&1)"; then
  traducir_fallo "$salida" >&2
  abortar "no se pudo descargar el release $ref de $repo"
fi

paquete="$(ls -1 "$destino"/*.tar.gz "$destino"/*.zip 2>/dev/null | head -n 1 || true)"
if [ -z "$paquete" ]; then
  abortar "el release $ref no trae paquete (.tar.gz ni .zip) en $destino"
fi

echo "Verificando la atestacion de $(basename "$paquete")"
echo "  firmante esperado: $REPO_FIRMANTE"
# `--repo` es OBLIGATORIO: sin el, `gh` corta con «at least one of the flags in the group
# [owner repo] is required» -- otro mensaje que no dice que falta --. Y `--signer-repo` tambien hace
# falta, por un motivo distinto: el paquete sale del repositorio del DOMINIO pero lo firma el
# workflow reutilizable del ESTANDAR, asi que sin declararlo la verificacion falla contra el
# repositorio equivocado.
verificacion=(gh attestation verify "$paquete" --repo "$repo" --signer-repo "$REPO_FIRMANTE")
if ! salida="$("${verificacion[@]}" 2>&1)"; then
  traducir_fallo "$salida" >&2
  abortar "atestacion NO verificada: no instales este paquete"
fi

comprobante="$destino/$NOMBRE_COMPROBANTE"
{
  echo "repo=$repo"
  echo "ref=$ref"
  echo "sha=$sha"
  echo "paquete=$(basename "$paquete")"
  echo "signer_repo=$REPO_FIRMANTE"
} > "$comprobante"

echo "Atestacion verificada. Comprobante escrito en $comprobante"
echo "Instala pasando ese directorio a instalar.sh: sin el comprobante, la instalacion se niega."
