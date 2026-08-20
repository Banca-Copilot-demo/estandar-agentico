#!/usr/bin/env bash
# Imprime a QUIEN se le pide la credencial, ANTES de que el cliente muestre su prompt.
#
# EL HUECO QUE CIERRA. Un artefacto `mcp` viaja sin secreto: el gate rechaza cualquier token
# literal, asi que solo lleva una referencia. Al instalarlo, el cliente pide el valor -- y el
# desarrollador se queda ahi. El `owner_team` de la ficha es quien PUBLICO el artefacto; el token lo
# da quien ADMINISTRA el servicio. Son dos duenos distintos.
#
# POR QUE ESTE SCRIPT Y NO UN CAMPO QUE EL CLIENTE MUESTRE. No existe convencion en la industria:
# el `server.json` del registro oficial de MCP declara que una credencial es secreta, pero no quien
# la concede. Asi que ningun cliente va a renderizar este dato, y el unico momento util para
# ensenarlo es justo ANTES del prompt.
#
# EL ORDEN ES EL PUNTO. Despues del prompt no sirve: el desarrollador ya esta bloqueado.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly MECANISMO_SIN_SECRETO="oauth"

mecanismo="${1:-}"
dueno="${2:-}"
donde_se_pide="${3:-}"
entitlement="${4:-}"

if [ -z "$mecanismo" ]; then
  abortar "uso: decir-quien-da-la-credencial.sh <mecanismo> [dueno] [url] [entitlement]"
fi

if [ "$mecanismo" = "$MECANISMO_SIN_SECRETO" ]; then
  echo "Este mcp usa $MECANISMO_SIN_SECRETO: te autenticas con TU PROPIA identidad."
  echo "No hay ningun secreto que pedirle a nadie, y no se guarda nada en disco."
  exit 0
fi

if [ -z "$dueno" ] || [ -z "$donde_se_pide" ]; then
  # No se aborta: el artefacto ya esta descargado y verificado, y el gate deberia haberlo impedido
  # en la publicacion. Lo que toca aqui es decir QUE falta, no bloquear al consumidor por un defecto
  # de la ficha que el no puede arreglar.
  echo "AVISO: la ficha no declara quien custodia esta credencial." >&2
  echo "  El cliente te va a pedir un token y no hay dato de a quien pedirselo." >&2
  echo "  Pidele al equipo dueno del artefacto que complete credentials.ownership." >&2
  exit 0
fi

echo "El cliente va a pedirte un token. ANTES de teclear nada:"
echo
echo "  Lo custodia:   $dueno"
echo "  Se solicita en: $donde_se_pide"
[ -n "$entitlement" ] && echo "  Pide el grupo:  $entitlement"
echo
echo "Ese equipo NO es el que publico el artefacto: administra el servicio."
