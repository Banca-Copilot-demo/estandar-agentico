#!/usr/bin/env bash
# Prueba de regresion del empaquetado determinista (T3, T6).
#
# El defecto que cubre: un empaquetado que cambia de digest cuando cambia el reloj o el orden de
# lectura del sistema de archivos. Se medio en la fase 4: sin `--mtime`, el mismo contenido daba
# un digest distinto en cada ejecucion, y la atestacion no habria sido verificable por nadie.
#
# Comprueba diez propiedades, cada una con su mensaje: si falla, el mensaje dice cual se rompio.
# Las cuatro ultimas cubren los repositorios que alojan VARIOS plugins: sin acotar el empaquetado a
# la subruta, los paquetes de dos plugins vecinos salian con el MISMO digest.
set -euo pipefail

readonly RAIZ="${1:?falta la raiz del repositorio a empaquetar}"
readonly AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TRABAJO="$(mktemp -d)"
trap 'rm -rf "$TRABAJO"' EXIT

fallos=0
comprobar() {  # comprobar <descripcion> <esperado> <obtenido>
  if [ "$2" = "$3" ]; then
    echo "  ok    $1"
  else
    echo "  FALLO $1"
    echo "        esperado: $2"
    echo "        obtenido: $3"
    fallos=$((fallos + 1))
  fi
}

primero="$(bash "$AQUI/empaquetar.sh" "$RAIZ" "$TRABAJO/a.tar.gz")"
segundo="$(bash "$AQUI/empaquetar.sh" "$RAIZ" "$TRABAJO/b.tar.gz")"
comprobar "dos empaquetados seguidos dan el mismo digest" "$primero" "$segundo"

# Toca las fechas de todo lo versionado: el contenido no cambio, el digest no debe cambiar.
git -C "$RAIZ" ls-files -z | tr '\0' '\n' | while read -r archivo; do
  touch -d '2001-02-03 04:05:06' "$RAIZ/$archivo"
done
tras_tocar="$(bash "$AQUI/empaquetar.sh" "$RAIZ" "$TRABAJO/c.tar.gz")"
comprobar "cambiar las fechas de modificacion no cambia el digest" "$primero" "$tras_tocar"

# Cambiar un byte del contenido SI debe cambiar el digest: si no, el sello no probaria nada.
copia="$TRABAJO/copia"
git -C "$RAIZ" ls-files -z | tr '\0' '\n' > "$TRABAJO/versionados"
git clone --quiet --no-hardlinks "$RAIZ" "$copia"
# NO se muta `.gitattributes`: es el archivo que decide la normalizacion de finales de linea,
# de la que depende el digest. Al tocarlo, el digest cambiaria por la normalizacion y no por
# el byte anadido, y la prueba pasaria por el motivo equivocado. Medido: en un repositorio
# donde `.gitattributes` ordena primero, git avisaba «is not a valid attribute name».
primer_archivo="$(grep -v '^\.git' "$TRABAJO/versionados" | head -1)"
if [ -z "$primer_archivo" ]; then
  echo "probar-empaquetado: el repositorio no tiene ningun archivo mutable" >&2
  exit 1
fi
printf '\n<byte de mas>\n' >> "$copia/$primer_archivo"
git -C "$copia" add -A && git -C "$copia" -c user.email=p@p -c user.name=p commit --quiet -m x
tras_editar="$(bash "$AQUI/empaquetar.sh" "$copia" "$TRABAJO/d.tar.gz")"
if [ "$primero" = "$tras_editar" ]; then
  echo "  FALLO editar el contenido debe cambiar el digest (no cambio)"
  fallos=$((fallos + 1))
else
  echo "  ok    editar el contenido cambia el digest"
fi

# ── UN PLUGIN POR PAQUETE ────────────────────────────────────────────────────────────────────
# MEDIDO: la primera version de esta funcionalidad no acotaba nada y los dos plugins de un
# repositorio producian paquetes IDENTICOS. El digest dejaba de significar «este plugin».
multi="$TRABAJO/multi"
mkdir -p "$multi/plugins/uno/skills/a" "$multi/plugins/dos/skills/b"
printf '{"name":"uno","version":"1.0.0"}' > "$multi/plugins/uno/plugin.json"
printf '{"name":"dos","version":"1.0.0"}' > "$multi/plugins/dos/plugin.json"
printf -- '---
name: a
---
' > "$multi/plugins/uno/skills/a/SKILL.md"
printf -- '---
name: b
---
' > "$multi/plugins/dos/skills/b/SKILL.md"
git -C "$multi" init --quiet
git -C "$multi" add -A
git -C "$multi" -c user.email=p@p -c user.name=p commit --quiet -m x

d_uno="$(bash "$AQUI/empaquetar.sh" "$multi" "$TRABAJO/uno.tar.gz" plugins/uno)"
d_dos="$(bash "$AQUI/empaquetar.sh" "$multi" "$TRABAJO/dos.tar.gz" plugins/dos)"
if [ "$d_uno" = "$d_dos" ]; then
  echo "  FALLO dos plugins del mismo repo deben dar digests distintos (dieron el mismo)"
  fallos=$((fallos + 1))
else
  echo "  ok    dos plugins del mismo repo dan digests distintos"
fi

if tar -tzf "$TRABAJO/uno.tar.gz" | grep -q '^plugins/'; then
  echo "  FALLO el paquete debe extraerse con el manifiesto en su RAIZ, sin el prefijo plugins/"
  fallos=$((fallos + 1))
else
  echo "  ok    el paquete se extrae con el manifiesto en su raiz"
fi

if tar -tzf "$TRABAJO/uno.tar.gz" | grep -q 'skills/b'; then
  echo "  FALLO el paquete de un plugin no debe contener artefactos de su vecino"
  fallos=$((fallos + 1))
else
  echo "  ok    el paquete de un plugin no arrastra a su vecino"
fi

if bash "$AQUI/empaquetar.sh" "$multi" "$TRABAJO/no.tar.gz" plugins/inexistente >/dev/null 2>&1; then
  echo "  FALLO una subruta inexistente debe abortar, no producir un paquete vacio"
  fallos=$((fallos + 1))
else
  echo "  ok    una subruta inexistente aborta"
fi

# EL GOBIERNO NO SE DISTRIBUYE. Ningun cliente lee `GOVERNANCE.json`: lo lee el gate, y lo lee del
# repositorio en el pull request. Dentro de lo que una persona instala es ruido -- aparece en su
# carpeta, no le dice nada y no hace nada --. La procedencia sigue viajando en la atestacion, que
# esta firmada y FUERA del artefacto, que es donde una prueba de origen vale algo.
bash "$AQUI/empaquetar.sh" "$multi" "$TRABAJO/gob.tar.gz" plugins/uno >/dev/null
if tar -tzf "$TRABAJO/gob.tar.gz" | grep -q "GOVERNANCE.json"; then
  echo "  FALLO el paquete de un plugin ANIDADO no debe llevar GOVERNANCE.json"
  fallos=$((fallos + 1))
else
  echo "  ok    el paquete de un plugin anidado no lleva el gobierno"
fi

bash "$AQUI/empaquetar.sh" "$RAIZ" "$TRABAJO/gob-raiz.tar.gz" >/dev/null
if tar -tzf "$TRABAJO/gob-raiz.tar.gz" | grep -q "GOVERNANCE.json"; then
  echo "  FALLO el paquete de un plugin en la RAIZ tampoco debe llevar GOVERNANCE.json"
  fallos=$((fallos + 1))
else
  echo "  ok    el paquete de un plugin en la raiz tampoco lleva el gobierno"
fi

# Y lo que NO debe desaparecer con el: el manifiesto es lo que hace que el cliente lo reconozca.
# Se aceptan sus DOS ubicaciones -- `plugin.json` en la raiz del plugin y `.claude-plugin/plugin.json`
# --, porque las dos son validas y este fixture usa la primera; exigir una sola hacia que la prueba
# fallara por la forma del fixture y no por el defecto que busca.
if tar -tzf "$TRABAJO/gob.tar.gz" | grep -Eq '^(\.claude-plugin/)?plugin\.json$'; then
  echo "  ok    el manifiesto sigue en la raiz del paquete"
else
  echo "  FALLO excluir el gobierno se llevo por delante el manifiesto"
  tar -tzf "$TRABAJO/gob.tar.gz" | sed 's|^|        contiene: |'
  fallos=$((fallos + 1))
fi

echo
if [ "$fallos" -ne 0 ]; then
  echo "empaquetado: $fallos propiedad(es) rota(s)" >&2
  exit 1
fi
echo "empaquetado determinista: 10 propiedades comprobadas | digest $primero"
