#!/usr/bin/env python3
"""Verify final release archive bytes and internal manifests without rebuilding."""
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from release_common import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    archive = args.archive.resolve()
    receipt_path = (args.receipt or archive.with_suffix(archive.suffix + ".receipt.json")).resolve()
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("archiveSha256") != sha256_file(archive):
            raise ValueError("final archive SHA-256 differs from receipt")
        if receipt.get("releaseStatus") != "RELEASE_ARTIFACT_VERIFIED" or receipt.get("rebuildPerformed") is not False:
            raise ValueError("receipt status/rebuild semantics invalid")
        with zipfile.ZipFile(archive) as zf:
            if zf.testzip() is not None:
                raise ValueError("ZIP CRC failure")
            with tempfile.TemporaryDirectory(prefix="gel-verify-") as td:
                zf.extractall(td)
                root = Path(td) / "gel-rust-bootstrap"
                checksums = root / "checksums.sha256"
                if not checksums.is_file():
                    raise ValueError("internal checksums.sha256 missing")
                expected = {}
                for line in checksums.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        digest, rel = line.split("  ", 1)
                        expected[rel] = digest
                actual = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "checksums.sha256"}
                if set(expected) != actual:
                    raise ValueError("internal checksum coverage differs from archive files")
                for rel, digest in expected.items():
                    if sha256_file(root / rel) != digest:
                        raise ValueError(f"internal checksum mismatch: {rel}")
        print("Release artifact verification: PASS")
        print(f"  sha256: {receipt['archiveSha256']}")
        return 0
    except Exception as exc:
        print(f"Release artifact verification: FAIL — {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
