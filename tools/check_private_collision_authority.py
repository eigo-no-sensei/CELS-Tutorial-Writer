#!/usr/bin/env python3
"""Validate the private C3 collision-authority fixtures through Rust reconciliation."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = json.loads((ROOT / "contracts" / "release_gate.json").read_text(encoding="utf-8"))
CONFIG = GATE["private_collision_authority"]


def default_fixture_paths() -> tuple[Path, Path]:
    override = os.environ.get(CONFIG.get("fixture_root_env", ""), "").strip()
    if override:
        root = Path(override).expanduser().resolve()
        return root / CONFIG["expected_subdir"], root / CONFIG["raw_subdir"]
    return ROOT / CONFIG["expected_dir"], ROOT / CONFIG["raw_dir"]


def main() -> int:
    default_expected, default_raw = default_fixture_paths()
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-dir", type=Path, default=default_expected)
    parser.add_argument("--raw-dir", type=Path, default=default_raw)
    args = parser.parse_args()

    expected = args.expected_dir.resolve()
    raw = args.raw_dir.resolve()
    if not expected.is_dir() or not raw.is_dir():
        print(
            f"private collision authority FAIL — fixture directories missing: expected={expected} raw={raw}",
            file=sys.stderr,
        )
        return 2

    labels = sorted(path.stem for path in expected.glob("*.json"))
    required = sorted(CONFIG["required_labels"])
    if labels != required:
        print(
            f"private collision authority FAIL — labels {labels!r} != required {required!r}",
            file=sys.stderr,
        )
        return 1
    if len(labels) != int(CONFIG["required_fixture_count"]):
        print(
            "private collision authority FAIL — fixture count "
            f"{len(labels)} != required {CONFIG['required_fixture_count']}",
            file=sys.stderr,
        )
        return 1

    cmd = [
        "cargo",
        "run",
        "--quiet",
        "--bin",
        "check_reconciliation_fixtures",
        "--",
        str(expected),
        str(raw),
    ]
    proc = subprocess.run(cmd, cwd=ROOT / "gel-core")
    if proc.returncode != 0:
        print(
            f"private collision authority FAIL — Rust checker exited {proc.returncode}",
            file=sys.stderr,
        )
        return proc.returncode or 1

    print(
        "private collision authority PASS — "
        f"{len(labels)} fixtures / no positional collision assignment / divergent revision blocked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
