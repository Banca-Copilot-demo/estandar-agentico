#!/usr/bin/env bash
# Lo que comparten todos los scripts del asistente. Se incluye con `source`, no se ejecuta.
#
# UNA SOLA FUENTE PARA EL MANIFIESTO. Todos los scripts necesitan lo mismo -- donde esta el plugin,
# de que repositorio salio y en que version --, y tenerlo repetido en cada uno significaria que una
# correccion se olvida en cuatro sitios.
set -euo pipefail

RUTA_MANIFIESTO=".claude-plugin/plugin.json"

# Sube desde el directorio actual buscando el manifiesto. Se sube en vez de asumir la raiz porque el
# desarrollador puede estar en cualquier subdirectorio del repositorio cuando invoca al asistente.
raiz_del_plugin() {
  local actual
  actual="$(pwd)"
  while [ "$actual" != "/" ] && [ "$actual" != "" ]; do
    if [ -f "$actual/$RUTA_MANIFIESTO" ]; then
      printf '%s' "$actual"
      return 0
    fi
    actual="$(dirname "$actual")"
  done
  return 1
}

# El directorio de ESTE skill, que es donde viven los esqueletos y el resto de los scripts.
raiz_del_skill() {
  cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd
}

campo_del_manifiesto() {  # campo_del_manifiesto <ruta al manifiesto> <campo>
  python -c "import json,sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
print(d.get(sys.argv[2], ''))" "$1" "$2"
}

# El dueno declarado en el gobierno del repositorio, si lo hay. Devuelve vacio si no.
campo_del_dueno() {  # campo_del_dueno <ruta a GOVERNANCE.json> <team|contact>
  python -c "import json,sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
print((d.get('owner') or {}).get(sys.argv[2], ''))" "$1" "$2"
}

abortar() {
  echo "error: $*" >&2
  exit 1
}

# DOS FORMAS DE ETIQUETA, y desde aqui no se puede deducir cual usa un repositorio. Un repositorio
# de un solo plugin en su raiz etiqueta `vX.Y.Z`; uno que aloja varios etiqueta `<nombre>--vX.Y.Z`,
# porque `vX.Y.Z` no diria de cual es. Las dos se derivan del manifiesto -- `name` y `version` -- y
# nada mas.
#
# POR QUE SE PREGUNTA AL REMOTO EN VEZ DE DEDUCIRLO. Este script corre desde la CACHE del cliente,
# donde el plugin ya esta extraido: no hay repositorio git, ni carpeta `plugins/`, ni nada que diga
# de que subdirectorio salio. Suponer una de las dos formas fallaria en la maquina del desarrollador
# -- no en CI -- la primera vez que usara el asistente. Una consulta al remoto lo resuelve sin
# suponer nada.
FORMA_ETIQUETA_ANIDADA="--v"

# Recibe la URL DE CLONADO ya formada, no el repositorio: el sufijo `.git` se anade una sola vez en
# el llamador, que tambien lo necesita para `pip`. Tenerlo aqui lo duplicaba.
etiqueta_publicada() {  # etiqueta_publicada <url de clonado> <nombre> <version>
  local url="$1" nombre="$2" version="$3"
  local anidada="${nombre}${FORMA_ETIQUETA_ANIDADA}${version}"
  local raiz="v${version}"
  local publicadas
  # `|| true`: sin acceso al remoto se devuelve vacio y el llamador da un error con contexto, en vez
  # de que `set -e` mate el script con el mensaje de git.
  publicadas="$(git ls-remote --tags "$url" 2>/dev/null || true)"
  for candidata in "$anidada" "$raiz"; do
    if printf '%s' "$publicadas" | grep -q "refs/tags/${candidata}\$"; then
      printf '%s' "$candidata"
      return 0
    fi
  done
  return 1
}
