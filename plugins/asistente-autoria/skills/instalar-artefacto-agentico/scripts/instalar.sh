#!/usr/bin/env bash
# Instala el artefacto YA VERIFICADO, con el alcance elegido de forma explicita.
#
# EL COMPROBANTE ES OBLIGATORIO. Si no existe el que escribe verificar-paquete.sh, este script se
# niega: el orden del que depende todo el skill -- descargar, verificar, instalar -- no puede quedar
# a merced de que alguien se salte un paso.
#
# EL ALCANCE NO SE ELIGE EN SILENCIO. `gh skill install` usa `project` por defecto, y `project` deja
# el archivo DENTRO del repositorio del consumidor, asi que afecta a todo el equipo; `user` va al
# home y solo afecta a quien instala. Aqui se pasa siempre. Los plugins de Copilot no tienen
# alcance de proyecto: son siempre de usuario.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly USO="instalar.sh <alcance:project|user> <directorio-verificado> <install_hint...>"

alcance="${1:-}"
directorio="${2:-}"
exigir_argumento "$alcance" "alcance" "$USO"
exigir_argumento "$directorio" "directorio-verificado" "$USO"
shift 2
if [ "$#" -eq 0 ]; then
  abortar "falta el install_hint de la ficha. uso: $USO"
fi

case "$alcance" in
  "$ALCANCE_PROYECTO"|"$ALCANCE_USUARIO") ;;
  *) abortar "alcance invalido: $alcance (validos: $ALCANCE_PROYECTO, $ALCANCE_USUARIO)" ;;
esac

comprobante="$directorio/$NOMBRE_COMPROBANTE"
if [ ! -f "$comprobante" ]; then
  echo "No encuentro el comprobante de verificacion en $comprobante." >&2
  echo "Ejecuta primero verificar-paquete.sh: instalar sin verificar es exactamente lo que" >&2
  echo "este skill existe para evitar." >&2
  exit 1
fi

# EL COMMIT DEL COMPROBANTE TIENE QUE SER EL QUE EL MARKETPLACE VA A INSTALAR.
#
# Lo verificado es un .tar.gz; lo instalado es un clon del repositorio en el commit que el MARKETPLACE
# declara. `verificar-paquete.sh` ya ata la atestacion a un commit; aqui se comprueba la otra mitad:
# que ese commit sea el que el marketplace apunta. Sin esto, una ficha de Port desincronizada del
# marketplace dejaria verificar un contenido e instalar otro sin que nada avisara.
#
# Solo aplica a la via del MARKETPLACE -- `plugin install <nombre>@<marketplace>` --. Un artefacto que
# se instala por su canal propio no resuelve contra el marketplace y no hay entrada que comparar.
commit_verificado="$(sed -n 's/^commit_atestado=//p' "$comprobante" | head -1)"
nombre_en_marketplace=""
for argumento in "$@"; do
  case "$argumento" in
    *"@$MARKETPLACE") nombre_en_marketplace="${argumento%"@$MARKETPLACE"}" ;;
  esac
done

if [ -n "$nombre_en_marketplace" ]; then
  if [ -z "$commit_verificado" ]; then
    abortar "el comprobante no trae commit_atestado: vuelve a ejecutar verificar-paquete.sh"
  fi
  if ! commit_en_marketplace="$(commit_que_el_marketplace_instalaria "$nombre_en_marketplace")"; then
    # NO SE PUDO LEER EL MARKETPLACE. Se avisa y se sigue: la atestacion ya ato el paquete a un
    # commit, asi que la garantia principal no depende de esta consulta. Negarse aqui convertiria un
    # fallo de red en un bloqueo, y quien lo sufriera acabaria saltandose el skill entero.
    echo "aviso: no se pudo leer el marketplace ($REPO_MARKETPLACE); no se comparo el commit." >&2
    echo "aviso: la atestacion SI se verifico. Reintenta con red para la comprobacion completa." >&2
  elif [ -z "$commit_en_marketplace" ]; then
    # EL MARKETPLACE SE LEYO Y NO LISTA EL ARTEFACTO, que no es lo mismo que no poder leerlo. Un
    # artefacto ausente del marketplace no esta distribuido: esta en Conforme -- publicado pero no
    # promocionado -- o Suspendido. En los dos casos instalarlo se salta la decision del gobierno.
    echo "El marketplace NO lista '$nombre_en_marketplace'." >&2
    echo "Puede seguir estando PUBLICADO y ser verificable: publicar y distribuir son dos cosas" >&2
    echo "distintas. Si el estandar promociona al certificar, un artefacto Conforme queda fuera del" >&2
    echo "marketplace a proposito hasta que supere su evaluacion." >&2
    echo "Un artefacto ausente del marketplace no esta distribuido: o no ha sido certificado, o fue" >&2
    echo "suspendido. Consulta su ficha de Port antes de instalarlo." >&2
    abortar "artefacto ausente del marketplace"
  elif [ "$commit_en_marketplace" != "$commit_verificado" ]; then
    echo "El marketplace instalaria un commit DISTINTO del verificado." >&2
    echo "  verificado (atestacion):  $commit_verificado" >&2
    echo "  marketplace instalaria:   $commit_en_marketplace" >&2
    echo "Instalar ahora seria instalar contenido que nadie verifico." >&2
    abortar "el commit del marketplace no coincide con el verificado"
  else
    echo "Commit atado: el marketplace instala $commit_verificado, que es el atestado."
  fi
fi

comando=("$@")
if [ "${comando[0]}" = "copilot" ] && [ "$alcance" = "$ALCANCE_PROYECTO" ]; then
  abortar "copilot plugin install es SIEMPRE de alcance de usuario: no hay alcance de proyecto"
fi
if [ "${comando[0]}" = "gh" ]; then
  case " ${comando[*]} " in
    *" --scope "*) ;;
    *) comando+=(--scope "$alcance") ;;
  esac
fi

echo "Instalando con el comprobante de $comprobante"
printf 'comando:'
printf ' %q' "${comando[@]}"
printf '\n'
if ! salida="$("${comando[@]}" 2>&1)"; then
  traducir_fallo "$salida" >&2
  abortar "la instalacion fallo"
fi
echo "$salida"
echo "Instalado con alcance $alcance."
