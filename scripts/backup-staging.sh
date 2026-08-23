#!/usr/bin/env bash
# Backup diario simplificado para staging. Corre EN el servidor, vía cron
# del host, en la carpeta donde vive docker-compose.staging.yml.
#
# Por qué no usa src/backups/backup.py (el de producción, ver devops.md):
# esa imagen de la API es Python slim sin `postgresql-client` ni `boto3`
# instalados — extender la imagen solo para esto no vale la pena mientras
# los datos de staging sean desechables. Este script hace `pg_dump` DESDE
# el propio contenedor `db` (Postgres lo trae incluido), sin instalar nada
# extra ni publicar el puerto de la base al host.
#
# Uso (crontab -e como `app`):
#   0 3 * * * cd /home/app/provecho-staging && ./scripts/backup-staging.sh >> backup.log 2>&1
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

BACKUP_DIR="${DIR}/backups"
RETENCION_DIAS=30
FECHA="$(date +%Y%m%d-%H%M%S)"
ARCHIVO="${BACKUP_DIR}/provecho-staging-${FECHA}.dump"

mkdir -p "$BACKUP_DIR"

docker compose -f docker-compose.staging.yml exec -T db \
  pg_dump -U provecho --format=custom provecho > "$ARCHIVO"

# Chequeo mínimo: un dump vacío o truncado (disco lleno) no pasa como éxito.
if [ ! -s "$ARCHIVO" ]; then
  echo "Backup vacío o falló: ${ARCHIVO}" >&2
  rm -f "$ARCHIVO"
  exit 1
fi

echo "Backup OK: ${ARCHIVO} ($(du -h "$ARCHIVO" | cut -f1))"

# Purga lo que excede la retención — nunca el más reciente, aunque esté
# fuera de retención (mismo criterio que src/backups/backup.py).
find "$BACKUP_DIR" -name 'provecho-staging-*.dump' -mtime +"$RETENCION_DIAS" -print -delete
