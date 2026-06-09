#!/usr/bin/env python3
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from glob_coverage import (  # noqa: E402
    check_paths_for_align,
    exclude_reason,
    merge_explicit_glob_paths,
    path_in_module_glob,
)


class TestGlobCoverage(unittest.TestCase):
    def test_exclude_resource(self) -> None:
        self.assertIsNotNone(exclude_reason("Assets/Foo/bar.prefab"))

    def test_merge_explicit_glob(self) -> None:
        out = merge_explicit_glob_paths(
            ["Assets/Old.cs", "Assets/**/*Shop*.cs"],
            ["Assets/New/ShopDraft.cs"],
        )
        self.assertIn("Assets/New/ShopDraft.cs", out)
        self.assertIn("Assets/Old.cs", out)
        self.assertTrue(any("*" in p for p in out))

    def test_check_paths_for_align(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proto = root / "Assets" / "Protocol" / "ShopDraft.cs"
            proto.parent.mkdir(parents=True)
            proto.write_text(
                "public struct ShopDraftReq { public string id; }\n",
                encoding="utf-8",
            )
            reg_path = root / "config"
            reg_path.mkdir()
            registry = {
                "modules": {},
                "module_map": {
                    "商店": {
                        "client_glob": ["Assets/Protocol/Other.cs"],
                    }
                },
            }
            (reg_path / "wiki-registry.yaml").write_text(
                yaml.dump(registry, allow_unicode=True), encoding="utf-8"
            )
            r = check_paths_for_align(
                root,
                registry,
                "商店",
                "client",
                ["Assets/Protocol/ShopDraft.cs"],
            )
            self.assertIn("Assets/Protocol/ShopDraft.cs", r["missing_from_glob"])
            self.assertTrue(r["needs_registry_update"])
            self.assertIn("Assets/Protocol/ShopDraft.cs", r["suggested_glob"])


if __name__ == "__main__":
    unittest.main()
