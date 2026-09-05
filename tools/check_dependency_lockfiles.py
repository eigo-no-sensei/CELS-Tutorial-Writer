#!/usr/bin/env python3
"""Validate governed npm/Rust dependency locks with one narrow portable exception.

Exit codes:
  0  complete dependency identity validated
  2  portable LOCK_GENERATOR_UNAVAILABLE exception applies (explicit SKIP)
  1  failure / strict blocker
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from release_common import ROOT

EXCEPTION_EXIT = 2


class LockError(Exception):
    pass


@dataclass(frozen=True)
class MissingLockAssessment:
    exceptions: tuple[str, ...]
    violations: tuple[str, ...]


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise LockError(msg)


def assess_missing_locks(
    *,
    cargo_lock_present: bool,
    npm_lock_present: bool,
    cargo_available: bool,
    npm_available: bool,
) -> MissingLockAssessment:
    exceptions: list[str] = []
    violations: list[str] = []
    if not cargo_lock_present:
        if cargo_available:
            violations.append("Cargo.lock missing while cargo is available")
        else:
            exceptions.append("Cargo.lock missing because cargo executable is unavailable")
    if not npm_lock_present:
        if npm_available:
            violations.append("writer-ui/package-lock.json missing while npm is available")
        else:
            exceptions.append("writer-ui/package-lock.json missing because npm executable is unavailable")
    return MissingLockAssessment(tuple(exceptions), tuple(violations))


def validate_present_locks(root_lock: Path, npm_lock: Path) -> None:
    if root_lock.is_file():
        root_text = root_lock.read_text(encoding="utf-8")
        require("[[package]]" in root_text, "Cargo.lock has no package graph")
        require('name = "tauri"' in root_text, "Cargo.lock does not contain Tauri dependency graph")
        require('name = "rusqlite"' in root_text, "Cargo.lock does not contain gel-core archive dependency graph")

    if npm_lock.is_file():
        package = json.loads((ROOT / "writer-ui" / "package.json").read_text(encoding="utf-8"))
        lock = json.loads(npm_lock.read_text(encoding="utf-8"))
        require(int(lock.get("lockfileVersion", 0)) >= 3, "npm lockfileVersion must be >= 3")
        root_pkg = lock.get("packages", {}).get("")
        require(isinstance(root_pkg, dict), "package-lock.json missing packages[''] root entry")
        require(root_pkg.get("name") == package.get("name"), "npm lock root name differs from package.json")
        require(root_pkg.get("version") == package.get("version"), "npm lock root version differs from package.json")
        require(root_pkg.get("dependencies", {}) == package.get("dependencies", {}), "npm direct dependencies are not synchronized with package.json")
        require(root_pkg.get("devDependencies", {}) == package.get("devDependencies", {}), "npm devDependencies are not synchronized with package.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["portable", "strict"], default="strict")
    args = parser.parse_args()
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "generate_dependency_lock_manifest.py"), "--check"],
            cwd=ROOT,
        )
        require(proc.returncode == 0, "derived dependency-lock manifest is stale")

        root_lock = ROOT / "Cargo.lock"
        npm_lock = ROOT / "writer-ui" / "package-lock.json"
        require(not (ROOT / "gel-core" / "Cargo.lock").exists(), "gel-core/Cargo.lock forbidden: one root workspace lock owns Rust release identity")
        require(not (ROOT / "writer-ui" / "src-tauri" / "Cargo.lock").exists(), "writer-ui/src-tauri/Cargo.lock forbidden: one root workspace lock owns Rust release identity")

        validate_present_locks(root_lock, npm_lock)
        assessment = assess_missing_locks(
            cargo_lock_present=root_lock.is_file(),
            npm_lock_present=npm_lock.is_file(),
            cargo_available=shutil.which("cargo") is not None,
            npm_available=shutil.which("npm") is not None,
        )
        require(not assessment.violations, "; ".join(assessment.violations))

        manifest = json.loads((ROOT / "governance" / "dependency-lock-manifest.json").read_text(encoding="utf-8"))
        if assessment.exceptions:
            require(manifest.get("status") == "INCOMPLETE", "missing-lock exception requires manifest status INCOMPLETE")
            require(manifest.get("lockSetSha256") is None, "missing-lock exception must not expose complete lockSetSha256")
            detail = "; ".join(assessment.exceptions)
            if args.profile == "portable":
                print(f"Dependency lockfiles: EXCEPTION — LOCK_GENERATOR_UNAVAILABLE — {detail}")
                print("  portable result: SKIP; dependency identity remains incomplete; promotion ceiling FAST_VERIFIED")
                return EXCEPTION_EXIT
            raise LockError(f"{detail}; strict profile requires complete dependency locks")

        require(manifest.get("status") == "COMPLETE", "dependency lock manifest must report COMPLETE")
        require(bool(manifest.get("lockSetSha256")), "dependency lock set SHA-256 missing")
    except (LockError, json.JSONDecodeError, OSError) as exc:
        print(f"Dependency lockfiles: FAIL — {exc}", file=sys.stderr)
        return 1

    print("Dependency lockfiles: PASS")
    print("  Cargo.lock: single workspace resolved graph")
    print("  writer-ui/package-lock.json: synchronized resolved graph")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
