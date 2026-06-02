#!/usr/bin/env python3
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from doc_placement import (  # noqa: E402
    _last_block_id_in_xml,
    _parse_h1_outline,
    strip_merge_location_paragraphs,
)


def test_strip_merge_location():
    xml = (
        "<p>【合并位置】接口文档 → 战斗 → h1 客户端 章节下</p>"
        "<h2>武器（agent生成，待审查）</h2><pre><code>x</code></pre>"
    )
    out = strip_merge_location_paragraphs(xml)
    assert "【合并位置】" not in out
    assert "武器" in out


def test_parse_h1_outline():
    content = (
        '<h1 id="blkA">客户端</h1>'
        '<h2 id="blkB">准备</h2>'
        '<h1 id="blkC">服务端</h1>'
    )
    h1s = _parse_h1_outline(content)
    assert h1s == [("客户端", "blkA"), ("服务端", "blkC")]


def test_last_block_id():
    xml = '<h1 id="blka">x</h1><pre id="blkz"><code>1</code></pre>'
    assert _last_block_id_in_xml(xml) == "blkz"


if __name__ == "__main__":
    test_strip_merge_location()
    test_parse_h1_outline()
    test_last_block_id()
    print("ok")
