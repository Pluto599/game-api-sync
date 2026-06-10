#!/usr/bin/env python3
"""Compare Feishu ApiSnapshot vs code by section, direction, and field-level types."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from compare_targets import resolve_compare_targets, scope_type_names_from_code
from extract_code import extract_from_sources, _normalize_type
from message_aliases import load_aliases_for_compare, resolve_code_name


def _message_name_from_raw(raw: str) -> str | None:
    m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*\{", raw.strip())
    return m.group(1) if m else None


def _doc_messages(
    snapshot: dict[str, Any],
    repo: str,
    *,
    target: str | None = None,
) -> list[dict[str, Any]]:
    """Messages from snapshot structs, filtered by repo direction and optional target."""
    repo_dir = "client" if repo == "client" else "server"
    parts = ("api_docs", "type_constraints")
    if target:
        parts = (target,)
    out: list[dict[str, Any]] = []
    for part in parts:
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
    index: dict[str, dict] = {}
    for msg in code.get("messages", []):
        key = _message_key(msg.get("section") or msg["name"], msg["direction"], msg["name"])
        index[key] = msg
        index[msg["name"]] = msg
    return index


def _find_code_message(
    dm: dict[str, Any],
    code_index: dict[str, dict],
    *,
    module: str,
    aliases: dict[str, dict[str, str]],
) -> tuple[dict | None, str | None]:
    """Match doc block to code; return (message, matched_via)."""
    name = dm.get("name") or ""
    section = dm.get("section") or ""

    cm = code_index.get(_message_key(section, dm["direction"], name))
    if cm:
        return cm, "exact_key"
    if name:
        cm = code_index.get(name)
        if cm:
            return cm, "name"

    alias_target = resolve_code_name(
        module, doc_name=name, section=section, aliases=aliases
    )
    if alias_target:
        cm = code_index.get(alias_target)
        if cm:
            return cm, "alias"

    for key in (section, name):
        if not key:
            continue
        alias_target = resolve_code_name(
            module, doc_name=key, section=key, aliases=aliases
        )
        if alias_target:
            cm = code_index.get(alias_target)
            if cm:
                return cm, "alias"

    return None, None


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
            optional_mismatch.append(
                f"`{n}`: optional 文档={df.get('optional')} 代码={cf.get('optional')}"
            )
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


def _compare_enums(
    doc_enums: list[dict],
    code_enums: list[dict],
    *,
    scope_type_names: set[str] | None = None,
    include_missing_in_doc: bool = True,
) -> list[dict[str, Any]]:
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
    doc_enum_names = {e.get("name") for e in doc_enums if e.get("name")}
    for name in sorted(set(code_by_name) - doc_enum_names):
        if scope_type_names is not None and name not in scope_type_names:
            continue
        if not include_missing_in_doc:
            continue
        issues.append({"enum": name, "kind": "missing_in_doc"})
    return issues


def _compare_interfaces(
    doc_enums: list[dict],
    code_interfaces: list[dict],
    *,
    scope_type_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Interfaces are documented in type_constraints; match by name against doc enums/types."""
    code_by_name = {i["name"]: i for i in code_interfaces}
    doc_names = {e.get("name") for e in doc_enums if e.get("name")}
    issues: list[dict[str, Any]] = []
    for name in sorted(set(code_by_name) - doc_names):
        if scope_type_names is not None and name not in scope_type_names:
            continue
        issues.append({"enum": name, "kind": "missing_in_doc", "type_kind": "interface"})
    return issues


def _compare_network_constants(
    doc_enums: list[dict],
    code: dict[str, Any],
) -> list[str]:
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


def _doc_enums_for_target(snapshot: dict[str, Any], target: str | None) -> list[dict]:
    out: list[dict] = []
    parts = (target,) if target else ("api_docs", "type_constraints")
    for part in parts:
        block = snapshot.get(part)
        if block:
            out.extend(block.get("enums", []))
    return out


def compare_snapshot_to_code(
    snapshot: dict[str, Any],
    files: dict[str, str],
    *,
    module: str,
    repo: str,
    report_title: str | None = None,
    target: str | None = None,
    scope_type_names: set[str] | None = None,
    aliases: dict[str, dict[str, str]] | None = None,
    registry_modules: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    aliases = (
        aliases
        if aliases is not None
        else load_aliases_for_compare(repo_root=repo_root, files=files)
    )
    code = extract_from_sources(files, repo=repo)
    if scope_type_names is None:
        scope_type_names = scope_type_names_from_code(code)

    doc_msgs = _doc_messages(snapshot, repo, target=target)
    code_index = _index_code_messages(code)

    message_results: list[dict[str, Any]] = []
    defects: list[str] = []
    ignored_out_of_scope: list[str] = []

    for dm in doc_msgs:
        name = dm.get("name") or ""
        cm, matched_via = _find_code_message(
            dm, code_index, module=module, aliases=aliases
        )
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
        row: dict[str, Any] = {
            "message": cm["name"],
            "section": dm["section"],
            "direction": dm["direction"],
            "status": status,
            "file": cm.get("file"),
            **diff,
        }
        if matched_via == "alias":
            row["matched_via"] = "alias"
            row["doc_title"] = name or dm["section"]
        message_results.append(row)

    matched_code_names: set[str] = set()
    for dm in doc_msgs:
        cm, _ = _find_code_message(dm, code_index, module=module, aliases=aliases)
        if cm:
            matched_code_names.add(cm["name"])

    compare_target = target or "api_docs"
    if compare_target == "api_docs":
        for msg in code.get("messages", []):
            if msg["name"] in matched_code_names:
                continue
            if scope_type_names is not None and msg["name"] not in scope_type_names:
                ignored_out_of_scope.append(msg["name"])
                continue
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

    doc_enums = _doc_enums_for_target(snapshot, target)
    enum_issues: list[dict[str, Any]] = []
    if compare_target == "type_constraints":
        enum_issues = _compare_enums(
            doc_enums,
            code.get("enums", []),
            scope_type_names=scope_type_names,
            include_missing_in_doc=True,
        )
        enum_issues.extend(
            _compare_interfaces(
                doc_enums,
                code.get("interfaces", []),
                scope_type_names=scope_type_names,
            )
        )
    elif compare_target == "api_docs":
        enum_issues = _compare_enums(
            doc_enums,
            code.get("enums", []),
            scope_type_names=scope_type_names,
            include_missing_in_doc=False,
        )
    for ei in enum_issues:
        if ei["kind"] == "missing_in_code":
            defects.append(f"文档枚举 `{ei['enum']}` 代码未找到")
        elif ei["kind"] == "missing_in_doc":
            defects.append(f"代码枚举 `{ei['enum']}` 文档未描述")

    network_notes: list[str] = []
    if module in ("网络相关", "联机大厅"):
        network_notes = _compare_network_constants(doc_enums, code)

    target_note = f"`{target}`" if target else "api_docs + type_constraints"
    lines = [
        report_title or f"# API 对比报告：{module}",
        "",
        f"- 仓库：`{repo}`（比对 **{repo}** 方向文档块与代码）",
        f"- 对比目标：{target_note}",
        f"- 文件数：{len(files)}",
        f"- 文档消息块：{len(doc_msgs)}",
        f"- 代码消息类型：{len(code.get('messages', []))}",
        f"- scope 内类型数：{len(scope_type_names)}",
        "",
    ]
    if ignored_out_of_scope:
        lines.append(
            f"- 已忽略 scope 外代码类型：{len(ignored_out_of_scope)} 个（见附录）"
        )
        lines.append("")

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
    lines.append("| 章节 | 方向 | 消息 | 状态 | 匹配 | 缺代码字段 | 缺文档字段 | 类型不一致 |")
    lines.append("|------|------|------|------|------|------------|------------|------------|")
    for r in message_results:
        via = r.get("matched_via") or ""
        lines.append(
            f"| {r.get('section','')} | {r.get('direction','')} | {r.get('message','')} | "
            f"{r.get('status','')} | {via} | "
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

    if ignored_out_of_scope:
        lines.append("## 附录：scope 外已忽略代码类型\n")
        for n in sorted(ignored_out_of_scope)[:50]:
            lines.append(f"- `{n}`")
        if len(ignored_out_of_scope) > 50:
            lines.append(f"- … 另有 {len(ignored_out_of_scope) - 50} 个")
        lines.append("")

    lines.append("## 扫描文件\n")
    for p in sorted(files):
        lines.append(f"- `{p}`")

    return {
        "ok": True,
        "module": module,
        "repo": repo,
        "target": target,
        "defects": defects,
        "message_results": message_results,
        "enum_issues": enum_issues,
        "network_notes": network_notes,
        "ignored_out_of_scope": ignored_out_of_scope,
        "report_md": "\n".join(lines),
    }


def compare_module_all_targets(
    snapshot: dict[str, Any],
    files: dict[str, str],
    *,
    module: str,
    repo: str,
    registry_modules: dict[str, Any] | None = None,
    explicit_target: str | None = None,
    scope_type_names: set[str] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Run compare for each resolved target; merge reports."""
    targets = resolve_compare_targets(
        snapshot, registry_modules, module, explicit_target=explicit_target
    )
    code = extract_from_sources(files, repo=repo)
    scope = scope_type_names if scope_type_names is not None else scope_type_names_from_code(code)
    aliases = load_aliases_for_compare(repo_root=repo_root, files=files)

    parts: list[dict[str, Any]] = []
    all_defects: list[str] = []
    for t in targets:
        tgt = t["target"]
        r = compare_snapshot_to_code(
            snapshot,
            files,
            module=module,
            repo=repo,
            target=tgt,
            scope_type_names=scope,
            aliases=aliases,
            registry_modules=registry_modules,
            report_title=f"## 对比目标：`{tgt}`（{t['reason']}）",
        )
        parts.append(r)
        all_defects.extend(r["defects"])

    if len(parts) == 1:
        parts[0]["compare_targets"] = targets
        return parts[0]

    md_parts = [f"# API 对比报告：{module}", ""]
    for p in parts:
        md_parts.append(p["report_md"])
        md_parts.append("")
    return {
        "ok": True,
        "module": module,
        "repo": repo,
        "compare_targets": targets,
        "defects": all_defects,
        "parts": parts,
        "report_md": "\n".join(md_parts),
    }


def main() -> None:
    if len(sys.argv) < 4:
        print(
            "Usage: diff_api.py <snapshot.json> <repo> <files.json> [repo_root]",
            file=sys.stderr,
        )
        sys.exit(1)
    snap_path = Path(sys.argv[1])
    repo = sys.argv[2]
    files_path = Path(sys.argv[3])
    repo_root = Path(sys.argv[4]) if len(sys.argv) > 4 else Path.cwd()
    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    payload = json.loads(files_path.read_text(encoding="utf-8"))
    module = snapshot.get("module", "unknown")
    files: dict[str, str] = payload.get("files", payload)
    result = compare_module_all_targets(
        snapshot, files, module=module, repo=repo, repo_root=repo_root
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
