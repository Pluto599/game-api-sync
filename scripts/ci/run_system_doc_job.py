#!/usr/bin/env python3
"""Orchestrate CI module system-design doc sync when a PR merges."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

from build_system_doc import (  # noqa: E402
    resolve_system_design_obj,
    system_doc_fingerprint,
)
from registry_globs import collect_module_files  # noqa: E402
from ci.gate import (  # noqa: E402
    discover_orphans,
    git_changed_files,
    load_registry,
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


def collect_changed_files(repo_root: Path, paths: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for p in paths:
        full = repo_root / p
        if full.is_file():
            files[p.replace("\\", "/")] = full.read_text(encoding="utf-8", errors="replace")
    return files


def run_module(
    *,
    module: str,
    repo: str,
    registry_path: Path,
    repo_root: Path,
    changed_paths: list[str],
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    mod_map = registry.get("module_map") or {}
    if module not in mod_map:
        raise ValueError(f"unknown module: {module}")

    if mod_map[module].get("_status") == "draft":
        return {"module": module, "skipped": True, "reason": "module_status_draft"}

    changed_norm = sorted({p.replace("\\", "/") for p in changed_paths})
    if not changed_norm:
        return {"module": module, "skipped": True, "reason": "no_changed_files"}

    changed_files = collect_changed_files(repo_root, changed_norm)
    if not changed_files:
        return {"module": module, "skipped": True, "reason": "no_readable_files"}

    glob_files: dict[str, str] = {}
    try:
        glob_files = collect_module_files(repo_root, registry, module, repo)
    except (ValueError, OSError):
        pass

    reg_token = resolve_system_design_obj(registry, module)
    if reg_token:
        files = changed_files
    else:
        files = {**glob_files, **changed_files} if glob_files else changed_files

    fp = system_doc_fingerprint(changed_files, repo)
    state_path = repo_root / ".api-sync" / "state-system-doc.json"
    state = read_state(state_path)
    prev = state.get(module) or {}
    if prev.get("fingerprint") == fp:
        return {"module": module, "skipped": True, "reason": "fingerprint_unchanged"}

    sync_body = {
        "module": module,
        "repo": repo,
        "mode": "auto",
        "files_changed": changed_norm,
        "files": files,
        "glob_files": glob_files or None,
    }
    sync_result = _api("POST", "/jobs/module-system-doc-sync", sync_body)

    if sync_result.get("skipped") and sync_result.get("reason") in (
        "fingerprint_unchanged",
        "all_sections_deduplicated",
    ):
        state[module] = {
            "fingerprint": fp,
            "mode": sync_result.get("mode"),
            "system_design_obj": sync_result.get("system_design_obj"),
        }
        write_state(state_path, state)
        return {
            "module": module,
            "skipped": True,
            "reason": sync_result.get("reason"),
            "mode": sync_result.get("mode"),
            "fingerprint": fp,
            "sync": sync_result,
        }

    state[module] = {
        "fingerprint": fp,
        "mode": sync_result.get("mode"),
        "system_design_obj": sync_result.get("system_design_obj"),
    }
    write_state(state_path, state)

    build_info = sync_result.get("build") or {}
    return {
        "module": module,
        "mode": sync_result.get("mode"),
        "fingerprint": fp,
        "sync": sync_result,
        "context_summary": {
            "functional": build_info.get("functional", 0),
            "data": build_info.get("data", 0),
            "agent_used": build_info.get("agent_used"),
            "sections": build_info.get("sections"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="CI module system-doc sync on PR merge")
    parser.add_argument("--repo", choices=("client", "server"), required=True)
    parser.add_argument("--base-ref", required=True)
    parser.add_argument("--registry", default="config/wiki-registry.yaml")
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
        changed, load_registry(registry_path), args.repo, repo_root=repo_root
    )
    if not modules_map:
        print(json.dumps({"ok": True, "skipped": True, "reason": "no_module_changes"}))
        return

    results: list[dict[str, Any]] = []
    for module in sorted(modules_map.keys()):
        try:
            r = run_module(
                module=module,
                repo=args.repo,
                registry_path=registry_path,
                repo_root=repo_root,
                changed_paths=modules_map[module],
            )
            results.append(r)
        except Exception as e:
            results.append({"module": module, "error": str(e)})

    summary = {"ok": True, "modules": results, "orphans": orphans}
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        lines = ["# Module System Doc Sync", ""]
        for r in results:
            lines.append(f"## {r.get('module', '?')}")
            if r.get("skipped"):
                lines.append(f"- skipped: {r.get('reason')}")
            elif r.get("error"):
                lines.append(f"- error: {r['error']}")
            else:
                sync = r.get("sync") or {}
                lines.append(f"- mode: {r.get('mode')}")
                if sync.get("action_required"):
                    lines.append(f"- **action_required**: {sync['action_required']}")
            lines.append("")
        Path(summary_path).write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
