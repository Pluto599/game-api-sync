#!/usr/bin/env python3
"""Tests for module system-design doc generation."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from build_system_doc import (
    build_initial_docx,
    build_module_doc_context,
    build_section_updates,
    format_update_date,
    resolve_mode,
    resolve_system_design_obj,
    system_doc_fingerprint,
)
from extract_code import extract_type_comment
from module_doc_layers import infer_module_layers
from module_doc_agent import agent_enabled, heuristic_interface_blurb, need_agent
from module_doc_placement import (
    SECTION_FUNC,
    _h3_label,
    _interface_names_from_html,
    _last_dated_block,
    parse_h2_sections,
    should_skip_section_insert,
    system_design_doc_is_empty,
)


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

    def test_csharp_summary_per_class_in_same_file(self) -> None:
        text = (
            "/// <summary>打开商店</summary>\n"
            "public class OpenShopReq { public int shopId; }\n\n"
            "/// <summary>商品同步</summary>\n"
            "public class ShopItemSync { public int itemId; }\n"
        )
        self.assertEqual(extract_type_comment(text, "OpenShopReq", path="Shop.cs"), "打开商店")
        self.assertEqual(extract_type_comment(text, "ShopItemSync", path="Shop.cs"), "商品同步")


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

    def test_format_update_date(self) -> None:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        label = format_update_date(
            datetime(2026, 6, 16, 23, 50, tzinfo=ZoneInfo("Asia/Shanghai"))
        )
        self.assertEqual(label, "2026-6-16 23:50 更新")

    def test_resolve_mode_full_when_no_token(self) -> None:
        self.assertEqual(resolve_mode(self.registry, "战斗"), "full")

    def test_resolve_system_design_obj_shop(self) -> None:
        token = resolve_system_design_obj(self.registry, "商店")
        self.assertTrue(token)

    def test_full_docx_has_dated_sections_no_h1(self) -> None:
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
            xml = build_initial_docx(ctx)
        self.assertNotIn("<h1>", xml)
        self.assertIn("模块概览", xml)
        self.assertIn("分层架构", xml)
        self.assertIn("功能接口", xml)
        self.assertIn("更新", xml)
        self.assertIn("EnterBattleReq", xml)
        self.assertNotIn("CI生成", xml)
        self.assertNotIn("（无）", xml)

    def test_full_docx_empty_data_section_heading_only(self) -> None:
        ctx = build_module_doc_context(
            module="战斗",
            repo="client",
            registry=self.registry,
            repo_root=Path(tempfile.gettempdir()),
            changed_paths=["Assets/Scripts/Battle/EnterBattle.cs"],
            files=self.files,
            mode="full",
        )
        ctx["data_interfaces"] = []
        xml = build_initial_docx(ctx)
        self.assertIn("<h2>数据接口</h2>", xml)
        self.assertNotIn("（无）", xml)
        idx = xml.index("<h2>数据接口</h2>")
        tail = xml[idx + len("<h2>数据接口</h2>") :]
        self.assertFalse(tail.startswith("<h3>"), msg="empty data section should have no dated block")

    def test_delta_section_updates(self) -> None:
        ctx = build_module_doc_context(
            module="战斗",
            repo="client",
            registry=self.registry,
            repo_root=Path(tempfile.gettempdir()),
            changed_paths=["Assets/Scripts/Battle/EnterBattle.cs"],
            files=self.files,
            mode="delta",
        )
        updates = build_section_updates(ctx)
        self.assertIn("模块概览", updates)
        self.assertIn("EnterBattleReq", updates.get("功能接口", ""))
        self.assertNotIn("变更说明", "".join(updates.values()))
        self.assertNotIn("客户端→服务端", updates.get("功能接口", ""))

    def test_delta_skips_empty_layers_section(self) -> None:
        ctx = build_module_doc_context(
            module="战斗",
            repo="client",
            registry=self.registry,
            repo_root=Path(tempfile.gettempdir()),
            changed_paths=["Assets/Scripts/Battle/EnterBattle.cs"],
            files=self.files,
            mode="delta",
        )
        ctx["changed_layers"] = []
        ctx["functional_interfaces"] = []
        ctx["data_interfaces"] = []
        updates = build_section_updates(ctx)
        self.assertNotIn("分层架构", updates)
        self.assertEqual(updates, {})


class TestModuleDocPlacement(unittest.TestCase):
    def test_parse_h2_sections(self) -> None:
        xml = (
            '<h2 id="blk1">模块概览</h2><p>x</p>'
            '<h2 id="blk2">分层架构</h2>'
        )
        sections = parse_h2_sections(xml)
        self.assertEqual(sections[0], ("模块概览", "blk1"))
        self.assertEqual(sections[1], ("分层架构", "blk2"))

    def test_empty_doc_detection(self) -> None:
        from unittest import mock

        with mock.patch(
            "module_doc_placement.fetch_doc_content", return_value="<p></p>"
        ):
            self.assertTrue(system_design_doc_is_empty("tok"))
        with mock.patch(
            "module_doc_placement.fetch_doc_content",
            return_value='<h2 id="b">模块概览</h2>',
        ):
            self.assertFalse(system_design_doc_is_empty("tok"))

    def test_skip_duplicate_interface_block(self) -> None:
        from unittest import mock

        section_xml = (
            '<h3>2026-6-17 12:36 更新</h3>'
            "<ul><li><b>OpenShopReq</b>：a</li><li><b>BuyItemReq</b>：b</li></ul>"
        )
        fragment = (
            '<h3>2026-6-17 12:37 更新</h3>'
            "<ul><li><b>OpenShopReq</b>：c</li><li><b>BuyItemReq</b>：d</li></ul>"
        )
        with mock.patch(
            "module_doc_placement.fetch_section_content", return_value=section_xml
        ):
            skip, reason = should_skip_section_insert("tok", SECTION_FUNC, fragment)
        self.assertTrue(skip)
        self.assertEqual(reason, "duplicate_interface_names")

    def test_skip_duplicate_timestamp_overview(self) -> None:
        section_xml = "<h3>2026-6-17 12:36 更新</h3><p>第一次概览</p>"
        fragment = "<h3>2026-6-17 12:36 更新</h3><p>第二次概览</p>"
        from unittest import mock

        from module_doc_placement import SECTION_OVERVIEW

        with mock.patch(
            "module_doc_placement.fetch_section_content", return_value=section_xml
        ):
            skip, reason = should_skip_section_insert("tok", SECTION_OVERVIEW, fragment)
        self.assertTrue(skip)
        self.assertEqual(reason, "duplicate_timestamp")

    def test_last_dated_block_helpers(self) -> None:
        xml = "<h3>2026-6-17 12:00 更新</h3><p>old</p><h3>2026-6-17 12:36 更新</h3><p>new</p>"
        block = _last_dated_block(xml)
        self.assertIn("new", block)
        self.assertEqual(_h3_label(block), "2026-6-17 12:36 更新")
        self.assertEqual(_interface_names_from_html(block), frozenset())


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
        self.assertIn("进入", blurb)
        self.assertIn("战斗", blurb)
        self.assertNotIn("自动生成", blurb)
        self.assertNotIn("待核对", blurb)
        self.assertNotIn("字段含", blurb)

    def test_heuristic_blurb_room_examples(self) -> None:
        blurb = heuristic_interface_blurb(
            "SetReadyStatusRequest", ["uid", "ready"], repo="client"
        )
        self.assertIn("设置", blurb)
        self.assertIn("准备", blurb)
        self.assertIn("请求", blurb)
        self.assertNotIn("Set Ready", blurb)
        self.assertNotIn("自动生成", blurb)

        blurb = heuristic_interface_blurb(
            "BroadcastRoomStatusResponse", ["roomInfo"], repo="server"
        )
        self.assertIn("广播", blurb)
        self.assertIn("响应", blurb)
        self.assertIn("roomInfo", blurb)
        self.assertNotIn("Broadcast Room", blurb)

    def test_sanitize_blurb_strips_placeholder(self) -> None:
        from module_doc_agent import _sanitize_blurb

        self.assertEqual(
            _sanitize_blurb(
                "Set Ready Status Request，字段含 uid, ready（自动生成，待核对）"
            ),
            "Set Ready Status Request，字段含 uid, ready",
        )
        self.assertEqual(_sanitize_blurb("打开商店（自动生成，待核对）"), "打开商店")

    def test_need_agent_on_by_default(self) -> None:
        old = os.environ.pop("MODULE_DOC_USE_AGENT", None)
        try:
            ctx = {
                "mode": "full",
                "functional_interfaces": [{"name": "EnterBattle"}],
                "data_interfaces": [],
                "layers": [],
            }
            self.assertTrue(agent_enabled())
            self.assertTrue(need_agent(ctx))
        finally:
            if old is not None:
                os.environ["MODULE_DOC_USE_AGENT"] = old

    def test_need_agent_off_when_disabled(self) -> None:
        old = os.environ.get("MODULE_DOC_USE_AGENT")
        os.environ["MODULE_DOC_USE_AGENT"] = "false"
        try:
            self.assertFalse(need_agent({"mode": "full", "functional_interfaces": [{"name": "X"}]}))
        finally:
            if old is None:
                os.environ.pop("MODULE_DOC_USE_AGENT", None)
            else:
                os.environ["MODULE_DOC_USE_AGENT"] = old


class TestLarkCliEnv(unittest.TestCase):
    def test_creator_profile_sets_home(self) -> None:
        from lark_cli_env import lark_cli_subprocess_env

        env = lark_cli_subprocess_env(profile="creator")
        self.assertIn("LARK_CLI_HOME", env)
        self.assertTrue(env["LARK_CLI_HOME"].endswith(".lark-creator"))


if __name__ == "__main__":
    unittest.main()
