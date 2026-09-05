#!/usr/bin/env python3
"""Dependency-minimal source/package intake gate.

Source-candidate intake may proceed with explicit LOCK_GENERATOR_UNAVAILABLE coverage
for missing lockfiles. Release-package intake never receives that exception.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from release_common import ROOT, sha256_file

BASE_REQUIRED = [
    "governance/current-state.json",
    "governance/dependency-lock-manifest.json",
    "governance/current-state.schema.json",
    "Cargo.toml",
    "writer-ui/package.json",
    "contracts/dependency_lock_policy.json",
    "contracts/release_identity.json",
    "contracts/verification_semantics.json",
]
LOCK_REQUIRED = ["Cargo.lock", "writer-ui/package-lock.json"]
FORBIDDEN = ["*.db", "*-wal", "*-shm", ".env", ".env.*", "*.pem", "*.key", "*.pyc"]
FORBIDDEN_PARTS = {"evidence-private", "fixtures-private", "node_modules", "target", "dist", "__pycache__"}


class IntakeError(Exception):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise IntakeError(msg)


def source_lock_exception(root: Path) -> list[str]:
    exceptions: list[str] = []
    violations: list[str] = []
    cases = [
        ("Cargo.lock", "cargo"),
        ("writer-ui/package-lock.json", "npm"),
    ]
    for rel, tool in cases:
        if (root / rel).is_file():
            continue
        if shutil.which(tool) is None:
            exceptions.append(f"{rel} covered by LOCK_GENERATOR_UNAVAILABLE ({tool} absent)")
        else:
            violations.append(f"{rel} missing while {tool} is available")
    require(not violations, "; ".join(violations))
    return exceptions


def scan_tree(root: Path, package_mode: bool) -> list[str]:
    for rel in BASE_REQUIRED:
        require((root / rel).is_file(), f"required intake file missing: {rel}")
    lock_manifest = json.loads((root / "governance" / "dependency-lock-manifest.json").read_text(encoding="utf-8"))
    exceptions: list[str] = []
    if package_mode:
        for rel in LOCK_REQUIRED:
            require((root / rel).is_file(), f"required release-package lock missing: {rel}")
        require(lock_manifest.get("status") == "COMPLETE", "release-package dependency-lock manifest is not COMPLETE")
        require(bool(lock_manifest.get("lockSetSha256")), "release-package dependency lockSetSha256 missing")
    elif lock_manifest.get("status") == "COMPLETE":
        for rel in LOCK_REQUIRED:
            require((root / rel).is_file(), f"COMPLETE lock manifest but lock missing: {rel}")
    else:
        exceptions = source_lock_exception(root)
        require(exceptions, "source dependency locks incomplete without an applicable LOCK_GENERATOR_UNAVAILABLE exception")
        require(lock_manifest.get("lockSetSha256") is None, "incomplete source lock identity must not expose lockSetSha256")

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        rel_text = rel.as_posix()
        if any(fnmatch.fnmatch(path.name, pat) for pat in FORBIDDEN):
            raise IntakeError(f"forbidden file present: {rel_text}")
        if package_mode and any(part in FORBIDDEN_PARTS for part in rel.parts):
            raise IntakeError(f"forbidden package path present: {rel_text}")
    if package_mode:
        release_manifest = root / "release-manifest.json"
        checksums = root / "checksums.sha256"
        require(release_manifest.is_file(), "package release-manifest.json missing")
        require(checksums.is_file(), "package checksums.sha256 missing")
        expected: dict[str, str] = {}
        for line in checksums.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, rel = line.split("  ", 1)
            expected[rel] = digest
        for rel, digest in expected.items():
            p = root / rel
            require(p.is_file(), f"checksum references missing file: {rel}")
            require(sha256_file(p) == digest, f"checksum mismatch: {rel}")
        distributed = {
            p.relative_to(root).as_posix()
            for p in root.rglob("*") if p.is_file() and p.name != "checksums.sha256"
        }
        require(distributed == set(expected), "checksums.sha256 must cover every distributed file except itself")
    return exceptions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["source", "package"], required=True)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    root = (args.root or ROOT).resolve()
    try:
        exceptions = scan_tree(root, args.mode == "package")
    except (IntakeError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Package intake: FAIL — {exc}", file=sys.stderr)
        return 1
    if exceptions:
        print(f"Package intake: PASS — mode={args.mode} with explicit source-only lock exception")
        for item in exceptions:
            print(f"  EXCEPTION: {item}")
        print("  dependency identity remains incomplete; strict/release package intake is not authorized")
    else:
        print(f"Package intake: PASS — mode={args.mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
