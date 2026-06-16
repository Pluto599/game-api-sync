#!/bin/bash
# Run ON ECS as root after copying game-api-sync to /tmp/game-api-sync
set -euo pipefail
SRC="${1:-/tmp/game-api-sync}"
DEST=/opt/api-sync

echo "Installing from $SRC to $DEST ..."
mkdir -p "$DEST"/{config,cache/snapshots,scripts,logs,api}

cp -f "$SRC/config/wiki-registry.yaml" "$DEST/config/wiki-registry.yaml"
cp -f "$SRC/config/message_aliases.yaml" "$DEST/config/message_aliases.yaml" 
cp -f "$SRC/scripts/"*.py "$DEST/scripts/"
cp -f "$SRC/scripts/"*.sh "$DEST/scripts/"
chmod +x "$DEST/scripts/"*.sh

pip3 install -q -r "$SRC/api-server/requirements.txt"
cp -f "$SRC/api-server/main.py" "$DEST/api/main.py"

# systemd already configured; restart
systemctl restart api-sync

echo "Nginx: copy deploy/nginx-api-sync.conf to /etc/nginx/sites-available/api-sync"
echo "  sudo nginx -t && sudo systemctl reload nginx"
echo "Run snapshot refresh (requires lark-cli auth login as ops user):"
echo "  python3 $DEST/scripts/refresh_all_snapshots.py"
echo "Module system-design docs use creator profile:"
echo "  /opt/api-sync/env/module-doc.env (MODULE_DOC_LARK_CLI_HOME=/opt/api-sync/.lark-creator)"
echo "Done."
