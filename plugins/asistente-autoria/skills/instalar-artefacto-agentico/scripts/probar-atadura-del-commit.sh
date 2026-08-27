#!/usr/bin/env bash
# Prueba de regresion de la ATADURA entre lo que se verifica y lo que se instala (T6).
#
# EL DEFECTO QUE FIJA, medido: lo que se VERIFICA es un `.tar.gz` y lo que se INSTALA es un CLON del
# repositorio en un commit -- el cliente no despliega el paquete --. Son objetos distintos, y nada
# comprobaba que fueran el mismo contenido: `verificar-paquete.sh` recibia el `sha` como ARGUMENTO y
# lo copiaba al comprobante sin contrastarlo, asi que el comprobante afirmaba algo que nadie habia
# verificado. Con un `sha` equivocado, la verificacion pasaba y se instalaba otro commit.
#
# ESTA PRUEBA SI USA LA RED, y conviene decirlo en vez de que alguien lo descubra cuando falle sin
# conexion: consulta el MARKETPLACE REAL con `gh`, asi que necesita credencial. Es una prueba de
# integracion, no unitaria, y por eso vive junto a los scripts y no en la suite rapida del dominio.
#
# Se hace asi a proposito: lo que se quiere fijar es que el marketplace publicado y el comprobante se
# comparan de verdad. Un doble del marketplace probaria la comparacion pero no que la consulta
# funcione -- y el defecto que motivo todo esto fue justamente un dato que nadie contrastaba con su
# fuente --. Lo unico que se prueba sin red es la distincion entre «marketplace ilegible» y
# «artefacto ausente»,
# que se comprueba apuntando a un repositorio inexistente.
#
# Lo que esta prueba NO cubre: la extraccion del commit desde la atestacion, que vive en
# `verificar-paquete.sh` y se comprueba ejecutandolo contra un release real.
set -euo pipefail

readonly AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly COMMIT_ATESTADO="0a864018b7d7997a3a3e60027b82cffb0091e0c0"
readonly COMMIT_DISTINTO="d4eaa980a4f9a9555f9314ba96815094518f3ba3"
readonly ESPERADO_BLOQUEA=1
readonly ESPERADO_CONTINUA=0

trabajo="$(mktemp -d)"
trap 'rm -rf "$trabajo"' EXIT

fallos=0

# Escribe un comprobante como el que deja `verificar-paquete.sh`.
escribir_comprobante() {  # escribir_comprobante <directorio> <commit_atestado>
  mkdir -p "$1"
  {
    echo "repo=Banca-Copilot-demo/agentes-sdlc"
    echo "ref=demo.sdlc.referencia--v0.1.2"
    echo "sha=$2"
    echo "commit_atestado=$2"
    echo "paquete=agentes-sdlc-demo.sdlc.referencia--v0.1.2.tar.gz"
    echo "signer_repo=Banca-Copilot-demo/estandar-agentico"
  } > "$1/atestacion-verificada.txt"
}

# El marketplace se sustituye por un DOBLE inyectado por entorno (T4): la prueba no toca la red ni
# parchea el modulo. `instalar.sh` lo consulta a traves de `commit_que_el_marketplace_instalaria`.
comprobar() {  # comprobar <descripcion> <esperado> <directorio> <nombre en el marketplace>
  local descripcion="$1" esperado="$2" directorio="$3" nombre="$4"
  local obtenido=0
  bash "$AQUI/instalar.sh" user "$directorio" echo copilot plugin install "$nombre@agentico" \
    >/dev/null 2>&1 || obtenido=$?
  if [ "$obtenido" = "$esperado" ]; then
    echo "  ok    $descripcion (codigo $obtenido)"
  else
    echo "  FALLO $descripcion: esperado $esperado, obtenido $obtenido"
    fallos=$((fallos + 1))
  fi
}

escribir_comprobante "$trabajo/correcto" "$COMMIT_ATESTADO"
escribir_comprobante "$trabajo/trucado" "$COMMIT_DISTINTO"

# Un comprobante SIN `commit_atestado` es el que dejaba la version anterior del script. Tiene que
# rechazarse en vez de instalarse sin comparar: si no, un comprobante viejo saltaria el control.
mkdir -p "$trabajo/sin-commit"
{
  echo "repo=Banca-Copilot-demo/agentes-sdlc"
  echo "sha=$COMMIT_ATESTADO"
} > "$trabajo/sin-commit/atestacion-verificada.txt"

comprobar "el commit del marketplace COINCIDE -> instala" \
  "$ESPERADO_CONTINUA" "$trabajo/correcto" demo.sdlc.referencia
comprobar "el commit del marketplace DIFIERE -> bloquea" \
  "$ESPERADO_BLOQUEA" "$trabajo/trucado" demo.sdlc.referencia
comprobar "artefacto AUSENTE del marketplace -> bloquea" \
  "$ESPERADO_BLOQUEA" "$trabajo/correcto" demo.sdlc.no-esta-en-el-marketplace
comprobar "comprobante SIN commit_atestado -> bloquea" \
  "$ESPERADO_BLOQUEA" "$trabajo/sin-commit" demo.sdlc.referencia

# Un marketplace ILEGIBLE no es lo mismo que un artefacto ausente, y confundirlos seria fail-open: un
# fallo de red haria pasar por «no distribuido» algo que si lo esta, o al reves.
codigo_ilegible=0
salida_ilegible="$(
  source "$AQUI/_comun.sh"
  REPO_MARKETPLACE="Banca-Copilot-demo/repositorio-que-no-existe-xyz"
  commit_que_el_marketplace_instalaria demo.sdlc.referencia
)" || codigo_ilegible=$?
if [ "$codigo_ilegible" -eq 2 ] && [ -z "$salida_ilegible" ]; then
  echo "  ok    marketplace ILEGIBLE se distingue de artefacto ausente (codigo 2)"
else
  echo "  FALLO marketplace ilegible: esperado codigo 2 y salida vacia; obtenido $codigo_ilegible '$salida_ilegible'"
  fallos=$((fallos + 1))
fi

echo
if [ "$fallos" -ne 0 ]; then
  echo "atadura del commit: $fallos comprobacion(es) rota(s)" >&2
  exit 1
fi
echo "atadura del commit: 5 comprobaciones, todas correctas"
