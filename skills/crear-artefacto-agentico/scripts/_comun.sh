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
