#!/usr/bin/env python3
"""Feishu wiki operations for module system-design docs (creator lark-cli profile)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from lark_cli_env import lark_cli_subprocess_env

LARK_PROFILE = "creator"


def _load_registry(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def system_design_parent_token(registry: dict[str, Any]) -> str:
    for root in registry.get("roots") or []:
        if root.get("key") == "system_design":
            token = root.get("node_token")
            if token:
                return str(token)
    raise ValueError("wiki-registry roots missing system_design.node_token")


def resolve_system_design_obj(registry: dict[str, Any], module: str) -> str | None:
    info = (registry.get("modules") or {}).get(module) or {}
    token = info.get("system_design_obj")
    if token and str(token).strip().lower() not in ("", "null", "none"):
        return str(token)
    return None


def _run_lark(args: list[str]) -> dict[str, Any]:
    cmd = ["lark-cli", *args, "--as", "user"]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=lark_cli_subprocess_env(profile=LARK_PROFILE),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "lark-cli failed").strip())
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout.strip()}


def create_module_wiki_doc(registry: dict[str, Any], module: str) -> dict[str, Any]:
    parent = system_design_parent_token(registry)
    payload = _run_lark(
        [
            "wiki",
            "+node-create",
            "--parent-node-token",
            parent,
            "--title",
            module,
            "--obj-type",
            "docx",
        ]
    )
    data = payload.get("data") or {}
    obj_token = data.get("obj_token")
    node_token = data.get("node_token")
    if not obj_token:
        raise RuntimeError(f"wiki +node-create missing obj_token: {payload}")
    return {
        "created": True,
        "obj_token": obj_token,
        "node_token": node_token,
        "parent_node_token": parent,
        "url": data.get("url"),
        "feishu": payload,
        "lark_profile": LARK_PROFILE,
    }


def append_system_doc(obj_token: str, docx_xml: str) -> dict[str, Any]:
    update_cmd = [
        "docs",
        "+update",
        "--api-version",
        "v2",
        "--doc",
        obj_token,
        "--command",
        "append",
        "--content",
        docx_xml,
    ]
    result = subprocess.run(
        ["lark-cli", *update_cmd, "--as", "user"],
        capture_output=True,
        text=True,
        check=False,
        env=lark_cli_subprocess_env(profile=LARK_PROFILE),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "docs +update failed").strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"raw": result.stdout.strip()}
    return {
        "ok": True,
        "doc_token": obj_token,
        "lark_profile": LARK_PROFILE,
        "feishu": payload,
    }


def sync_system_doc(
    reg_path: Path,
    *,
    module: str,
    repo: str,
    docx_draft: str,
    files_changed: list[str],
    mode: str,
) -> dict[str, Any]:
    reg = _load_registry(reg_path)
    obj_token = resolve_system_design_obj(reg, module)
    created = False
    action_required: str | None = None

    if mode == "full" and not obj_token:
        create_result = create_module_wiki_doc(reg, module)
        obj_token = create_result["obj_token"]
        created = True
        action_required = (
            f"将 system_design_obj: {obj_token} 写入 config/wiki-registry.yaml "
            f"modules.{module}"
        )

    if not obj_token:
        raise ValueError(
            f"module '{module}' has no system_design_obj; create wiki node first"
        )

    if not docx_draft.strip():
        raise ValueError("docx_draft must not be empty")

    sync_result = append_system_doc(obj_token, docx_draft)
    out: dict[str, Any] = {
        **sync_result,
        "module": module,
        "repo": repo,
        "mode": mode,
        "created": created,
        "system_design_obj": obj_token,
        "files_changed": files_changed,
    }
    if action_required:
        out["action_required"] = action_required
    return out
