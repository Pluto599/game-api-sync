#!/usr/bin/env python3
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_doc_draft import build_agent_drafts  # noqa: E402
from glob_coverage import apply_registry_glob_update, check_paths_for_align  # noqa: E402


class TestAgentDocDraft(unittest.TestCase):
    def test_apply_registry_glob_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reg_path = root / "config" / "wiki-registry.yaml"
            reg_path.parent.mkdir(parents=True)
            reg_path.write_text(
                yaml.dump(
                    {
                        "modules": {"商店": {"api_docs_obj": "x"}},
                        "module_map": {"商店": {"client_glob": "Assets/Old.cs"}},
                    },
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
            changed = apply_registry_glob_update(
                reg_path,
                "商店",
                "client",
                ["Assets/Old.cs", "Assets/New.cs"],
            )
            self.assertTrue(changed)
            data = yaml.safe_load(reg_path.read_text(encoding="utf-8"))
            globs = data["module_map"]["商店"]["client_glob"]
            self.assertIn("Assets/New.cs", globs)

    def test_build_agent_drafts_api_docs_only_messages(self) -> None:
        draft_cs = """
public struct ShopBuyReq { public string itemId; }
public enum ShopTab { A, B }
"""
        files = {"Assets/Shop/Proto.cs": draft_cs}
        snapshot = {
            "module": "商店",
            "api_docs": {"structs": [{"direction": "client"}]},
            "type_constraints": {"structs": []},
        }
        registry = {
            "modules": {
                "商店": {
                    "api_docs_obj": "tok",
                    "type_constraints_obj": "tok2",
                }
            },
            "module_map": {"商店": {}},
        }
        compare_stub = {
            "message_results": [{"status": "missing_in_doc", "message": "ShopBuyReq"}],
            "enum_issues": [{"kind": "missing_in_doc", "enum": "ShopTab"}],
        }

        # Patch compare via injecting only what build uses — call real build with mocked compare
        from unittest.mock import patch

        with patch("agent_doc_draft.compare_snapshot_to_code") as mock_cmp:
            mock_cmp.side_effect = [
                compare_stub,
                {
                    "message_results": [],
                    "enum_issues": [{"kind": "missing_in_doc", "enum": "ShopTab"}],
                },
            ]
            drafts = build_agent_drafts(
                module="商店",
                repo="client",
                registry=registry,
                snapshot=snapshot,
                paths=["Assets/Shop/Proto.cs"],
                files=files,
            )
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["target"], "api_docs")
        self.assertIn("ShopBuyReq", drafts[0]["docx_draft"])
        self.assertNotIn("ShopTab", drafts[0]["docx_draft"])

    def test_build_agent_drafts_network_type_constraints(self) -> None:
        draft_cs = """
public struct NetPacket { public int id; }
public enum PacketKind { A, B }
"""
        files = {"Assets/Network/P.cs": draft_cs}
        snapshot = {
            "module": "网络相关",
            "api_docs": None,
            "type_constraints": {"structs": []},
        }
        registry = {
            "modules": {"网络相关": {"type_constraints_obj": "tok"}},
            "module_map": {"网络相关": {}},
        }
        from unittest.mock import patch

        with patch("agent_doc_draft.compare_snapshot_to_code") as mock_cmp:
            mock_cmp.return_value = {
                "message_results": [{"status": "missing_in_doc", "message": "NetPacket"}],
                "enum_issues": [{"kind": "missing_in_doc", "enum": "PacketKind"}],
            }
            drafts = build_agent_drafts(
                module="网络相关",
                repo="client",
                registry=registry,
                snapshot=snapshot,
                paths=["Assets/Network/P.cs"],
                files=files,
            )
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["target"], "type_constraints")
        self.assertIn("PacketKind", drafts[0]["docx_draft"])
        self.assertNotIn("NetPacket", drafts[0]["docx_draft"])


if __name__ == "__main__":
    unittest.main()
