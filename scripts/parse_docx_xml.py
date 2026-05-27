#!/usr/bin/env python3
"""Parse Feishu Docx XML (from lark-cli docs +fetch) into ApiSnapshot JSON."""

from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from typing import Any
from xml.etree import ElementTree as ET


@dataclass
class FieldDef:
    name: str
    type: str
    optional: bool = False
    comment: str = ""


@dataclass
class StructDef:
    name: str | None
    direction: str | None  # client | server | unknown
    section: str | None
    fields: list[FieldDef] = field(default_factory=list)
    raw_code: str = ""


@dataclass
class ApiSnapshot:
    module: str
    document_id: str | None = None
    revision_id: int | None = None
    source: str = ""  # api_docs | type_constraints
    title: str | None = None
    structs: list[StructDef] = field(default_factory=list)
    enums: list[dict[str, Any]] = field(default_factory=list)
    raw_blocks: list[dict[str, str]] = field(default_factory=list)


def _strip_br(text: str) -> str:
    return re.sub(r"<br\s*/?>", "\n", text, flags=re.I)


def _text_from_code_el(el: ET.Element | None) -> str:
    if el is None:
        return ""
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        if child.tag == "br":
            parts.append("\n")
        if child.tail:
            parts.append(child.tail)
    return html.unescape("".join(parts))


def _detect_direction(caption: str, section: str) -> str | None:
    blob = f"{caption} {section}"
    if "客户端" in blob:
        return "client"
    if "服务端" in blob:
        return "server"
    return None


def _parse_ts_fields(code: str) -> list[FieldDef]:
    fields: list[FieldDef] = []
    for line in code.splitlines():
        line = line.strip()
        if not line or line in ("{", "}", "};"):
            continue
        m = re.match(
            r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^;]+);(?:\s*//\s*(.*))?$",
            line,
        )
        if not m:
            continue
        name, typ, comment = m.group(1), m.group(2).strip(), (m.group(3) or "").strip()
        optional = "?" in typ
        typ = typ.replace("?", "").strip()
        fields.append(
            FieldDef(name=name, type=typ, optional=optional, comment=comment)
        )
    return fields


def _parse_enums(code: str) -> list[dict[str, Any]]:
    enums: list[dict[str, Any]] = []
    for m in re.finditer(
        r"enum\s+(\w+)\s*\{([^}]*)\}",
        code,
        flags=re.DOTALL,
    ):
        name = m.group(1)
        body = m.group(2)
        members: list[dict[str, str]] = []
        for line in body.splitlines():
            line = line.strip().rstrip(",;")
            if not line or line.startswith("//"):
                continue
            mm = re.match(r"(\w+)\s*=\s*([^,]+)", line)
            if mm:
                members.append({"name": mm.group(1), "value": mm.group(2).strip()})
        enums.append({"name": name, "members": members})
    return enums


def parse_docx_content(
    xml_content: str,
    *,
    module: str,
    source: str,
    document_id: str | None = None,
    revision_id: int | None = None,
) -> ApiSnapshot:
    """Parse inner XML string from docs +fetch document.content."""
    wrapped = f"<root>{xml_content}</root>"
    try:
        root = ET.fromstring(wrapped)
    except ET.ParseError:
        # fallback: treat whole blob as one block
        snap = ApiSnapshot(
            module=module,
            document_id=document_id,
            revision_id=revision_id,
            source=source,
        )
        snap.raw_blocks.append({"type": "unparsed", "text": xml_content[:2000]})
        return snap

    snap = ApiSnapshot(
        module=module,
        document_id=document_id,
        revision_id=revision_id,
        source=source,
    )

    title_el = root.find("title")
    if title_el is not None and title_el.text:
        snap.title = title_el.text.strip()

    current_section: str | None = None
    current_h1: str | None = None

    for child in list(root):
        tag = child.tag
        if tag == "h1":
            current_h1 = "".join(child.itertext()).strip() or None
            current_section = current_h1
        elif tag == "h2":
            current_section = "".join(child.itertext()).strip() or current_h1
        elif tag == "pre":
            lang = child.get("lang") or child.get("{http://www.w3.org/1999/xhtml}lang")
            caption = child.get("caption") or ""
            code_el = child.find("code")
            raw = _text_from_code_el(code_el)
            if not raw.strip():
                continue
            direction = _detect_direction(caption, current_section or "")
            snap.raw_blocks.append(
                {
                    "section": current_section or "",
                    "lang": lang or "",
                    "caption": caption,
                    "code": raw,
                }
            )
            if lang and "typescript" in lang.lower():
                if "enum " in raw:
                    snap.enums.extend(_parse_enums(raw))
                else:
                    snap.structs.append(
                        StructDef(
                            name=None,
                            direction=direction,
                            section=current_section,
                            fields=_parse_ts_fields(raw),
                            raw_code=raw,
                        )
                    )

    return snap


def snapshot_to_dict(snap: ApiSnapshot) -> dict[str, Any]:
    def struct_dict(s: StructDef) -> dict[str, Any]:
        return {
            "name": s.name,
            "direction": s.direction,
            "section": s.section,
            "fields": [asdict(f) for f in s.fields],
            "raw_code": s.raw_code,
        }

    return {
        "module": snap.module,
        "document_id": snap.document_id,
        "revision_id": snap.revision_id,
        "source": snap.source,
        "title": snap.title,
        "structs": [struct_dict(s) for s in snap.structs],
        "enums": snap.enums,
        "raw_blocks": snap.raw_blocks,
    }


def merge_snapshots(api: ApiSnapshot, types: ApiSnapshot | None) -> dict[str, Any]:
    merged = {
        "module": api.module,
        "api_docs": snapshot_to_dict(api),
        "type_constraints": snapshot_to_dict(types) if types else None,
    }
    return merged


def parse_fetch_json(
    fetch_json: dict[str, Any],
    *,
    module: str,
    source: str,
) -> ApiSnapshot:
    doc = fetch_json.get("data", {}).get("document", fetch_json.get("document", {}))
    content = doc.get("content", "")
    rev = doc.get("revision_id")
    revision_id = int(rev) if rev is not None else None
    return parse_docx_content(
        content,
        module=module,
        source=source,
        document_id=doc.get("document_id"),
        revision_id=revision_id,
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: parse_docx_xml.py <fetch.json> [module] [source]", file=sys.stderr)
        sys.exit(1)
    path = sys.argv[1]
    module = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    source = sys.argv[3] if len(sys.argv) > 3 else "api_docs"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    snap = parse_fetch_json(data, module=module, source=source)
    print(json.dumps(snapshot_to_dict(snap), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
