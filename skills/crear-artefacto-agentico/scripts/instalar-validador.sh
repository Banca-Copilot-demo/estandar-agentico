#!/usr/bin/env bash
# Instala el validador del estandar FIJADO A LA MISMA VERSION que este asistente.
#
# POR QUE NO VIAJA DENTRO DEL PAQUETE. El paquete publicado excluye `validador/` a proposito:
# incluir el codigo en cada release lo duplicaria con el repositorio que ya lo contiene. Se instala
# desde el repositorio del estandar, y la ETIQUETA garantiza el invariante que el estandar exige:
# el validador que juzga y los esqueletos que generan son de la MISMA version.
#
# EL ORIGEN NO ESTA CODIFICADO AQUI. Se deriva de `repository` y `version` del manifiesto, asi que
# funciona igual en la organizacion de la demo y en la del banco.
#
# SI EL REPOSITORIO DEL ESTANDAR ES PRIVADO, `pip` necesita las credenciales de git del
# desarrollador. Se resuelve una sola vez con `gh auth setup-git`, y el error lo recuerda.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_comun.sh"

readonly SUBDIRECTORIO="validador"
readonly MODULO="validador_agentico"
readonly PISTA_CREDENCIALES="si el repositorio del estandar es privado, configura las
  credenciales de git una sola vez con: gh auth setup-git"

raiz_skill="$(raiz_del_skill)"
# El manifiesto del plugin que contiene a este skill: skills/<nombre>/ -> raiz del plugin.
manifiesto="$raiz_skill/../../$RUTA_MANIFIESTO"
[ -f "$manifiesto" ] || abortar "no encuentro el manifiesto del plugin en $manifiesto"

version="$(campo_del_manifiesto "$manifiesto" version)"
repositorio="$(campo_del_manifiesto "$manifiesto" repository)"
[ -n "$version" ] || abortar 'el manifiesto no declara el campo version'
if [ -z "$repositorio" ]; then
  abortar 'el manifiesto no declara repository: sin el no se sabe de donde bajar el validador'
fi

origen="git+${repositorio}.git@v${version}#subdirectory=${SUBDIRECTORIO}"
echo "Instalando el validador del estandar, version v${version}"
echo "  desde ${origen}"

if ! pip install --quiet --upgrade "$origen"; then
  abortar "no se pudo instalar el validador desde ${origen}. ${PISTA_CREDENCIALES}"
fi

python -c "import ${MODULO}" || abortar "el validador se instalo pero no se puede importar"
echo "Listo. El gate local ya es el mismo que corre en CI."
