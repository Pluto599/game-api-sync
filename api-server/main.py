"""API Sync central service — deploy to ECS /opt/api-sync/api/."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="game-api-sync")

TOKEN = os.environ.get("API_SYNC_TOKEN", "")
CACHE = Path(os.environ.get("API_SYNC_CACHE", "/opt/api-sync/cache"))
SNAPSHOT_DIR = CACHE / "snapshots"
REGISTRY = Path(os.environ.get("API_SYNC_REGISTRY", "/opt/api-sync/config/wiki-registry.yaml"))
SCRIPTS_DIR = Path(os.environ.get("API_SYNC_SCRIPTS", "/opt/api-sync/scripts"))
REFRESH_SCRIPT = SCRIPTS_DIR / "refresh_all_snapshots.py"


class RefreshBody(BaseModel):
    module: str | None = None


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


@app.post("/jobs/refresh-cache")
def refresh_cache(
    body: RefreshBody | None = None,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Pull Feishu docs on ECS and update snapshot cache (lark-cli runs server-side only)."""
    check_auth(authorization)
    if not REFRESH_SCRIPT.is_file():
        raise HTTPException(status_code=500, detail=f"refresh script not found: {REFRESH_SCRIPT}")

    body = body or RefreshBody()
    cmd = [
        sys.executable,
        str(REFRESH_SCRIPT),
        str(REGISTRY),
        str(SNAPSHOT_DIR),
    ]
    if body.module:
        cmd.append(body.module.strip())

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("API_SYNC_REFRESH_TIMEOUT", "600")),
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="refresh-cache timed out") from None

    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=(proc.stderr or proc.stdout or "refresh failed").strip(),
        )

    modules = [line.split()[1] for line in proc.stdout.splitlines() if line.startswith("OK ")]
    return {
        "ok": True,
        "modules": modules,
        "count": len(modules),
        "scope": body.module or "all",
        "log": proc.stdout.strip(),
    }
