#!/usr/bin/env bash
# Take a backup immediately using the running postgres container.
set -euo pipefail
cd "$(dirname "$0")/.."
source .env
mkdir -p backups
docker compose exec -T -e BACKUP_DIR=/tmp/bk postgres sh -c \
  "mkdir -p /tmp/bk && PGUSER=$POSTGRES_USER PGDATABASE=$POSTGRES_DB pg_dump --format=custom --no-owner -f /tmp/bk/now.dump"
docker compose cp postgres:/tmp/bk/now.dump "backups/manual_$(date +%Y-%m-%d_%H%M).dump"
docker compose exec -T postgres rm -rf /tmp/bk
ls -lh backups | tail -3
