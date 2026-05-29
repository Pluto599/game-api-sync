#!/usr/bin/env python3
"""Collect module sources and call ECS POST /jobs/api-review (for GitHub Actions)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

from registry_globs import collect_module_files, load_registry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", required=True)
    ap.add_argument("--module", required=True)
    ap.add_argument("--repo", default="client", choices=("client", "server"))
    ap.add_argument("--root", default=".")
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--output", default="report.json")
    args = ap.parse_args()

    reg = load_registry(Path(args.registry))
    files = collect_module_files(Path(args.root), reg, args.module, args.repo)
    if not files:
        print("no files matched registry globs", file=sys.stderr)
        sys.exit(1)

    url = f"{args.base_url.rstrip('/')}/jobs/api-review"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {args.token}",
            "Content-Type": "application/json",
        },
        json={"module": args.module, "repo": args.repo, "files": files},
        timeout=120,
    )
    resp.raise_for_status()
    out = Path(args.output)
    out.write_text(resp.text, encoding="utf-8")
    data = resp.json()
    if data.get("defects"):
        print("API Review: defects found:", "; ".join(data["defects"]))
        sys.exit(0)
    print("API Review: no obvious defects")


if __name__ == "__main__":
    main()
