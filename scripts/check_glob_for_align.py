#!/usr/bin/env python3
"""CLI: check align file paths against module glob; print JSON for IDE Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from glob_coverage import check_paths_for_align  # noqa: E402
from registry_globs import load_registry  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Check paths vs wiki-registry glob before align")
    parser.add_argument("--module", required=True, help="module name e.g. 商店")
    parser.add_argument("--repo", choices=("client", "server"), default="client")
    parser.add_argument("--registry", default="config/wiki-registry.yaml")
    parser.add_argument("--paths", nargs="+", required=True, help="protocol file paths to align")
    parser.add_argument(
        "--user-explicit",
        nargs="*",
        default=[],
        help="paths user @ or explicitly requested (bypass ui/resource skip)",
    )
    parser.add_argument("--repo-root", default=".", help="game repo root")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    reg = load_registry(root / args.registry)
    result = check_paths_for_align(
        root,
        reg,
        args.module,
        args.repo,
        args.paths,
        user_explicit=set(args.user_explicit or []),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
