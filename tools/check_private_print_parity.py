#!/usr/bin/env python3
"""Strict A1 private print-fixture parity wrapper."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fixture_stems(directory: Path, suffix: str) -> list[str]:
    return sorted(path.stem for path in directory.glob(f"*{suffix}") if path.is_file())


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--expected-dir", type=Path, required=True)
    p.add_argument("--raw-dir", type=Path, required=True)
    p.add_argument("--required-count", type=int, default=None)
    args = p.parse_args()

    if not args.expected_dir.is_dir():
        print(f"private A1 print parity FAIL — expected directory missing: {args.expected_dir}", file=sys.stderr)
        return 1
    if not args.raw_dir.is_dir():
        print(f"private A1 print parity FAIL — raw directory missing: {args.raw_dir}", file=sys.stderr)
        return 1

    expected_stems = fixture_stems(args.expected_dir, ".json")
    raw_stems = fixture_stems(args.raw_dir, ".html")
    if expected_stems != raw_stems:
        only_expected = sorted(set(expected_stems) - set(raw_stems))
        only_raw = sorted(set(raw_stems) - set(expected_stems))
        print(
            "private A1 print parity FAIL — raw/expected fixture stems differ "
            f"(missing_raw={only_expected}, missing_expected={only_raw})",
            file=sys.stderr,
        )
        return 1

    if args.required_count is not None and len(expected_stems) != args.required_count:
        print(
            "private A1 print parity FAIL — "
            f"required {args.required_count} fixtures, found {len(expected_stems)}",
            file=sys.stderr,
        )
        return 1

    if not expected_stems:
        print("private A1 print parity FAIL — no fixtures found", file=sys.stderr)
        return 1

    if not shutil.which("cargo"):
        print("private A1 print parity FAIL — cargo unavailable", file=sys.stderr)
        return 1

    cmd = [
        "cargo",
        "run",
        "--quiet",
        "--locked",
        "-p",
        "gel-core",
        "--bin",
        "check_print_fixtures",
        "--",
        str(args.expected_dir),
        str(args.raw_dir),
    ]
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode == 0:
        print(f"private A1 print parity PASS — {len(expected_stems)} fixture(s)")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
