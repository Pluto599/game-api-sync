#!/usr/bin/env python3
"""Compare Feishu ApiSnapshot cache vs posted source files; emit Markdown report."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from extract_code import extract_from_sources


def _doc_field_names(snapshot: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Collect fields from api_docs and type_constraints structs."""
    out: dict[str, list[dict[str, str]]] = {"api_docs": [], "type_constraints": []}
    for part in ("api_docs", "type_constraints"):
        block = snapshot.get(part)
        if not block:
            continue
        for st in block.get("structs", []):
            for f in st.get("fields", []):
                out[part].append(
                    {
                        "name": f.get("name", ""),
                        "type": f.get("type", ""),
                        "section": st.get("section") or "",
                    }
                )
    return out


def _all_doc_names(snapshot: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for part in _doc_field_names(snapshot).values():
        for f in part:
            if f["name"]:
                names.add(f["name"])
    return names


def _doc_enums(snapshot: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for part in ("api_docs", "type_constraints"):
        block = snapshot.get(part)
        if not block:
            continue
        for en in block.get("enums", []):
            if en.get("name"):
                names.add(en["name"])
    return names


def compare_snapshot_to_code(
    snapshot: dict[str, Any],
    files: dict[str, str],
    *,
    module: str,
    repo: str,
    report_title: str | None = None,
) -> dict[str, Any]:
    code = extract_from_sources(files)
    code_names = set(code["fields"])
    doc_names = _all_doc_names(snapshot)
    doc_enums = _doc_enums(snapshot)
    code_enums = set(code["enums"])

    doc_only = sorted(doc_names - code_names)
    code_only = sorted(code_names - doc_names)
    enum_doc_only = sorted(doc_enums - code_enums)
    enum_code_only = sorted(code_enums - doc_enums)

    defects: list[str] = []
    if doc_only:
        defects.append(f"文档有而代码未体现字段 {len(doc_only)} 个")
    if code_only:
        defects.append(f"代码有而文档未描述字段 {len(code_only)} 个")
    if enum_doc_only:
        defects.append(f"文档有而代码未体现枚举 {len(enum_doc_only)} 个")
    if enum_code_only:
        defects.append(f"代码有而文档未描述枚举 {len(enum_code_only)} 个")

    lines = [
        report_title or f"# API 对比报告：{module}",
        "",
        f"- 仓库侧：`{repo}`",
        f"- 比对文件数：{len(files)}",
        f"- 文档字段数：{len(doc_names)}",
        f"- 代码提取字段数：{len(code_names)}",
        "",
    ]
    if not defects:
        lines.append("## 结论\n\n未发现明显字段/枚举名差异（基于名称级粗对比）。")
    else:
        lines.append("## 结论\n")
        for d in defects:
            lines.append(f"- **缺陷**：{d}")
        lines.append("")

    if doc_only:
        lines.append("## 文档有 / 代码无（字段）\n")
        for n in doc_only:
            lines.append(f"- `{n}`")
        lines.append("")

    if code_only:
        lines.append("## 代码有 / 文档无（字段）\n")
        for n in code_only:
            lines.append(f"- `{n}`")
        lines.append("")

    if enum_doc_only:
        lines.append("## 文档有 / 代码无（枚举）\n")
        for n in enum_doc_only:
            lines.append(f"- `{n}`")
        lines.append("")

    if enum_code_only:
        lines.append("## 代码有 / 文档无（枚举）\n")
        for n in enum_code_only:
            lines.append(f"- `{n}`")
        lines.append("")

    lines.append("## 扫描文件\n")
    for p in sorted(files):
        lines.append(f"- `{p}`")

    report_md = "\n".join(lines)
    return {
        "ok": True,
        "module": module,
        "repo": repo,
        "defects": defects,
        "doc_only_fields": doc_only,
        "code_only_fields": code_only,
        "enum_doc_only": enum_doc_only,
        "enum_code_only": enum_code_only,
        "report_md": report_md,
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
