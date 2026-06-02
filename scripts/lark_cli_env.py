"""Ensure lark-cli finds config when run from systemd (HOME may be unset)."""

from __future__ import annotations

import os
from pathlib import Path


def lark_cli_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    home = env.get("HOME", "").strip()
    if not home or not Path(home).is_dir():
        for candidate in ("/root", str(Path.home())):
            if candidate and Path(candidate).is_dir():
                env["HOME"] = candidate
                break
    env.setdefault("USER", "root")
    return env
