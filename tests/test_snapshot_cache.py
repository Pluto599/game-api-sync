#!/usr/bin/env python3
"""Tests for snapshot_cache revision compare."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from snapshot_cache import (  # noqa: E402
    cached_part_revision,
    module_doc_tokens,
    parse_revision_from_fetch,
    revisions_stale,
)


class TestSnapshotCache(unittest.TestCase):
    def test_parse_revision_from_fetch(self) -> None:
        raw = {"data": {"document": {"revision_id": 42}}}
        self.assertEqual(parse_revision_from_fetch(raw), 42)

    def test_module_doc_tokens(self) -> None:
        tokens = module_doc_tokens(
            {"api_docs_obj": "tok1", "type_constraints_obj": "tok2"}
        )
        self.assertEqual(tokens, {"api_docs": "tok1", "type_constraints": "tok2"})

    def test_revisions_stale_no_cache(self) -> None:
        stale, reason, _ = revisions_stale(None, {"api_docs": 10})
        self.assertTrue(stale)
        self.assertEqual(reason, "no_cache")

    def test_revisions_fresh_when_match(self) -> None:
        cached = {"api_docs": {"revision_id": 10}, "type_constraints": {"revision_id": 20}}
        stale, reason, detail = revisions_stale(
            cached, {"api_docs": 10, "type_constraints": 20}
        )
        self.assertFalse(stale)
        self.assertEqual(reason, "revision_unchanged")
        self.assertEqual(detail["parts"]["api_docs"]["remote"], 10)

    def test_revisions_stale_on_mismatch(self) -> None:
        cached = {"api_docs": {"revision_id": 10}}
        stale, reason, _ = revisions_stale(cached, {"api_docs": 11})
        self.assertTrue(stale)
        self.assertEqual(reason, "revision_mismatch:api_docs")

    def test_revisions_stale_missing_remote(self) -> None:
        cached = {"api_docs": {"revision_id": 10}}
        stale, reason, _ = revisions_stale(cached, {"api_docs": None})
        self.assertTrue(stale)
        self.assertEqual(reason, "missing_remote_revision:api_docs")

    def test_cached_part_revision(self) -> None:
        cached = {"api_docs": {"revision_id": 7}}
        self.assertEqual(cached_part_revision(cached, "api_docs"), 7)
        self.assertIsNone(cached_part_revision(cached, "type_constraints"))


if __name__ == "__main__":
    unittest.main()
