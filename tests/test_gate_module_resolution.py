#!/usr/bin/env python3
"""Tests for CI gate module path resolution."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ci.gate import resolve_modules_for_paths  # noqa: E402
from code_to_docx import sync_targets_for_module  # noqa: E402


class TestGateModuleResolution(unittest.TestCase):
    def test_path_may_match_multiple_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proto = root / "Assets" / "Scripts" / "Network" / "NetModels" / "ShopTest.cs"
            proto.parent.mkdir(parents=True)
            proto.write_text("public struct ShopTest { public int x; }", encoding="utf-8")
            rel = proto.relative_to(root).as_posix()
            registry = {
                "modules": {
                    "商店": {"api_docs_obj": "a", "type_constraints_obj": "b"},
                    "网络相关": {"type_constraints_obj": "c"},
                },
                "module_map": {
                    "商店": {"client_glob": [rel]},
                    "网络相关": {"client_glob": ["Assets/Scripts/Network/**/*.cs"]},
                },
            }
            result = resolve_modules_for_paths([rel], registry, "client", repo_root=root)
            self.assertEqual(result["商店"], [rel])
            self.assertEqual(result["网络相关"], [rel])

    def test_sync_targets_split_shop_vs_network(self) -> None:
        snap = {"module": "商店"}
        shop_mod = {"api_docs_obj": "a", "type_constraints_obj": "b"}
        self.assertEqual(sync_targets_for_module(snap, shop_mod), ["api_docs"])

        snap_net = {"module": "网络相关"}
        net_mod = {"type_constraints_obj": "c"}
        self.assertEqual(sync_targets_for_module(snap_net, net_mod), ["type_constraints"])


if __name__ == "__main__":
    unittest.main()
