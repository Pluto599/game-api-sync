#!/usr/bin/env python3
"""GitHub Actions / local CI helpers for api-doc sync."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from extract_code import extract_from_sources

PROTOCOL_EXTS = {".cs", ".h", ".hpp", ".cpp", ".c"}


def git_changed_files(base_ref: str, head_ref: str = "HEAD") -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...{head_ref}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{head_ref}~1", head_ref],
            capture_output=True,
            text=True,
            check=False,
        )
    lines = [ln.strip().replace("\\", "/") for ln in proc.stdout.splitlines() if ln.strip()]
    return lines


def filter_protocol_paths(paths: list[str]) -> list[str]:
    return [p for p in paths if Path(p).suffix.lower() in PROTOCOL_EXTS]


def protocol_fingerprint(files: dict[str, str], repo: str) -> str:
    code = extract_from_sources(files, repo=repo)
    payload = {
        "messages": sorted(
            (m["name"], m.get("fields")) for m in code.get("messages", [])
        ),
        "enums": sorted(
            (e["name"], tuple((x["name"], x.get("value")) for x in e.get("members", [])))
            for e in code.get("enums", [])
        ),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_registry(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def path_matches_pattern(repo_root: Path, path: str, pattern: str) -> bool:
    pat = pattern.replace("\\", "/")
    norm_path = Path(path).as_posix()
    full = repo_root / pat
    if full.is_file():
        return norm_path == pat
    return any(
        norm_path == hit.relative_to(repo_root).as_posix()
        for hit in repo_root.glob(pat)
        if hit.is_file()
    )


def resolve_modules_for_paths(
    changed: list[str],
    registry: dict[str, Any],
    repo: str,
) -> dict[str, list[str]]:
    from registry_globs import normalize_patterns

    glob_key = "client_glob" if repo == "client" else "server_glob"
    module_map = registry.get("module_map") or {}
    result: dict[str, list[str]] = {}

    if "config/wiki-registry.yaml" in changed:
        for mod in module_map:
            result.setdefault(mod, [])
        return result

    repo_root = Path.cwd()
    for path in changed:
        for mod, info in module_map.items():
            for pat in normalize_patterns(info.get(glob_key)):
                if path_matches_pattern(repo_root, path, pat):
                    result.setdefault(mod, []).append(path)
    for mod in list(result):
        result[mod] = sorted(set(result[mod]))
    return result


def discover_orphans(
    changed: list[str],
    registry: dict[str, Any],
    repo: str,
    repo_root: Path | None = None,
) -> list[str]:
    from registry_globs import normalize_patterns

    root = repo_root or Path.cwd()
    module_map = registry.get("module_map") or {}
    glob_key = "client_glob" if repo == "client" else "server_glob"
    orphans: list[str] = []

    def in_any_glob(path: str) -> bool:
        for info in module_map.values():
            for pat in normalize_patterns(info.get(glob_key)):
                if path_matches_pattern(root, path, pat):
                    return True
        return False

    for path in changed:
        if Path(path).suffix.lower() not in PROTOCOL_EXTS:
            continue
        full = root / path
        if not full.is_file():
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        code = extract_from_sources({path: text}, repo=repo)
        if not code.get("messages") and not code.get("enums"):
            continue
        if not in_any_glob(path):
            orphans.append(path)
    return orphans


def read_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
