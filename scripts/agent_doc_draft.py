#!/usr/bin/env python3
"""
IDE Agent CLI: glob check → compare → DocxXML draft (same pipeline as CI sync).

Usage (from game repo root):
  python <central>/scripts/agent_doc_draft.py \\
    --module 商店 --repo client \\
    --paths Assets/Protocol/Shop.cs \\
    [--user-explicit Assets/Protocol/Shop.cs] \\
    [--apply-glob] [--sync] [--force-refresh]

Prints JSON to stdout. With --sync, POST each draft to ECS /jobs/api-doc-sync.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from classify_diff import classify_compare_result  # noqa: E402
from code_to_docx import AGENT_MARKER, build_docx_draft, sync_targets_for_module  # noqa: E402
from diff_api import compare_snapshot_to_code  # noqa: E402
from glob_coverage import apply_registry_glob_update, check_paths_for_align  # noqa: E402
from message_aliases import ALIASES_REL  # noqa: E402
from registry_globs import load_registry  # noqa: E402


def _norm(path: str) -> str:
    return path.replace("\\", "/")


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
        return (time.time() - cached) / 3600 > ttl_hours
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


def git_paths_since(ref: str, repo_root: Path) -> list[str]:
    r = subprocess.run(
        ["git", "diff", "--name-only", f"{ref}...HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise RuntimeError(f"git diff failed: {r.stderr.strip() or r.stdout.strip()}")
    return [_norm(p) for p in r.stdout.splitlines() if p.strip()]


def resolve_paths(args: argparse.Namespace, repo_root: Path) -> list[str]:
    if args.paths:
        return sorted({_norm(p) for p in args.paths})
    if args.git_since:
        return sorted(set(git_paths_since(args.git_since, repo_root)))
    raise ValueError("need --paths or --git-since")


def collect_files(repo_root: Path, paths: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for p in paths:
        full = repo_root / p
        if full.is_file():
            files[_norm(p)] = full.read_text(encoding="utf-8", errors="replace")
    aliases = repo_root / ALIASES_REL
    if aliases.is_file() and ALIASES_REL not in files:
        files[ALIASES_REL] = aliases.read_text(encoding="utf-8", errors="replace")
    return files


def build_agent_drafts(
    *,
    module: str,
    repo: str,
    registry: dict[str, Any],
    snapshot: dict[str, Any],
    paths: list[str],
    files: dict[str, str],
    repo_root: Path | None = None,
) -> list[dict[str, Any]]:
    """Compare + build DocxXML per sync target (no ECS)."""
    mod_map = registry.get("module_map") or {}
    mod_info = (registry.get("modules") or {}).get(module) or {}
    map_entry = mod_map.get(module) or {}
    changed_norm = sorted({_norm(p) for p in paths})
    protocol_files = {k: v for k, v in files.items() if k in changed_norm}

    targets = sync_targets_for_module(snapshot, mod_info, module_map_entry=map_entry)
    if not targets:
        return [
            {
                "target": None,
                "skipped": True,
                "reason": "no_feishu_target",
                "classification": None,
                "sync_recommended": False,
                "docx_draft": "",
                "files_changed": changed_norm,
            }
        ]

    out: list[dict[str, Any]] = []
    for tgt in targets:
        compare = compare_snapshot_to_code(
            snapshot,
            files,
            module=module,
            repo=repo,
            target=tgt,
            registry_modules=registry.get("modules"),
            repo_root=repo_root,
        )
        classification = classify_compare_result(compare)
        entry: dict[str, Any] = {
            "target": tgt,
            "classification": classification,
            "sync_recommended": classification["sync_recommended"],
            "files_changed": changed_norm,
            "docx_draft": "",
        }
        if not classification["sync_recommended"]:
            entry["skipped"] = True
            entry["reason"] = classification["classification"]
            out.append(entry)
            continue

        draft = build_docx_draft(
            snapshot=snapshot,
            compare_result=compare,
            files=protocol_files,
            repo=repo,
            target=tgt,
            marker=AGENT_MARKER,
            changed_paths=changed_norm,
        )
        if not draft.strip():
            entry["skipped"] = True
            entry["reason"] = "no_draft_in_changed_files"
            out.append(entry)
            continue

        entry["docx_draft"] = draft
        entry["skipped"] = False
        entry["api_doc_sync_body"] = {
            "module": module,
            "repo": repo,
            "target": tgt,
            "summary": (
                f"Agent draft {module}/{tgt} "
                f"({classification['classification']})"
            ),
            "files_changed": changed_norm,
            "docx_draft": draft,
        }
        out.append(entry)
    return out


def run_agent_doc_draft(
    *,
    module: str,
    repo: str,
    paths: list[str],
    registry_path: Path,
    repo_root: Path,
    user_explicit: set[str] | None = None,
    apply_glob: bool = False,
    force_refresh: bool = False,
    ttl_hours: float = 6.0,
    do_sync: bool = False,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    mod_map = registry.get("module_map") or {}
    if module not in mod_map:
        raise ValueError(f"unknown module: {module}")

    status = mod_map[module].get("_status")
    if status == "draft":
        return {
            "ok": True,
            "skipped": True,
            "reason": "module_status_draft",
            "module": module,
            "repo": repo,
            "paths": paths,
        }

    if not paths:
        return {
            "ok": True,
            "skipped": True,
            "reason": "no_paths",
            "module": module,
            "repo": repo,
            "paths": [],
        }

    glob_report = check_paths_for_align(
        repo_root,
        registry,
        module,
        repo,
        paths,
        user_explicit=user_explicit,
    )
    registry_applied = False
    user_action_required: str | None = None

    if glob_report["needs_registry_update"]:
        if apply_glob:
            registry_applied = apply_registry_glob_update(
                registry_path,
                module,
                repo,
                glob_report["suggested_glob"],
            )
            if registry_applied:
                registry = load_registry(registry_path)
            user_action_required = (
                "已自动更新 wiki-registry.yaml，请核对 git diff 中的 glob 路径"
                if registry_applied
                else "glob 建议与 registry 一致，未写入"
            )
        else:
            user_action_required = (
                "以下路径不在 glob 中："
                + ", ".join(glob_report["missing_from_glob"])
                + "。请运行 --apply-glob 或手动更新 wiki-registry.yaml 后核对"
            )

    if force_refresh or needs_refresh(module, ttl_hours):
        refresh_module(module, force=force_refresh)

    snapshot = fetch_snapshot(module)
    files = collect_files(repo_root, paths)
    drafts = build_agent_drafts(
        module=module,
        repo=repo,
        registry=registry,
        snapshot=snapshot,
        paths=paths,
        files=files,
        repo_root=repo_root,
    )

    sync_results: list[dict[str, Any]] = []
    if do_sync:
        for d in drafts:
            body = d.get("api_doc_sync_body")
            if not body or d.get("skipped"):
                continue
            sync_results.append(_api("POST", "/jobs/api-doc-sync", body))

    return {
        "ok": True,
        "module": module,
        "repo": repo,
        "paths": paths,
        "glob": {
            **glob_report,
            "registry_applied": registry_applied,
            "registry_path": str(registry_path.relative_to(repo_root))
            if registry_path.is_relative_to(repo_root)
            else str(registry_path),
        },
        "user_action_required": user_action_required,
        "drafts": drafts,
        "sync_results": sync_results if do_sync else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="IDE Agent: glob check + compare + DocxXML draft for Feishu sync"
    )
    parser.add_argument("--module", required=True, help="module name e.g. 商店")
    parser.add_argument("--repo", choices=("client", "server"), required=True)
    parser.add_argument("--registry", default="config/wiki-registry.yaml")
    parser.add_argument("--repo-root", default=".", help="game repo root")
    parser.add_argument("--paths", nargs="*", default=[], help="protocol file paths")
    parser.add_argument(
        "--git-since",
        default="",
        help="git ref for diff (e.g. origin/main); lists changed files vs HEAD",
    )
    parser.add_argument(
        "--user-explicit",
        nargs="*",
        default=[],
        help="paths user @ explicitly (bypass ui/resource skip for glob)",
    )
    parser.add_argument(
        "--apply-glob",
        action="store_true",
        help="auto-write suggested_glob to wiki-registry.yaml",
    )
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--ttl-hours", type=float, default=6.0)
    parser.add_argument(
        "--sync",
        action="store_true",
        help="POST drafts to ECS /jobs/api-doc-sync (requires API_SYNC_* env)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="skip ECS refresh/snapshot; requires --snapshot-json",
    )
    parser.add_argument(
        "--snapshot-json",
        default="",
        help="local snapshot JSON (with --offline)",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    registry_path = repo_root / args.registry

    try:
        paths = resolve_paths(args, repo_root)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)

    user_explicit = {_norm(p) for p in (args.user_explicit or [])}

    if args.offline:
        if not args.snapshot_json:
            print(
                json.dumps(
                    {"ok": False, "error": "--offline requires --snapshot-json"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            sys.exit(1)
        registry = load_registry(registry_path)
        snapshot = json.loads(Path(args.snapshot_json).read_text(encoding="utf-8"))
        glob_report = check_paths_for_align(
            repo_root, registry, args.module, args.repo, paths, user_explicit=user_explicit
        )
        files = collect_files(repo_root, paths)
        drafts = build_agent_drafts(
            module=args.module,
            repo=args.repo,
            registry=registry,
            snapshot=snapshot,
            paths=paths,
            files=files,
        )
        result = {
            "ok": True,
            "module": args.module,
            "repo": args.repo,
            "paths": paths,
            "glob": glob_report,
            "offline": True,
            "drafts": drafts,
        }
    else:
        try:
            result = run_agent_doc_draft(
                module=args.module,
                repo=args.repo,
                paths=paths,
                registry_path=registry_path,
                repo_root=repo_root,
                user_explicit=user_explicit,
                apply_glob=args.apply_glob,
                force_refresh=args.force_refresh,
                ttl_hours=args.ttl_hours,
                do_sync=args.sync,
            )
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
