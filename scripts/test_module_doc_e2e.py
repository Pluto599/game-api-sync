#!/usr/bin/env python3
"""One-off E2E test: fictional protocol files -> ECS module-system-doc-sync."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import yaml  # noqa: E402

from build_system_doc import (  # noqa: E402
    build_initial_docx,
    build_module_doc_context,
    build_section_updates,
    resolve_mode,
)

REGISTRY = Path(__file__).resolve().parents[1] / "config" / "wiki-registry.yaml"
MODULE = "商店"
REPO = "client"
CHANGED = "Assets/Scripts/Protocol/Shop/FictionalE2ETest.cs"
FAKE_CODE = """\
/// <summary>请求打开商店界面（E2E 虚构测试）</summary>
public class OpenShopReq { public int shopId; }

/// <summary>商店商品列表同步</summary>
public class ShopItemSync { public int itemId; public int price; }

/// <summary>购买商品</summary>
public class BuyItemReq { public int itemId; public int count; }
public class BuyItemRsp { public bool success; }
"""


def api_post(path: str, body: dict) -> tuple[int, dict | str]:
    base = os.environ.get("API_SYNC_BASE", "http://120.27.249.20").rstrip("/")
    token = os.environ.get("API_SYNC_TOKEN", "")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{base}{path}", data=data, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(detail)
        except json.JSONDecodeError:
            return e.code, detail


def main() -> None:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    files = {CHANGED: FAKE_CODE}
    mode = resolve_mode(registry, MODULE, check_doc_content=False)
    if os.environ.get("E2E_FORCE_MODE"):
        mode = os.environ["E2E_FORCE_MODE"]

    ctx = build_module_doc_context(
        module=MODULE,
        repo=REPO,
        registry=registry,
        repo_root=Path("/tmp"),
        changed_paths=[CHANGED],
        files=files,
        mode=mode,
    )
    preview = (
        build_initial_docx(ctx) if mode == "full" else "".join(build_section_updates(ctx).values())
    )
    print(f"mode={mode} agent_used={ctx.get('agent_used')} preview_len={len(preview)}")
    print("--- preview (first 500 chars) ---")
    print(preview[:500])

    code, resp_files = api_post(
        "/jobs/module-system-doc-sync",
        {
            "module": MODULE,
            "repo": REPO,
            "mode": "auto",
            "files_changed": [CHANGED],
            "files": files,
        },
    )
    print(f"\n[files-only POST] HTTP {code}")
    print(json.dumps(resp_files, ensure_ascii=False, indent=2))

    if code >= 400:
        print("\nPOST failed — deploy latest api-server to ECS and retry.")
        sys.exit(1)
    print("\nServer-side build succeeded on ECS.")
    if resp_files.get("sections_updated"):
        print("sections_updated:", resp_files["sections_updated"])


if __name__ == "__main__":
    main()
