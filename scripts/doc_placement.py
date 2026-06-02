#!/usr/bin/env python3
"""Resolve Feishu insert anchor for api-doc-sync (end of h1 客户端 / 服务端 section)."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from lark_cli_env import lark_cli_subprocess_env

TITLE_MARKER = "（agent生成，待审查）"
_MERGE_PARA = re.compile(
    r"<p[^>]*>\s*[^<]*【合并位置】[^<]*</p>\s*",
    re.IGNORECASE,
)
_BLOCK_ID = re.compile(r'\bid="(blk[^"]+)"')
_H1 = re.compile(r"<h1\s+id=\"([^\"]+)\"[^>]*>(.*?)</h1>", re.DOTALL | re.IGNORECASE)

_REPO_TO_H1 = {"client": "客户端", "server": "服务端"}


def strip_merge_location_paragraphs(xml: str) -> str:
    """Remove 【合并位置】 hint paragraphs; must not appear in published doc body."""
    return _MERGE_PARA.sub("", xml).strip()


def _plain_heading(inner: str) -> str:
    text = re.sub(r"<[^>]+>", "", inner)
    text = text.replace(TITLE_MARKER, "").strip()
    return text


def _fetch_content(doc_token: str, *, scope: str | None = None, start_block_id: str | None = None) -> str:
    cmd = [
        "lark-cli",
        "docs",
        "+fetch",
        "--api-version",
        "v2",
        "--doc",
        doc_token,
        "--detail",
        "with-ids",
        "--as",
        "user",
        "--format",
        "json",
    ]
    if scope:
        cmd.extend(["--scope", scope])
        if scope == "outline":
            cmd.extend(["--max-depth", "3"])
    if start_block_id:
        cmd.extend(["--start-block-id", start_block_id])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=lark_cli_subprocess_env(),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "docs +fetch failed").strip())
    payload = json.loads(result.stdout)
    doc = payload.get("data", {}).get("document", payload.get("document", {}))
    return doc.get("content") or ""


def _parse_h1_outline(content: str) -> list[tuple[str, str]]:
    """Return (plain title, block_id) for each h1 in document order."""
    out: list[tuple[str, str]] = []
    for m in _H1.finditer(content):
        out.append((_plain_heading(m.group(2)), m.group(1)))
    return out


def _last_block_id_in_xml(content: str) -> str | None:
    ids = _BLOCK_ID.findall(content)
    return ids[-1] if ids else None


def resolve_section_end_anchor(doc_token: str, repo: str) -> str | None:
    """
    Block id after which to insert draft for mode A (h1 客户端 / 服务端).
    Returns None if outline has no matching h1 or fetch fails.
    """
    h1_label = _REPO_TO_H1.get(repo)
    if not h1_label:
        return None
    try:
        outline = _fetch_content(doc_token, scope="outline")
    except (RuntimeError, json.JSONDecodeError):
        return None
    h1s = _parse_h1_outline(outline)
    section_start: str | None = None
    for title, block_id in h1s:
        if title == h1_label:
            section_start = block_id
            break
    if not section_start:
        return None
    try:
        section = _fetch_content(doc_token, scope="section", start_block_id=section_start)
    except (RuntimeError, json.JSONDecodeError):
        return None
    return _last_block_id_in_xml(section) or section_start


def placement_for_repo(doc_token: str, repo: str) -> dict[str, Any]:
    anchor = resolve_section_end_anchor(doc_token, repo)
    if anchor:
        return {
            "command": "block_insert_after",
            "block_id": anchor,
            "insert_mode": "section_end",
            "section_h1": _REPO_TO_H1.get(repo),
        }
    return {
        "command": "append",
        "block_id": None,
        "insert_mode": "document_end",
        "section_h1": None,
    }
