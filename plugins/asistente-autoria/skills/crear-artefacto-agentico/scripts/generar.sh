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

# `--unidad` publica el artefacto COMO SU PROPIA UNIDAD, con manifiesto propio, en vez de dentro del
# plugin que lo aloje.
#
# POR QUE HACE FALTA. Un artefacto suelto SIN manifiesto no entra al marketplace, y esta medido contra
# los dos clientes: con el contenido en otro repositorio -- que es la topologia real -- la
# instalacion falla con «No plugin.json found in repository». Sin entrada de marketplace, el ESTADO no
# lo gobierna: se instala igual este certificado, conforme o suspendido. Con unidad propia obtiene
# ademas version, etiqueta y digesto propios, en vez de compartirlos con todos los sueltos del
# repositorio -- donde tocar un prompt cambiaba el digesto del skill que nadie habia tocado --.
modo_unidad="no"
if [ "${1:-}" = "--unidad" ]; then
  modo_unidad="si"
  shift
fi

tipo="${1:-}"
nombre="${2:-}"
if [ -z "$tipo" ] || [ -z "$nombre" ]; then
  abortar "uso: generar.sh [--unidad] <tipo> <nombre>   (tipos: $TIPOS_SOPORTADOS)"
fi
case " $TIPOS_SOPORTADOS " in
  *" $tipo "*) ;;
  *) abortar "tipo no soportado: $tipo (soportados: $TIPOS_SOPORTADOS)" ;;
esac
# El `name` de un skill debe coincidir con su directorio: se valida antes de crear nada.
if ! printf '%s' "$nombre" | grep -Eq '^[a-z0-9]+(-[a-z0-9]+)*$'; then
  abortar "el nombre debe ser minusculas, digitos y guiones simples: $nombre"
fi

skill="$(raiz_del_skill)"
if [ "$modo_unidad" = "si" ]; then
  # La unidad se crea en la RAIZ DEL REPOSITORIO, no dentro de un plugin: es una unidad hermana.
  raiz="$(git rev-parse --show-toplevel 2>/dev/null)" \
    || abortar "--unidad necesita estar dentro de un repositorio git"
  # El gobierno de la raiz no gobierna a esta unidad: es de donde se COPIAN el dominio, el dueno y la
  # version del estandar al gobierno PROPIO que se genera abajo. Copiados quedan escritos y se
  # revisan; heredados en tiempo de validacion no los veia nadie.
  [ -f "$raiz/GOVERNANCE.json" ] \
    || abortar "--unidad necesita el GOVERNANCE.json de la raiz de donde copiar dominio y dueno"
  id_plugin="$(prefijo_del_dominio "$raiz/GOVERNANCE.json").$nombre"
else
  raiz="$(raiz_del_plugin)" || abortar "no estoy dentro de un repositorio con $RUTA_MANIFIESTO"
  id_plugin="$(campo_json "$raiz/$RUTA_MANIFIESTO" name)"
fi

# El dueno sale del gobierno del repositorio si existe; si no, queda por rellenar y el gate lo dira.
equipo="EQUIPO"; contacto="CONTACTO"
if [ -f "$raiz/GOVERNANCE.json" ]; then
  equipo="$(campo_del_dueno "$raiz/GOVERNANCE.json" team)"
  contacto="$(campo_del_dueno "$raiz/GOVERNANCE.json" contact)"
fi

# LA VERSION DEL ARTEFACTO ES LA DE SU UNIDAD, y el gate lo EXIGE. Con `--unidad` la unidad se crea
# aqui mismo, asi que arranca en `VERSION_DE_ARRANQUE`; dentro de un plugin existente se toma la suya,
# que es justo el caso donde divergian -- medido: un skill nacia en 0.1.0 dentro de un plugin que iba
# por 0.1.3, y nadie lo notaba porque los dos numeros se leen en sitios distintos.
if [ "$modo_unidad" = "si" ]; then
  version="$VERSION_DE_ARRANQUE"
else
  version="$(version_de_la_unidad "$raiz")"
  [ -n "$version" ] || abortar "la unidad $raiz no declara version: sin ella no se sabe con que numero nace el artefacto, y el gate exige que coincidan"
fi

# DONDE ATERRIZA CADA TIPO. Con `--unidad` el artefacto cuelga de un directorio propio que es la raiz
# del plugin, y dentro conserva la ruta que su cliente espera. El skill es el unico que NO se anida:
# un plugin de un solo skill puede llevar su `SKILL.md` en la raiz -- comprobado instalando en los
# dos clientes --, y entonces el nombre de invocacion sale del frontmatter, sin prefijo de plugin.
case "$tipo" in
  skill)  plantilla="$skill/assets/skill/SKILL.md"
          if [ "$modo_unidad" = "si" ]; then
            unidad="$raiz/skills/$nombre"; destino="$unidad/SKILL.md"
          else
            destino="$raiz/skills/$nombre/SKILL.md"
          fi ;;
  agent)  plantilla="$skill/assets/agent/agent.md"
          if [ "$modo_unidad" = "si" ]; then
            unidad="$raiz/agents/$nombre"; destino="$unidad/agents/$id_plugin.agent.md"
          else
            destino="$raiz/agents/$nombre.agent.md"
          fi ;;
  prompt) plantilla="$skill/assets/prompt/prompt.md"
          if [ "$modo_unidad" = "si" ]; then
            unidad="$raiz/commands/$nombre"; destino="$unidad/commands/$id_plugin.prompt.md"
          else
            destino="$raiz/commands/$nombre.prompt.md"
          fi ;;
esac

[ -e "$destino" ] && abortar "ya existe: $destino"
mkdir -p "$(dirname "$destino")"
sed -e "s/NOMBRE/$nombre/g" \
    -e "s/ID_DEL_PLUGIN/$id_plugin/g" \
    -e "s/EQUIPO/$equipo/g" \
    -e "s/CONTACTO/$contacto/g" \
    -e "s/VERSION_DE_LA_UNIDAD/$version/g" \
    "$plantilla" > "$destino"

echo "Creado: ${destino#"$raiz"/}"

if [ "$modo_unidad" = "si" ]; then
  escribir_manifiesto_de_unidad "$unidad/$RUTA_MANIFIESTO" "$id_plugin" \
    "PENDIENTE: la misma descripcion del artefacto." "$tipo"
  echo "Creado: ${unidad#"$raiz"/}/$RUTA_MANIFIESTO   (se publica como $id_plugin v0.1.0)"
  # EL GOBIERNO DE LA UNIDAD SE GENERA AQUI, y es lo que hace viable exigirlo. Sin generarlo, cada
  # suelto obligaria a escribir a mano un archivo con los mismos campos -- y ese coste fue justo el
  # argumento con el que el gate acabo heredando el gobierno de la raiz, con su dueno incluido.
  # EL ID DEL ARTEFACTO ES EL MISMO que la plantilla acaba de escribir en su frontmatter --
  # `ID_DEL_PLUGIN.NOMBRE` -- y se pasa en vez de recalcularse dentro: con la formula en dos sitios
  # acabarian divergiendo, y el gate lo veria como un id declarado que el arbol real no tiene.
  escribir_gobierno_de_unidad "$unidad/$RUTA_GOBIERNO" "$id_plugin" "$tipo" "$raiz/$RUTA_GOBIERNO" \
    "$id_plugin.$nombre"
  echo "Creado: ${unidad#"$raiz"/}/$RUTA_GOBIERNO   (dueno: $equipo)"
  echo
  echo "Falta lo que solo tu sabes: la description y el cuerpo. Todo lo marcado PENDIENTE."
  echo "La description va en DOS sitios y el gate comprueba que coincidan: el frontmatter del"
  echo "artefacto y el manifiesto de su unidad."
  echo
  echo "COMPRUEBA EL DUENO de ${unidad#"$raiz"/}/$RUTA_GOBIERNO. Se copio el de la raiz del"
  echo "repositorio para que arranques, pero esta unidad se publica sola: si quien la mantiene no"
  echo "es $equipo, corrigelo ahora -- es a ese equipo a quien se le pedira la aprobacion y a"
  echo "quien se le abrira el issue cuando el artefacto falle."
  echo
  echo "NO toques el inventario del GOVERNANCE.json de la raiz: esta unidad no forma parte del"
  echo "conjunto suelto y lleva el suyo."
  exit 0
fi

echo
echo "Falta lo que solo tu sabes: la description y el cuerpo. Todo lo marcado PENDIENTE."
echo "Y acuerdate de subir el contador de este tipo en GOVERNANCE.json: el gate compara"
echo "lo declarado con el arbol real."
