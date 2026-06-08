#!/usr/bin/env python3
"""Load section/title → code type name aliases from config/message_aliases.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_DEFAULT = Path(__file__).resolve().parents[1] / "config" / "message_aliases.yaml"


def load_aliases(path: Path | None = None) -> dict[str, dict[str, str]]:
    p = path or _DEFAULT
    if not p.is_file():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    out: dict[str, dict[str, str]] = {}
    for module, mapping in data.items():
        if not isinstance(mapping, dict):
            continue
        out[str(module)] = {str(k): str(v) for k, v in mapping.items()}
    return out


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
