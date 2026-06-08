#!/usr/bin/env python3
"""Snapshot cache helpers: revision compare for conditional refresh."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CACHE_PARTS = ("api_docs", "type_constraints")


def load_cached_snapshot(cache_dir: Path, module: str) -> dict[str, Any] | None:
    path = cache_dir / f"{module}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def cached_part_revision(cached: dict[str, Any] | None, part: str) -> int | None:
    if not cached:
        return None
    block = cached.get(part)
    if not block:
        return None
    rev = block.get("revision_id")
    if rev is None:
        return None
    return int(rev)


def module_doc_tokens(module_info: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    api = module_info.get("api_docs_obj")
    tc = module_info.get("type_constraints_obj")
    if api:
        out["api_docs"] = str(api)
    if tc:
        out["type_constraints"] = str(tc)
    return out


def revisions_stale(
    cached: dict[str, Any] | None,
    remote_revisions: dict[str, int | None],
    *,
    parts: tuple[str, ...] = CACHE_PARTS,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Return (stale, reason, detail).
    stale=True means a full refresh is needed.
    """
    detail: dict[str, Any] = {"parts": {}}
    if cached is None:
        return True, "no_cache", detail

    active_parts = [p for p in parts if p in remote_revisions]
    if not active_parts:
        return True, "no_doc_tokens", detail

    for part in active_parts:
        cached_rev = cached_part_revision(cached, part)
        remote_rev = remote_revisions.get(part)
        detail["parts"][part] = {"cached": cached_rev, "remote": remote_rev}
        if cached_rev is None:
            return True, f"missing_cached_revision:{part}", detail
        if remote_rev is None:
            return True, f"missing_remote_revision:{part}", detail
        if cached_rev != remote_rev:
            return True, f"revision_mismatch:{part}", detail

    return False, "revision_unchanged", detail


def parse_revision_from_fetch(raw: dict[str, Any]) -> int | None:
    doc = raw.get("data", {}).get("document", raw.get("document", {}))
    rev = doc.get("revision_id")
    if rev is None:
        return None
    return int(rev)
