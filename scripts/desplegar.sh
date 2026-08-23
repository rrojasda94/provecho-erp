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
#   4. Verifica /health/ready.
set -euo pipefail

VERSION="${1:?Uso: ./scripts/desplegar.sh <version|latest>}"
COMPOSE="docker compose -f docker-compose.staging.yml"

export PROVECHO_IMAGE="ghcr.io/rrojasda94/provecho-erp:${VERSION}"
export PROVECHO_WEB_IMAGE="ghcr.io/rrojasda94/provecho-erp-web:${VERSION}"

echo "Desplegando ${PROVECHO_IMAGE} / ${PROVECHO_WEB_IMAGE}"
$COMPOSE pull
$COMPOSE up -d

echo "Esperando /health/ready..."
for intento in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health/ready >/dev/null 2>&1; then
    echo "OK — staging respondiendo en ${VERSION}"
    exit 0
  fi
  sleep 2
done

echo "No respondió /health/ready a tiempo. Revisar:"
echo "  $COMPOSE logs --tail=100 api init"
exit 1
