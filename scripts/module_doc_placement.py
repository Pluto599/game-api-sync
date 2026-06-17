#!/usr/bin/env python3
"""Feishu section anchors for module system-design docs (creator profile)."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from lark_cli_env import lark_cli_subprocess_env

LARK_PROFILE = "creator"

SECTION_OVERVIEW = "模块概览"
SECTION_LAYERS = "分层架构"
SECTION_FUNC = "功能接口"
SECTION_DATA = "数据接口"

SYSTEM_DESIGN_SECTIONS = (
    SECTION_OVERVIEW,
    SECTION_LAYERS,
    SECTION_FUNC,
    SECTION_DATA,
)

# Insert deltas bottom-up so earlier block ids stay valid.
SECTION_INSERT_ORDER = (
    SECTION_DATA,
    SECTION_FUNC,
    SECTION_LAYERS,
    SECTION_OVERVIEW,
)

_BLOCK_ID = re.compile(r'\bid="(blk[^"]+)"')
_H2 = re.compile(r'<h2\s+id="([^"]+)"[^>]*>(.*?)</h2>', re.DOTALL | re.IGNORECASE)
_H3 = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL | re.IGNORECASE)
_BOLD = re.compile(r"<b>([^<]+)</b>")


def _plain_heading(inner: str) -> str:
    text = re.sub(r"<[^>]+>", "", inner)
    return text.replace("（CI生成，待审查）", "").strip()


def fetch_doc_content(
    doc_token: str,
    *,
    scope: str | None = None,
    start_block_id: str | None = None,
) -> str:
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
            cmd.extend(["--max-depth", "4"])
    if start_block_id:
        cmd.extend(["--start-block-id", start_block_id])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=lark_cli_subprocess_env(profile=LARK_PROFILE),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "docs +fetch failed").strip())
    payload = json.loads(result.stdout)
    doc = payload.get("data", {}).get("document", payload.get("document", {}))
    return doc.get("content") or ""


def parse_h2_sections(content: str) -> list[tuple[str, str]]:
    """Return (plain h2 title, block_id) in document order."""
    out: list[tuple[str, str]] = []
    for m in _H2.finditer(content):
        out.append((_plain_heading(m.group(2)), m.group(1)))
    return out


def _last_block_id_in_xml(content: str) -> str | None:
    ids = _BLOCK_ID.findall(content)
    return ids[-1] if ids else None


def system_design_doc_is_empty(doc_token: str) -> bool:
    """True when sub-doc has no system-design section structure yet."""
    try:
        content = fetch_doc_content(doc_token, scope="outline")
    except (RuntimeError, json.JSONDecodeError, OSError):
        return True
    if not content.strip():
        return True
    h2s = parse_h2_sections(content)
    if not h2s:
        return True
    titles = {t for t, _ in h2s}
    return SECTION_OVERVIEW not in titles and not titles.intersection(set(SYSTEM_DESIGN_SECTIONS))


def resolve_section_insert_anchor(doc_token: str, section_title: str) -> str | None:
    """Block id after which to insert the next dated update under section_title."""
    try:
        outline = fetch_doc_content(doc_token, scope="outline")
    except (RuntimeError, json.JSONDecodeError, OSError):
        return None
    h2_block_id: str | None = None
    for title, block_id in parse_h2_sections(outline):
        if title == section_title:
            h2_block_id = block_id
            break
    if not h2_block_id:
        return None
    try:
        section = fetch_doc_content(
            doc_token, scope="section", start_block_id=h2_block_id
        )
    except (RuntimeError, json.JSONDecodeError, OSError):
        return h2_block_id
    return _last_block_id_in_xml(section) or h2_block_id


def document_end_anchor(doc_token: str) -> str | None:
    try:
        outline = fetch_doc_content(doc_token, scope="outline")
    except (RuntimeError, json.JSONDecodeError, OSError):
        return None
    return _last_block_id_in_xml(outline)


def fetch_section_content(doc_token: str, section_title: str) -> str:
    try:
        outline = fetch_doc_content(doc_token, scope="outline")
    except (RuntimeError, json.JSONDecodeError, OSError):
        return ""
    h2_block_id: str | None = None
    for title, block_id in parse_h2_sections(outline):
        if title == section_title:
            h2_block_id = block_id
            break
    if not h2_block_id:
        return ""
    try:
        return fetch_doc_content(
            doc_token, scope="section", start_block_id=h2_block_id
        )
    except (RuntimeError, json.JSONDecodeError, OSError):
        return ""


def _h3_label(fragment: str) -> str | None:
    m = _H3.search(fragment)
    return _plain_heading(m.group(1)) if m else None


def _last_dated_block(section_xml: str) -> str:
    matches = list(_H3.finditer(section_xml))
    if not matches:
        return ""
    return section_xml[matches[-1].start() :]


def _interface_names_from_html(xml: str) -> frozenset[str]:
    return frozenset(_BOLD.findall(xml))


def should_skip_section_insert(
    doc_token: str, section_title: str, fragment: str
) -> tuple[bool, str]:
    """
    Skip duplicate delta inserts:
    - 功能/数据接口：最近一次块已包含相同接口名集合
    - 其他章节：最近一次块与本次 h3 时间戳相同（同分钟重复跑）
    """
    section_xml = fetch_section_content(doc_token, section_title)
    if not section_xml.strip():
        return False, ""
    last_block = _last_dated_block(section_xml)
    if not last_block:
        return False, ""

    frag_names = _interface_names_from_html(fragment)
    last_names = _interface_names_from_html(last_block)
    if (
        section_title in (SECTION_FUNC, SECTION_DATA)
        and frag_names
        and frag_names == last_names
    ):
        return True, "duplicate_interface_names"

    frag_h3 = _h3_label(fragment)
    last_h3 = _h3_label(last_block)
    if frag_h3 and last_h3 and frag_h3 == last_h3:
        return True, "duplicate_timestamp"

    return False, ""


def update_system_design_doc(
    doc_token: str,
    *,
    mode: str,
    initial_docx: str | None = None,
    section_updates: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Write full skeleton or insert dated blocks under h2 sections."""
    if mode == "full":
        content = (initial_docx or "").strip()
        if not content:
            raise ValueError("initial_docx required for full mode")
        return _run_update(doc_token, command="append", content=content)

    updates = section_updates or {}
    if not updates:
        raise ValueError("section_updates required for delta mode")

    insert_results: list[dict[str, Any]] = []
    skipped_sections: list[dict[str, str]] = []
    for section in SECTION_INSERT_ORDER:
        fragment = updates.get(section)
        if not fragment or not fragment.strip():
            continue
        skip, reason = should_skip_section_insert(doc_token, section, fragment.strip())
        if skip:
            skipped_sections.append({"section": section, "reason": reason})
            continue
        anchor = resolve_section_insert_anchor(doc_token, section)
        if anchor:
            r = _run_update(
                doc_token,
                command="block_insert_after",
                content=fragment.strip(),
                block_id=anchor,
            )
            r["section"] = section
            r["insert_mode"] = "under_section"
            r["anchor_block_id"] = anchor
        else:
            wrapped = f"<h2>{section}</h2>{fragment.strip()}"
            end = document_end_anchor(doc_token)
            if end:
                r = _run_update(
                    doc_token,
                    command="block_insert_after",
                    content=wrapped,
                    block_id=end,
                )
                r["insert_mode"] = "new_section_at_end"
            else:
                r = _run_update(doc_token, command="append", content=wrapped)
                r["insert_mode"] = "append_new_section"
            r["section"] = section
        insert_results.append(r)

    if not insert_results:
        return {
            "ok": True,
            "doc_token": doc_token,
            "mode": "delta",
            "skipped": True,
            "reason": "all_sections_deduplicated",
            "sections_skipped": skipped_sections,
            "lark_profile": LARK_PROFILE,
        }

    out: dict[str, Any] = {
        "ok": True,
        "doc_token": doc_token,
        "mode": "delta",
        "sections_updated": [r["section"] for r in insert_results],
        "inserts": insert_results,
        "lark_profile": LARK_PROFILE,
    }
    if skipped_sections:
        out["sections_skipped"] = skipped_sections
    return out


def _run_update(
    doc_token: str,
    *,
    command: str,
    content: str,
    block_id: str | None = None,
) -> dict[str, Any]:
    cmd = [
        "lark-cli",
        "docs",
        "+update",
        "--api-version",
        "v2",
        "--doc",
        doc_token,
        "--command",
        command,
        "--content",
        content,
        "--as",
        "user",
    ]
    if block_id:
        cmd.extend(["--block-id", block_id])
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=lark_cli_subprocess_env(profile=LARK_PROFILE),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "docs +update failed").strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"raw": result.stdout.strip()}
    return {
        "ok": True,
        "doc_token": doc_token,
        "command": command,
        "lark_profile": LARK_PROFILE,
        "feishu": payload,
    }
