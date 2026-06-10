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


class TestGateModuleResolution(unittest.TestCase):
    def test_explicit_glob_wins_over_wildcard_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proto = root / "Assets" / "Scripts" / "Network" / "NetModels" / "ShopTest.cs"
            proto.parent.mkdir(parents=True)
            proto.write_text("public struct ShopTest { public int x; }", encoding="utf-8")
            rel = proto.relative_to(root).as_posix()
            registry = {
                "module_map": {
                    "商店": {
                        "client_glob": [rel],
                    },
                    "网络相关": {
                        "client_glob": ["Assets/Scripts/Network/**/*.cs"],
                    },
                }
            }
            cfg = root / "config"
            cfg.mkdir()
            (cfg / "wiki-registry.yaml").write_text(
                yaml.dump(registry, allow_unicode=True), encoding="utf-8"
            )
            result = resolve_modules_for_paths([rel], registry, "client", repo_root=root)
            self.assertIn("商店", result)
            self.assertEqual(result["商店"], [rel])
            self.assertNotIn("网络相关", result)


if __name__ == "__main__":
    unittest.main()
