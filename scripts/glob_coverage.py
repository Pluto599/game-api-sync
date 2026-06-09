#!/usr/bin/env python3
"""Check align/compare file paths against wiki-registry globs; suggest registry updates."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from extract_code import extract_from_sources
from registry_globs import glob_key_for_repo, load_registry, normalize_patterns

PROTOCOL_EXTS = {".cs", ".h", ".hpp", ".cpp", ".c"}

# 勿写入 glob：资源、场景、纯 UI 资产等
EXCLUDE_SUFFIXES = {
    ".prefab",
    ".unity",
    ".asset",
    ".meta",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".fbx",
    ".mat",
    ".controller",
    ".anim",
    ".shader",
    ".ttf",
    ".otf",
    ".wav",
    ".mp3",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".md",
    ".txt",
    ".asmdef",
}

EXCLUDE_PATH_PARTS = (
    "/resources/",
    "/streamingassets/",
    "/editor/",
    "/tests/",
    "/test/",
    "/__tests__/",
    "/generated/",
    "/.git/",
)

# 默认不自动加入 glob 的路径片段（UI/视图层；用户 @ 指定时仍可纳入对齐范围）
DEFAULT_SKIP_GLOB_PARTS = (
    "viewmodel",
    "viewmodels/",
    "/views/",
    "/dialogs/",
    "/states/",
    "state.cs",
)


def _norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def path_matches_pattern(repo_root: Path, path: str, pattern: str) -> bool:
    pat = pattern.replace("\\", "/")
    norm_path = _norm(path)
    full = repo_root / pat
    if full.is_file():
        return norm_path == pat
    return any(
        norm_path == hit.relative_to(repo_root).as_posix()
        for hit in repo_root.glob(pat)
        if hit.is_file()
    )


def path_in_module_glob(
    repo_root: Path,
    registry: dict[str, Any],
    module: str,
    repo: str,
    path: str,
) -> bool:
    module_map = registry.get("module_map") or {}
    info = module_map.get(module) or {}
    key = glob_key_for_repo(repo)
    for pat in normalize_patterns(info.get(key)):
        if path_matches_pattern(repo_root, path, pat):
            return True
    return False


def exclude_reason(path: str, *, user_explicit: bool = False) -> str | None:
    """Return reason to skip auto glob add, or None if candidate."""
    if user_explicit:
        return None
    p = _norm(path).lower()
    suffix = Path(p).suffix.lower()
    if suffix in EXCLUDE_SUFFIXES:
        return f"resource_or_non_source_suffix:{suffix}"
    for part in EXCLUDE_PATH_PARTS:
        if part in p:
            return f"excluded_path_segment:{part.strip('/')}"
    for part in DEFAULT_SKIP_GLOB_PARTS:
        if part in p:
            return f"ui_or_state_layer:{part}"
    return None


def is_protocol_source(path: str, text: str | None, repo: str) -> bool:
    suffix = Path(_norm(path)).suffix.lower()
    if suffix not in PROTOCOL_EXTS:
        return False
    if text is None:
        return True
    code = extract_from_sources({_norm(path): text}, repo=repo)
    if code.get("messages") or code.get("enums") or code.get("constants"):
        return True
    # extract 可能漏单行 struct；有 struct/class/enum 定义仍视为协议候选
    return bool(re.search(r"\b(?:struct|class)\s+\w+", text)) or bool(
        re.search(r"\benum\s+\w+", text)
    )


def merge_explicit_glob_paths(
    existing_patterns: list[str],
    new_paths: list[str],
) -> list[str]:
    """Merge single-file paths into explicit YAML list; keep non-file patterns."""
    singles: list[str] = []
    patterns: list[str] = []
    for pat in existing_patterns:
        p = pat.replace("\\", "/")
        if "*" in p or "**" in p:
            patterns.append(p)
        else:
            singles.append(p)
    merged = sorted(set(singles) | {_norm(p) for p in new_paths})
    return merged + patterns


def check_paths_for_align(
    repo_root: Path,
    registry: dict[str, Any],
    module: str,
    repo: str,
    paths: list[str],
    *,
    user_explicit: set[str] | None = None,
) -> dict[str, Any]:
    """
    Check which align targets are missing from module glob.
    Returns structured result for Agent / CLI.
    """
    user_explicit = {_norm(p) for p in (user_explicit or set())}
    module_map = registry.get("module_map") or {}
    info = module_map.get(module) or {}
    key = glob_key_for_repo(repo)
    existing = normalize_patterns(info.get(key))

    in_glob: list[str] = []
    missing_protocol: list[str] = []
    skipped: dict[str, str] = {}
    to_add: list[str] = []

    for raw in paths:
        path = _norm(raw)
        full = repo_root / path
        if not full.is_file():
            skipped[path] = "file_not_found"
            continue
        explicit = path in user_explicit
        if path_in_module_glob(repo_root, registry, module, repo, path):
            in_glob.append(path)
            continue
        reason = exclude_reason(path, user_explicit=explicit)
        if reason and not explicit:
            skipped[path] = reason
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        if not is_protocol_source(path, text, repo) and not explicit:
            skipped[path] = "no_protocol_struct_or_enum"
            continue
        missing_protocol.append(path)
        to_add.append(path)

    suggested = merge_explicit_glob_paths(existing, to_add) if to_add else list(existing)

    return {
        "module": module,
        "repo": repo,
        "glob_key": key,
        "in_glob": sorted(in_glob),
        "missing_from_glob": sorted(missing_protocol),
        "skipped_auto_add": skipped,
        "suggested_glob": suggested,
        "needs_registry_update": bool(to_add),
    }
