#!/usr/bin/env python3
"""Behavioral tests for source fingerprint, package intake and tamper detection."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from release_common import ROOT, file_manifest, manifest_digest, sha256_file


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gel-release-control-") as td:
        root = Path(td) / "pkg"
        root.mkdir()
        # Minimal package-shaped fixture with complete-looking locks.
        for rel in [
            "governance/current-state.json",
            "governance/current-state.schema.json",
            "governance/dependency-lock-manifest.json",
            "Cargo.toml",
            "Cargo.lock",
            "writer-ui/package.json",
            "writer-ui/package-lock.json",
            "contracts/dependency_lock_policy.json",
            "contracts/release_identity.json",
            "contracts/verification_semantics.json",
        ]:
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if rel.endswith("dependency-lock-manifest.json"):
                p.write_text(json.dumps({"status": "COMPLETE", "lockSetSha256": "a" * 64}), encoding="utf-8")
            else:
                p.write_text("{}\n", encoding="utf-8")
        # A package manifest is itself covered by checksums; checksums excludes only itself.
        (root / "release-manifest.json").write_text(json.dumps({"schemaVersion": 1}) + "\n", encoding="utf-8")
        files = sorted(p for p in root.rglob("*") if p.is_file())
        lines = [f"{sha256_file(p)}  {p.relative_to(root).as_posix()}" for p in files]
        (root / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
        cmd = [sys.executable, str(ROOT / "tools" / "check_intake.py"), "--mode", "package", "--root", str(root)]
        ok = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if ok.returncode != 0:
            print("release-control behavior FAIL: valid package fixture rejected", file=sys.stderr)
            print(ok.stdout + ok.stderr, file=sys.stderr)
            return 1
        (root / "Cargo.toml").write_text("tampered\n", encoding="utf-8")
        bad = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        if bad.returncode == 0:
            print("release-control behavior FAIL: tampered package fixture accepted", file=sys.stderr)
            return 1
    print("Release-control behavior: PASS — package checksum tampering fails closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
