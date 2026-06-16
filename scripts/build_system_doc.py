#!/usr/bin/env python3
"""Build ModuleDocContext and DocxXML for module system-design docs."""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from extract_code import extract_from_sources, extract_type_comment
from module_doc_agent import enrich_context
from module_doc_layers import infer_module_layers

CI_MARKER = "（CI生成，待审查）"

_DIRECTION_LABEL = {
    "client": "客户端→服务端",
    "server": "服务端→客户端",
}


def system_doc_fingerprint(files: dict[str, str], repo: str) -> str:
    code = extract_from_sources(files, repo=repo)
    payload = {
        "messages": sorted(
            (m["name"], tuple((f["name"], f.get("type")) for f in m.get("fields") or []))
            for m in code.get("messages", [])
        ),
        "enums": sorted(
            (e["name"], tuple(m["name"] for m in e.get("members") or []))
            for e in code.get("enums", [])
        ),
        "interfaces": sorted(
            (i["name"], tuple(m["name"] for m in i.get("members") or []))
            for i in code.get("interfaces", [])
        ),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def build_module_doc_context(
    *,
    module: str,
    repo: str,
    registry: dict[str, Any],
    repo_root: Path,
    changed_paths: list[str],
    files: dict[str, str],
    mode: str,
) -> dict[str, Any]:
    code = extract_from_sources(files, repo=repo)
    mod_map = (registry.get("module_map") or {}).get(module) or {}
    mod_info = (registry.get("modules") or {}).get(module) or {}

    functional: list[dict[str, Any]] = []
    for msg in code.get("messages", []):
        path = msg.get("file") or ""
        text = files.get(path, "")
        comment = extract_type_comment(text, msg["name"], path=path) if text else None
        fields = [f["name"] for f in msg.get("fields") or []]
        functional.append(
            {
                "name": msg["name"],
                "direction": _DIRECTION_LABEL.get(repo, repo),
                "fields_summary": ", ".join(fields),
                "source_comment": comment,
                "file": path,
            }
        )

    data: list[dict[str, Any]] = []
    for en in code.get("enums", []):
        path = en.get("file") or ""
        text = files.get(path, "")
        comment = extract_type_comment(text, en["name"], path=path) if text else None
        members = [m["name"] for m in en.get("members") or []]
        data.append(
            {
                "kind": "enum",
                "name": en["name"],
                "members": members,
                "source_comment": comment,
                "file": path,
            }
        )
    for iface in code.get("interfaces", []):
        path = iface.get("file") or ""
        text = files.get(path, "")
        comment = extract_type_comment(text, iface["name"], path=path) if text else None
        members = [m["name"] for m in iface.get("members") or []]
        data.append(
            {
                "kind": "interface",
                "name": iface["name"],
                "members": members,
                "source_comment": comment,
                "file": path,
            }
        )

    layer_info = infer_module_layers(
        module=module,
        repo=repo,
        registry=registry,
        repo_root=repo_root,
        changed_paths=changed_paths,
    )

    ctx: dict[str, Any] = {
        "module": module,
        "repo": repo,
        "mode": mode,
        "changed_paths": sorted(changed_paths),
        "functional_interfaces": functional,
        "data_interfaces": data,
        "layers": layer_info["layers"],
        "layer_dependencies": layer_info["layer_dependencies"],
        "changed_layers": layer_info["changed_layers"],
        "registry_notes": mod_map.get("_notes") or "",
        "system_design_obj": mod_info.get("system_design_obj"),
    }
    return enrich_context(ctx)


def _esc(text: str) -> str:
    return html.escape(text or "")


def _layer_section(context: dict[str, Any], *, delta_only: bool) -> str:
    layers = context.get("layers") or []
    changed_layers = set(context.get("changed_layers") or [])
    if delta_only and not changed_layers:
        return ""
    parts: list[str] = []
    title = "架构变更" if delta_only else "分层架构"
    parts.append(f"<h2>{_esc(title)}{CI_MARKER if not delta_only else ''}</h2>")
    for layer in layers:
        if delta_only and layer["name"] not in changed_layers:
            continue
        parts.append(f"<p><b>{_esc(layer['name'])}</b>：{_esc(layer.get('role', ''))}</p>")
        if layer.get("files"):
            items = "".join(
                f"<li>{_esc(Path(f).name)}</li>" for f in layer["files"][:8]
            )
            parts.append(f"<ul>{items}</ul>")
    return "".join(parts)


def _interface_lists(context: dict[str, Any]) -> tuple[str, str]:
    blurbs = context.get("interface_blurbs") or {}
    func_items: list[str] = []
    for iface in context.get("functional_interfaces") or []:
        name = iface["name"]
        blurb = blurbs.get(name) or iface.get("source_comment") or name
        direction = iface.get("direction") or ""
        func_items.append(
            f"<li><b>{_esc(name)}</b>（{_esc(direction)}）：{_esc(blurb)}</li>"
        )
    data_items: list[str] = []
    for item in context.get("data_interfaces") or []:
        name = item["name"]
        blurb = blurbs.get(name) or item.get("source_comment") or name
        data_items.append(f"<li><b>{_esc(name)}</b>：{_esc(blurb)}</li>")
    func_xml = f"<ul>{''.join(func_items)}</ul>" if func_items else "<p>（无）</p>"
    data_xml = f"<ul>{''.join(data_items)}</ul>" if data_items else "<p>（无）</p>"
    return func_xml, data_xml


def build_docx_xml(context: dict[str, Any]) -> str:
    module = context["module"]
    repo = context["repo"]
    mode = context.get("mode", "delta")
    func_xml, data_xml = _interface_lists(context)
    parts: list[str] = []

    if mode == "full":
        parts.append(f"<h1>{_esc(module)}模块{CI_MARKER}</h1>")
        parts.append(f"<h2>模块概览{CI_MARKER}</h2>")
        parts.append(f"<p>仓库：{_esc(repo)}</p>")
        for para in context.get("overview_paragraphs") or []:
            parts.append(f"<p>{_esc(para)}</p>")
        parts.append(_layer_section(context, delta_only=False))
        parts.append(f"<h2>功能接口{CI_MARKER}</h2>")
        parts.append(func_xml)
        parts.append(f"<h2>数据接口{CI_MARKER}</h2>")
        parts.append(data_xml)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        parts.append("<hr/>")
        parts.append(f"<h2>{ts} 变更{CI_MARKER}</h2>")
        parts.append(f"<h3>变更说明</h3>")
        for para in context.get("overview_paragraphs") or []:
            parts.append(f"<p>{_esc(para)}</p>")
        arch = _layer_section(context, delta_only=True)
        if arch:
            parts.append(arch)
        if context.get("functional_interfaces"):
            parts.append(f"<h3>功能接口</h3>")
            parts.append(func_xml)
        if context.get("data_interfaces"):
            parts.append(f"<h3>数据接口</h3>")
            parts.append(data_xml)

    return "".join(parts)


def resolve_mode(registry: dict[str, Any], module: str) -> str:
    mod_info = (registry.get("modules") or {}).get(module) or {}
    token = mod_info.get("system_design_obj")
    if token and str(token).strip().lower() not in ("", "null", "none"):
        return "delta"
    return "full"


def main() -> None:
    import argparse
    import yaml

    parser = argparse.ArgumentParser(description="Build module system-design DocxXML (local preview)")
    parser.add_argument("--module", required=True)
    parser.add_argument("--repo", choices=("client", "server"), default="client")
    parser.add_argument("--paths", nargs="+", required=True)
    parser.add_argument("--registry", default="config/wiki-registry.yaml")
    parser.add_argument("--mode", choices=("full", "delta", "auto"), default="auto")
    args = parser.parse_args()

    repo_root = Path.cwd()
    registry_path = repo_root / args.registry
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    changed = sorted({p.replace("\\", "/") for p in args.paths})
    files: dict[str, str] = {}
    for p in changed:
        full = repo_root / p
        if full.is_file():
            files[p] = full.read_text(encoding="utf-8", errors="replace")
    mode = resolve_mode(registry, args.module) if args.mode == "auto" else args.mode
    ctx = build_module_doc_context(
        module=args.module,
        repo=args.repo,
        registry=registry,
        repo_root=repo_root,
        changed_paths=changed,
        files=files,
        mode=mode,
    )
    xml = build_docx_xml(ctx)
    print(json.dumps({"mode": mode, "context": ctx, "docx_draft": xml}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
