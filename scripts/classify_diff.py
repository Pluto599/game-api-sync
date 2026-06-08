#!/usr/bin/env python3
"""Classify api-compare results for CI sync decisions."""

from __future__ import annotations

from typing import Any


def classify_compare_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    Returns classification: ok | doc_ahead | code_ahead | conflict
    """
    message_results = result.get("message_results") or []
    if result.get("parts"):
        message_results = []
        for p in result["parts"]:
            message_results.extend(p.get("message_results") or [])

    has_missing_in_code = False
    has_missing_in_doc = False
    has_type_conflict = False
    has_field_both_ways = False

    for r in message_results:
        if r.get("status") == "missing_in_code":
            has_missing_in_code = True
        if r.get("status") == "missing_in_doc":
            has_missing_in_doc = True
        if r.get("status") == "diff":
            mic = r.get("missing_in_code") or []
            mid = r.get("missing_in_doc") or []
            tm = r.get("type_mismatch") or []
            if mic:
                has_missing_in_code = True
            if mid:
                has_missing_in_doc = True
            if tm:
                has_type_conflict = True
            if mic and mid:
                has_field_both_ways = True

    enum_issues = result.get("enum_issues") or []
    if result.get("parts"):
        enum_issues = []
        for p in result["parts"]:
            enum_issues.extend(p.get("enum_issues") or [])

    for ei in enum_issues:
        kind = ei.get("kind")
        if kind == "missing_in_code":
            has_missing_in_code = True
        elif kind in ("missing_in_doc", "member_set", "value_mismatch"):
            if kind == "missing_in_doc":
                has_missing_in_doc = True
            else:
                has_type_conflict = True

    if has_type_conflict or has_field_both_ways:
        classification = "conflict"
    elif has_missing_in_doc and not has_missing_in_code:
        classification = "code_ahead"
    elif has_missing_in_code and not has_missing_in_doc:
        classification = "doc_ahead"
    elif has_missing_in_doc and has_missing_in_code:
        classification = "conflict"
    elif not (result.get("defects") or enum_issues):
        classification = "ok"
    else:
        classification = "conflict"

    sync_recommended = classification in ("code_ahead", "conflict")
    return {
        "classification": classification,
        "sync_recommended": sync_recommended,
        "has_missing_in_code": has_missing_in_code,
        "has_missing_in_doc": has_missing_in_doc,
        "has_type_conflict": has_type_conflict,
    }
