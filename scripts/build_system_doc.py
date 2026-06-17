#!/usr/bin/env python3
"""Build ModuleDocContext and DocxXML for module system-design docs."""

from __future__ import annotations

import hashlib
import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from extract_code import extract_from_sources, extract_type_comment
from module_doc_agent import enrich_context
from module_doc_layers import infer_module_layers
from module_doc_placement import (
    SECTION_DATA,
    SECTION_FUNC,
    SECTION_LAYERS,
    SECTION_OVERVIEW,
    system_design_doc_is_empty,
)

_DIRECTION_LABEL = {
    "client": "客户端→服务端",
    "server": "服务端→客户端",
}


_DOC_TZ = ZoneInfo(os.environ.get("MODULE_DOC_TIMEZONE", "Asia/Shanghai"))


def format_update_date(when: datetime | None = None) -> str:
    """e.g. 2026-6-17 23:50 更新 (Asia/Shanghai by default)."""
    dt = when or datetime.now(_DOC_TZ)
    return f"{dt.year}-{dt.month}-{dt.day} {dt.hour}:{dt.minute:02d} 更新"


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


def _files_for_interface_extraction(
    files: dict[str, str],
    changed_paths: list[str],
    mode: str,
) -> dict[str, str]:
    if mode == "full":
        return files
    changed = {p.replace("\\", "/") for p in changed_paths}
    return {k: v for k, v in files.items() if k.replace("\\", "/") in changed}


def _extract_interfaces(
    files: dict[str, str],
    *,
    repo: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    code = extract_from_sources(files, repo=repo)
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
    return functional, data


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
    mod_map = (registry.get("module_map") or {}).get(module) or {}
    mod_info = (registry.get("modules") or {}).get(module) or {}

    iface_files = _files_for_interface_extraction(files, changed_paths, mode)
    functional, data = _extract_interfaces(iface_files, repo=repo)

    layer_paths = None if mode == "full" else changed_paths
    layer_info = infer_module_layers(
        module=module,
        repo=repo,
        registry=registry,
        repo_root=repo_root,
        changed_paths=layer_paths,
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
        "update_date": format_update_date(),
    }
    return enrich_context(ctx)


def _esc(text: str) -> str:
    return html.escape(text or "")


def _dated_heading(context: dict[str, Any]) -> str:
    label = context.get("update_date") or format_update_date()
    return f"<h3>{_esc(label)}</h3>"


def _overview_body(context: dict[str, Any], *, include_repo: bool) -> str:
    parts: list[str] = [_dated_heading(context)]
    if include_repo:
        parts.append(f"<p>仓库：{_esc(context.get('repo', ''))}</p>")
    for para in context.get("overview_paragraphs") or []:
        parts.append(f"<p>{_esc(para)}</p>")
    return "".join(parts)


def _layers_body(context: dict[str, Any], *, only_changed: bool) -> str:
    layers = context.get("layers") or []
    changed_layers = set(context.get("changed_layers") or [])
    if only_changed and not changed_layers:
        return ""
    parts: list[str] = [_dated_heading(context)]
    for layer in layers:
        if only_changed and layer["name"] not in changed_layers:
            continue
        parts.append(f"<p><b>{_esc(layer['name'])}</b>：{_esc(layer.get('role', ''))}</p>")
        if layer.get("files"):
            items = "".join(
                f"<li>{_esc(Path(f).name)}</li>" for f in layer["files"][:8]
            )
            parts.append(f"<ul>{items}</ul>")
    return "".join(parts) if len(parts) > 1 else ""


def _interface_lists(context: dict[str, Any]) -> tuple[str, str]:
    blurbs = context.get("interface_blurbs") or {}
    func_items: list[str] = []
    for iface in context.get("functional_interfaces") or []:
        name = iface["name"]
        blurb = blurbs.get(name) or iface.get("source_comment") or name
        func_items.append(f"<li><b>{_esc(name)}</b>：{_esc(blurb)}</li>")
    data_items: list[str] = []
    for item in context.get("data_interfaces") or []:
        name = item["name"]
        blurb = blurbs.get(name) or item.get("source_comment") or name
        data_items.append(f"<li><b>{_esc(name)}</b>：{_esc(blurb)}</li>")
    func_xml = f"<ul>{''.join(func_items)}</ul>" if func_items else ""
    data_xml = f"<ul>{''.join(data_items)}</ul>" if data_items else ""
    return func_xml, data_xml


def build_initial_docx(context: dict[str, Any]) -> str:
    """Full skeleton for a new/empty sub-doc (no document h1 — wiki title is the module name)."""
    func_xml, data_xml = _interface_lists(context)
    layers = _layers_body(context, only_changed=False)
    parts: list[str] = [
        f"<h2>{SECTION_OVERVIEW}</h2>",
        _overview_body(context, include_repo=True),
        f"<h2>{SECTION_LAYERS}</h2>",
    ]
    if layers:
        parts.append(layers)
    parts.append(f"<h2>{SECTION_FUNC}</h2>")
    if func_xml:
        parts.append(_dated_heading(context) + func_xml)
    parts.append(f"<h2>{SECTION_DATA}</h2>")
    if data_xml:
        parts.append(_dated_heading(context) + data_xml)
    return "".join(parts)


def build_section_updates(context: dict[str, Any]) -> dict[str, str]:
    """Dated fragments to insert under each h2 section (delta mode). Omit empty sections."""
    updates: dict[str, str] = {}
    func_n = len(context.get("functional_interfaces") or [])
    data_n = len(context.get("data_interfaces") or [])
    has_layer_delta = bool(context.get("changed_layers"))

    layers = _layers_body(context, only_changed=True)
    if layers:
        updates[SECTION_LAYERS] = layers

    func_xml, data_xml = _interface_lists(context)
    if func_xml:
        updates[SECTION_FUNC] = _dated_heading(context) + func_xml
    if data_xml:
        updates[SECTION_DATA] = _dated_heading(context) + data_xml

    if func_n or data_n or has_layer_delta:
        updates[SECTION_OVERVIEW] = _overview_body(context, include_repo=False)

    return updates


def build_docx_xml(context: dict[str, Any]) -> str:
    """Legacy single blob (local preview); prefer build_initial_docx / build_section_updates."""
    mode = context.get("mode", "delta")
    if mode == "full":
        return build_initial_docx(context)
    return "".join(build_section_updates(context).values())


def resolve_system_design_obj(registry: dict[str, Any], module: str) -> str | None:
    info = (registry.get("modules") or {}).get(module) or {}
    token = info.get("system_design_obj")
    if token and str(token).strip().lower() not in ("", "null", "none"):
        return str(token)
    return None


def resolve_mode(
    registry: dict[str, Any],
    module: str,
    *,
    check_doc_content: bool = False,
) -> str:
    """
    full — no sub-doc token, or sub-doc exists but has no section content yet.
    delta — sub-doc already has 模块概览 (or other system-design sections).
    """
    token = resolve_system_design_obj(registry, module)
    if not token:
        return "full"
    if not check_doc_content:
        return "delta"
    if system_design_doc_is_empty(token):
        return "full"
    return "delta"


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
    if mode == "full":
        xml = build_initial_docx(ctx)
        sections = None
    else:
        sections = build_section_updates(ctx)
        xml = build_docx_xml(ctx)
    print(
        json.dumps(
            {"mode": mode, "context": ctx, "docx_draft": xml, "section_updates": sections},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
