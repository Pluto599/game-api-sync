#!/usr/bin/env python3
"""Fetch all module docs via lark-cli and write parsed snapshots to cache."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from parse_docx_xml import merge_snapshots, parse_fetch_json, snapshot_to_dict  # noqa: E402


def load_registry(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


from lark_cli_env import lark_cli_subprocess_env  # noqa: E402


def lark_fetch(obj_token: str) -> dict:
    result = subprocess.run(
        [
            "lark-cli",
            "docs",
            "+fetch",
            "--api-version",
            "v2",
            "--doc",
            obj_token,
            "--scope",
            "full",
            "--as",
            "user",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=lark_cli_subprocess_env(),
    )
    return json.loads(result.stdout)


def refresh_snapshots(
    reg_path: Path,
    cache_dir: Path,
    only_module: str | None = None,
) -> list[str]:
    """Refresh one or all modules. Returns list of module names written."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    reg = load_registry(reg_path)
    modules: dict = reg.get("modules", {})
    if only_module:
        if only_module not in modules:
            raise ValueError(f"unknown module: {only_module}")
        modules = {only_module: modules[only_module]}

    done: list[str] = []
    for name, info in modules.items():
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

        out = cache_dir / f"{name}.json"
        out.write_text(
            json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"OK {name} -> {out}")
        done.append(name)
    return done


def main() -> None:
    reg_path = Path(
        sys.argv[1] if len(sys.argv) > 1 else "/opt/api-sync/config/wiki-registry.yaml"
    )
    cache_dir = Path(
        sys.argv[2] if len(sys.argv) > 2 else "/opt/api-sync/cache/snapshots"
    )
    only = sys.argv[3] if len(sys.argv) > 3 else None
    try:
        refresh_snapshots(reg_path, cache_dir, only)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
