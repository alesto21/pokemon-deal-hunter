#!/bin/sh
# Postgres backup with rotation: keep 7 daily + 4 weekly (Sunday) dumps.
# Works inside the `backup` container (PG* env vars) or on the host via scripts/backup-now.sh.
set -eu
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"
STAMP="$(date +%Y-%m-%d_%H%M)"
FILE="$BACKUP_DIR/daily/dealhunter_$STAMP.dump"

pg_dump --format=custom --no-owner --file "$FILE.partial"
mv "$FILE.partial" "$FILE"
echo "backup written: $FILE ($(du -h "$FILE" | cut -f1))"

if [ "$(date +%u)" = "7" ]; then
  cp "$FILE" "$BACKUP_DIR/weekly/"
fi

# rotation (sorted by name = by date)
ls -1 "$BACKUP_DIR"/daily/*.dump 2>/dev/null | sort -r | tail -n +8 | xargs -r rm -f
ls -1 "$BACKUP_DIR"/weekly/*.dump 2>/dev/null | sort -r | tail -n +5 | xargs -r rm -f
