#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from classify_diff import classify_compare_result  # noqa: E402
from code_to_docx import build_docx_draft  # noqa: E402
from diff_api import compare_snapshot_to_code  # noqa: E402
from message_aliases import resolve_code_name  # noqa: E402


FIX = ROOT / "tests" / "fixtures"


class DiffApiTests(unittest.TestCase):
    def test_battle_field_level_diff(self):
        snap = json.loads((FIX / "battle_snapshot.json").read_text(encoding="utf-8"))
        code = (FIX / "battle_client.cs").read_text(encoding="utf-8")
        r = compare_snapshot_to_code(
            snap,
            {"Assets/Battle/Proto.cs": code},
            module="战斗",
            repo="client",
        )
        self.assertTrue(r["ok"])
        self.assertTrue(any("extraField" in d or "多字段" in d for d in r["defects"]))
        enter = next(x for x in r["message_results"] if x.get("message") == "EnterBattleReq")
        self.assertEqual(enter["status"], "diff")
        self.assertIn("extraField", enter["missing_in_doc"])

    def test_battle_uid_not_global_false_positive(self):
        snap = json.loads((FIX / "battle_snapshot.json").read_text(encoding="utf-8"))
        code = (FIX / "battle_client.cs").read_text(encoding="utf-8")
        r = compare_snapshot_to_code(
            snap,
            {"Assets/Battle/Proto.cs": code},
            module="战斗",
            repo="client",
        )
        ready = next(x for x in r["message_results"] if x.get("message") == "PlayerReadyMsg")
        self.assertEqual(ready["status"], "ok")

    def test_network_enum_member_diff(self):
        snap = json.loads((FIX / "network_snapshot.json").read_text(encoding="utf-8"))
        code = (FIX / "network_server.cpp").read_text(encoding="utf-8")
        r = compare_snapshot_to_code(
            snap,
            {"src/packet.h": code},
            module="网络相关",
            repo="server",
        )
        self.assertTrue(any(ei.get("enum") == "PacketType" for ei in r["enum_issues"]))

    def test_alias_match_login(self):
        snap = {
            "module": "登录界面",
            "api_docs": {
                "structs": [
                    {
                        "name": None,
                        "section": "注册请求",
                        "direction": "server",
                        "fields": [{"name": "username", "type": "string", "optional": False}],
                        "raw_code": "username: string;",
                    }
                ],
                "enums": [],
            },
        }
        code_src = """
        public struct RegisterReq {
            public string username;
        }
        """
        r = compare_snapshot_to_code(
            snap,
            {"src/register.cs": code_src},
            module="登录界面",
            repo="server",
        )
        row = next(x for x in r["message_results"] if x.get("message") == "RegisterReq")
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row.get("matched_via"), "alias")

    def test_scoped_compare_ignores_out_of_scope(self):
        snap = {"module": "战斗", "api_docs": {"structs": [], "enums": []}}
        battle = (FIX / "battle_client.cs").read_text(encoding="utf-8")
        extra = "public struct ShopInitReq {\n  public int shopId;\n}\n"
        r = compare_snapshot_to_code(
            snap,
            {"Assets/Battle/Proto.cs": battle + extra},
            module="战斗",
            repo="client",
            scope_type_names={"EnterBattleReq", "PlayerReadyMsg"},
        )
        self.assertIn("ShopInitReq", r["ignored_out_of_scope"])
        self.assertFalse(any(x.get("message") == "ShopInitReq" for x in r["message_results"]))


class ClassifyTests(unittest.TestCase):
    def test_code_ahead(self):
        r = classify_compare_result(
            {"message_results": [{"status": "missing_in_doc", "message": "Foo"}], "defects": ["x"]}
        )
        self.assertEqual(r["classification"], "code_ahead")
        self.assertTrue(r["sync_recommended"])


class CodeToDocxTests(unittest.TestCase):
    def test_build_draft_contains_type_name(self):
        snap = json.loads((FIX / "battle_snapshot.json").read_text(encoding="utf-8"))
        code = (FIX / "battle_client.cs").read_text(encoding="utf-8")
        compare = compare_snapshot_to_code(
            snap,
            {"Assets/Battle/Proto.cs": code},
            module="战斗",
            repo="client",
        )
        draft = build_docx_draft(
            snapshot=snap,
            compare_result=compare,
            files={"Assets/Battle/Proto.cs": code},
            repo="client",
        )
        self.assertIn("EnterBattleReq", draft)
        self.assertIn("CI生成", draft)


class AliasTests(unittest.TestCase):
    def test_resolve_alias(self):
        self.assertEqual(
            resolve_code_name("联机大厅", doc_name="开启房间", section="开启房间"),
            "CreateRoomReq",
        )


if __name__ == "__main__":
    unittest.main()
