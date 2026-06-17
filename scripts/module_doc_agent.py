#!/usr/bin/env python3
"""LLM blurbs for module system docs (default: Cursor Agent)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

_MAX_OVERVIEW_LEN = 120
_MAX_ROLE_LEN = 60
_MAX_BLURB_LEN = 80

_FORBIDDEN_BLURB_MARKERS = (
    "（自动生成，待核对）",
    "自动生成，待核对",
    "（待核对）",
    "待核对",
)


def _sanitize_blurb(text: str) -> str:
    s = (text or "").strip()
    for marker in _FORBIDDEN_BLURB_MARKERS:
        s = s.replace(marker, "")
    s = re.sub(r"[（(]\s*[）)]", "", s)
    return re.sub(r"\s+", " ", s).strip(" ，,;；")


def _camel_to_words(name: str) -> str:
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name).replace("_", " ")
    return parts.strip()


def heuristic_interface_blurb(name: str, fields: list[str], *, repo: str) -> str:
    words = _camel_to_words(name)
    if fields:
        fs = ", ".join(fields[:4])
        return f"{words}，字段含 {fs}"[: _MAX_BLURB_LEN]
    return words[: _MAX_BLURB_LEN]


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


def agent_enabled() -> bool:
    """Default on; set MODULE_DOC_USE_AGENT=false to disable."""
    return os.environ.get("MODULE_DOC_USE_AGENT", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _validate_agent_json(raw: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    allowed_ifaces = {i["name"] for i in context.get("functional_interfaces") or []}
    allowed_ifaces |= {i["name"] for i in context.get("data_interfaces") or []}
    out: dict[str, Any] = {}
    paras = raw.get("overview_paragraphs")
    if isinstance(paras, list):
        out["overview_paragraphs"] = [str(p)[:_MAX_OVERVIEW_LEN] for p in paras[:3]]
    delta = raw.get("delta_summary")
    if isinstance(delta, str) and delta.strip():
        out["delta_summary"] = delta.strip()[:200]
    blurbs = raw.get("interface_blurbs")
    if isinstance(blurbs, dict):
        out["interface_blurbs"] = {
            k: _sanitize_blurb(str(v))[:_MAX_BLURB_LEN]
            for k, v in blurbs.items()
            if k in allowed_ifaces and _sanitize_blurb(str(v))
        }
    roles = raw.get("layer_roles")
    if isinstance(roles, dict):
        allowed_layers = {l["name"] for l in context.get("layers") or []}
        out["layer_roles"] = {
            k: str(v)[:_MAX_ROLE_LEN] for k, v in roles.items() if k in allowed_layers
        }
    return out


def need_agent(context: dict[str, Any]) -> bool:
    if not agent_enabled():
        return False
    ifaces = context.get("functional_interfaces") or []
    data = context.get("data_interfaces") or []
    layers = context.get("layers") or []
    mode = context.get("mode")
    if mode == "full":
        return bool(ifaces or data or layers)
    if mode == "delta":
        return bool(ifaces or data)
    return bool(ifaces or data)


def _call_ollama(prompt: str) -> str | None:
    import urllib.error
    import urllib.request

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
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            return (data.get("response") or "").strip() or None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _call_cursor(prompt: str) -> str | None:
    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from cursor_sdk import Agent, AgentOptions
    except ImportError:
        return None
    model = os.environ.get("MODULE_DOC_CURSOR_MODEL", "composer-2.5")
    try:
        result = Agent.prompt(prompt, AgentOptions(api_key=api_key, model=model))
        text = getattr(result, "result", None) or ""
        return str(text).strip() or None
    except Exception:
        return None


def _build_prompt(context: dict[str, Any]) -> str:
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
            "changed_paths",
        )
        if k in context
    }
    delta_hint = ""
    if context.get("mode") == "delta":
        delta_hint = '含 "delta_summary":"本次PR变更一句话", '
    return (
        "你是游戏模块文档助手。仅返回 JSON，不要 markdown 代码块。"
        f'格式: {{{delta_hint}"overview_paragraphs":["..."], "layer_roles":{{"层名":"..."}}, '
        '"interface_blurbs":{"接口名":"一句功能说明"}}}。'
        "overview 每段不超过120字；interface_blurbs 每条不超过80字。"
        "interface_blurbs 写自然中文功能说明，禁止「自动生成」「待核对」等占位语。"
        "不得编造 context 中不存在的接口名或层名。\n"
        + json.dumps(compact, ensure_ascii=False)[:4000]
    )


def _invoke_llm(prompt: str) -> str | None:
    backend = os.environ.get("MODULE_DOC_AGENT_BACKEND", "cursor").lower()
    if backend == "ollama":
        return _call_ollama(prompt)
    if backend == "cursor":
        return _call_cursor(prompt)
    return None


def _parse_agent_json(raw_text: str, context: dict[str, Any]) -> dict[str, Any]:
    try:
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start >= 0 and end > start:
            return _validate_agent_json(json.loads(raw_text[start:end]), context)
    except json.JSONDecodeError:
        pass
    return {}


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
        raw_text = _invoke_llm(_build_prompt(context))
        if raw_text:
            agent_data = _parse_agent_json(raw_text, context)

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
        if name in blurbs:
            blurbs[name] = _sanitize_blurb(blurb)

    for name in list(blurbs.keys()):
        blurbs[name] = _sanitize_blurb(blurbs[name])

    result["interface_blurbs"] = blurbs
    result["agent_used"] = bool(agent_data)
    result["agent_requested"] = need_agent(context)
    return result
