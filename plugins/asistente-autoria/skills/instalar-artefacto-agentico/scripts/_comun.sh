#!/usr/bin/env bash
# Lo que comparten los scripts de instalacion. Se incluye con `source`, no se ejecuta.
#
# UNA SOLA FUENTE PARA EL FIRMANTE Y PARA LOS FALLOS CONOCIDOS. El `--signer-repo` y la traduccion
# de los tres errores opacos aparecen en mas de un script; repetidos, una correccion se olvidaria
# en alguno de ellos.
set -euo pipefail

# El paquete sale del repositorio del dominio, pero lo FIRMA el workflow reutilizable del estandar.
# Sin este dato `gh attestation verify` falla contra el emisor y su mensaje no nombra al firmante.
REPO_FIRMANTE="Banca-Copilot-demo/estandar-agentico"

# El repositorio del CATALOGO instalable, y el archivo que el cliente resuelve al instalar. Se
# consulta para comprobar que el commit que el catalogo va a instalar es el que quedo atestado: sin
# esa comparacion, la verificacion demuestra menos de lo que parece -- se verifica un paquete y se
# instala un clon del repositorio, y nada ata las dos mitades --.
REPO_CATALOGO="Banca-Copilot-demo/marketplace"
RUTA_CATALOGO=".github/plugin/marketplace.json"

# El nombre con el que el catalogo se registra en el cliente. Es el sufijo de `<plugin>@<catalogo>`
# que trae el install_hint de la ficha, y lo que permite distinguir una instalacion POR CATALOGO
# -- comparable contra el commit atestado -- de una por canal propio, que no resuelve contra el.
CATALOGO="agentico"

# Estados de la ficha de Port que cambian lo que se puede hacer con el artefacto.
ESTADO_DEPRECADO="deprecated"
ESTADO_RETIRADO="retired"

# Alcances de instalacion. `proyecto` deja el artefacto DENTRO del repositorio del consumidor.
ALCANCE_PROYECTO="project"
ALCANCE_USUARIO="user"

NOMBRE_COMPROBANTE="atestacion-verificada.txt"

abortar() {
  echo "error: $*" >&2
  exit 1
}

# El commit que el CATALOGO instalaria para un plugin, o vacio si el catalogo no lo lista.
#
# Devuelve por SALIDA el commit y por CODIGO si el catalogo se pudo leer, porque los dos fallos
# posibles no son el mismo y quien llama tiene que poder distinguirlos:
#   codigo 2  -> no se pudo LEER el catalogo (red, credencial): la garantia de la atestacion sigue
#                en pie, asi que no es motivo para negarse a instalar.
#   salida ""  -> el catalogo se leyo y NO lista el plugin: eso SI es motivo para negarse. Un
#                artefacto ausente del catalogo esta en Conforme o Suspendido, y ninguno de los dos
#                se distribuye.
commit_que_el_catalogo_instalaria() {  # commit_que_el_catalogo_instalaria <nombre del plugin>
  local nombre="$1" catalogo
  catalogo="$(gh api "repos/$REPO_CATALOGO/contents/$RUTA_CATALOGO" \
    -H "Accept: application/vnd.github.raw" 2>/dev/null)" || return 2
  [ -n "$catalogo" ] || return 2
  printf '%s' "$catalogo" \
    | jq -r --arg n "$nombre" '[.plugins[]? | select(.name == $n) | .source.sha // ""] | first // ""'
}

exigir_argumento() {  # exigir_argumento <valor> <nombre> <linea de uso>
  [ -n "$1" ] || abortar "falta <$2>. uso: $3"
}

# Traduce la salida de gh o de copilot a una frase que diga QUE hacer. Los tres casos estan
# medidos: ninguno de los mensajes originales nombra su causa real.
traducir_fallo() {  # traducir_fallo <texto del fallo>
  local texto="$1"
  case "$texto" in
    *strictKnownMarketplaces*)
      echo "Rechazo por POLITICA administrada de la organizacion (strictKnownMarketplaces): el"
      echo "marketplace de este artefacto no esta en la lista permitida. El mensaje original no"
      echo "dice que sea una politica. No se arregla en tu maquina: pidelo a quien administra la"
      echo "organizacion." ;;
    *'verifying with issuer'*|*sigstore.dev*)
      echo "Falta --signer-repo $REPO_FIRMANTE. El paquete sale del repositorio del dominio pero"
      echo "lo firma el workflow reutilizable del estandar, y el mensaje del emisor no nombra al"
      echo "firmante. Repite la verificacion con esa opcion." ;;
    *sha256*|*SHA256*)
      echo "El sha256 del archivo descargado NO coincide con el sha256_archivo de la ficha de"
      echo "Port. El contenido no es el que se sello: no lo instales ni lo copies al repositorio."
      echo "Confirma que el sha de la ficha es el que descargaste y avisa al equipo dueno." ;;
    *)
      echo "Fallo no catalogado. Copia el texto tal cual al equipo dueno del artefacto:"
      echo "$texto" ;;
  esac
}
