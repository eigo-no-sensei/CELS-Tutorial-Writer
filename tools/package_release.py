#!/usr/bin/env python3
"""Package a strict-accepted source tree without rebuilding it."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from release_common import ROOT, file_manifest, iter_source_files, sha256_file, source_fingerprint


class PackageError(Exception):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise PackageError(msg)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True, help="External strict-gate evidence JSON")
    parser.add_argument("--output", type=Path, required=True, help="Final .zip path")
    args = parser.parse_args()
    evidence_path = args.evidence.expanduser().resolve()
    output = args.output.expanduser().resolve()
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        require(evidence.get("profile") == "strict", "evidence is not strict-profile")
        require(evidence.get("scope") == "w2", "evidence is not the canonical W2 scope")
        require(evidence.get("targetStatus") == "STRICT_ACCEPTED", "evidence is not STRICT_ACCEPTED")
        require(evidence.get("counts", {}).get("FAIL") == 0 and evidence.get("counts", {}).get("SKIP") == 0, "strict evidence contains FAIL/SKIP")
        current_fp = source_fingerprint(ROOT)
        require(evidence.get("sourceFingerprint") == current_fp, "source tree changed since strict acceptance; rerun strict gate")
        lock_manifest = json.loads((ROOT / "governance" / "dependency-lock-manifest.json").read_text(encoding="utf-8"))
        require(lock_manifest.get("status") == "COMPLETE", "dependency locks are not complete")

        with tempfile.TemporaryDirectory(prefix="gel-package-") as td:
            stage = Path(td) / "gel-rust-bootstrap"
            stage.mkdir()
            for src in iter_source_files(ROOT):
                rel = src.relative_to(ROOT)
                dst = stage / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            release_manifest = {
                "schemaVersion": 1,
                "artifactType": "accepted-release",
                "sourceFingerprint": current_fp,
                "dependencyLockSetSha256": lock_manifest.get("lockSetSha256"),
                "strictEvidenceSha256": sha256_file(evidence_path),
                "toolchainIdentity": evidence.get("toolchainIdentity"),
                "strictScope": "w2",
                "strictResult": evidence.get("counts"),
                "buildAfterAcceptance": False,
                "automaticPromotion": False,
                "sourceFiles": file_manifest(stage),
            }
            (stage / "release-manifest.json").write_text(json.dumps(release_manifest, indent=2) + "\n", encoding="utf-8")
            checksum_files = sorted(p for p in stage.rglob("*") if p.is_file())
            checksum_lines = [f"{sha256_file(p)}  {p.relative_to(stage).as_posix()}" for p in checksum_files]
            (stage / "checksums.sha256").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
            intake = subprocess.run([sys.executable, str(ROOT / "tools" / "check_intake.py"), "--mode", "package", "--root", str(stage)], cwd=ROOT)
            require(intake.returncode == 0, "staged package failed intake")
            output.parent.mkdir(parents=True, exist_ok=True)
            if output.exists():
                output.unlink()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
                for p in sorted(stage.rglob("*")):
                    if p.is_file():
                        zf.write(p, Path("gel-rust-bootstrap") / p.relative_to(stage))
            with zipfile.ZipFile(output) as zf:
                require(zf.testzip() is None, "ZIP CRC validation failed")
                with tempfile.TemporaryDirectory(prefix="gel-package-verify-") as vd:
                    zf.extractall(vd)
                    extracted = Path(vd) / "gel-rust-bootstrap"
                    checksum_path = extracted / "checksums.sha256"
                    require(checksum_path.is_file(), "packaged checksums.sha256 missing")
                    expected = {}
                    for line in checksum_path.read_text(encoding="utf-8").splitlines():
                        if line.strip():
                            digest, rel = line.split("  ", 1)
                            expected[rel] = digest
                    actual = {
                        p.relative_to(extracted).as_posix()
                        for p in extracted.rglob("*")
                        if p.is_file() and p.name != "checksums.sha256"
                    }
                    require(set(expected) == actual, "packaged checksum coverage differs from archive files")
                    for rel, digest in expected.items():
                        require(sha256_file(extracted / rel) == digest, f"packaged checksum mismatch: {rel}")
            receipt = output.with_suffix(output.suffix + ".receipt.json")
            receipt.write_text(json.dumps({
                "schemaVersion": 1,
                "archive": output.name,
                "archiveSha256": sha256_file(output),
                "strictEvidenceSha256": sha256_file(evidence_path),
                "sourceFingerprint": current_fp,
                "releaseStatus": "RELEASE_ARTIFACT_VERIFIED",
                "rebuildPerformed": False,
            }, indent=2) + "\n", encoding="utf-8")
            print(f"packaged {output}")
            print(f"receipt {receipt}")
            print(f"archive sha256 {sha256_file(output)}")
    except (PackageError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Release package: FAIL — {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
