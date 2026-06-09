#!/usr/bin/env python3
"""Orchestrate CI api-doc sync: compare on PR, conditional write on main push."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from classify_diff import classify_compare_result  # noqa: E402
from code_to_docx import build_docx_draft, infer_doc_sync_target  # noqa: E402
from diff_api import compare_module_all_targets  # noqa: E402
from registry_globs import collect_module_files  # noqa: E402

from ci.gate import (  # noqa: E402
    discover_orphans,
    git_changed_files,
    load_registry,
    protocol_fingerprint,
    read_state,
    resolve_modules_for_paths,
    write_state,
)


def _api(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
    base = os.environ.get("API_SYNC_BASE", "http://120.27.249.20").rstrip("/")
    token = os.environ.get("API_SYNC_TOKEN", "")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> {e.code}: {detail}") from e


def needs_refresh(module: str, ttl_hours: float) -> bool:
    try:
        status = _api("GET", "/api/status")
    except RuntimeError:
        return True
    for item in status.get("modules") or []:
        if item.get("module") != module:
            continue
        cached = item.get("cached_at") or 0
        age_h = (time.time() - cached) / 3600
        return age_h > ttl_hours
    return True


def refresh_module(module: str, *, force: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {"module": module}
    if force:
        body["force"] = True
    return _api("POST", "/jobs/refresh-cache", body)


def fetch_snapshot(module: str) -> dict[str, Any]:
    import urllib.parse

    q = urllib.parse.quote(module)
    r = _api("GET", f"/api/snapshot?module={q}")
    return r.get("snapshot") or r


def collect_files_for_module(
    repo_root: Path,
    registry: dict[str, Any],
    module: str,
    repo: str,
    extra_paths: list[str] | None = None,
) -> dict[str, str]:
    files = collect_module_files(repo_root, registry, module, repo)
    for p in extra_paths or []:
        full = repo_root / p
        if full.is_file():
            rel = full.relative_to(repo_root).as_posix()
            files[rel] = full.read_text(encoding="utf-8", errors="replace")
    return files


def run_module(
    *,
    mode: str,
    module: str,
    repo: str,
    registry_path: Path,
    repo_root: Path,
    changed_paths: list[str],
    ttl_hours: float,
    force_refresh: bool,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    mod_map = registry.get("module_map") or {}
    if module not in mod_map:
        raise ValueError(f"unknown module: {module}")

    status = mod_map[module].get("_status")
    if status == "draft":
        return {"module": module, "skipped": True, "reason": "module_status_draft"}

    if force_refresh or needs_refresh(module, ttl_hours):
        refresh_module(module)

    snapshot = fetch_snapshot(module)
    files = collect_files_for_module(
        repo_root, registry, module, repo, extra_paths=changed_paths
    )
    fp = protocol_fingerprint(files, repo)
    compare = compare_module_all_targets(
        snapshot,
        files,
        module=module,
        repo=repo,
        registry_modules=registry.get("modules"),
        repo_root=repo_root,
    )
    classification = classify_compare_result(compare)
    out: dict[str, Any] = {
        "module": module,
        "fingerprint": fp,
        "classification": classification,
    }
    if mode == "pr":
        out["report_md"] = compare.get("report_md", "")

    if mode == "pr":
        return out

    state_path = repo_root / ".api-sync" / "state.json"
    state = read_state(state_path)
    prev = state.get(module) or {}
    if prev.get("fingerprint") == fp:
        out["skipped"] = True
        out["reason"] = "fingerprint_unchanged"
        return out

    if not classification["sync_recommended"]:
        out["skipped"] = True
        out["reason"] = classification["classification"]
        return out

    changed_norm = sorted({p.replace("\\", "/") for p in changed_paths})
    target = infer_doc_sync_target(snapshot, (registry.get("modules") or {}).get(module))
    draft = build_docx_draft(
        snapshot=snapshot,
        compare_result=compare,
        files=files,
        repo=repo,
        target=target,
        changed_paths=changed_norm,
    )
    if not draft.strip():
        out["skipped"] = True
        out["reason"] = "no_draft_in_changed_files"
        return out

    sync_body = {
        "module": module,
        "repo": repo,
        "target": target,
        "summary": f"CI sync {module} ({classification['classification']})",
        "files_changed": changed_norm,
        "docx_draft": draft,
    }
    sync_result = _api("POST", "/jobs/api-doc-sync", sync_body)
    out["sync"] = sync_result
    state[module] = {
        "fingerprint": fp,
        "classification": classification["classification"],
        "revision_id": sync_result.get("feishu"),
    }
    write_state(state_path, state)
    return out


def _format_sync_module_summary(r: dict[str, Any]) -> list[str]:
    """Concise per-module lines for main (sync) mode — no compare report body."""
    lines: list[str] = []
    cls = r.get("classification") or {}
    label = cls.get("classification", "?")
    lines.append(f"- **classification**: `{label}`")
    if r.get("skipped"):
        lines.append(f"- **skipped**: `{r.get('reason', 'unknown')}`")
    elif r.get("sync"):
        sync = r["sync"]
        ok = sync.get("ok", sync.get("success"))
        lines.append(f"- **sync**: {'ok' if ok else 'failed'}")
        if sync.get("message"):
            lines.append(f"- **message**: {sync['message']}")
    if r.get("error"):
        lines.append(f"- **error**: {r['error']}")
    return lines


def _write_step_summary(
    *,
    mode: str,
    results: list[dict[str, Any]],
    orphans: list[str],
    summary_path: str,
) -> None:
    lines = [f"# API Sync ({mode})", ""]
    if orphans:
        lines.append("## Orphans\n")
        for o in orphans:
            lines.append(f"- `{o}`")
        lines.append("")
    for r in results:
        lines.append(f"## {r.get('module', '?')}\n")
        if mode == "pr":
            if r.get("report_md"):
                lines.append(r["report_md"])
            if r.get("skipped"):
                lines.append(f"\n_skipped: {r.get('reason')}_\n")
            if r.get("error"):
                lines.append(f"\n**error**: {r['error']}\n")
        else:
            lines.extend(_format_sync_module_summary(r))
            lines.append("")
        lines.append("")
    Path(summary_path).write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="CI api-doc sync job")
    parser.add_argument("--mode", choices=("pr", "main"), required=True)
    parser.add_argument("--repo", choices=("client", "server"), required=True)
    parser.add_argument("--base-ref", default=os.environ.get("GITHUB_BASE_REF", "main"))
    parser.add_argument("--registry", default="config/wiki-registry.yaml")
    parser.add_argument("--ttl-hours", type=float, default=6.0)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--orphan-policy", choices=("warn", "fail"), default="warn")
    args = parser.parse_args()

    repo_root = Path.cwd()
    registry_path = repo_root / args.registry
    changed = git_changed_files(args.base_ref)
    orphans = discover_orphans(changed, load_registry(registry_path), args.repo, repo_root)
    if orphans:
        msg = "Orphan protocol files (not in any module glob):\n" + "\n".join(orphans)
        print(msg, file=sys.stderr)
        if args.orphan_policy == "fail":
            sys.exit(2)

    modules_map = resolve_modules_for_paths(
        changed, load_registry(registry_path), args.repo
    )
    if not modules_map and not changed:
        print(json.dumps({"ok": True, "skipped": True, "reason": "no_changes"}))
        return

    results: list[dict[str, Any]] = []
    for module in sorted(modules_map.keys()):
        try:
            r = run_module(
                mode=args.mode,
                module=module,
                repo=args.repo,
                registry_path=registry_path,
                repo_root=repo_root,
                changed_paths=modules_map[module],
                ttl_hours=args.ttl_hours,
                force_refresh=args.force_refresh,
            )
            results.append(r)
        except Exception as e:
            results.append({"module": module, "error": str(e)})

    summary = {
        "ok": True,
        "mode": args.mode,
        "modules": results,
        "orphans": orphans,
    }
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        _write_step_summary(
            mode=args.mode,
            results=results,
            orphans=orphans,
            summary_path=summary_path,
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
