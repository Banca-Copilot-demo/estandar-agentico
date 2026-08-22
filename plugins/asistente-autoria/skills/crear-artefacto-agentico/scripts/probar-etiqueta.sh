#!/usr/bin/env bash
# Prueba de regresion de la resolucion de la etiqueta del estandar (T3, T6).
#
# EL DEFECTO QUE CUBRE, y por que merece prueba propia: la etiqueta se construia como `v${version}`,
# asi que al pasar el plugin del estandar a `plugins/<nombre>/` -- donde su etiqueta es
# `<nombre>--v${version}` -- el `pip install` habria buscado una etiqueta inexistente. Y habria
# fallado en la MAQUINA DEL DESARROLLADOR la primera vez que usara el asistente, no en CI: es la
# peor clase de fallo de toda la cadena porque no lo ve quien puede arreglarlo.
#
# Se usa un repositorio LOCAL como remoto: `git ls-remote` funciona igual contra una ruta que contra
# una URL, asi que la prueba no toca la red y no depende de que exista ningun repositorio publicado.
set -euo pipefail

readonly AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TRABAJO="$(mktemp -d)"
trap 'rm -rf "$TRABAJO"' EXIT

source "$AQUI/_comun.sh"

readonly NOMBRE="demo.plataforma.agentico"
readonly VERSION="0.1.0"

fallos=0
comprobar() {  # comprobar <descripcion> <esperado> <obtenido>
  if [ "$2" = "$3" ]; then
    echo "  ok    $1"
  else
    echo "  FALLO $1"
    echo "        esperado: '$2'"
    echo "        obtenido: '$3'"
    fallos=$((fallos + 1))
  fi
}

# Un repositorio con las etiquetas que se le pidan, servido como remoto local.
crear_remoto() {  # crear_remoto <nombre del directorio> <etiqueta>...
  local destino="$TRABAJO/$1"; shift
  mkdir -p "$destino"
  git -C "$destino" init --quiet
  echo "contenido" > "$destino/archivo.txt"
  git -C "$destino" add -A
  git -C "$destino" -c user.email=p@p -c user.name=p commit --quiet -m inicial
  for etiqueta in "$@"; do
    git -C "$destino" tag "$etiqueta"
  done
  printf '%s' "$destino"
}

# ── las dos formas, cada una en su repositorio ──────────────────────────────────────────────
raiz="$(crear_remoto un-plugin "v${VERSION}")"
comprobar "un plugin en la raiz resuelve a vX.Y.Z" \
  "v${VERSION}" "$(etiqueta_publicada "$raiz" "$NOMBRE" "$VERSION" || echo SIN_RESOLVER)"

anidado="$(crear_remoto varios-plugins "${NOMBRE}--v${VERSION}")"
comprobar "un plugin anidado resuelve a <nombre>--vX.Y.Z" \
  "${NOMBRE}--v${VERSION}" "$(etiqueta_publicada "$anidado" "$NOMBRE" "$VERSION" || echo SIN_RESOLVER)"

# ── la forma por plugin gana cuando conviven ────────────────────────────────────────────────
# Se mide porque el estandar TIENE las dos: `v0.1.0` de cuando era un plugin en la raiz, y la nueva
# por plugin. Resolver a la vieja instalaria el validador de una version anterior sin avisar.
ambas="$(crear_remoto conviven "v${VERSION}" "${NOMBRE}--v${VERSION}")"
comprobar "con las dos etiquetas gana la del plugin" \
  "${NOMBRE}--v${VERSION}" "$(etiqueta_publicada "$ambas" "$NOMBRE" "$VERSION" || echo SIN_RESOLVER)"

# ── lo que NO debe resolver ─────────────────────────────────────────────────────────────────
# Sin etiqueta no se inventa ninguna: el llamador tiene que poder dar un error con contexto en vez
# de que `pip` falle con un mensaje de git que nadie sabe interpretar.
sin="$(crear_remoto sin-etiquetas)"
if etiqueta_publicada "$sin" "$NOMBRE" "$VERSION" >/dev/null 2>&1; then
  echo "  FALLO un repositorio sin etiquetas no debe resolver ninguna"
  fallos=$((fallos + 1))
else
  echo "  ok    un repositorio sin la version no resuelve"
fi

# Una version distinta tampoco: `v0.1.0` no sirve para pedir la 0.2.0.
if etiqueta_publicada "$raiz" "$NOMBRE" "9.9.9" >/dev/null 2>&1; then
  echo "  FALLO una version que no existe no debe resolver a otra"
  fallos=$((fallos + 1))
else
  echo "  ok    una version inexistente no resuelve a otra"
fi

echo
if [ "$fallos" -ne 0 ]; then
  echo "resolucion de etiqueta: $fallos propiedad(es) rota(s)" >&2
  exit 1
fi
echo "resolucion de etiqueta: 5 propiedades comprobadas"
