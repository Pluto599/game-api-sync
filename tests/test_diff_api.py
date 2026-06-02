#!/usr/bin/env python3
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from diff_api import compare_snapshot_to_code  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
