#!/bin/sh
# Runs backup.sh once per day at $BACKUP_HOUR (container-local time).
set -eu
echo "backup scheduler started; daily at ${BACKUP_HOUR}:00"
last=""
while true; do
  today="$(date +%Y-%m-%d)"
  if [ "$(date +%H)" = "$BACKUP_HOUR" ] && [ "$last" != "$today" ]; then
    if sh /scripts/backup.sh; then last="$today"; else echo "backup FAILED" >&2; fi
  fi
  sleep 300
done
