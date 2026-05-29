#!/usr/bin/env python3
"""Resolve wiki-registry globs and read source files from a game repo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_registry(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalize_patterns(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(p).strip() for p in value if str(p).strip()]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        if "," in s and "**" not in s and "*" not in s:
            return [p.strip() for p in s.split(",") if p.strip()]
        return [s]
    return []


def glob_key_for_repo(repo: str) -> str:
    return "client_glob" if repo == "client" else "server_glob"


def collect_module_files(
    repo_root: Path,
    registry: dict[str, Any],
    module: str,
    repo: str,
) -> dict[str, str]:
    module_map = registry.get("module_map", {})
    if module not in module_map:
        raise ValueError(f"unknown module in module_map: {module}")
    patterns = normalize_patterns(module_map[module].get(glob_key_for_repo(repo)))
    if not patterns:
        raise ValueError(f"no {glob_key_for_repo(repo)} for module {module}")

    files: dict[str, str] = {}
    root = repo_root.resolve()
    for pat in patterns:
        pat = pat.replace("\\", "/")
        path = root / pat
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            files[rel] = path.read_text(encoding="utf-8", errors="replace")
            continue
        for hit in root.glob(pat):
            if hit.is_file():
                rel = hit.relative_to(root).as_posix()
                files[rel] = hit.read_text(encoding="utf-8", errors="replace")
    return files


def obj_token_to_modules(registry: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, info in registry.get("modules", {}).items():
        for key in ("api_docs_obj", "type_constraints_obj"):
            token = info.get(key)
            if token:
                out.setdefault(token, []).append(name)
    return out
