#!/usr/bin/env bash
# Genera el esqueleto de un artefacto HEREDANDO lo que ya esta declarado.
#
# QUE HEREDA Y POR QUE. El `id`, el equipo dueno y el contacto salen del manifiesto y del
# GOVERNANCE.json, no se teclean. Medido en el activo del cliente: los campos que se copian a mano
# divergen -- distinto equipo en artefactos del mismo dominio, contactos que ya no existen --. Lo
# unico que queda por escribir es lo que ningun script puede deducir: la `description`.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly TIPOS_SOPORTADOS="skill agent prompt"

tipo="${1:-}"
nombre="${2:-}"
if [ -z "$tipo" ] || [ -z "$nombre" ]; then
  abortar "uso: generar.sh <tipo> <nombre>   (tipos: $TIPOS_SOPORTADOS)"
fi
case " $TIPOS_SOPORTADOS " in
  *" $tipo "*) ;;
  *) abortar "tipo no soportado: $tipo (soportados: $TIPOS_SOPORTADOS)" ;;
esac
# El `name` de un skill debe coincidir con su directorio: se valida antes de crear nada.
if ! printf '%s' "$nombre" | grep -Eq '^[a-z0-9]+(-[a-z0-9]+)*$'; then
  abortar "el nombre debe ser minusculas, digitos y guiones simples: $nombre"
fi

raiz="$(raiz_del_plugin)" || abortar "no estoy dentro de un repositorio con $RUTA_MANIFIESTO"
skill="$(raiz_del_skill)"
id_plugin="$(campo_del_manifiesto "$raiz/$RUTA_MANIFIESTO" name)"

# El dueno sale del gobierno del repositorio si existe; si no, queda por rellenar y el gate lo dira.
equipo="EQUIPO"; contacto="CONTACTO"
if [ -f "$raiz/GOVERNANCE.json" ]; then
  equipo="$(campo_del_dueno "$raiz/GOVERNANCE.json" team)"
  contacto="$(campo_del_dueno "$raiz/GOVERNANCE.json" contact)"
fi

case "$tipo" in
  skill)  destino="$raiz/skills/$nombre/SKILL.md"
          plantilla="$skill/assets/skill/SKILL.md" ;;
  agent)  destino="$raiz/agents/$nombre.agent.md"
          plantilla="$skill/assets/agent/agent.md" ;;
  prompt) destino="$raiz/commands/$nombre.prompt.md"
          plantilla="$skill/assets/prompt/prompt.md" ;;
esac

[ -e "$destino" ] && abortar "ya existe: $destino"
mkdir -p "$(dirname "$destino")"
sed -e "s/NOMBRE/$nombre/g" \
    -e "s/ID_DEL_PLUGIN/$id_plugin/g" \
    -e "s/EQUIPO/$equipo/g" \
    -e "s/CONTACTO/$contacto/g" \
    "$plantilla" > "$destino"

echo "Creado: ${destino#"$raiz"/}"
echo
echo "Falta lo que solo tu sabes: la description y el cuerpo. Todo lo marcado PENDIENTE."
echo "Y acuerdate de subir el contador de este tipo en GOVERNANCE.json: el gate compara"
echo "lo declarado con el arbol real."
