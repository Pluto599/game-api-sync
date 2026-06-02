#!/usr/bin/env python3
"""Compare Feishu ApiSnapshot vs code by section, direction, and field-level types."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from extract_code import extract_from_sources, _normalize_type


def _message_name_from_raw(raw: str) -> str | None:
    m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{", raw.strip())
    return m.group(1) if m else None


def _doc_messages(snapshot: dict[str, Any], repo: str) -> list[dict[str, Any]]:
    """Messages from api_docs + type_constraints structs, filtered by repo direction."""
    repo_dir = "client" if repo == "client" else "server"
    out: list[dict[str, Any]] = []
    for part in ("api_docs", "type_constraints"):
        block = snapshot.get(part)
        if not block:
            continue
        for st in block.get("structs", []):
            direction = st.get("direction") or "unknown"
            if direction not in ("unknown", repo_dir):
                continue
            raw = st.get("raw_code") or ""
            name = st.get("name") or _message_name_from_raw(raw)
            fields = []
            for f in st.get("fields", []):
                fields.append(
                    {
                        "name": f.get("name", ""),
                        "type": _normalize_type(f.get("type", "")),
                        "optional": bool(f.get("optional")),
                    }
                )
            if not fields and not name:
                continue
            key = _message_key(st.get("section") or "", direction, name or "")
            out.append(
                {
                    "key": key,
                    "section": st.get("section") or "",
                    "direction": direction,
                    "name": name or key,
                    "fields": fields,
                    "source": part,
                }
            )
    return out


def _message_key(section: str, direction: str, name: str) -> str:
    return f"{section}::{direction}::{name}"


def _index_code_messages(code: dict[str, Any]) -> dict[str, dict]:
    by_name: dict[str, list[dict]] = {}
    for msg in code.get("messages", []):
        by_name.setdefault(msg["name"], []).append(msg)
    index: dict[str, dict] = {}
    for msg in code.get("messages", []):
        key = _message_key(msg.get("section") or msg["name"], msg["direction"], msg["name"])
        index[key] = msg
        # also allow match by message name only when section differs
        index[msg["name"]] = msg
    return index


def _field_map(fields: list[dict]) -> dict[str, dict]:
    return {f["name"]: f for f in fields if f.get("name")}


def _compare_field_sets(
    doc_fields: list[dict],
    code_fields: list[dict],
) -> dict[str, Any]:
    dmap = _field_map(doc_fields)
    cmap = _field_map(code_fields)
    doc_names = set(dmap)
    code_names = set(cmap)
    missing_in_code = sorted(doc_names - code_names)
    missing_in_doc = sorted(code_names - doc_names)
    type_mismatch: list[str] = []
    optional_mismatch: list[str] = []
    for n in sorted(doc_names & code_names):
        df, cf = dmap[n], cmap[n]
        if df["type"] and cf["type"] and df["type"] != cf["type"]:
            if not _types_compatible(df["type"], cf["type"]):
                type_mismatch.append(f"`{n}`: 文档 `{df['type']}` vs 代码 `{cf['type']}`")
        if df.get("optional") != cf.get("optional"):
            optional_mismatch.append(f"`{n}`: optional 文档={df.get('optional')} 代码={cf.get('optional')}")
    return {
        "missing_in_code": missing_in_code,
        "missing_in_doc": missing_in_doc,
        "type_mismatch": type_mismatch,
        "optional_mismatch": optional_mismatch,
    }


def _types_compatible(a: str, b: str) -> bool:
    if a == b:
        return True
    pair = {a, b}
    if pair <= {"int32", "number"}:
        return True
    if pair <= {"uint32", "number"}:
        return True
    return False


def _compare_enums(doc_enums: list[dict], code_enums: list[dict]) -> list[dict[str, Any]]:
    code_by_name = {e["name"]: e for e in code_enums}
    issues: list[dict[str, Any]] = []
    for de in doc_enums:
        name = de.get("name")
        if not name:
            continue
        ce = code_by_name.get(name)
        if not ce:
            issues.append({"enum": name, "kind": "missing_in_code"})
            continue
        dmem = {m["name"]: m.get("value", "") for m in de.get("members", [])}
        cmem = {m["name"]: m.get("value", "") for m in ce.get("members", [])}
        if set(dmem) != set(cmem):
            issues.append(
                {
                    "enum": name,
                    "kind": "member_set",
                    "doc_only": sorted(set(dmem) - set(cmem)),
                    "code_only": sorted(set(cmem) - set(dmem)),
                }
            )
        else:
            for k in dmem:
                if dmem[k] and cmem[k] and dmem[k] != cmem[k]:
                    issues.append(
                        {
                            "enum": name,
                            "kind": "value_mismatch",
                            "member": k,
                            "doc": dmem[k],
                            "code": cmem[k],
                        }
                    )
    for name in sorted(set(code_by_name) - {e.get("name") for e in doc_enums if e.get("name")}):
        issues.append({"enum": name, "kind": "missing_in_doc"})
    return issues


def _compare_network_constants(
    doc_enums: list[dict],
    code: dict[str, Any],
) -> list[str]:
    """Align PacketType / MessageId style enums and consts for 网络相关."""
    lines: list[str] = []
    code_const = {c["name"]: c["value"] for c in code.get("constants", [])}
    for de in doc_enums:
        ename = de.get("name") or ""
        if not re.search(r"packet|message|msg|opcode", ename, re.I):
            continue
        cenum = next((e for e in code.get("enums", []) if e["name"] == ename), None)
        if not cenum:
            lines.append(f"枚举 `{ename}` 在代码中未找到同名定义")
            continue
        dmem = {m["name"]: m.get("value", "") for m in de.get("members", [])}
        cmem = {m["name"]: m.get("value", "") for m in cenum.get("members", [])}
        for k, v in dmem.items():
            if k in cmem and v and cmem[k] and v != cmem[k]:
                lines.append(f"`{ename}.{k}`: 文档={v} 代码={cmem[k]}")
    for cname, cval in sorted(code_const.items()):
        if re.search(r"MSG_|PACKET_|OPCODE_", cname):
            lines.append(f"代码常量 `{cname}={cval}`（请与文档 PacketType/MessageId 核对）")
    return lines


def compare_snapshot_to_code(
    snapshot: dict[str, Any],
    files: dict[str, str],
    *,
    module: str,
    repo: str,
    report_title: str | None = None,
) -> dict[str, Any]:
    code = extract_from_sources(files, repo=repo)
    doc_msgs = _doc_messages(snapshot, repo)
    code_index = _index_code_messages(code)

    message_results: list[dict[str, Any]] = []
    defects: list[str] = []

    for dm in doc_msgs:
        name = dm.get("name") or ""
        cm = code_index.get(_message_key(dm["section"], dm["direction"], name))
        if not cm and name:
            cm = code_index.get(name)
        if not cm:
            message_results.append(
                {
                    "message": name or dm["key"],
                    "section": dm["section"],
                    "direction": dm["direction"],
                    "status": "missing_in_code",
                    "doc_fields": [f["name"] for f in dm["fields"]],
                }
            )
            defects.append(f"文档消息 `{name or dm['key']}` 在代码中未找到对应类型")
            continue
        diff = _compare_field_sets(dm["fields"], cm["fields"])
        status = "ok"
        if any(
            diff[k]
            for k in ("missing_in_code", "missing_in_doc", "type_mismatch", "optional_mismatch")
        ):
            status = "diff"
            if diff["missing_in_code"]:
                defects.append(
                    f"`{name}` 缺字段 {len(diff['missing_in_code'])} 个（文档有/代码无）"
                )
            if diff["missing_in_doc"]:
                defects.append(
                    f"`{name}` 多字段 {len(diff['missing_in_doc'])} 个（代码有/文档无）"
                )
            if diff["type_mismatch"]:
                defects.append(f"`{name}` 类型不一致 {len(diff['type_mismatch'])} 处")
        message_results.append(
            {
                "message": name,
                "section": dm["section"],
                "direction": dm["direction"],
                "status": status,
                "file": cm.get("file"),
                **diff,
            }
        )

    # code messages not matched from doc
    matched_code_names: set[str] = set()
    for dm in doc_msgs:
        cm = code_index.get(dm.get("name") or "")
        if cm:
            matched_code_names.add(cm["name"])
    for msg in code.get("messages", []):
        if msg["name"] not in matched_code_names:
            message_results.append(
                {
                    "message": msg["name"],
                    "section": msg.get("section"),
                    "direction": msg["direction"],
                    "status": "missing_in_doc",
                    "code_fields": [f["name"] for f in msg["fields"]],
                }
            )
            defects.append(f"代码类型 `{msg['name']}` 在文档（同方向）中未描述")

    doc_enums: list[dict] = []
    for part in ("api_docs", "type_constraints"):
        block = snapshot.get(part)
        if block:
            doc_enums.extend(block.get("enums", []))
    enum_issues = _compare_enums(doc_enums, code.get("enums", []))
    for ei in enum_issues:
        if ei["kind"] == "missing_in_code":
            defects.append(f"文档枚举 `{ei['enum']}` 代码未找到")
        elif ei["kind"] == "missing_in_doc":
            defects.append(f"代码枚举 `{ei['enum']}` 文档未描述")

    network_notes: list[str] = []
    if module in ("网络相关", "联机大厅"):
        network_notes = _compare_network_constants(doc_enums, code)

    lines = [
        report_title or f"# API 对比报告：{module}",
        "",
        f"- 仓库：`{repo}`（比对 **{repo}** 方向文档块与代码）",
        f"- 文件数：{len(files)}",
        f"- 文档消息块：{len(doc_msgs)}",
        f"- 代码消息类型：{len(code.get('messages', []))}",
        "",
    ]
    if not defects and not enum_issues and not network_notes:
        lines.append("## 结论\n\n未发现 section/方向/字段级差异。")
    else:
        lines.append("## 结论\n")
        for d in defects[:30]:
            lines.append(f"- **缺陷**：{d}")
        if len(defects) > 30:
            lines.append(f"- … 另有 {len(defects) - 30} 条")
        lines.append("")

    lines.append("## 消息级对比\n")
    lines.append("| 章节 | 方向 | 消息 | 状态 | 缺代码字段 | 缺文档字段 | 类型不一致 |")
    lines.append("|------|------|------|------|------------|------------|------------|")
    for r in message_results:
        lines.append(
            f"| {r.get('section','')} | {r.get('direction','')} | {r.get('message','')} | "
            f"{r.get('status','')} | "
            f"{len(r.get('missing_in_code') or [])} | "
            f"{len(r.get('missing_in_doc') or [])} | "
            f"{len(r.get('type_mismatch') or [])} |"
        )
    lines.append("")

    for r in message_results:
        if r.get("status") != "diff":
            continue
        lines.append(f"### {r.get('message')} ({r.get('section')} / {r.get('direction')})\n")
        if r.get("missing_in_code"):
            lines.append("**文档有 / 代码无**：" + ", ".join(f"`{x}`" for x in r["missing_in_code"]))
        if r.get("missing_in_doc"):
            lines.append("**代码有 / 文档无**：" + ", ".join(f"`{x}`" for x in r["missing_in_doc"]))
        for t in r.get("type_mismatch") or []:
            lines.append(f"- {t}")
        lines.append("")

    if enum_issues:
        lines.append("## 枚举对比\n")
        for ei in enum_issues:
            lines.append(f"- {json.dumps(ei, ensure_ascii=False)}")
        lines.append("")

    if network_notes:
        lines.append("## 网络相关（PacketType / 常量提示）\n")
        for n in network_notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("## 扫描文件\n")
    for p in sorted(files):
        lines.append(f"- `{p}`")

    return {
        "ok": True,
        "module": module,
        "repo": repo,
        "defects": defects,
        "message_results": message_results,
        "enum_issues": enum_issues,
        "network_notes": network_notes,
        "report_md": "\n".join(lines),
    }


def main() -> None:
    if len(sys.argv) < 4:
        print(
            "Usage: diff_api.py <snapshot.json> <repo> <files.json>",
            file=sys.stderr,
        )
        sys.exit(1)
    snap_path = Path(sys.argv[1])
    repo = sys.argv[2]
    files_path = Path(sys.argv[3])
    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    payload = json.loads(files_path.read_text(encoding="utf-8"))
    module = snapshot.get("module", "unknown")
    files: dict[str, str] = payload.get("files", payload)
    result = compare_snapshot_to_code(snapshot, files, module=module, repo=repo)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
