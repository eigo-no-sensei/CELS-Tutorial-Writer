#!/usr/bin/env python3
"""Ensure supplied CI performs portable enforcement without claiming strict acceptance."""
from __future__ import annotations

import sys
from pathlib import Path

from release_common import ROOT


def main() -> int:
    path = ROOT / ".github" / "workflows" / "portable-governance.yml"
    if not path.is_file():
        print("CI contract: FAIL — portable workflow missing", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    required = [
        "python tools/release_gate.py --profile portable --scope w2",
        "actions/checkout@v4",
        "actions/setup-python@v5",
        "actions/setup-node@v4",
        "dtolnay/rust-toolchain@stable",
    ]
    missing = [x for x in required if x not in text]
    if missing:
        print(f"CI contract: FAIL — missing {missing}", file=sys.stderr)
        return 1
    forbidden = ["--profile strict", "GEL_PRIVATE_FIXTURES_DIR", "STRICT_ACCEPTED", "RELEASE_ARTIFACT_VERIFIED"]
    present = [x for x in forbidden if x in text]
    if present:
        print(f"CI contract: FAIL — CI crosses strict/private authority boundary: {present}", file=sys.stderr)
        return 1
    print("CI contract: PASS — portable enforcement only; strict acceptance remains target-host/manual")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
