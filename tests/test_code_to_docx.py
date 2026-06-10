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
        msgs, enums, ifaces = _items_to_sync(
            compare_result,
            code_draft,
            target="api_docs",
            changed_paths={"Assets/Network/ShopProtocolDraft.cs"},
        )
        names = {m["name"] for m in msgs}
        self.assertIn("ShopCatalogItem", names)
        self.assertNotIn("ShopState", names)
        self.assertEqual(enums, [])
        self.assertEqual(ifaces, [])

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
            target="api_docs",
            changed_paths=["Assets/Network/ShopProtocolDraft.cs"],
        )
        self.assertIn("ShopCatalogItem", xml)
        self.assertNotIn("ShopState", xml)

    def test_empty_changed_paths_syncs_nothing(self) -> None:
        snap = {"module": "商店", "api_docs": {"structs": []}}
        draft = "public struct ShopCatalogItem { public string itemId; }"
        files = {"Assets/Network/ShopProtocolDraft.cs": draft}
        code = extract_from_sources(files, repo="client")
        compare_result = {
            "message_results": [
                {"status": "missing_in_doc", "message": m["name"]}
                for m in code["messages"]
            ],
            "enum_issues": [],
        }
        msgs, _, _ = _items_to_sync(
            compare_result, code, target="api_docs", changed_paths=set()
        )
        self.assertEqual(msgs, [])
        xml = build_docx_draft(
            snapshot=snap,
            compare_result=compare_result,
            files=files,
            repo="client",
            target="api_docs",
            changed_paths=[],
        )
        self.assertEqual(xml, "")

    def test_type_constraints_gets_enums_not_classes(self) -> None:
        proto = """
public enum ShopGitActionsTestRequestType {
    PROBE = 99,
}
public class ShopGitActionsTestProbeRequest {
    public string uid;
}
"""
        files = {"Assets/Network/ShopGitActionsTestProtocol.cs": proto}
        code = extract_from_sources(files, repo="client")
        compare_tc = {
            "message_results": [
                {
                    "status": "missing_in_doc",
                    "message": "ShopGitActionsTestProbeRequest",
                }
            ],
            "enum_issues": [
                {"kind": "missing_in_doc", "enum": "ShopGitActionsTestRequestType"},
            ],
        }
        msgs, enums, ifaces = _items_to_sync(
            compare_tc, code, target="type_constraints", changed_paths=None
        )
        self.assertEqual(msgs, [])
        self.assertEqual(len(enums), 1)
        self.assertEqual(enums[0]["name"], "ShopGitActionsTestRequestType")

        snap = {"module": "商店", "type_constraints": {"structs": []}}
        xml = build_docx_draft(
            snapshot=snap,
            compare_result=compare_tc,
            files=files,
            repo="client",
            target="type_constraints",
        )
        self.assertIn("ShopGitActionsTestRequestType", xml)
        self.assertNotIn("ShopGitActionsTestProbeRequest", xml)

    def test_shop_module_api_docs_only_has_classes(self) -> None:
        proto = """
public enum ShopGitActionsTestRequestType {
    PROBE = 99,
}
public class ShopGitActionsTestProbeRequest {
    public string uid;
}
"""
        files = {"Assets/Network/ShopGitActionsTestProtocol.cs": proto}
        code = extract_from_sources(files, repo="client")
        compare_api = {
            "message_results": [
                {"status": "missing_in_doc", "message": "ShopGitActionsTestProbeRequest"},
            ],
            "enum_issues": [],
        }
        snap = {"module": "商店", "api_docs": {"structs": [{"direction": "client"}]}}
        xml = build_docx_draft(
            snapshot=snap,
            compare_result=compare_api,
            files=files,
            repo="client",
            target="api_docs",
        )
        self.assertIn("ShopGitActionsTestProbeRequest", xml)
        self.assertNotIn("ShopGitActionsTestRequestType", xml)


if __name__ == "__main__":
    unittest.main()
