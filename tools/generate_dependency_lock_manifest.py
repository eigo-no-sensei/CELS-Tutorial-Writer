#!/usr/bin/env python3
"""Generate the derived dependency-lock identity manifest.

The Rust dependency identity covers every workspace Cargo manifest, not only
root Cargo.toml. A declared external Rust dependency absent from Cargo.lock
keeps the source projection INCOMPLETE so member-manifest changes cannot hide
behind an apparently current root lock hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tomllib
from pathlib import Path

from release_common import ROOT, sha256_file

TARGET = ROOT / "governance" / "dependency-lock-manifest.json"
RUST_MANIFESTS = [
    ROOT / "Cargo.toml",
    ROOT / "gel-core" / "Cargo.toml",
    ROOT / "writer-ui" / "src-tauri" / "Cargo.toml",
]
RUST_LOCK = ROOT / "Cargo.lock"
NPM_MANIFEST = ROOT / "writer-ui" / "package.json"
NPM_LOCK = ROOT / "writer-ui" / "package-lock.json"


def entry(path: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "present": path.is_file(),
        "sha256": sha256_file(path) if path.is_file() else None,
    }


def declared_external_rust_dependencies() -> list[str]:
    names: set[str] = set()
    for path in RUST_MANIFESTS:
        if not path.is_file():
            continue
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        dependencies = data.get("dependencies", {})
        if not isinstance(dependencies, dict):
            continue
        for name, spec in dependencies.items():
            if isinstance(spec, dict) and ("path" in spec or "workspace" in spec):
                continue
            names.add(str(name))
    return sorted(names)


def combined_lock_sha() -> str | None:
    if not RUST_LOCK.is_file() or not NPM_LOCK.is_file():
        return None
    h = hashlib.sha256()
    for path in (RUST_LOCK, NPM_LOCK):
        rel = path.relative_to(ROOT).as_posix().encode("utf-8")
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        data = path.read_bytes()
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def render() -> dict[str, object]:
    blockers: list[str] = []
    missing_manifests = [p.relative_to(ROOT).as_posix() for p in RUST_MANIFESTS if not p.is_file()]
    blockers.extend(f"Rust workspace manifest missing: {rel}" for rel in missing_manifests)
    if not RUST_LOCK.is_file():
        blockers.append("Cargo.lock missing")
    if not NPM_LOCK.is_file():
        blockers.append("writer-ui/package-lock.json missing")

    declared = declared_external_rust_dependencies()
    if RUST_LOCK.is_file():
        lock_text = RUST_LOCK.read_text(encoding="utf-8")
        missing_from_lock = [name for name in declared if f'name = "{name}"' not in lock_text]
        blockers.extend(f"Cargo.lock missing declared external dependency: {name}" for name in missing_from_lock)

    return {
        "schemaVersion": 3,
        "classification": "derived",
        "writer": "dependency_lock_tooling",
        "policyContract": "contracts/dependency_lock_policy.json",
        "toolUnavailableException": "run evidence only; never persisted as dependency identity",
        "status": "COMPLETE" if not blockers else "INCOMPLETE",
        "rustManifests": [entry(path) for path in RUST_MANIFESTS],
        "declaredExternalRustDependencies": declared,
        "rustLock": entry(RUST_LOCK),
        "npmManifest": entry(NPM_MANIFEST),
        "npmLock": entry(NPM_LOCK),
        "lockSetSha256": combined_lock_sha() if not blockers else None,
        "blockers": blockers,
        "invalidation": "Any workspace Cargo.toml, package.json, Cargo.lock, or package-lock.json change invalidates this projection; declared external Rust dependencies must exist in Cargo.lock.",
    }


def serialized() -> str:
    return json.dumps(render(), indent=2, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = serialized()
    if args.check:
        if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != expected:
            print("dependency lock manifest: STALE")
            return 1
        print("dependency lock manifest: CURRENT")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(expected, encoding="utf-8")
    print(f"generated {TARGET.relative_to(ROOT)} ({render()['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
