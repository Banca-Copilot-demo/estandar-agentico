#!/usr/bin/env bash
# Recorre el camino de INSTALACION completo contra lo que esta publicado de verdad.
#
# QUE LO HACE UTIL: no mockea nada. Lee la ficha de Port real, descarga el release real y
# verifica su atestacion real. Y comprueba los casos NEGATIVOS, que son los que de verdad importan:
# un paquete manipulado no debe verificar, un sha256 que no coincide no debe aceptarse, y sin
# comprobante de verificacion no debe instalarse nada.
#
# POR QUE VIVE AQUI Y NO EN LA MAQUINA DE ALGUIEN: un recorrido que solo corre en un portatil
# deja de correr el dia que ese portatil no esta. Corre en CI, con credenciales de la organizacion.
set -uo pipefail

readonly AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly RAIZ="$AQUI/.."

# EL SKILL SE BUSCA, NO SE ESCRIBE A MANO, y esto es un defecto MEDIDO. La ruta estaba fija en
# `../skills/instalar-artefacto-agentico/scripts`, y al reestructurar el repositorio en `plugins/` el
# skill se mudo a `plugins/asistente-autoria/skills/...`. Consecuencia: este recorrido llevaba TRES
# NOCHES en rojo -- paso hasta el 21-ago y fallo el 22, el 23 y al dispararlo a mano -- y cada corrida
# reportaba CUATRO fallos confusos («la atestacion no verifica», «el sha256 no coincide») en vez de la
# unica causa real, que era que el directorio no existia. Un fallo mal atribuido es peor que ninguno:
# manda a investigar la atestacion cuando el problema era una ruta.
#
# El comodin sobre `plugins/*` sobrevive a que el plugin se renombre, que es justo lo que paso. Y si
# no aparece exactamente UNO, se aborta con el motivo: seguir con una ruta que no existe es lo que
# produjo los cuatro mensajes enganosos.
_encontrados=("$RAIZ"/plugins/*/skills/instalar-artefacto-agentico/scripts)
if [ ! -d "${_encontrados[0]:-}" ]; then
  echo "FALLO no encuentro los scripts del skill de instalacion bajo $RAIZ/plugins/*/skills/instalar-artefacto-agentico/scripts" >&2
  echo "      si el skill se movio o se renombro, este recorrido no puede comprobar nada: se aborta en vez de reportar fallos que no son." >&2
  exit 1
fi
if [ "${#_encontrados[@]}" -ne 1 ]; then
  echo "FALLO hay ${#_encontrados[@]} skills de instalacion y no se cual usar: ${_encontrados[*]}" >&2
  exit 1
fi
readonly SKILL="${_encontrados[0]}"
readonly FIRMANTE="Banca-Copilot-demo/estandar-agentico"
readonly SHA256_IMPOSIBLE="0000000000000000000000000000000000000000000000000000000000000000"

readonly ID_SKILL="${1:?falta el id del artefacto de tipo skill}"
readonly ID_PROMPT="${2:?falta el id del artefacto de tipo prompt}"
readonly NOMBRE_SKILL="${3:?falta el nombre del skill tal como lo pide gh skill install}"

trabajo="$(mktemp -d)"
trap 'rm -rf "$trabajo"' EXIT

fallos=0
fase() { echo; echo "--- $* ---"; }
comprobar() {  # comprobar <descripcion> <0 si paso>
  if [ "$2" -eq 0 ]; then
    echo "  ok    $1"
  else
    echo "  FALLO $1"
    fallos=$((fallos + 1))
  fi
}

fase "1 · la ficha, de Port real"
python3 "$AQUI/leer_ficha.py" "$ID_SKILL" > "$trabajo/skill.env"
comprobar "se lee la ficha del skill" $?
# shellcheck disable=SC1090
source "$trabajo/skill.env"
echo "  status=$FICHA_STATUS ref=$FICHA_REF sha=${FICHA_SHA:0:12} marketplace=$FICHA_MARKETPLACE"

fase "2 · el estado permite continuar"
bash "$SKILL/comprobar-estado.sh" "$FICHA_STATUS" >/dev/null 2>&1
comprobar "el estado $FICHA_STATUS deja pasar" $?

fase "3 · descarga y verificacion de la atestacion"
bash "$SKILL/verificar-paquete.sh" "$FICHA_REPO" "$FICHA_REF" "$FICHA_SHA" \
  "$trabajo/paquete" >/dev/null 2>&1
comprobar "la atestacion verifica contra el firmante del estandar" $?
[ -f "$trabajo/paquete/atestacion-verificada.txt" ]
comprobar "queda el comprobante de verificacion" $?

fase "3b · caso negativo: paquete manipulado"
printf 'byte de mas' >> "$trabajo/paquete/"*.tar.gz
if gh attestation verify "$trabajo/paquete/"*.tar.gz --repo "$FICHA_REPO" \
     --signer-repo "$FIRMANTE" >/dev/null 2>&1; then
  comprobar "un paquete manipulado NO verifica" 1
else
  comprobar "un paquete manipulado NO verifica" 0
fi

fase "4 · sin comprobante no se instala"
mkdir -p "$trabajo/sin-comprobante"
sin_comprobante=("$SKILL/instalar.sh" user "$trabajo/sin-comprobante" gh skill install x)
if bash "${sin_comprobante[@]}" >/dev/null 2>&1; then
  comprobar "sin comprobante NO instala" 1
else
  comprobar "sin comprobante NO instala" 0
fi

fase "4 · instalacion real en un repositorio de prueba"
mkdir -p "$trabajo/consumidor"
( cd "$trabajo/consumidor" && git init -q . \
  && gh skill install "$FICHA_REPO" "$NOMBRE_SKILL@$FICHA_REF" \
       --agent github-copilot --scope project --force >/dev/null 2>&1 )
[ -f "$trabajo/consumidor/.agents/skills/$NOMBRE_SKILL/SKILL.md" ]
comprobar "el skill aterriza en .agents/skills del repositorio" $?

fase "4 · el prompt, que no viaja en el plugin"
python3 "$AQUI/leer_ficha.py" "$ID_PROMPT" > "$trabajo/prompt.env"
# shellcheck disable=SC1090
source "$trabajo/prompt.env"
bash "$SKILL/verificar-archivo.sh" "$FICHA_REPO" "$FICHA_SHA" "$FICHA_RUTA" \
  "$FICHA_SHA256" "$trabajo/prompt" >/dev/null 2>&1
comprobar "el sha256 del prompt coincide con lo firmado" $?
if bash "$SKILL/verificar-archivo.sh" "$FICHA_REPO" "$FICHA_SHA" "$FICHA_RUTA" \
     "$SHA256_IMPOSIBLE" "$trabajo/malo" >/dev/null 2>&1; then
  comprobar "un sha256 que no coincide NO se acepta" 1
else
  comprobar "un sha256 que no coincide NO se acepta" 0
fi
[ ! -f "$trabajo/malo/$(basename "$FICHA_RUTA")" ]
comprobar "el archivo rechazado se borra" $?

echo
if [ "$fallos" -ne 0 ]; then
  echo "camino de instalacion: $fallos comprobacion(es) rota(s)" >&2
  exit 1
fi
echo "camino de instalacion: 10 comprobaciones, todas correctas"
