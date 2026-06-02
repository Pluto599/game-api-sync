#!/usr/bin/env python3
"""Append agent-generated DocxXML to Feishu module docs (direct body, no callout)."""

from __future__ import annotations

import html
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from doc_placement import placement_for_repo, strip_merge_location_paragraphs
from lark_cli_env import lark_cli_subprocess_env

TITLE_MARKER = "（agent生成，待审查）"
_H_TAG = re.compile(r"(<(h[12])>)(.*?)(</\1>)", re.DOTALL)


def _load_registry(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _resolve_doc_token(reg: dict, module: str, target: str) -> str:
    modules: dict = reg.get("modules", {})
    if module not in modules:
        raise ValueError(f"unknown module: {module}")
    info = modules[module]
    token = info.get(f"{target}_obj") or info.get("api_docs_obj") or info.get(
        "type_constraints_obj"
    )
    if not token:
        raise ValueError(f"module '{module}' has no Feishu doc token for target '{target}'")
    return token


def mark_review_headings(xml: str) -> str:
    """Ensure each h1/h2 ends with TITLE_MARKER in the title text."""

    def repl(m: re.Match[str]) -> str:
        open_tag, _tag, inner, close_tag = m.group(1), m.group(2), m.group(3), m.group(4)
        text = inner.strip()
        if TITLE_MARKER in text:
            return m.group(0)
        return f"{open_tag}{text}{TITLE_MARKER}{close_tag}"

    return _H_TAG.sub(repl, xml)


def _build_body_xml(
    *,
    module: str,
    repo: str,
    summary: str,
    files_changed: list[str],
    docx_draft: str | None = None,
    section_insert: bool = False,
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    parts: list[str] = []
    if not section_insert:
        parts.append("<hr/>")

    if docx_draft and docx_draft.strip():
        draft = strip_merge_location_paragraphs(docx_draft.strip())
        parts.append(mark_review_headings(draft))
    else:
        parts.append(f"<h1>文档变更说明{TITLE_MARKER}</h1>")
        parts.append(
            f"<p>模块：{html.escape(module)} | 仓库：{html.escape(repo)} | 时间：{ts}</p>"
        )
        if summary.strip():
            parts.append(f"<p>{html.escape(summary.strip())}</p>")
        if files_changed:
            items = "".join(f"<li>{html.escape(f)}</li>" for f in files_changed)
            parts.append(f"<p><b>变更文件</b></p><ul>{items}</ul>")

    return "".join(parts)


def sync_doc_draft(
    reg_path: Path,
    *,
    module: str,
    repo: str,
    summary: str,
    files_changed: list[str] | None = None,
    target: str = "api_docs",
    docx_draft: str | None = None,
) -> dict[str, Any]:
    reg = _load_registry(reg_path)
    doc_token = _resolve_doc_token(reg, module, target)
    if not summary.strip() and not (docx_draft and docx_draft.strip()):
        raise ValueError("summary or docx_draft must be provided")
    place = placement_for_repo(doc_token, repo)
    section_insert = place["command"] == "block_insert_after"
    content = _build_body_xml(
        module=module,
        repo=repo,
        summary=summary,
        files_changed=files_changed or [],
        docx_draft=docx_draft,
        section_insert=section_insert,
    )
    update_cmd = [
        "lark-cli",
        "docs",
        "+update",
        "--api-version",
        "v2",
        "--doc",
        doc_token,
        "--command",
        place["command"],
        "--content",
        content,
        "--as",
        "user",
    ]
    if place.get("block_id"):
        update_cmd.extend(["--block-id", place["block_id"]])
    result = subprocess.run(
        update_cmd,
        capture_output=True,
        text=True,
        check=False,
        env=lark_cli_subprocess_env(),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "docs +update failed").strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"raw": result.stdout.strip()}
    return {
        "ok": True,
        "module": module,
        "repo": repo,
        "doc_token": doc_token,
        "target": target,
        "insert_mode": place.get("insert_mode"),
        "insert_after_block_id": place.get("block_id"),
        "section_h1": place.get("section_h1"),
        "feishu": payload,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: doc_sync.py <request.json> [registry.yaml]",
            file=sys.stderr,
        )
        sys.exit(1)
    req_path = Path(sys.argv[1])
    reg_path = Path(
        sys.argv[2] if len(sys.argv) > 2 else "/opt/api-sync/config/wiki-registry.yaml"
    )
    req = json.loads(req_path.read_text(encoding="utf-8"))
    try:
        out = sync_doc_draft(
            reg_path,
            module=req["module"],
            repo=req.get("repo", "client"),
            summary=req.get("summary", ""),
            files_changed=req.get("files_changed") or [],
            target=req.get("target", "api_docs"),
            docx_draft=req.get("docx_draft"),
        )
    except (ValueError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
