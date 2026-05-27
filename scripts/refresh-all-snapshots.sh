#!/bin/bash
set -euo pipefail
REG="${1:-/opt/api-sync/config/wiki-registry.yaml}"
CACHE="${2:-/opt/api-sync/cache/snapshots}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
pip3 install -q pyyaml 2>/dev/null || true
python3 "$SCRIPT_DIR/refresh_all_snapshots.py" "$REG" "$CACHE"
