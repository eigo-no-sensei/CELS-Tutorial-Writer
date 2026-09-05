#!/usr/bin/env python3
"""Shared deterministic release-control helpers.

This module never writes GEL/archive/runtime state. It operates only on repository
source files, dependency locks, release metadata, and external evidence paths.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]

EXCLUDED_DIR_NAMES = {
    ".git",
    ".venv",
    ".venv-renderer",
    "node_modules",
    "target",
    "dist",
    "__pycache__",
    "evidence-private",
    "fixtures-private",
    ".pytest_cache",
    ".mypy_cache",
}
EXCLUDED_FILE_SUFFIXES = {".pyc", ".pyo"}
EXCLUDED_ROOT_FILES = {
    "release-manifest.json",
    "checksums.sha256",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_source_file(path: Path, root: Path = ROOT) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    if not path.is_file():
        return False
    if rel.as_posix() in EXCLUDED_ROOT_FILES:
        return False
    if path.suffix in EXCLUDED_FILE_SUFFIXES:
        return False
    if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
        return False
    return True


def iter_source_files(root: Path = ROOT) -> list[Path]:
    return sorted(
        (p for p in root.rglob("*") if is_source_file(p, root)),
        key=lambda p: p.relative_to(root).as_posix(),
    )


def file_manifest(root: Path = ROOT) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for path in iter_source_files(root):
        rel = path.relative_to(root).as_posix()
        out.append({"path": rel, "sha256": sha256_file(path), "size": path.stat().st_size})
    return out


def manifest_digest(entries: Iterable[dict[str, object]]) -> str:
    canonical = json.dumps(list(entries), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(canonical)


def source_fingerprint(root: Path = ROOT) -> str:
    return manifest_digest(file_manifest(root))


def command_version(command: list[str]) -> dict[str, object]:
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=20, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "command": command, "detail": str(exc)}
    text = (proc.stdout or proc.stderr).strip()
    return {
        "available": proc.returncode == 0,
        "command": command,
        "returnCode": proc.returncode,
        "version": text,
    }


def toolchain_identity() -> dict[str, object]:
    import platform
    import sys

    return {
        "python": {
            "available": True,
            "executable": sys.executable,
            "version": sys.version.replace("\n", " "),
        },
        "cargo": command_version(["cargo", "--version"]),
        "rustc": command_version(["rustc", "--version", "--verbose"]),
        "node": command_version(["node", "--version"]),
        "npm": command_version(["npm", "--version"]),
        "platform": platform.platform(),
    }


def inside_root(path: Path, root: Path = ROOT) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
