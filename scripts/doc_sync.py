#!/usr/bin/env python3
"""Append a pending-review callout draft to Feishu module docs via lark-cli."""

from __future__ import annotations

import html
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


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


def _build_callout_xml(
    *,
    module: str,
    repo: str,
    summary: str,
    files_changed: list[str],
) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary_esc = html.escape(summary.strip())
    files_html = ""
    if files_changed:
        items = "".join(f"<li>{html.escape(f)}</li>" for f in files_changed)
        files_html = f"<p><b>变更文件</b></p><ul>{items}</ul>"
    return (
        '<callout emoji="📝" background-color="light-yellow" border-color="yellow">'
        f"<p><b>【待审核】代码 → 文档同步草稿</b></p>"
        f"<p>模块：{html.escape(module)} | 仓库：{html.escape(repo)} | 时间：{ts}</p>"
        f"<p>{summary_esc}</p>"
        f"{files_html}"
        "<p><i>请负责人在飞书审阅后合并进正文，并删除本 callout。</i></p>"
        "</callout>"
    )


def sync_doc_draft(
    reg_path: Path,
    *,
    module: str,
    repo: str,
    summary: str,
    files_changed: list[str] | None = None,
    target: str = "api_docs",
) -> dict[str, Any]:
    reg = _load_registry(reg_path)
    doc_token = _resolve_doc_token(reg, module, target)
    content = _build_callout_xml(
        module=module,
        repo=repo,
        summary=summary,
        files_changed=files_changed or [],
    )
    result = subprocess.run(
        [
            "lark-cli",
            "docs",
            "+update",
            "--api-version",
            "v2",
            "--doc",
            doc_token,
            "--command",
            "append",
            "--content",
            content,
            "--as",
            "user",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
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
        )
    except (ValueError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
