#!/usr/bin/env python3
"""Generate DocxXML drafts from code extract + compare diff (feishu-doc-write-format.md)."""

from __future__ import annotations

import html
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


def _interface_to_pseudo_ts(iface: dict) -> str:
    members = iface.get("members") or []
    body = "; ".join(f"{m['name']}()" for m in members)
    return f"interface {iface['name']} {{ {body}; }}"


def snapshot_uses_mode_a(snapshot: dict[str, Any], target: str = "api_docs") -> bool:
    block = snapshot.get(target) or {}
    for st in block.get("structs", []):
        d = st.get("direction")
        if d in ("client", "server"):
            return True
    for rb in block.get("raw_blocks", []):
        text = (rb.get("text") or rb.get("code") or "")
        if "客户端" in text or "服务端" in text:
            return True
    return False


def _norm_path(path: str) -> str:
    return path.replace("\\", "/")


def _in_changed_paths(item: dict[str, Any], changed_paths: set[str] | None) -> bool:
    if changed_paths is None:
        return True
    if not changed_paths:
        return False
    return _norm_path(item.get("file") or "") in changed_paths


def _compare_parts(compare_result: dict[str, Any]) -> list[dict[str, Any]]:
    if compare_result.get("parts"):
        return list(compare_result["parts"])
    return [compare_result]


def _items_to_sync(
    compare_result: dict[str, Any],
    code: dict[str, Any],
    *,
    target: str,
    changed_paths: set[str] | None = None,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Pick items to write back by document target:
    - api_docs: struct/class messages only
    - type_constraints: enums and interfaces only
    """
    sync_msgs: list[dict] = []
    sync_enums: list[dict] = []
    sync_ifaces: list[dict] = []
    code_msgs = {m["name"]: m for m in code.get("messages", [])}
    code_enums = {e["name"]: e for e in code.get("enums", [])}
    code_ifaces = {i["name"]: i for i in code.get("interfaces", [])}

    part = _compare_parts(compare_result)[0]
    message_results = part.get("message_results") or []
    enum_issues = part.get("enum_issues") or []

    if target == "api_docs":
        seen_msg: set[str] = set()
        for r in message_results:
            if r.get("status") == "missing_in_doc":
                name = r.get("message")
                if name and name in code_msgs and name not in seen_msg:
                    msg = code_msgs[name]
                    if _in_changed_paths(msg, changed_paths):
                        sync_msgs.append(msg)
                        seen_msg.add(name)
            elif r.get("status") == "diff" and r.get("missing_in_doc"):
                name = r.get("message")
                if name and name in code_msgs and name not in seen_msg:
                    msg = code_msgs[name]
                    if _in_changed_paths(msg, changed_paths):
                        sync_msgs.append(msg)
                        seen_msg.add(name)

    if target == "type_constraints":
        seen_en: set[str] = set()
        for ei in enum_issues:
            if ei.get("kind") != "missing_in_doc":
                continue
            if ei.get("type_kind") == "interface":
                name = ei.get("enum")
                if name and name in code_ifaces and name not in seen_en:
                    iface = code_ifaces[name]
                    if _in_changed_paths(iface, changed_paths):
                        sync_ifaces.append(iface)
                        seen_en.add(name)
                continue
            name = ei.get("enum")
            if name and name in code_enums and name not in seen_en:
                en = code_enums[name]
                if _in_changed_paths(en, changed_paths):
                    sync_enums.append(en)
                    seen_en.add(name)

    return sync_msgs, sync_enums, sync_ifaces


def build_docx_draft(
    *,
    snapshot: dict[str, Any],
    compare_result: dict[str, Any],
    files: dict[str, str],
    repo: str,
    target: str = "api_docs",
    marker: str = CI_MARKER,
    changed_paths: list[str] | None = None,
) -> str:
    if changed_paths is None:
        changed_set = None
        draft_files = files
    else:
        changed_set = {_norm_path(p) for p in changed_paths}
        draft_files = {
            k: v for k, v in files.items() if _norm_path(k) in changed_set
        }
    code = extract_from_sources(draft_files, repo=repo)
    sync_msgs, sync_enums, sync_ifaces = _items_to_sync(
        compare_result, code, target=target, changed_paths=changed_set
    )
    mode_a = snapshot_uses_mode_a(snapshot, target)
    parts: list[str] = []

    if target == "type_constraints":
        tc_blocks: list[str] = []
        if sync_enums:
            tc_blocks.append("\n".join(_enum_to_pseudo_ts(e) for e in sync_enums))
        if sync_ifaces:
            tc_blocks.append("\n".join(_interface_to_pseudo_ts(i) for i in sync_ifaces))
        if tc_blocks:
            parts.append(f"<h1>类型补充{marker}</h1>")
            parts.append(
                f'<pre lang="TypeScript"><code>{html.escape(chr(10).join(tc_blocks))}</code></pre>'
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


def sync_targets_for_module(
    snapshot: dict[str, Any],
    registry_module: dict[str, Any] | None,
    *,
    module_map_entry: dict[str, Any] | None = None,
) -> list[str]:
    """
    Feishu doc targets for this module CI sync.

    - struct/class → api_docs (modules with api_docs_obj)
    - enum/interface → type_constraints on modules **without** api_docs_obj (e.g. 网络相关)

    Same changed file may run under 商店 (api_docs) and 网络相关 (type_constraints).

    Override: module_map.<名>._sync_targets: [api_docs, type_constraints]
    """
    mod_info = registry_module or {}
    map_entry = module_map_entry or {}

    override = map_entry.get("_sync_targets")
    if override:
        allowed = {str(t) for t in override}
        out: list[str] = []
        if "api_docs" in allowed and mod_info.get("api_docs_obj"):
            out.append("api_docs")
        if "type_constraints" in allowed and mod_info.get("type_constraints_obj"):
            out.append("type_constraints")
        return out

    has_api = bool(mod_info.get("api_docs_obj"))
    has_tc = bool(mod_info.get("type_constraints_obj"))
    targets: list[str] = []
    if has_api:
        targets.append("api_docs")
    if has_tc and not has_api:
        targets.append("type_constraints")
    return targets
