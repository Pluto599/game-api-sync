#!/usr/bin/env python3
"""Send Feishu group notification via lark-cli (optional infra)."""

from __future__ import annotations

import os
import subprocess


def notify_doc_updated(module: str, *, chat_id: str | None = None) -> None:
    cid = chat_id or os.environ.get("FEISHU_NOTIFY_CHAT_ID", "").strip()
    if not cid:
        return
    text = (
        f"【接口文档】{module} 已更新。"
        f"请在 client/server 当前分支 IDE 说：对齐 {module} 模块代码到文档。"
    )
    subprocess.run(
        [
            "lark-cli",
            "im",
            "+messages-send",
            "--chat-id",
            cid,
            "--text",
            text,
            "--as",
            "bot",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
