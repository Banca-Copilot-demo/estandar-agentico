#!/usr/bin/env bash
# Lo que comparten todos los scripts del asistente. Se incluye con `source`, no se ejecuta.
#
# UNA SOLA FUENTE PARA EL MANIFIESTO. Todos los scripts necesitan lo mismo -- donde esta el plugin,
# de que repositorio salio y en que version --, y tenerlo repetido en cada uno significaria que una
# correccion se olvida en cuatro sitios.
set -euo pipefail

RUTA_MANIFIESTO=".claude-plugin/plugin.json"
# El gobierno va en la RAIZ de la unidad y NO dentro de `.claude-plugin/`: ese directorio es el que
# lee el cliente, lo define una especificacion ajena, y su contenido viaja en el paquete hasta la
# maquina de quien instala -- el gobierno lleva dueno, contacto y clasificacion del dato --.
RUTA_GOBIERNO="GOVERNANCE.json"

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

# Un campo de primer nivel de cualquier JSON del repositorio. Sirve para el manifiesto y para el
# `GOVERNANCE.json`: tener una funcion por archivo seria la misma lectura escrita dos veces.
campo_json() {  # campo_json <ruta al json> <campo>
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

# Los tipos de artefacto, con la clave con la que cada uno se cuenta en el inventario del gobierno.
# El plural del gate no es el nombre del tipo -- `agent` cuenta en `agents` -- y escribirlo en el
# sitio de uso lo convertiria en un literal disperso.
CLAVE_DE_INVENTARIO_skill="skills"
CLAVE_DE_INVENTARIO_agent="agents"
CLAVE_DE_INVENTARIO_prompt="prompts"

# Escribe el `GOVERNANCE.json` de una unidad de UN SOLO artefacto, con la forma de
# `plantillas/unidad-plugin/GOVERNANCE.json` -- que es la que le toca: la unidad TIENE manifiesto --.
#
# VA EN LA RAIZ DE LA UNIDAD, HERMANO DE `.claude-plugin/` Y NO DENTRO. Ese directorio es lo que lee
# el CLIENTE y su contenido lo fija una especificacion que no controlamos, asi que meterle un archivo
# nuestro es apostar contra la proxima version de la spec. Y hay un motivo mas fuerte: todo lo que
# vive en la unidad viaja en el paquete sellado hasta la maquina de quien instala, y el gobierno
# lleva equipo dueno, correo de contacto y clasificacion del dato -- informacion interna que un
# consumidor no necesita para usar el artefacto --.
#
# SIN `version`: la unidad trae `plugin.json` y la version del paquete es la del manifiesto.
# Declararla en los dos sitios es un error del gate, y con razon: dos declaraciones de lo mismo
# divergen y la etiqueta saldria de una de las dos sin saber cual.
#
# EL DUENO SE ARRASTRA DEL GOBIERNO DE LA RAIZ y queda ESCRITO en el archivo de la unidad, que es la
# diferencia que importa: antes se heredaba en tiempo de validacion, sin dejar rastro, y todos los
# sueltos de un repositorio acababan con el mismo dueno sin que nadie lo hubiera decidido. Escrito,
# es un valor que se ve en la revision y se corrige de una linea.
escribir_gobierno_de_unidad() {  # ... <destino> <id> <tipo> <gobierno de la raiz>
  local destino="$1" identificador="$2" tipo="$3" de_la_raiz="$4"
  local clave="CLAVE_DE_INVENTARIO_$tipo"
  mkdir -p "$(dirname "$destino")"
  python -c "import json,sys
raiz = json.load(open(sys.argv[4], encoding='utf-8'))
gobierno = {
    'id': sys.argv[2],
    'domain': raiz.get('domain', 'PENDIENTE'),
    'owner': {
        'team': (raiz.get('owner') or {}).get('team', 'PENDIENTE'),
        'contact': (raiz.get('owner') or {}).get('contact', 'PENDIENTE'),
    },
    'status': 'draft',
    'data_classification': raiz.get('data_classification', 'internal'),
    'standard_version': raiz.get('standard_version', ''),
    'artifacts': {'skills': 0, 'agents': 0, 'prompts': 0},
}
gobierno['artifacts'][sys.argv[3]] = 1
open(sys.argv[1], 'w', encoding='utf-8').write(json.dumps(gobierno, indent=2) + '\n')
" "$destino" "$identificador" "${!clave}" "$de_la_raiz"
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
