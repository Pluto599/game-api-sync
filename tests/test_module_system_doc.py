#!/usr/bin/env python3
"""Tests for module system-design doc generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from build_system_doc import (
    build_docx_xml,
    build_module_doc_context,
    resolve_mode,
    system_doc_fingerprint,
)
from extract_code import extract_type_comment
from module_doc_layers import infer_module_layers
from module_doc_agent import heuristic_interface_blurb, need_agent


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "battle_client.cs"
REGISTRY = Path(__file__).resolve().parents[1] / "config" / "wiki-registry.yaml"


class TestExtractComment(unittest.TestCase):
    def test_csharp_summary(self) -> None:
        text = (
            "/// <summary>请求进入战斗</summary>\n"
            "public class EnterBattleReq { public string roomId; }"
        )
        c = extract_type_comment(text, "EnterBattleReq", path="Battle.cs")
        self.assertEqual(c, "请求进入战斗")


class TestBuildSystemDoc(unittest.TestCase):
    def setUp(self) -> None:
        self.code = FIXTURE.read_text(encoding="utf-8")
        self.files = {"Assets/Scripts/Battle/EnterBattle.cs": self.code}
        import yaml

        self.registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))

    def test_fingerprint_stable(self) -> None:
        fp1 = system_doc_fingerprint(self.files, "client")
        fp2 = system_doc_fingerprint(self.files, "client")
        self.assertEqual(fp1, fp2)

    def test_resolve_mode_full_when_no_token(self) -> None:
        self.assertEqual(resolve_mode(self.registry, "战斗"), "full")

    def test_full_docx_has_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ctx = build_module_doc_context(
                module="战斗",
                repo="client",
                registry=self.registry,
                repo_root=root,
                changed_paths=["Assets/Scripts/Battle/EnterBattle.cs"],
                files=self.files,
                mode="full",
            )
            xml = build_docx_xml(ctx)
        self.assertIn("模块概览", xml)
        self.assertIn("功能接口", xml)
        self.assertIn("EnterBattleReq", xml)
        self.assertIn("CI生成，待审查", xml)

    def test_delta_docx_has_change_header(self) -> None:
        ctx = build_module_doc_context(
            module="战斗",
            repo="client",
            registry=self.registry,
            repo_root=Path(tempfile.gettempdir()),
            changed_paths=["Assets/Scripts/Battle/EnterBattle.cs"],
            files=self.files,
            mode="delta",
        )
        xml = build_docx_xml(ctx)
        self.assertIn("变更", xml)
        self.assertIn("EnterBattleReq", xml)


class TestModuleDocLayers(unittest.TestCase):
    def test_infer_layers_from_path(self) -> None:
        import yaml

        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proto = root / "Assets/Scripts/Protocol/Battle/EnterBattle.cs"
            proto.parent.mkdir(parents=True)
            proto.write_text("public class X { public int a; }", encoding="utf-8")
            info = infer_module_layers(
                module="战斗",
                repo="client",
                registry=registry,
                repo_root=root,
                changed_paths=["Assets/Scripts/Protocol/Battle/EnterBattle.cs"],
            )
        names = {l["name"] for l in info["layers"]}
        self.assertTrue(names)


class TestModuleDocAgent(unittest.TestCase):
    def test_heuristic_blurb(self) -> None:
        blurb = heuristic_interface_blurb("EnterBattle", ["roomId"], repo="client")
        self.assertIn("Enter Battle", blurb)

    def test_need_agent_off_by_default(self) -> None:
        self.assertFalse(need_agent({"mode": "full", "functional_interfaces": []}))


class TestLarkCliEnv(unittest.TestCase):
    def test_creator_profile_sets_home(self) -> None:
        from lark_cli_env import lark_cli_subprocess_env

        env = lark_cli_subprocess_env(profile="creator")
        self.assertIn("LARK_CLI_HOME", env)
        self.assertTrue(env["LARK_CLI_HOME"].endswith(".lark-creator"))


if __name__ == "__main__":
    unittest.main()
