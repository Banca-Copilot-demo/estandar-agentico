#!/usr/bin/env bash
# Empaqueta un repositorio de dominio de forma DETERMINISTA: los mismos archivos producen
# siempre el mismo digest, en cualquier maquina y en cualquier momento.
#
# Importa porque el digest es lo que se sella en la atestacion. Si el empaquetado no fuera
# determinista, dos publicaciones del mismo contenido darian digests distintos y la atestacion
# no probaria nada verificable: nadie podria reconstruir el paquete y comparar.
#
# Las cuatro fuentes de no-determinismo que se eliminan, y por que cada una:
#   1. El ORDEN de los archivos    -> `LC_ALL=C sort`     (el orden del directorio varia por FS)
#   2. Las FECHAS de modificacion  -> `--mtime=@0`        (cada clon tiene mtimes distintos)
#   3. El DUENO y el grupo         -> `--owner=0 --group=0 --numeric-owner`
#   4. La fecha dentro de GZIP     -> `gzip -n`           (gzip escribe la hora en su cabecera)
#
# La lista de archivos sale de `git ls-files`, no del directorio: asi solo entra lo versionado
# —nunca un `.venv`, un `__pycache__` ni un archivo a medias— y el contenido del paquete es
# exactamente el que se reviso en el pull request.
set -euo pipefail

readonly RAIZ="${1:?falta la raiz del repositorio}"
readonly DESTINO="${2:?falta la ruta del paquete de salida}"

# Lo que NO se distribuye: la mecanica del repositorio no es parte del artefacto.
readonly EXCLUIDOS='^(\.github/|\.gitattributes$|\.gitignore$|validador/)'

cd "$RAIZ"

lista="$(mktemp)"
trap 'rm -f "$lista"' EXIT
git ls-files -z \
  | tr '\0' '\n' \
  | grep -Ev "$EXCLUIDOS" \
  | LC_ALL=C sort > "$lista"

if [ ! -s "$lista" ]; then
  echo "empaquetar: no hay archivos que empaquetar en $RAIZ" >&2
  exit 1
fi

tar --create \
    --format=ustar \
    --owner=0 --group=0 --numeric-owner \
    --mtime='@0' \
    --files-from="$lista" \
  | gzip -n -9 > "$DESTINO"

sha256sum "$DESTINO" | cut -d' ' -f1
