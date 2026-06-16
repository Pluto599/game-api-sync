#!/usr/bin/env python3
"""Infer in-module layered architecture from path heuristics."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from registry_globs import collect_module_files, glob_key_for_repo, normalize_patterns

_EXCLUDE_PARTS = frozenset(
    {"editor", "tests", "test", "resources", "generated", "__pycache__"}
)

_LAYER_RULES: list[tuple[str, str, str]] = [
    ("表现/UI", r"(?:^|/)(?:ui|view|panel|screen)(?:/|$)", "high"),
    ("状态/协调", r"(?:^|/)(?:viewmodel|presenter|state|controller)(?:/|$)", "high"),
    ("业务/领域", r"(?:^|/)(?:manager|service|system|logic)(?:/|$)", "medium"),
    ("协议/网络", r"(?:^|/)(?:protocol|net|packet|network)(?:/|$)", "high"),
    ("数据/模型", r"(?:^|/)(?:model|data|dto|config)(?:/|$)", "medium"),
    ("服务端处理", r"(?:^|/)(?:handlers?/|.*handler)", "high"),
]

_DEFAULT_LAYER = ("其他", "medium")


def _module_keywords(module: str, registry: dict[str, Any], repo: str) -> list[str]:
    keys: list[str] = [module]
    info = (registry.get("module_map") or {}).get(module) or {}
    glob_key = glob_key_for_repo(repo)
    for pat in normalize_patterns(info.get(glob_key)):
        for m in re.findall(r"([A-Za-z][A-Za-z0-9]{2,})", pat):
            if m not in keys:
                keys.append(m)
        for m in re.findall(r"\*([^*{}]+)\*", pat):
            token = m.strip("*.")
            if len(token) >= 2 and token not in keys:
                keys.append(token)
    return keys


def _should_exclude(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
    parts = lower.split("/")
    return any(p in _EXCLUDE_PARTS for p in parts)


def _classify_path(path: str, *, protocol_paths: set[str]) -> tuple[str, str]:
    norm = path.replace("\\", "/").lower()
    if path in protocol_paths or norm.endswith((".h", ".hpp")) and "protocol" in norm:
        return "协议/网络", "high"
    for layer_name, pattern, conf in _LAYER_RULES:
        if re.search(pattern, norm, re.IGNORECASE):
            return layer_name, conf
    return _DEFAULT_LAYER


def _expand_scan(
    repo_root: Path,
    seed_paths: set[str],
    keywords: list[str],
    *,
    max_files: int = 200,
) -> set[str]:
    found: set[str] = set(seed_paths)
    if len(found) >= max_files:
        return found
    exts = {".cs", ".h", ".hpp", ".cpp", ".c"}
    for kw in keywords:
        if len(kw) < 2:
            continue
        for hit in repo_root.rglob("*"):
            if not hit.is_file() or hit.suffix.lower() not in exts:
                continue
            rel = hit.relative_to(repo_root).as_posix()
            if _should_exclude(rel):
                continue
            if kw.lower() in rel.lower():
                found.add(rel)
            if len(found) >= max_files:
                return found
    return found


def _default_role(layer_name: str, files: list[str]) -> str:
    basenames = ", ".join(Path(f).name for f in files[:3])
    suffix = f"（如 {basenames}）" if basenames else ""
    roles = {
        "表现/UI": f"用户界面与交互{suffix}",
        "状态/协调": f"界面状态与流程协调{suffix}",
        "业务/领域": f"模块核心业务逻辑{suffix}",
        "协议/网络": f"网络消息与协议定义{suffix}",
        "数据/模型": f"数据结构与配置{suffix}",
        "服务端处理": f"服务端请求处理{suffix}",
        "其他": f"模块相关辅助代码{suffix}",
    }
    return roles.get(layer_name, f"{layer_name}{suffix}")


def infer_module_layers(
    *,
    module: str,
    repo: str,
    registry: dict[str, Any],
    repo_root: Path,
    changed_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Return layers[] and layer_dependencies[] for ModuleDocContext."""
    try:
        seed_files = collect_module_files(repo_root, registry, module, repo)
    except (ValueError, OSError):
        seed_files = {}
    protocol_paths = set(seed_files.keys())
    keywords = _module_keywords(module, registry, repo)
    all_paths = _expand_scan(repo_root, set(seed_files.keys()), keywords)

    if changed_paths:
        scan_set = {p.replace("\\", "/") for p in changed_paths}
    else:
        scan_set = all_paths

    layer_map: dict[str, dict[str, Any]] = {}
    for path in sorted(all_paths):
        layer_name, confidence = _classify_path(path, protocol_paths=protocol_paths)
        entry = layer_map.setdefault(
            layer_name,
            {"name": layer_name, "files": [], "confidence": confidence, "role": ""},
        )
        entry["files"].append(path)
        if confidence == "high":
            entry["confidence"] = "high"

    layers = []
    for name in sorted(layer_map.keys()):
        info = layer_map[name]
        info["files"] = sorted(info["files"])
        info["file_count"] = len(info["files"])
        info["role"] = _default_role(name, info["files"])
        layers.append(info)

    changed_layers = sorted(
        {
            _classify_path(p, protocol_paths=protocol_paths)[0]
            for p in scan_set
            if p in all_paths or p in protocol_paths
        }
    )

    order = ["表现/UI", "状态/协调", "业务/领域", "协议/网络", "数据/模型", "服务端处理", "其他"]
    present = [n for n in order if n in layer_map]
    deps: list[dict[str, str]] = []
    for i in range(len(present) - 1):
        deps.append({"from": present[i], "to": present[i + 1], "evidence": "path_order"})

    return {
        "layers": layers,
        "layer_dependencies": deps,
        "changed_layers": changed_layers,
        "scanned_file_count": len(all_paths),
    }
