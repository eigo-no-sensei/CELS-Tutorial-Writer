#!/usr/bin/env python3
"""Validate C4 offline semantic-to-POST round trips across all private edit fixtures."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = json.loads((ROOT / "contracts" / "release_gate.json").read_text(encoding="utf-8"))
CONFIG = GATE["private_post_round_trip"]


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
            f"private POST round trip FAIL — fixture directories missing: expected={expected} raw={raw}",
            file=sys.stderr,
        )
        return 2

    expected_files = sorted(expected.glob("*.json"))
    raw_files = sorted(raw.glob("*.html"))
    required_count = int(CONFIG["required_fixture_count"])
    if len(expected_files) != required_count or len(raw_files) != required_count:
        print(
            "private POST round trip FAIL — fixture file counts "
            f"expected={len(expected_files)} raw={len(raw_files)} required={required_count}",
            file=sys.stderr,
        )
        return 1

    expected_labels = {path.stem for path in expected_files}
    raw_labels = {path.stem for path in raw_files}
    if expected_labels != raw_labels:
        print(
            "private POST round trip FAIL — expected/raw fixture labels differ: "
            f"expected_only={sorted(expected_labels - raw_labels)} "
            f"raw_only={sorted(raw_labels - expected_labels)}",
            file=sys.stderr,
        )
        return 1

    cmd = [
        "cargo",
        "run",
        "--quiet",
        "--bin",
        "check_post_round_trip_fixtures",
        "--",
        str(expected),
        str(raw),
    ]
    proc = subprocess.run(
        cmd,
        cwd=ROOT / "gel-core",
        text=True,
        stdout=subprocess.PIPE,
        stderr=None,
    )
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.returncode != 0:
        print(
            f"private POST round trip FAIL — Rust checker exited {proc.returncode}",
            file=sys.stderr,
        )
        return proc.returncode or 1

    match = re.search(
        r"offline POST round-trip fixtures PASS — (\d+) fixture\(s\) / (\d+) Final / (\d+) governed absent source discrepancies",
        proc.stdout,
    )
    if not match:
        print("private POST round trip FAIL — Rust checker summary was not parseable", file=sys.stderr)
        return 1

    observed = tuple(int(value) for value in match.groups())
    required = (
        required_count,
        int(CONFIG["required_final_fixture_count"]),
        int(CONFIG["required_absent_source_discrepancy_count"]),
    )
    if observed != required:
        print(
            f"private POST round trip FAIL — observed counts {observed} != required {required}",
            file=sys.stderr,
        )
        return 1

    print(
        "private POST round trip PASS — "
        f"{observed[0]} exact payloads / {observed[1]} Final Reading payloads / "
        f"{observed[2]} archive-authoritative absent discrepancies"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
