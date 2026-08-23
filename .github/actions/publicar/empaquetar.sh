#!/usr/bin/env bash
# Empaqueta UN PLUGIN de forma DETERMINISTA: los mismos archivos producen siempre el mismo digest,
# en cualquier maquina y en cualquier momento.
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
#
# UN PLUGIN POR PAQUETE, no el repositorio. Cuando un repositorio de dominio aloja varios plugins
# bajo `plugins/<nombre>/`, empaquetar el arbol completo meteria en el paquete de cada plugin el
# contenido de sus vecinos: el digest dejaria de significar «este plugin» y la atestacion probaria
# algo distinto de lo que se instala. De ahi el tercer argumento.
#
# LIMITE CONOCIDO: el paquete se arma con el contenido del ARBOL DE TRABAJO, asi que los finales
# de linea forman parte del digest. Por eso todo repositorio de dominio lleva `.gitattributes` con
# `* text=auto eol=lf`: sin eso, empaquetar el mismo commit en Windows y en Linux daria digests
# distintos. El empaquetado de verdad ocurre siempre en CI, donde el checkout es limpio.

set -euo pipefail

readonly RAIZ="${1:?falta la raiz del repositorio}"
readonly DESTINO="${2:?falta la ruta del paquete de salida}"
# Subdirectorio del plugin, relativo a la raiz. `.` = el repositorio ES el plugin.
readonly SUBRUTA="${3:-.}"

# Lo que NO se distribuye: la mecanica del repositorio no es parte del artefacto.
#
# `GOVERNANCE.json` SE EXCLUYE, y no es un descuido. Ningun cliente lo lee: quien lo lee es el gate,
# y lo lee del REPOSITORIO en el pull request, nunca del paquete -- se comprobo en toda la cadena, y
# el lector del paquete solo busca `.claude-plugin/plugin.json` --. La procedencia no se pierde: viaja
# en la ATESTACION del veredicto, que esta firmada y fuera del artefacto, que es donde una prueba de
# origen tiene valor -- un archivo dentro del paquete lo podria editar cualquiera con permiso de
# escritura.
#
# CORRECCION MEDIDA AL INSTALAR DE VERDAD. Este comentario decia tambien que excluirlo mantiene limpia
# la carpeta de quien instala, porque «un archivo de nuestra maquinaria es ruido». ESO ES FALSO por la
# via del plugin: el cliente NO despliega el paquete, CLONA EL COMMIT, asi que `GOVERNANCE.json`
# aparece igual en su cache -- se vio en `~/.claude/plugins/cache/` tras un `plugin install` real --.
# La exclusion sigue valiendo para lo que de verdad importa: el paquete es lo que se FIRMA, y meter en
# el un archivo que ningun consumidor lee solo añade superficie al digesto. Pero no limpia nada.
# El `GOVERNANCE.json` se excluye a CUALQUIER profundidad: `git ls-files` da la ruta completa desde
# la raiz del repositorio, asi que en un plugin anidado llega como `plugins/<nombre>/GOVERNANCE.json`.
readonly EXCLUIDOS='^(\.github/|\.gitattributes$|\.gitignore$|validador/)|(^|/)GOVERNANCE\.json$'

cd "$RAIZ"

# El ambito acota `git ls-files` a un subdirectorio, y la transformacion quita ese prefijo del
# paquete: un cliente busca el manifiesto en la RAIZ de lo que extrae, no bajo `plugins/<nombre>/`.
ambito=()
transformacion=()
# EL CONJUNTO SUELTO EXCLUYE `plugins/`, y es lo que permite que un repositorio de dominio tenga
# plugins Y artefactos sueltos a la vez -- que es lo que el estandar recomienda: repositorios por
# DOMINIO, no repositorios separados segun se empaquete o no --. Sin esta exclusion, el paquete del
# conjunto suelto CONTENDRIA los plugins, asi que cada artefacto viajaria en dos paquetes distintos y
# el digesto del suelto cambiaria cada vez que alguien tocara un plugin que no tiene nada que ver.
#
# Se aplica solo con `SUBRUTA` en `.` y cuando existe el directorio: un repositorio de puros sueltos no
# tiene `plugins/` y no hay nada que excluir.
exclusiones="$EXCLUIDOS"
if [ "$SUBRUTA" = "." ] && [ -d "plugins" ]; then
  exclusiones="${EXCLUIDOS}|^plugins/"
fi

if [ "$SUBRUTA" != "." ]; then
  if [ ! -d "$SUBRUTA" ]; then
    echo "empaquetar: la subruta $SUBRUTA no existe en $RAIZ" >&2
    exit 1
  fi
  ambito=("$SUBRUTA")
  transformacion=(--transform "s|^${SUBRUTA}/||")
fi

lista="$(mktemp)"
trap 'rm -f "$lista"' EXIT
git ls-files -z -- "${ambito[@]}" \
  | tr '\0' '\n' \
  | grep -Ev "$exclusiones" \
  | LC_ALL=C sort > "$lista"

if [ ! -s "$lista" ]; then
  echo "empaquetar: no hay archivos que empaquetar en $RAIZ/$SUBRUTA" >&2
  exit 1
fi

tar --create \
    --format=ustar \
    --owner=0 --group=0 --numeric-owner \
    --mtime='@0' \
    "${transformacion[@]}" \
    --files-from="$lista" \
  | gzip -n -9 > "$DESTINO"

sha256sum "$DESTINO" | cut -d' ' -f1
