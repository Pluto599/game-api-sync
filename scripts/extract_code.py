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


def _body_after_brace(text: str, from_pos: int) -> str | None:
    brace = text.find("{", from_pos)
    if brace < 0:
        return None
    block, _ = _brace_block(text, brace)
    return block


def _is_nested_declaration(text: str, match_start: int) -> bool:
    """Skip private nested types (e.g. serializer helpers), not namespace-level declarations."""
    line_start = text.rfind("\n", 0, match_start) + 1
    line_end = text.find("\n", match_start)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end]
    return bool(re.search(r"\bprivate\s+(?:sealed\s+)?(?:class|struct)\b", line))


def _extract_csharp_interfaces(text: str, *, file_path: str) -> list[dict]:
    interfaces: list[dict] = []
    for m in re.finditer(r"public\s+interface\s+(\w+)", text):
        if _is_nested_declaration(text, m.start()):
            continue
        name = m.group(1)
        block = _body_after_brace(text, m.end())
        if block is None:
            continue
        members: list[dict[str, str]] = []
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith("["):
                continue
            mm = re.match(
                r"[\w<>,\[\]\.\?\s]+\s+(\w+)\s*(?:<[^>]*>)?\s*\(",
                line,
            )
            if mm and mm.group(1) not in _CS_SKIP:
                members.append({"name": mm.group(1), "value": ""})
        if members:
            interfaces.append({"name": name, "members": members, "file": file_path})
    return interfaces


def _extract_csharp_messages(text: str, *, file_path: str) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    messages: list[dict] = []
    enums: list[dict] = []
    constants: list[dict] = []

    for m in re.finditer(
        r"(?:public\s+)?(?:partial\s+)?(?:class|struct)\s+(\w+)",
        text,
    ):
        if _is_nested_declaration(text, m.start()):
            continue
        name = m.group(1)
        block = _body_after_brace(text, m.end())
        if block is None:
            continue
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
        block = _body_after_brace(text, m.end())
        if block is None:
            continue
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

    interfaces = _extract_csharp_interfaces(text, file_path=file_path)
    return messages, enums, constants, interfaces


def _extract_cpp_messages(text: str, *, file_path: str) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    messages: list[dict] = []
    enums: list[dict] = []
    constants: list[dict] = []

    for m in re.finditer(r"(?:struct|class)\s+(\w+)", text):
        name = m.group(1)
        if name in _CPP_SKIP:
            continue
        block = _body_after_brace(text, m.end())
        if block is None:
            continue
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
        block = _body_after_brace(text, m.end())
        if block is None:
            continue
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

    return messages, enums, constants, []


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


def _extract_csharp_summary_before(text: str, pos: int) -> str | None:
    """XML doc /// <summary> immediately preceding pos."""
    chunk = text[max(0, pos - 800) : pos]
    matches = list(
        re.finditer(
            r"///\s*<summary>\s*(.*?)\s*</summary>",
            chunk,
            re.DOTALL | re.IGNORECASE,
        )
    )
    if not matches:
        return None
    # Closest summary block to the type declaration (not an earlier class in the same file).
    m = matches[-1]
    return re.sub(r"\s+", " ", m.group(1).strip()) or None


def _extract_cpp_comment_before(text: str, pos: int) -> str | None:
    chunk = text[max(0, pos - 600) : pos]
    m = re.search(r"/\*\*(.*?)\*/", chunk, re.DOTALL)
    if m:
        body = m.group(1)
        lines = [
            re.sub(r"^\s*\*\s?", "", ln).strip()
            for ln in body.splitlines()
            if ln.strip() and not ln.strip().startswith("@")
        ]
        if lines:
            return " ".join(lines[:3])
    lines = chunk.splitlines()
    for ln in reversed(lines[-5:]):
        ln = ln.strip()
        if ln.startswith("//"):
            return ln[2:].strip() or None
    return None


def extract_type_comment(text: str, type_name: str, *, path: str) -> str | None:
    """Best-effort doc comment for a struct/class/enum/interface name."""
    ext = _ext(path)
    for m in re.finditer(rf"\b(?:class|struct|enum|interface)\s+{re.escape(type_name)}\b", text):
        if ext == ".cs":
            c = _extract_csharp_summary_before(text, m.start())
        elif ext in (".h", ".hpp", ".cpp", ".c"):
            c = _extract_cpp_comment_before(text, m.start())
        else:
            c = None
        if c:
            return c
    return None


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
    interfaces: list[dict] = []

    for path, text in files.items():
        ext = _ext(path)
        if ext == ".cs":
            msgs, ens, consts, ifaces = _extract_csharp_messages(text, file_path=path)
        elif ext in (".h", ".hpp", ".cpp", ".c"):
            msgs, ens, consts, ifaces = _extract_cpp_messages(text, file_path=path)
        else:
            continue
        for msg in msgs:
            msg["direction"] = direction
            messages.append(msg)
        enums.extend(ens)
        constants.extend(consts)
        interfaces.extend(ifaces)

    return {
        "repo": repo,
        "direction": direction,
        "messages": messages,
        "enums": enums,
        "interfaces": interfaces,
        "constants": constants,
    }
