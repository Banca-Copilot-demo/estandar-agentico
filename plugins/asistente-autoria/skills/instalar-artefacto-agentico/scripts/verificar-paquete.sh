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

# EL COMMIT SE SACA DE LA ATESTACION, NO DEL ARGUMENTO. Es la costura que este paso cierra.
#
# Lo que se VERIFICA es un .tar.gz; lo que se INSTALA es un CLON del repositorio en un commit -- esta
# medido: el cliente no despliega el paquete, clona --. Son objetos distintos, y lo unico que los une
# es el commit. Hasta aqui `$sha` era un argumento que este script copiaba al comprobante sin
# comprobarlo contra nada, asi que el comprobante afirmaba algo que nadie habia verificado.
#
# `sourceRepositoryDigest` viene del CERTIFICADO de firma, no de un campo que alguien pueda rellenar:
# es el commit desde el que el workflow construyo el paquete. Compararlo con el commit que se va a
# instalar convierte «verifique un paquete de ese repositorio» en «verifique lo que voy a instalar».
commit_atestado="$("${verificacion[@]}" --format json \
  -q '[.[].verificationResult.signature.certificate.sourceRepositoryDigest] | unique | .[0]' 2>/dev/null || true)"
if [ -z "$commit_atestado" ] || [ "$commit_atestado" = "null" ]; then
  abortar "la atestacion no declara commit de origen: no se puede atar lo verificado a lo que se instala"
fi
if [ "$commit_atestado" != "$sha" ]; then
  echo "El commit ATESTADO no es el que se va a instalar." >&2
  echo "  atestado por la firma: $commit_atestado" >&2
  echo "  declarado para instalar: $sha" >&2
  echo "Verificarias un paquete y instalarias otro contenido. Confirma el sha con el equipo dueno." >&2
  abortar "commit atestado distinto del declarado"
fi

comprobante="$destino/$NOMBRE_COMPROBANTE"
{
  echo "repo=$repo"
  echo "ref=$ref"
  echo "sha=$sha"
  echo "commit_atestado=$commit_atestado"
  echo "paquete=$(basename "$paquete")"
  echo "signer_repo=$REPO_FIRMANTE"
} > "$comprobante"

echo "Atestacion verificada. Comprobante escrito en $comprobante"
echo "Instala pasando ese directorio a instalar.sh: sin el comprobante, la instalacion se niega."
