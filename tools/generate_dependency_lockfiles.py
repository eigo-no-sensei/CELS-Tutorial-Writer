#!/usr/bin/env python3
"""Materialize governed npm/Cargo locks where their real generators are available."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from release_common import ROOT


def run_if_available(cmd: list[str], cwd: Path, output: Path) -> bool:
    exe = shutil.which(cmd[0])
    if not exe:
        if output.is_file():
            print(f"= {cmd[0]} unavailable; retaining existing {output.relative_to(ROOT)} for validation")
        else:
            print(f"! LOCK_GENERATOR_UNAVAILABLE: {cmd[0]} missing; cannot create {output.relative_to(ROOT)}")
        return False
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)
    return True


def main() -> int:
    npm_lock = ROOT / "writer-ui" / "package-lock.json"
    cargo_lock = ROOT / "Cargo.lock"
    run_if_available(
        ["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"],
        ROOT / "writer-ui",
        npm_lock,
    )
    run_if_available(
        ["cargo", "generate-lockfile", "--manifest-path", str(ROOT / "Cargo.toml")],
        ROOT,
        cargo_lock,
    )
    subprocess.run([sys.executable, str(ROOT / "tools" / "generate_dependency_lock_manifest.py")], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(ROOT / "tools" / "generate_current_state.py")], cwd=ROOT, check=True)
    check = subprocess.run([sys.executable, str(ROOT / "tools" / "check_dependency_lockfiles.py"), "--profile", "portable"], cwd=ROOT)
    if check.returncode not in (0, 2):
        return check.returncode
    if check.returncode == 2:
        print("Dependency lock generation incomplete under explicit portable LOCK_GENERATOR_UNAVAILABLE exception.")
        print("Strict/release acceptance remains blocked until all real lockfiles exist and validate.")
    else:
        print("Dependency lockfiles generated. Review and commit both lockfiles in the same change.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
