#!/usr/bin/env python3
"""Extract struct/enum field names from C# / C++ source (existing protocol files)."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any


def _ext(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).suffix.lower()


def _extract_csharp_fields(text: str) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    seen: set[str] = set()
    patterns = [
        r"(?:public|private|protected|internal)\s+[\w<>,\[\]\.?]+\s+(\w+)\s*\{",
        r"(?:public|private|protected|internal)\s+[\w<>,\[\]\.?]+\s+(\w+)\s*;",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            name = m.group(1)
            if name in ("get", "set", "value") or name in seen:
                continue
            seen.add(name)
            fields.append({"name": name, "type": ""})
    return fields


def _extract_cpp_fields(text: str) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        m = re.match(
            r"(?:const\s+)?(?:static\s+)?(?:[\w:<>,\*\&]+\s+)+(\w+)\s*(?:=|;)",
            line,
        )
        if not m:
            continue
        name = m.group(1)
        if name in ("if", "for", "while", "return", "class", "struct", "enum") or name in seen:
            continue
        seen.add(name)
        fields.append({"name": name, "type": ""})
    return fields


def extract_from_sources(files: dict[str, str]) -> dict[str, Any]:
    """files: repo-relative path -> source text."""
    all_fields: list[dict[str, str]] = []
    per_file: dict[str, list[dict[str, str]]] = {}
    enums: list[str] = []

    for path, text in files.items():
        ext = _ext(path)
        if ext == ".cs":
            flds = _extract_csharp_fields(text)
        elif ext in (".h", ".hpp", ".cpp", ".c"):
            flds = _extract_cpp_fields(text)
        else:
            continue
        per_file[path] = flds
        all_fields.extend(flds)
        for m in re.finditer(r"enum\s+(?:class\s+)?(\w+)", text):
            enums.append(m.group(1))

    names = sorted({f["name"] for f in all_fields})
    return {
        "field_count": len(names),
        "fields": names,
        "fields_detail": all_fields,
        "per_file": {k: [f["name"] for f in v] for k, v in per_file.items()},
        "enums": sorted(set(enums)),
    }
