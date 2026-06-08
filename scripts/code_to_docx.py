#!/usr/bin/env python3
"""Generate DocxXML drafts from code extract + compare diff (feishu-doc-write-format.md)."""

from __future__ import annotations

import html
import re
from typing import Any

from extract_code import extract_from_sources

CI_MARKER = "（CI生成，待审查）"
AGENT_MARKER = "（agent生成，待审查）"


def _denormalize_type_for_doc(typ: str) -> str:
    t = (typ or "unknown").strip()
    if t in ("int32", "uint32", "int64", "uint64", "byte"):
        return "number"
    return t


def _fields_to_pseudo_ts(name: str, fields: list[dict]) -> str:
    lines = [f"{name}: {{"]
    for f in fields:
        opt = "?" if f.get("optional") else ""
        lines.append(f"  {f['name']}{opt}: {_denormalize_type_for_doc(f.get('type', ''))};")
    lines.append("};")
    return "\n".join(lines)


def _enum_to_pseudo_ts(en: dict) -> str:
    members = en.get("members") or []
    body = ", ".join(
        f"{m['name']}" + (f" = {m['value']}" if m.get("value") else "")
        for m in members
    )
    return f"enum {en['name']} {{ {body} }}"


def snapshot_uses_mode_a(snapshot: dict[str, Any], target: str = "api_docs") -> bool:
    block = snapshot.get(target) or {}
    for st in block.get("structs") or []:
        d = st.get("direction")
        if d in ("client", "server"):
            return True
    for rb in block.get("raw_blocks") or []:
        text = (rb.get("text") or rb.get("code") or "")
        if "客户端" in text or "服务端" in text:
            return True
    return False


def _items_to_sync(
    compare_result: dict[str, Any],
    code: dict[str, Any],
) -> tuple[list[dict], list[dict]]:
    """Messages/enums that are missing_in_doc or diff with missing_in_doc fields."""
    sync_msgs: list[dict] = []
    sync_enums: list[dict] = []
    code_msgs = {m["name"]: m for m in code.get("messages", [])}
    code_enums = {e["name"]: e for e in code.get("enums", [])}

    message_results = compare_result.get("message_results") or []
    if compare_result.get("parts"):
        message_results = []
        for p in compare_result["parts"]:
            message_results.extend(p.get("message_results") or [])

    seen_msg: set[str] = set()
    for r in message_results:
        if r.get("status") == "missing_in_doc":
            name = r.get("message")
            if name and name in code_msgs and name not in seen_msg:
                sync_msgs.append(code_msgs[name])
                seen_msg.add(name)
        elif r.get("status") == "diff" and r.get("missing_in_doc"):
            name = r.get("message")
            if name and name in code_msgs and name not in seen_msg:
                sync_msgs.append(code_msgs[name])
                seen_msg.add(name)

    enum_issues = compare_result.get("enum_issues") or []
    if compare_result.get("parts"):
        enum_issues = []
        for p in compare_result["parts"]:
            enum_issues.extend(p.get("enum_issues") or [])

    seen_en: set[str] = set()
    for ei in enum_issues:
        if ei.get("kind") == "missing_in_doc":
            name = ei.get("enum")
            if name and name in code_enums and name not in seen_en:
                sync_enums.append(code_enums[name])
                seen_en.add(name)

    if not sync_msgs and not sync_enums:
        for msg in code.get("messages", []):
            sync_msgs.append(msg)
        for en in code.get("enums", []):
            sync_enums.append(en)

    return sync_msgs, sync_enums


def build_docx_draft(
    *,
    snapshot: dict[str, Any],
    compare_result: dict[str, Any],
    files: dict[str, str],
    repo: str,
    target: str = "api_docs",
    marker: str = CI_MARKER,
) -> str:
    code = extract_from_sources(files, repo=repo)
    sync_msgs, sync_enums = _items_to_sync(compare_result, code)
    mode_a = snapshot_uses_mode_a(snapshot, target)
    parts: list[str] = []

    if target == "type_constraints":
        if sync_enums:
            enum_body = "\n".join(_enum_to_pseudo_ts(e) for e in sync_enums)
            parts.append(f"<h1>类型补充{marker}</h1>")
            parts.append(f'<pre lang="TypeScript"><code>{html.escape(enum_body)}</code></pre>')
        if sync_msgs:
            for msg in sync_msgs:
                body = _fields_to_pseudo_ts(msg["name"], msg.get("fields") or [])
                parts.append(f"<h1>{html.escape(msg['name'])}{marker}</h1>")
                parts.append(
                    f'<pre lang="TypeScript"><code>{html.escape(body)}</code></pre>'
                )
        return "".join(parts)

    if sync_enums and sync_msgs:
        topic = sync_msgs[0].get("section") or sync_msgs[0]["name"]
        h = "h2" if mode_a else "h1"
        parts.append(f"<{h}>{html.escape(str(topic))}{marker}</{h}>")
        enum_body = "\n".join(_enum_to_pseudo_ts(e) for e in sync_enums)
        parts.append(f'<pre lang="TypeScript"><code>{html.escape(enum_body)}</code></pre>')
        type_lines = [
            f"type {m['name']} = {_fields_to_pseudo_ts(m['name'], m.get('fields') or []).split(':', 1)[1].strip()};"
            for m in sync_msgs
        ]
        parts.append(
            f'<pre lang="TypeScript"><code>{html.escape(chr(10).join(type_lines))}</code></pre>'
        )
        return "".join(parts)

    for msg in sync_msgs:
        section = msg.get("section") or msg["name"]
        h = "h2" if mode_a else "h1"
        parts.append(f"<{h}>{html.escape(str(section))}{marker}</{h}>")
        caption = ""
        if not mode_a:
            cap = "客户端" if repo == "client" else "服务端"
            caption = f' caption="{cap}"'
        body = _fields_to_pseudo_ts(msg["name"], msg.get("fields") or [])
        parts.append(
            f'<pre lang="TypeScript"{caption}><code>{html.escape(body)}</code></pre>'
        )

    if sync_enums and not sync_msgs:
        h = "h2" if mode_a else "h1"
        parts.append(f"<{h}>枚举{marker}</{h}>")
        enum_body = "\n".join(_enum_to_pseudo_ts(e) for e in sync_enums)
        parts.append(f'<pre lang="TypeScript"><code>{html.escape(enum_body)}</code></pre>')

    return "".join(parts)


def infer_doc_sync_target(snapshot: dict[str, Any], registry_module: dict[str, Any] | None) -> str:
    from compare_targets import resolve_compare_targets

    mod = snapshot.get("module", "")
    targets = resolve_compare_targets(snapshot, None, mod)
    if registry_module:
        if registry_module.get("type_constraints_obj") and not registry_module.get("api_docs_obj"):
            return "type_constraints"
    if targets and targets[0]["target"] == "type_constraints":
        return "type_constraints"
    return "api_docs"
