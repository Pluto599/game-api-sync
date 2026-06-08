#!/usr/bin/env python3
"""Tests for code_to_docx CI draft scoping."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from code_to_docx import _items_to_sync, build_docx_draft  # noqa: E402
from extract_code import extract_from_sources  # noqa: E402


class CodeToDocxScopeTests(unittest.TestCase):
    def test_items_to_sync_only_changed_file(self) -> None:
        main = """
public class ShopState {
    public ShopViewModel vm;
}
"""
        draft = """
public struct ShopCatalogItem {
    public string itemId;
}
"""
        files = {
            "Assets/Shop/ShopState.cs": main,
            "Assets/Network/ShopProtocolDraft.cs": draft,
        }
        code_all = extract_from_sources(files, repo="client")
        compare_result = {
            "message_results": [
                {"status": "missing_in_doc", "message": "ShopState"},
                {"status": "missing_in_doc", "message": "ShopCatalogItem"},
            ],
            "enum_issues": [],
        }
        code_draft = extract_from_sources(
            {"Assets/Network/ShopProtocolDraft.cs": draft}, repo="client"
        )
        msgs, enums = _items_to_sync(
            compare_result,
            code_draft,
            changed_paths={"Assets/Network/ShopProtocolDraft.cs"},
        )
        names = {m["name"] for m in msgs}
        self.assertIn("ShopCatalogItem", names)
        self.assertNotIn("ShopState", names)

    def test_build_draft_uses_changed_paths_only(self) -> None:
        snap = {"module": "商店", "api_docs": {"structs": [{"direction": "client"}]}}
        draft = """
public struct ShopCatalogItem {
    public string itemId;
}
"""
        other = """
public class ShopState {
    public int x;
}
"""
        files = {
            "Assets/Network/ShopProtocolDraft.cs": draft,
            "Assets/Shop/ShopState.cs": other,
        }
        code_all = extract_from_sources(files, repo="client")
        compare_result = {
            "message_results": [
                {"status": "missing_in_doc", "message": n}
                for n in (m["name"] for m in code_all["messages"])
            ],
            "enum_issues": [],
        }
        xml = build_docx_draft(
            snapshot=snap,
            compare_result=compare_result,
            files=files,
            repo="client",
            changed_paths=["Assets/Network/ShopProtocolDraft.cs"],
        )
        self.assertIn("ShopCatalogItem", xml)
        self.assertNotIn("ShopState", xml)


if __name__ == "__main__":
    unittest.main()
