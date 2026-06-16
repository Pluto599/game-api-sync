#!/usr/bin/env python3
"""Optional LLM blurbs for module system docs (Phase 2). MVP: heuristics only."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

_MAX_OVERVIEW_LEN = 120
_MAX_ROLE_LEN = 60
_MAX_BLURB_LEN = 80


def _camel_to_words(name: str) -> str:
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ")
    return parts.strip()


def heuristic_interface_blurb(name: str, fields: list[str], *, repo: str) -> str:
    words = _camel_to_words(name)
    dir_label = "客户端→服务端" if repo == "client" else "服务端→客户端"
    if fields:
        fs = ", ".join(fields[:4])
        return f"{words}，字段含 {fs}（{dir_label}，自动生成，待核对）"[: _MAX_BLURB_LEN]
    return f"{words}（{dir_label}，自动生成，待核对）"[: _MAX_BLURB_LEN]


def heuristic_overview_paragraphs(context: dict[str, Any]) -> list[str]:
    module = context.get("module", "")
    notes = (context.get("registry_notes") or "").strip()
    func_n = len(context.get("functional_interfaces") or [])
    data_n = len(context.get("data_interfaces") or [])
    paras: list[str] = []
    if notes:
        paras.append(notes[:_MAX_OVERVIEW_LEN])
    paras.append(
        f"「{module}」模块，含 {func_n} 个功能接口与 {data_n} 个数据类型。"
        if func_n or data_n
        else f"「{module}」模块相关代码变更。"
    )
    return [p[:_MAX_OVERVIEW_LEN] for p in paras[:3]]


def heuristic_delta_summary(context: dict[str, Any]) -> str:
    from pathlib import Path

    func_n = len(context.get("functional_interfaces") or [])
    data_n = len(context.get("data_interfaces") or [])
    paths = context.get("changed_paths") or []
    files = ", ".join(Path(p).name for p in paths[:5])
    return (
        f"本次合并：新增/变更功能接口 {func_n} 个、数据接口 {data_n} 个。"
        + (f" 涉及文件：{files}" if files else "")
    )[:200]


def _cache_key(context: dict[str, Any]) -> str:
    raw = json.dumps(context, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _call_ollama(prompt: str) -> str | None:
    base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0},
    }
    try:
        req = urllib.request.Request(
            f"{base}/api/generate",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return (data.get("response") or "").strip() or None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _validate_agent_json(raw: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    allowed_ifaces = {i["name"] for i in context.get("functional_interfaces") or []}
    allowed_ifaces |= {i["name"] for i in context.get("data_interfaces") or []}
    out: dict[str, Any] = {}
    paras = raw.get("overview_paragraphs")
    if isinstance(paras, list):
        out["overview_paragraphs"] = [str(p)[:_MAX_OVERVIEW_LEN] for p in paras[:3]]
    blurbs = raw.get("interface_blurbs")
    if isinstance(blurbs, dict):
        out["interface_blurbs"] = {
            k: str(v)[:_MAX_BLURB_LEN]
            for k, v in blurbs.items()
            if k in allowed_ifaces
        }
    roles = raw.get("layer_roles")
    if isinstance(roles, dict):
        allowed_layers = {l["name"] for l in context.get("layers") or []}
        out["layer_roles"] = {
            k: str(v)[:_MAX_ROLE_LEN] for k, v in roles.items() if k in allowed_layers
        }
    return out


def need_agent(context: dict[str, Any]) -> bool:
    if os.environ.get("MODULE_DOC_USE_AGENT", "").lower() not in ("1", "true", "yes"):
        return False
    mode = context.get("mode")
    notes = (context.get("registry_notes") or "").strip()
    ifaces = context.get("functional_interfaces") or []
    data = context.get("data_interfaces") or []
    if mode == "full" and not notes:
        return True
    if any(not (i.get("source_comment") or "").strip() for i in ifaces + data):
        return True
    return False


def enrich_context(context: dict[str, Any]) -> dict[str, Any]:
    """Add overview_paragraphs, layer role overrides, interface blurbs."""
    result = dict(context)
    blurbs: dict[str, str] = {}
    repo = context.get("repo", "client")

    for iface in context.get("functional_interfaces") or []:
        name = iface["name"]
        comment = (iface.get("source_comment") or "").strip()
        fields = [f.strip() for f in (iface.get("fields_summary") or "").split(",") if f.strip()]
        blurbs[name] = comment or heuristic_interface_blurb(name, fields, repo=repo)

    for item in context.get("data_interfaces") or []:
        name = item["name"]
        comment = (item.get("source_comment") or "").strip()
        members = item.get("members") or []
        if comment:
            blurbs[name] = comment
        elif item.get("kind") == "enum":
            blurbs[name] = f"{_camel_to_words(name)} 枚举：{', '.join(members[:5])}"[
                :_MAX_BLURB_LEN
            ]
        else:
            blurbs[name] = f"{_camel_to_words(name)} 类型约束"[:_MAX_BLURB_LEN]

    agent_data: dict[str, Any] = {}
    if need_agent(context):
        compact = {
            k: context[k]
            for k in (
                "module",
                "repo",
                "mode",
                "functional_interfaces",
                "data_interfaces",
                "layers",
                "registry_notes",
            )
            if k in context
        }
        prompt = (
            "你是游戏模块文档助手。仅返回 JSON，不要 markdown。"
            '格式: {"overview_paragraphs":["..."], "layer_roles":{"层名":"..."}, '
            '"interface_blurbs":{"接口名":"..."}}。'
            "每条 interface_blurbs 不超过80字。不得编造 context 中不存在的接口名。\n"
            + json.dumps(compact, ensure_ascii=False)[:4000]
        )
        backend = os.environ.get("MODULE_DOC_AGENT_BACKEND", "ollama")
        raw_text: str | None = None
        if backend == "ollama":
            raw_text = _call_ollama(prompt)
        if raw_text:
            try:
                start = raw_text.find("{")
                end = raw_text.rfind("}") + 1
                if start >= 0 and end > start:
                    agent_data = _validate_agent_json(
                        json.loads(raw_text[start:end]), context
                    )
            except json.JSONDecodeError:
                agent_data = {}

    if context.get("mode") == "delta":
        result["delta_summary"] = agent_data.get("delta_summary") or heuristic_delta_summary(
            context
        )
        result["overview_paragraphs"] = [result["delta_summary"]]
    else:
        result["overview_paragraphs"] = agent_data.get("overview_paragraphs") or (
            heuristic_overview_paragraphs(context)
        )

    for layer in result.get("layers") or []:
        overrides = agent_data.get("layer_roles") or {}
        if layer["name"] in overrides:
            layer["role"] = overrides[layer["name"]]

    for name, blurb in (agent_data.get("interface_blurbs") or {}).items():
        if name in blurbs and blurbs[name].endswith("待核对）"):
            blurbs[name] = blurb

    result["interface_blurbs"] = blurbs
    result["agent_used"] = bool(agent_data)
    return result
