#!/bin/bash
# Run ON ECS as root — install daily snapshot refresh cron
set -euo pipefail

CRON_LINE='0 3 * * * /opt/api-sync/scripts/refresh-all-snapshots.sh >> /opt/api-sync/logs/refresh.log 2>&1'
MARKER='# game-api-sync refresh'

mkdir -p /opt/api-sync/logs

TMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v 'refresh-all-snapshots.sh' >"$TMP" || true
echo "$CRON_LINE $MARKER" >>"$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "Installed crontab:"
crontab -l | grep game-api-sync || crontab -l | tail -3
