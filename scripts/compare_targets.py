#!/usr/bin/env python3
"""Decide api_docs vs type_constraints compare targets from snapshot + registry."""

from __future__ import annotations

from typing import Any


def _struct_count(block: dict[str, Any] | None) -> int:
    if not block:
        return 0
    return len(block.get("structs") or [])


def resolve_compare_targets(
    snapshot: dict[str, Any],
    registry_modules: dict[str, Any] | None,
    module: str,
    *,
    explicit_target: str | None = None,
) -> list[dict[str, str]]:
    """Return list of {target, reason} to compare."""
    if explicit_target:
        return [{"target": explicit_target, "reason": "explicit"}]

    api = snapshot.get("api_docs")
    tc = snapshot.get("type_constraints")
    api_n = _struct_count(api)
    tc_n = _struct_count(tc)

    mod_info = (registry_modules or {}).get(module) or {}
    has_api_token = bool(mod_info.get("api_docs_obj"))
    has_tc_token = bool(mod_info.get("type_constraints_obj"))

    targets: list[dict[str, str]] = []
    if has_api_token and api_n > 0:
        targets.append({"target": "api_docs", "reason": "api_docs_has_structs"})
    elif has_api_token and api_n == 0 and has_tc_token and tc_n > 0:
        targets.append(
            {
                "target": "type_constraints",
                "reason": "api_docs_empty_fallback_type_constraints",
            }
        )
    elif has_tc_token and tc_n > 0 and not targets:
        targets.append({"target": "type_constraints", "reason": "type_constraints_only"})
    elif has_api_token:
        targets.append({"target": "api_docs", "reason": "api_docs_token_only"})
    elif has_tc_token:
        targets.append({"target": "type_constraints", "reason": "type_constraints_token_only"})

    if has_api_token and api_n > 0 and has_tc_token and tc_n > 0:
        if not any(t["target"] == "type_constraints" for t in targets):
            targets.append({"target": "type_constraints", "reason": "both_have_structs"})
    return targets or [{"target": "api_docs", "reason": "default"}]


def scope_type_names_from_code(code: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for msg in code.get("messages", []):
        if msg.get("name"):
            names.add(msg["name"])
    for en in code.get("enums", []):
        if en.get("name"):
            names.add(en["name"])
    return names
