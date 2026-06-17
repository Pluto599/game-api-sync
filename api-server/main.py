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
from diff_api import compare_module_all_targets  # noqa: E402
from compare_targets import scope_type_names_from_code  # noqa: E402
from extract_code import extract_from_sources  # noqa: E402
from doc_sync import sync_doc_draft  # noqa: E402
from build_system_doc import (  # noqa: E402
    build_initial_docx,
    build_module_doc_context,
    build_section_updates,
    resolve_mode,
)
from wiki_module_doc import sync_system_doc  # noqa: E402
from registry_globs import load_registry, obj_token_to_modules  # noqa: E402
from refresh_all_snapshots import refresh_snapshots  # noqa: E402


class RefreshBody(BaseModel):
    module: str | None = None
    force: bool = False


class CompareBody(BaseModel):
    module: str
    repo: str = "client"
    files: dict[str, str]
    target: str | None = None
    scoped: bool = True


class DocSyncBody(BaseModel):
    module: str
    repo: str = "client"
    summary: str = ""
    files_changed: list[str] = []
    target: str = "api_docs"
    docx_draft: str | None = None


class ModuleSystemDocSyncBody(BaseModel):
    module: str
    repo: str = "client"
    mode: str = "auto"
    files_changed: list[str] = []
    docx_draft: str | None = None
    files: dict[str, str] | None = None
    glob_files: dict[str, str] | None = None


def _compare_from_cache(body: CompareBody) -> dict[str, Any]:
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
    reg = load_registry(REGISTRY)
    scope = None
    if body.scoped:
        code = extract_from_sources(body.files, repo=body.repo)
        scope = scope_type_names_from_code(code)
    return compare_module_all_targets(
        snapshot,
        body.files,
        module=name,
        repo=body.repo,
        registry_modules=reg.get("modules"),
        explicit_target=body.target,
        scope_type_names=scope,
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
    if body.force:
        cmd.append("--force")

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
    skipped = [
        line.split()[1].rstrip(":")
        for line in proc.stdout.splitlines()
        if line.startswith("SKIP ") and "revision_unchanged" in line
    ]
    return {
        "ok": True,
        "modules": modules,
        "skipped": skipped,
        "count": len(modules),
        "skipped_count": len(skipped),
        "scope": body.module or "all",
        "force": body.force,
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


@app.get("/api/status")
def api_status(authorization: str | None = Header(None)) -> dict[str, Any]:
    """Latest cached snapshot metadata per module."""
    check_auth(authorization)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    items: list[dict[str, Any]] = []
    for path in sorted(SNAPSHOT_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rev = None
        parts_meta: dict[str, Any] = {}
        for part in ("api_docs", "type_constraints"):
            block = data.get(part) or {}
            if block.get("revision_id") is not None:
                rev = block.get("revision_id")
            parts_meta[part] = {
                "revision_id": block.get("revision_id"),
                "fetched_at": block.get("fetched_at"),
                "struct_count": len(block.get("structs") or []),
            }
        items.append(
            {
                "module": path.stem,
                "cached_at": path.stat().st_mtime,
                "fetched_at": data.get("fetched_at"),
                "revision_id": rev,
                "api_docs": parts_meta.get("api_docs"),
                "type_constraints": parts_meta.get("type_constraints"),
            }
        )
    return {"ok": True, "modules": items, "count": len(items)}


@app.post("/webhook/feishu")
async def feishu_webhook(request: Request) -> dict[str, Any]:
    """Feishu event URL verification + doc update → refresh snapshot."""
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

    return {
        "ok": True,
        "event_type": header.get("event_type"),
        "refreshed": modules_note,
        "modules": modules,
    }


@app.post("/jobs/api-doc-sync")
def api_doc_sync(
    body: DocSyncBody,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Append agent DocxXML to Feishu doc body (h1/h2 marked 待审查; no callout)."""
    check_auth(authorization)
    if not body.summary.strip() and not (body.docx_draft and body.docx_draft.strip()):
        raise HTTPException(status_code=400, detail="summary or docx_draft required")
    try:
        return sync_doc_draft(
            REGISTRY,
            module=body.module.strip(),
            repo=body.repo,
            summary=body.summary,
            files_changed=body.files_changed,
            target=body.target,
            docx_draft=body.docx_draft,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/jobs/module-system-doc-sync")
def module_system_doc_sync(
    body: ModuleSystemDocSyncBody,
    authorization: str | None = Header(None),
) -> dict[str, Any]:
    """Build (optional) and write module system-design DocxXML under section headings."""
    check_auth(authorization)
    has_draft = bool(body.docx_draft and body.docx_draft.strip())
    has_files = bool(body.files)
    if not has_draft and not has_files:
        raise HTTPException(status_code=400, detail="docx_draft or files required")

    reg = load_registry(REGISTRY)
    module = body.module.strip()
    mode = (
        body.mode
        if body.mode in ("full", "delta")
        else resolve_mode(reg, module, check_doc_content=True)
    )
    files_changed = body.files_changed or sorted((body.files or {}).keys())
    initial_docx: str | None = body.docx_draft or None
    section_updates: dict[str, str] | None = None
    context_summary: dict[str, Any] | None = None

    if not has_draft and has_files:
        build_files = dict(body.files or {})
        if mode == "full" and body.glob_files:
            build_files = {**body.glob_files, **build_files}
        ctx = build_module_doc_context(
            module=module,
            repo=body.repo,
            registry=reg,
            repo_root=Path("/tmp"),
            changed_paths=files_changed,
            files=build_files,
            mode=mode,
        )
        if mode == "full":
            initial_docx = build_initial_docx(ctx)
        else:
            section_updates = build_section_updates(ctx)
        context_summary = {
            "agent_used": ctx.get("agent_used"),
            "agent_requested": ctx.get("agent_requested"),
            "functional": len(ctx.get("functional_interfaces") or []),
            "data": len(ctx.get("data_interfaces") or []),
            "sections": list((section_updates or {}).keys()),
        }

    try:
        result = sync_system_doc(
            REGISTRY,
            module=module,
            repo=body.repo,
            files_changed=files_changed,
            mode=mode,
            initial_docx=initial_docx,
            section_updates=section_updates,
        )
        if context_summary:
            result["build"] = context_summary
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
