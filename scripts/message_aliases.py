#!/usr/bin/env python3
"""Load section/title → code type name aliases from config/message_aliases.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ALIASES_REL = "config/message_aliases.yaml"
_DEFAULT = Path(__file__).resolve().parents[1] / ALIASES_REL


def _parse_aliases_data(data: Any) -> dict[str, dict[str, str]]:
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, str]] = {}
    for module, mapping in data.items():
        if not isinstance(mapping, dict):
            continue
        out[str(module)] = {str(k): str(v) for k, v in mapping.items()}
    return out


def load_aliases(path: Path | None = None) -> dict[str, dict[str, str]]:
    p = path or _DEFAULT
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return _parse_aliases_data(data)


def load_aliases_from_text(text: str) -> dict[str, dict[str, str]]:
    data = yaml.safe_load(text) or {}
    return _parse_aliases_data(data)


def find_aliases_in_files(files: dict[str, str]) -> dict[str, dict[str, str]] | None:
    """Return aliases parsed from config/message_aliases.yaml embedded in files dict."""
    norm_suffix = ALIASES_REL.replace("\\", "/")
    for path, content in files.items():
        p = path.replace("\\", "/")
        if p == norm_suffix or p.endswith("/" + norm_suffix):
            return load_aliases_from_text(content)
    return None


def load_aliases_for_compare(
    *,
    repo_root: Path | None = None,
    files: dict[str, str] | None = None,
    path: Path | None = None,
) -> dict[str, dict[str, str]]:
    """
    Resolve alias table for api-compare (game repo first, then embedded files, then fallback).

    Priority:
    1. explicit path
    2. {repo_root}/config/message_aliases.yaml  (CI, local diff_api in game repo)
    3. config/message_aliases.yaml inside files  (IDE → ECS api-compare body)
    4. script/ECS default (central /opt/api-sync config)
    """
    if path is not None and path.is_file():
        return load_aliases(path)
    if repo_root is not None:
        game_path = repo_root / ALIASES_REL
        if game_path.is_file():
            return load_aliases(game_path)
    if files:
        embedded = find_aliases_in_files(files)
        if embedded is not None:
            return embedded
    return load_aliases()


def resolve_code_name(
    module: str,
    *,
    doc_name: str | None,
    section: str | None,
    aliases: dict[str, dict[str, str]] | None = None,
) -> str | None:
    """Map doc section/title to expected code struct name via alias table."""
    aliases = aliases if aliases is not None else load_aliases()
    mod = aliases.get(module) or {}
    for key in (section, doc_name):
        if key and key in mod:
            return mod[key]
    return None
