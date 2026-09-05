#!/usr/bin/env python3
"""Behavioral invariant tests for LOCK_GENERATOR_UNAVAILABLE policy."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from check_dependency_lockfiles import assess_missing_locks  # noqa: E402


def req(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> int:
    both_absent = assess_missing_locks(
        cargo_lock_present=False, npm_lock_present=False,
        cargo_available=False, npm_available=False,
    )
    req(len(both_absent.exceptions) == 2 and not both_absent.violations, "both unavailable generators must cover both missing locks")

    cargo_available = assess_missing_locks(
        cargo_lock_present=False, npm_lock_present=True,
        cargo_available=True, npm_available=False,
    )
    req(cargo_available.violations == ("Cargo.lock missing while cargo is available",), "available cargo must invalidate Cargo.lock exception")

    npm_available = assess_missing_locks(
        cargo_lock_present=True, npm_lock_present=False,
        cargo_available=False, npm_available=True,
    )
    req(npm_available.violations == ("writer-ui/package-lock.json missing while npm is available",), "available npm must invalidate package-lock exception")

    complete = assess_missing_locks(
        cargo_lock_present=True, npm_lock_present=True,
        cargo_available=False, npm_available=False,
    )
    req(not complete.exceptions and not complete.violations, "complete locks need no generator availability exception")

    mixed = assess_missing_locks(
        cargo_lock_present=False, npm_lock_present=True,
        cargo_available=False, npm_available=True,
    )
    req(mixed.exceptions == ("Cargo.lock missing because cargo executable is unavailable",) and not mixed.violations, "exception must apply per missing lock only")

    print("Dependency lock exception behavior: PASS — automatic per-lock tool-unavailable exception is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
