#!/usr/bin/env python3
"""Extract protocol messages, enums, and constants from C# / C++ sources."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

_CS_SKIP = frozenset({"get", "set", "value", "class", "struct", "enum", "namespace"})
_CPP_SKIP = frozenset(
    {"if", "for", "while", "return", "class", "struct", "enum", "namespace", "using"}
)


def _ext(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).suffix.lower()


def _normalize_type(typ: str) -> str:
    t = (typ or "").strip().lower().replace(" ", "")
    aliases = {
        "uint32": "uint32",
        "uint": "uint32",
        "int32": "int32",
        "int": "int32",
        "long": "int64",
        "int64": "int64",
        "ulong": "uint64",
        "uint64": "uint64",
        "string": "string",
        "str": "string",
        "bool": "bool",
        "boolean": "bool",
        "float": "float",
        "double": "double",
        "number": "number",
        "byte": "byte",
        "sbyte": "byte",
    }
    for k, v in aliases.items():
        if t == k or t.endswith(k):
            return v
    return t or "unknown"


def _brace_block(text: str, start: int) -> tuple[str, int]:
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    return text[start + 1 :], len(text)


def _parse_csharp_type_and_name(decl: str) -> tuple[str, str] | None:
    decl = decl.strip()
    m = re.match(
        r"(?:public|private|protected|internal)\s+"
        r"(?:readonly\s+)?(?:static\s+)?"
        r"([\w<>,\[\]\.?]+?)\s+(\w+)\s*(?:\{|;|=)",
        decl,
    )
    if not m:
        return None
    typ, name = m.group(1).strip(), m.group(2)
    if name in _CS_SKIP:
        return None
    return _normalize_type(typ), name


def _extract_csharp_messages(text: str, *, file_path: str) -> tuple[list[dict], list[dict], list[dict]]:
    messages: list[dict] = []
    enums: list[dict] = []
    constants: list[dict] = []

    for m in re.finditer(
        r"(?:public\s+)?(?:partial\s+)?(?:class|struct)\s+(\w+)",
        text,
    ):
        name = m.group(1)
        block, _ = _brace_block(text, m.end() - 1)
        fields: list[dict] = []
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("["):
                continue
            parsed = _parse_csharp_type_and_name(line)
            if parsed:
                typ, fname = parsed
                fields.append({"name": fname, "type": typ, "optional": False})
        if fields:
            messages.append(
                {
                    "name": name,
                    "section": name,
                    "fields": fields,
                    "file": file_path,
                }
            )

    for m in re.finditer(r"enum\s+(\w+)", text):
        ename = m.group(1)
        block, _ = _brace_block(text, m.end() - 1)
        members = _parse_enum_members(block)
        if members:
            enums.append({"name": ename, "members": members, "file": file_path})

    for m in re.finditer(
        r"(?:public\s+)?const\s+(?:int|uint|byte|ushort)\s+(\w+)\s*=\s*([^;]+);",
        text,
    ):
        constants.append(
            {"name": m.group(1), "value": m.group(2).strip(), "file": file_path}
        )

    return messages, enums, constants


def _extract_cpp_messages(text: str, *, file_path: str) -> tuple[list[dict], list[dict], list[dict]]:
    messages: list[dict] = []
    enums: list[dict] = []
    constants: list[dict] = []

    for m in re.finditer(r"(?:struct|class)\s+(\w+)", text):
        name = m.group(1)
        if name in _CPP_SKIP:
            continue
        block, _ = _brace_block(text, m.end() - 1)
        fields: list[dict] = []
        for line in block.splitlines():
            line = line.strip().rstrip(",")
            if not line or line.startswith("//") or line.startswith("#"):
                continue
            mm = re.match(
                r"(?:const\s+)?(?:static\s+)?([\w:<>,\*\&]+?)\s+(\w+)\s*(?:\{|;|=)",
                line,
            )
            if not mm:
                continue
            fname = mm.group(2)
            if fname in _CPP_SKIP:
                continue
            fields.append(
                {
                    "name": fname,
                    "type": _normalize_type(mm.group(1).replace("*", "").replace("&", "")),
                    "optional": False,
                }
            )
        if fields:
            messages.append(
                {
                    "name": name,
                    "section": name,
                    "fields": fields,
                    "file": file_path,
                }
            )

    for m in re.finditer(r"enum\s+(?:class\s+)?(\w+)", text):
        ename = m.group(1)
        block, _ = _brace_block(text, m.end() - 1)
        members = _parse_enum_members(block)
        if members:
            enums.append({"name": ename, "members": members, "file": file_path})

    for m in re.finditer(r"#define\s+(\w+)\s+(\S+)", text):
        constants.append(
            {"name": m.group(1), "value": m.group(2).strip(), "file": file_path}
        )
    for m in re.finditer(
        r"(?:static\s+)?const\s+(?:int|uint32_t|uint16_t|uint8_t)\s+(\w+)\s*=\s*([^;]+);",
        text,
    ):
        constants.append(
            {"name": m.group(1), "value": m.group(2).strip(), "file": file_path}
        )

    return messages, enums, constants


def _parse_enum_members(body: str) -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    for line in body.replace("\n", " ").split(","):
        line = line.strip().rstrip(";")
        if not line or line.startswith("//"):
            continue
        mm = re.match(r"(\w+)\s*=\s*(.+)", line)
        if mm:
            members.append({"name": mm.group(1), "value": mm.group(2).strip()})
        else:
            mm2 = re.match(r"(\w+)$", line)
            if mm2:
                members.append({"name": mm2.group(1), "value": ""})
    return members


def extract_from_sources(
    files: dict[str, str],
    *,
    repo: str = "client",
) -> dict[str, Any]:
    """Structured protocol extract for diff_api. repo hints client vs server."""
    direction = "client" if repo == "client" else "server"
    messages: list[dict] = []
    enums: list[dict] = []
    constants: list[dict] = []

    for path, text in files.items():
        ext = _ext(path)
        if ext == ".cs":
            msgs, ens, consts = _extract_csharp_messages(text, file_path=path)
        elif ext in (".h", ".hpp", ".cpp", ".c"):
            msgs, ens, consts = _extract_cpp_messages(text, file_path=path)
        else:
            continue
        for msg in msgs:
            msg["direction"] = direction
            messages.append(msg)
        enums.extend(ens)
        constants.extend(consts)

    return {
        "repo": repo,
        "direction": direction,
        "messages": messages,
        "enums": enums,
        "constants": constants,
    }
