"""Ensure lark-cli finds config when run from systemd (HOME may be unset)."""

from __future__ import annotations

import os
from pathlib import Path


def lark_cli_subprocess_env(*, profile: str = "default") -> dict[str, str]:
    """Build subprocess env for lark-cli.

    profile=default — existing GameBot / ops user (api-doc sync, snapshots).
    profile=creator — ModuleDocBot under MODULE_DOC_LARK_CLI_HOME (system-design wiki).
    """
    env = os.environ.copy()
    home = env.get("HOME", "").strip()
    if not home or not Path(home).is_dir():
        for candidate in ("/root", str(Path.home())):
            if candidate and Path(candidate).is_dir():
                env["HOME"] = candidate
                break
    env.setdefault("USER", "root")
    if profile == "creator":
        env["LARK_CLI_HOME"] = os.environ.get(
            "MODULE_DOC_LARK_CLI_HOME",
            "/opt/api-sync/.lark-creator",
        )
    return env
