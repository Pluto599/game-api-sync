"""API Sync central service — deploy to ECS /opt/api-sync/api/."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, Header, HTTPException, Query

app = FastAPI(title="game-api-sync")

TOKEN = os.environ.get("API_SYNC_TOKEN", "")
CACHE = Path(os.environ.get("API_SYNC_CACHE", "/opt/api-sync/cache"))
SNAPSHOT_DIR = CACHE / "snapshots"


def check_auth(authorization: str | None) -> None:
    if not TOKEN:
        return
    if not authorization or authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/wiki-nodes")
def wiki_nodes(authorization: str | None = Header(None)) -> dict[str, Any]:
    check_auth(authorization)
    files = sorted(CACHE.glob("nodes_*.json"))
    return {"ok": True, "files": [f.name for f in files], "count": len(files)}


@app.get("/api/snapshot/modules")
def snapshot_modules(authorization: str | None = Header(None)) -> dict[str, Any]:
    check_auth(authorization)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    modules = sorted(p.stem for p in SNAPSHOT_DIR.glob("*.json"))
    return {"ok": True, "modules": modules, "count": len(modules)}


@app.get("/api/snapshot")
def snapshot(
    module: str = Query(..., description="模块名，如 战斗"),
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    check_auth(authorization)
    name = unquote(module).strip()
    path = SNAPSHOT_DIR / f"{name}.json"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"snapshot not found for module '{name}'; run refresh-all-snapshots on ECS",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"ok": True, "module": name, "snapshot": data}
