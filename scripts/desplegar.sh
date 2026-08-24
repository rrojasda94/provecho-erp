#!/usr/bin/env bash
# Actualiza staging a una versión nueva. Corre EN el servidor, en la carpeta
# donde vive docker-compose.staging.yml y el .env real.
#
# Uso:
#   ./scripts/desplegar.sh 1.4.0
#   ./scripts/desplegar.sh latest      # último push a main
#
# Qué hace, en orden (el mismo criterio que devops.md#despliegue: nunca
# migrar dentro del arranque automático de varias réplicas a la vez —
# acá hay una sola réplica de cada servicio, así que el servicio `init`
# del compose puede migrar solo con seguridad):
#   1. Fija PROVECHO_IMAGE/PROVECHO_WEB_IMAGE a la versión pedida.
#   2. `docker compose pull` — baja las imágenes nuevas.
#   3. `docker compose up -d` — reinicia con las imágenes nuevas; el
#      servicio `init` corre `alembic upgrade head` antes de que `api`
#      arranque (depends_on: service_completed_successfully).
#   4. Reinicia Caddy, que si no sigue proxeando a una IP muerta.
#   5. Verifica /health/ready por el loopback y por el dominio público.
set -euo pipefail

VERSION="${1:?Uso: ./scripts/desplegar.sh <version|latest>}"
COMPOSE="docker compose -f docker-compose.staging.yml"
DOMINIO_API="${DOMINIO_API:-https://api-staging.majambo.com.pe}"

export PROVECHO_IMAGE="ghcr.io/rrojasda94/provecho-erp:${VERSION}"
export PROVECHO_WEB_IMAGE="ghcr.io/rrojasda94/provecho-erp-web:${VERSION}"

echo "Desplegando ${PROVECHO_IMAGE} / ${PROVECHO_WEB_IMAGE}"
$COMPOSE pull
$COMPOSE up -d

echo "Esperando /health/ready..."
listo=""
for intento in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health/ready >/dev/null 2>&1; then
    listo="si"
    break
  fi
  sleep 2
done

if [ -z "$listo" ]; then
  echo "No respondió /health/ready a tiempo. Revisar:"
  echo "  $COMPOSE logs --tail=100 api init"
  exit 1
fi

# Caddy resuelve `reverse_proxy api:8000` una sola vez, al arrancar. Recrear
# `api` o `web` les da una IP nueva en la red de Docker, y Caddy —que no se
# recreó— sigue hablándole a la vieja: el dominio público devuelve 502 con la
# API perfectamente sana. Por eso el paso de arriba no alcanza: pega al
# loopback y no pasa por el proxy. Ver staging.md, bug del 2026-08-24; la
# solución de fondo (`dynamic a` en el Caddyfile) está en deuda/ci-cd.md.
echo "Reiniciando Caddy para que resuelva las IP nuevas..."
$COMPOSE restart caddy

echo "Comprobando el dominio público..."
for intento in $(seq 1 15); do
  if curl -fsS "${DOMINIO_API}/health/ready" >/dev/null 2>&1; then
    echo "OK — staging respondiendo en ${VERSION}"
    exit 0
  fi
  sleep 2
done

echo "La API responde por el loopback pero ${DOMINIO_API} no. Es el proxy:"
echo "  $COMPOSE logs --tail=50 caddy"
exit 1
