#!/usr/bin/env bash
# Restore a pg_dump custom-format file into the running postgres container.
# Usage: scripts/restore.sh backups/daily/dealhunter_2026-09-30_0200.dump
set -euo pipefail
cd "$(dirname "$0")/.."
DUMP="${1:?usage: scripts/restore.sh <file.dump>}"
source .env
read -r -p "This REPLACES the current database '$POSTGRES_DB'. Type 'restore' to continue: " ok
[ "$ok" = "restore" ] || { echo "aborted"; exit 1; }
docker compose stop api worker web
docker compose cp "$DUMP" postgres:/tmp/restore.dump
docker compose exec -T postgres sh -c \
  "pg_restore -U $POSTGRES_USER -d $POSTGRES_DB --clean --if-exists --no-owner /tmp/restore.dump && rm /tmp/restore.dump"
docker compose run --rm migrate
docker compose start api worker web
echo "restore complete"
