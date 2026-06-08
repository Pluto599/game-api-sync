#!/usr/bin/env python3
"""Tests for message_aliases resolution."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from message_aliases import (  # noqa: E402
    find_aliases_in_files,
    load_aliases_for_compare,
)


class TestMessageAliases(unittest.TestCase):
    def test_load_aliases_for_compare_prefers_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = root / "config"
            cfg.mkdir()
            (cfg / "message_aliases.yaml").write_text(
                yaml.dump({"商店": {"初始化": "ShopInitRequest"}}, allow_unicode=True),
                encoding="utf-8",
            )
            aliases = load_aliases_for_compare(repo_root=root)
            self.assertEqual(aliases["商店"]["初始化"], "ShopInitRequest")

    def test_load_aliases_for_compare_from_files_embedded(self) -> None:
        text = yaml.dump({"登录界面": {"登录请求": "LoginRequest"}}, allow_unicode=True)
        aliases = load_aliases_for_compare(
            files={"config/message_aliases.yaml": text, "Assets/Foo.cs": "class X {}"}
        )
        self.assertEqual(aliases["登录界面"]["登录请求"], "LoginRequest")

    def test_find_aliases_in_files_windows_path(self) -> None:
        text = yaml.dump({"战斗": {"攻击": "BattleShoot"}}, allow_unicode=True)
        found = find_aliases_in_files({r"config\message_aliases.yaml": text})
        self.assertEqual(found["战斗"]["攻击"], "BattleShoot")


if __name__ == "__main__":
    unittest.main()
