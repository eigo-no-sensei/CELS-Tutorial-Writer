#!/usr/bin/env python3
"""Validate the exact private fixture baseline and mismatch allowlist."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = json.loads((ROOT / "contracts" / "release_gate.json").read_text(encoding="utf-8"))
PARITY = GATE["private_fixture_parity"]


def default_fixture_paths() -> tuple[Path, Path]:
    override = os.environ.get(PARITY.get("fixture_root_env", ""), "").strip()
    if override:
        fixture_root = Path(override).expanduser().resolve()
        return fixture_root / PARITY["expected_subdir"], fixture_root / PARITY["raw_subdir"]
    return ROOT / PARITY["expected_dir"], ROOT / PARITY["raw_dir"]


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
            f"private fixture parity FAIL — fixture directories missing: expected={expected} raw={raw}",
            file=sys.stderr,
        )
        return 2

    with tempfile.TemporaryDirectory(prefix="gel-private-parity-") as td:
        report_path = Path(td) / "report.json"
        cmd = [
            "cargo", "run", "--quiet", "--bin", "compare_edit_fixtures", "--",
            str(expected), str(raw), "--json", str(report_path),
        ]
        proc = subprocess.run(cmd, cwd=ROOT / "gel-core")
        if proc.returncode != 0:
            print(f"private fixture parity FAIL — comparator exited {proc.returncode}", file=sys.stderr)
            return proc.returncode or 1
        report = json.loads(report_path.read_text(encoding="utf-8"))

    observed = (
        report["fixture_count"], report["field_count"], report["ok_count"],
        report["mismatch_count"], report["unavailable_count"],
    )
    required = (
        PARITY["required_fixture_count"], PARITY["required_field_count"], PARITY["required_ok"],
        PARITY["required_mismatch"], PARITY["required_unavailable"],
    )
    if observed != required:
        print(f"private fixture parity FAIL — counts {observed} != required {required}", file=sys.stderr)
        return 1

    actual_mismatches = Counter()
    for row in report["comparisons"]:
        if row["status"] == "unavailable":
            print(f"private fixture parity FAIL — unavailable field: {row['fixture']} {row['field']}", file=sys.stderr)
            return 1
        if row["status"] == "mismatch":
            actual_mismatches[(row["field"], row["archive_value"], row.get("edit_value"))] += 1

    allowed = Counter()
    for item in PARITY["allowed_mismatches"]:
        allowed[(item["field"], item["archive_value"], item["edit_value"])] += item["count"]

    if actual_mismatches != allowed:
        print("private fixture parity FAIL — mismatch identities differ from allowlist", file=sys.stderr)
        print(f"  actual:  {dict(actual_mismatches)}", file=sys.stderr)
        print(f"  allowed: {dict(allowed)}", file=sys.stderr)
        return 1

    semantic_cmd = [
        "cargo", "run", "--quiet", "--bin", "check_semantic_fixtures", "--",
        str(expected), str(raw),
    ]
    semantic_proc = subprocess.run(semantic_cmd, cwd=ROOT / "gel-core")
    if semantic_proc.returncode != 0:
        print(
            f"private fixture parity FAIL — C2 semantic revision fixture check exited {semantic_proc.returncode}",
            file=sys.stderr,
        )
        return semantic_proc.returncode or 1

    print(
        "private fixture parity PASS — "
        f"{report['fixture_count']} fixtures / {report['field_count']} fields / "
        f"{report['ok_count']} OK / {report['mismatch_count']} known mismatches / "
        f"{report['unavailable_count']} unavailable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
