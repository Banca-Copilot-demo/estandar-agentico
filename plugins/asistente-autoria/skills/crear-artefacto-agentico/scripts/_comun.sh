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

# EL PREFIJO DE DOMINIO, para nombrar la unidad de un artefacto suelto publicado por separado.
#
# Sale del `id` del `GOVERNANCE.json` de la raiz quitandole su ultimo segmento: `demo.sdlc.sueltos`
# da `demo.sdlc`, y con el nombre del artefacto queda `demo.sdlc.revisar-jql`. Se deriva en vez de
# preguntarse para que dos artefactos del mismo dominio no acaben con prefijos distintos, que es el
# defecto medido en el activo del cliente con los campos que se copian a mano.
prefijo_del_dominio() {  # prefijo_del_dominio <ruta a GOVERNANCE.json>
  python -c "import json,sys
d = json.load(open(sys.argv[1], encoding='utf-8'))
identificador = d.get('id') or ''
print(identificador.rsplit('.', 1)[0] if '.' in identificador else identificador)" "$1"
}

# Escribe el manifiesto de una unidad de UN SOLO artefacto.
#
# `commands` SOLO PARA LOS PROMPTS, y no es un capricho: la referencia de plugins de Copilot lista
# `commands` como componente pero es el unico SIN RUTA POR DEFECTO, asi que un prompt sin declararlo
# se instala y no lo registra nadie -- los archivos aterrizan y no los ve el cliente --. Al
# declararlo cambia lo que Copilot copia, que es como se comprobo que lo lee. `skills/` y `agents/`
# si son rutas por defecto en los dos clientes y declararlas seria ruido.
escribir_manifiesto_de_unidad() {  # ... <destino> <nombre> <descripcion> <tipo>
  local destino="$1" nombre="$2" descripcion="$3" tipo="$4"
  mkdir -p "$(dirname "$destino")"
  python -c "import json,sys
manifiesto = {
    '\$schema': 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json',
    'name': sys.argv[2],
    'version': '0.1.0',
    'description': sys.argv[3],
}
if sys.argv[4] == 'prompt':
    manifiesto['commands'] = './commands'
open(sys.argv[1], 'w', encoding='utf-8').write(json.dumps(manifiesto, indent=2) + '\n')
" "$destino" "$nombre" "$descripcion" "$tipo"
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
