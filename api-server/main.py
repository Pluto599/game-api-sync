"""API Sync central service — deploy to ECS /opt/api-sync/api/."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel

app = FastAPI(title="game-api-sync")

TOKEN = os.environ.get("API_SYNC_TOKEN", "")
CACHE = Path(os.environ.get("API_SYNC_CACHE", "/opt/api-sync/cache"))
SNAPSHOT_DIR = CACHE / "snapshots"
REGISTRY = Path(os.environ.get("API_SYNC_REGISTRY", "/opt/api-sync/config/wiki-registry.yaml"))
SCRIPTS_DIR = Path(os.environ.get("API_SYNC_SCRIPTS", "/opt/api-sync/scripts"))
REFRESH_SCRIPT = SCRIPTS_DIR / "refresh_all_snapshots.py"

sys.path.insert(0, str(SCRIPTS_DIR))
from diff_api import compare_snapshot_to_code  # noqa: E402
from doc_sync import sync_doc_draft  # noqa: E402
from feishu_notify import notify_doc_updated  # noqa: E402
from registry_globs import load_registry, obj_token_to_modules  # noqa: E402
from refresh_all_snapshots import refresh_snapshots  # noqa: E402


class RefreshBody(BaseModel):
    module: str | None = None


class CompareBody(BaseModel):
    module: str
    repo: str = "client"
    files: dict[str, str]


class DocSyncBody(BaseModel):
    module: str
    repo: str = "client"
    summary: str
    files_changed: list[str] = []
    target: str = "api_docs"


class ApiReviewBody(CompareBody):
    pr_number: int | None = None


def _compare_from_cache(body: CompareBody, *, report_title: str | None = None) -> dict[str, Any]:
    name = body.module.strip()
    path = SNAPSHOT_DIR / f"{name}.json"
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail=f"snapshot not found for module '{name}'; run refresh-cache first",
        )
    if not body.files:
        raise HTTPException(status_code=400, detail="files must not be empty")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    return compare_snapshot_to_code(
        snapshot,
        body.files,
        module=name,
        repo=body.repo,
        report_title=report_title,
    )


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


@app.post("/jobs/api-compare")
def api_compare(
    body: CompareBody,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Compare cached Feishu snapshot vs posted source files; return Markdown report."""
    check_auth(authorization)
    return _compare_from_cache(body)


@app.post("/jobs/api-review")
def api_review(
    body: ApiReviewBody,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """PR Review: same as api-compare, titled for Pull Request comments."""
    check_auth(authorization)
    title = f"# API Review（PR）：{body.module.strip()}"
    if body.pr_number is not None:
        title += f" · PR #{body.pr_number}"
    result = _compare_from_cache(body, report_title=title)
    result["kind"] = "pr_review"
    if body.pr_number is not None:
        result["pr_number"] = body.pr_number
    return result


@app.get("/api/status")
def api_status(authorization: str | None = Header(None)) -> dict[str, Any]:
    """Latest cached snapshot metadata per module (for Bot status / debugging)."""
    check_auth(authorization)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rev = None
        for part in ("api_docs", "type_constraints"):
            block = data.get(part) or {}
            if block.get("revision_id") is not None:
                rev = block.get("revision_id")
        items.append(
            {
                "module": path.stem,
                "cached_at": path.stat().st_mtime,
                "revision_id": rev,
            }
        )
    return {"ok": True, "modules": items, "count": len(items)}


@app.post("/webhook/feishu")
async def feishu_webhook(request: Request) -> dict[str, Any]:
    """Feishu event URL verification + doc update → refresh snapshot (+ optional group notify)."""
    body = await request.json()
    if body.get("type") == "url_verification" or "challenge" in body:
        return {"challenge": body.get("challenge")}

    event = body.get("event") or {}
    header = body.get("header") or {}
    file_token = (
        event.get("file_token")
        or event.get("file_id")
        or event.get("obj_token")
        or event.get("document_id")
    )

    reg = load_registry(REGISTRY)
    modules: list[str] = []
    if file_token:
        modules = obj_token_to_modules(reg).get(str(file_token), [])

    if not modules:
        refresh_snapshots(REGISTRY, SNAPSHOT_DIR, None)
        modules_note = "all"
    else:
        for m in modules:
            refresh_snapshots(REGISTRY, SNAPSHOT_DIR, m)
        modules_note = ",".join(modules)

    for m in (modules if modules else []):
        notify_doc_updated(m)

    return {
        "ok": True,
        "event_type": header.get("event_type"),
        "refreshed": modules_note,
        "notified": modules,
    }


@app.post("/jobs/api-doc-sync")
def api_doc_sync(
    body: DocSyncBody,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Append pending-review callout draft to Feishu module doc (ECS runs lark-cli)."""
    check_auth(authorization)
    if not body.summary.strip():
        raise HTTPException(status_code=400, detail="summary must not be empty")
    try:
        return sync_doc_draft(
            REGISTRY,
            module=body.module.strip(),
            repo=body.repo,
            summary=body.summary,
            files_changed=body.files_changed,
            target=body.target,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
