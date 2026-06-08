#!/usr/bin/env python3
"""Fetch module docs via lark-cli and write parsed snapshots to cache."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lark_cli_env import lark_cli_subprocess_env  # noqa: E402
from parse_docx_xml import merge_snapshots, parse_fetch_json, snapshot_to_dict  # noqa: E402
from snapshot_cache import (  # noqa: E402
    load_cached_snapshot,
    module_doc_tokens,
    parse_revision_from_fetch,
    revisions_stale,
)


def load_registry(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _lark_cli_fetch(
    obj_token: str,
    *,
    scope: str = "full",
    max_depth: str | None = None,
) -> dict:
    cmd = [
        "lark-cli",
        "docs",
        "+fetch",
        "--api-version",
        "v2",
        "--doc",
        obj_token,
        "--as",
        "user",
        "--format",
        "json",
        "--scope",
        scope,
    ]
    if max_depth is not None:
        cmd.extend(["--max-depth", max_depth])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
        env=lark_cli_subprocess_env(),
    )
    return json.loads(result.stdout)


def lark_fetch_revision(obj_token: str) -> int | None:
    """Lightweight revision probe (outline depth 0, no full body)."""
    raw = _lark_cli_fetch(obj_token, scope="outline", max_depth="0")
    return parse_revision_from_fetch(raw)


def lark_fetch(obj_token: str) -> dict:
    return _lark_cli_fetch(obj_token, scope="full")


def probe_remote_revisions(tokens: dict[str, str]) -> dict[str, int | None]:
    remote: dict[str, int | None] = {}
    for part, token in tokens.items():
        remote[part] = lark_fetch_revision(token)
    return remote


def refresh_snapshots(
    reg_path: Path,
    cache_dir: Path,
    only_module: str | None = None,
    *,
    force: bool = False,
) -> dict[str, list[str]]:
    """Refresh one or all modules. Returns {"refreshed": [...], "skipped": [...]}."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    reg = load_registry(reg_path)
    modules: dict = reg.get("modules", {})
    if only_module:
        if only_module not in modules:
            raise ValueError(f"unknown module: {only_module}")
        modules = {only_module: modules[only_module]}

    refreshed: list[str] = []
    skipped: list[str] = []

    for name, info in modules.items():
        tokens = module_doc_tokens(info)
        if not tokens:
            print(f"SKIP {name}: no obj_token", file=sys.stderr)
            continue

        if not force:
            cached = load_cached_snapshot(cache_dir, name)
            try:
                remote_revisions = probe_remote_revisions(tokens)
            except subprocess.CalledProcessError as e:
                err = (e.stderr or e.stdout or str(e)).strip()
                print(f"WARN {name}: revision_probe_failed ({err}); will full refresh", file=sys.stderr)
                remote_revisions = None

            if remote_revisions is not None:
                stale, reason, detail = revisions_stale(cached, remote_revisions)
                if not stale:
                    parts = detail.get("parts") or {}
                    rev_note = ", ".join(
                        f"{p}={parts[p]['remote']}" for p in sorted(parts) if parts[p].get("remote") is not None
                    )
                    print(f"SKIP {name}: revision_unchanged ({rev_note})")
                    skipped.append(name)
                    continue
                if reason != "no_cache":
                    print(f"REFRESH {name}: {reason}", file=sys.stderr)

        api_snap = None
        type_snap = None
        api_token = info.get("api_docs_obj")
        type_token = info.get("type_constraints_obj")

        if api_token:
            raw = lark_fetch(api_token)
            api_snap = parse_fetch_json(raw, module=name, source="api_docs")

        if type_token:
            raw = lark_fetch(type_token)
            type_snap = parse_fetch_json(raw, module=name, source="type_constraints")

        fetched_at = datetime.now(timezone.utc).isoformat()
        if api_snap and type_snap:
            merged = merge_snapshots(api_snap, type_snap)
        elif api_snap:
            merged = {
                "module": name,
                "api_docs": snapshot_to_dict(api_snap),
                "type_constraints": None,
            }
        elif type_snap:
            merged = {
                "module": name,
                "api_docs": None,
                "type_constraints": snapshot_to_dict(type_snap),
            }
        else:
            print(f"SKIP {name}: no obj_token", file=sys.stderr)
            continue

        merged["fetched_at"] = fetched_at
        for part in ("api_docs", "type_constraints"):
            if merged.get(part):
                merged[part]["fetched_at"] = fetched_at

        out = cache_dir / f"{name}.json"
        out.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"OK {name} -> {out}")
        refreshed.append(name)

    return {"refreshed": refreshed, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh Feishu doc snapshots on ECS")
    parser.add_argument("registry", nargs="?", default="/opt/api-sync/config/wiki-registry.yaml")
    parser.add_argument("cache_dir", nargs="?", default="/opt/api-sync/cache/snapshots")
    parser.add_argument("module", nargs="?", default=None, help="optional module name")
    parser.add_argument("--force", action="store_true", help="skip revision check, always full fetch")
    args = parser.parse_args()

    try:
        refresh_snapshots(
            Path(args.registry),
            Path(args.cache_dir),
            args.module,
            force=args.force,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
