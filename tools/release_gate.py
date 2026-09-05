#!/usr/bin/env python3
"""Canonical portable/strict release gate runner.

Check membership, evidence class and SKIP/FAIL semantics come from
contracts/release_gate.json. The runner never invokes GEL tutorial writes.
For the current strict release scope it records immutable evidence outside the
source tree and binds that evidence to the exact governed source/lock/toolchain
identity observed before and after the gate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.dont_write_bytecode = True

from release_common import ROOT, inside_root, manifest_digest, sha256_file, source_fingerprint, toolchain_identity

GATE_PATH = ROOT / "contracts" / "release_gate.json"


@dataclass
class Result:
    check_id: str
    status: str
    detail: str
    evidence_class: str


def load_gate() -> dict:
    return json.loads(GATE_PATH.read_text(encoding="utf-8"))


def command_for(raw: list[str]) -> list[str]:
    if raw and raw[0] == "python":
        return [sys.executable, *raw[1:]]
    return raw


def result(check: dict, status: str, detail: str) -> Result:
    return Result(check["id"], status, detail, check.get("evidence_class", "structural"))


def run_command(check: dict) -> Result:
    cmd = command_for(check["command"])
    exe = shutil.which(cmd[0]) if not Path(cmd[0]).is_absolute() else cmd[0]
    if not exe:
        return result(check, "FAIL", f"required executable missing: {cmd[0]}")
    cwd = ROOT / check.get("cwd", ".")
    proc = subprocess.run(cmd, cwd=cwd)
    if proc.returncode == 0:
        return result(check, "PASS", "command succeeded")
    return result(check, "FAIL", f"command exited {proc.returncode}")


def active_python_files() -> list[Path]:
    return sorted((ROOT / "tools").glob("*.py")) + sorted((ROOT / "python-oracle").glob("*.py"))


def run_python_compile(check: dict) -> Result:
    try:
        files = active_python_files()
        if not files:
            return result(check, "FAIL", "no active Python files found")
        for path in files:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
    except Exception as exc:
        return result(check, "FAIL", f"Python compile failed: {exc}")
    return result(check, "PASS", f"compiled {len(files)} active Python files")


def private_paths(config: dict) -> tuple[Path, Path]:
    override = os.environ.get(config.get("fixture_root_env", ""), "").strip()
    if override:
        fixture_root = Path(override).expanduser().resolve()
        return fixture_root / config["expected_subdir"], fixture_root / config["raw_subdir"]
    return ROOT / config["expected_dir"], ROOT / config["raw_dir"]


def missing_private_result(check: dict, profile: str, expected: Path, raw: Path, config: dict, label: str) -> Result | None:
    if expected.is_dir() and raw.is_dir():
        return None
    policy = check["portable_missing_policy"] if profile == "portable" else check["strict_missing_policy"]
    location = f"expected={expected} raw={raw}"
    hint = f"set {config['fixture_root_env']} to the directory containing expected/ and raw/ if fixtures are stored outside this checkout"
    if policy == "skip":
        return result(check, "SKIP", f"{label} unavailable ({location}); portable contract permits explicit SKIP; {hint}")
    return result(check, "FAIL", f"{label} unavailable ({location}); strict contract requires them; {hint}")


def run_private_fixture_parity(check: dict, profile: str, gate: dict) -> Result:
    config = gate["private_fixture_parity"]
    expected, raw = private_paths(config)
    missing = missing_private_result(check, profile, expected, raw, config, "private fixture directories")
    if missing:
        return missing
    proc = subprocess.run([
        sys.executable, str(ROOT / "tools" / "check_private_fixture_parity.py"),
        "--expected-dir", str(expected), "--raw-dir", str(raw),
    ], cwd=ROOT)
    if proc.returncode == 0:
        return result(check, "PASS", "exact private fixture baseline and mismatch allowlist satisfied")
    return result(check, "FAIL", f"private fixture checker exited {proc.returncode}")


def run_private_collision_authority(check: dict, profile: str, gate: dict) -> Result:
    config = gate["private_collision_authority"]
    expected, raw = private_paths(config)
    missing = missing_private_result(check, profile, expected, raw, config, "private collision fixtures")
    if missing:
        return missing
    proc = subprocess.run([
        sys.executable, str(ROOT / "tools" / "check_private_collision_authority.py"),
        "--expected-dir", str(expected), "--raw-dir", str(raw),
    ], cwd=ROOT)
    if proc.returncode == 0:
        return result(check, "PASS", "C3 collision authority fixtures satisfied")
    return result(check, "FAIL", f"private collision checker exited {proc.returncode}")


def run_dependency_locks(check: dict, profile: str) -> Result:
    cmd = command_for(check["command"]) + ["--profile", profile]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip(), file=sys.stderr)
    if proc.returncode == 0:
        return result(check, "PASS", "complete dependency lock identity validated")
    if proc.returncode == 2 and profile == "portable":
        return result(check, "SKIP", "LOCK_GENERATOR_UNAVAILABLE: portable exception applied; dependency identity remains incomplete")
    return result(check, "FAIL", f"dependency lock checker exited {proc.returncode}; strict/release identity requires complete locks")


def run_private_print_parity(check: dict, profile: str, gate: dict) -> Result:
    config = gate["private_print_parity"]
    expected, raw = private_paths(config)
    missing = missing_private_result(check, profile, expected, raw, config, "private A1 print fixtures")
    if missing:
        return missing
    proc = subprocess.run([
        sys.executable, str(ROOT / "tools" / "check_private_print_parity.py"),
        "--expected-dir", str(expected), "--raw-dir", str(raw),
        "--required-count", str(config["required_fixture_count"]),
    ], cwd=ROOT)
    if proc.returncode == 0:
        return result(check, "PASS", "A1 exact private print parity satisfied")
    return result(check, "FAIL", f"private A1 print parity checker exited {proc.returncode}")


def run_private_post_round_trip(check: dict, profile: str, gate: dict) -> Result:
    config = gate["private_post_round_trip"]
    expected, raw = private_paths(config)
    missing = missing_private_result(check, profile, expected, raw, config, "private POST round-trip fixtures")
    if missing:
        return missing
    proc = subprocess.run([
        sys.executable, str(ROOT / "tools" / "check_private_post_round_trip.py"),
        "--expected-dir", str(expected), "--raw-dir", str(raw),
    ], cwd=ROOT)
    if proc.returncode == 0:
        return result(check, "PASS", "C4 exact offline POST round trips satisfied")
    return result(check, "FAIL", f"private POST round-trip checker exited {proc.returncode}")


def execute(check: dict, profile: str, gate: dict) -> Result:
    kind = check.get("kind", "command")
    if kind == "command":
        return run_command(check)
    if kind == "python_compile":
        return run_python_compile(check)
    if kind == "dependency_locks":
        return run_dependency_locks(check, profile)
    if kind == "private_fixture_parity":
        return run_private_fixture_parity(check, profile, gate)
    if kind == "private_print_parity":
        return run_private_print_parity(check, profile, gate)
    if kind == "private_collision_authority":
        return run_private_collision_authority(check, profile, gate)
    if kind == "private_post_round_trip":
        return run_private_post_round_trip(check, profile, gate)
    return result(check, "FAIL", f"unknown release check kind: {kind}")


def contract_set_digest() -> str:
    entries = []
    for path in sorted((ROOT / "contracts").glob("*.json")) + [ROOT / "schema" / "archive_v2.sql"]:
        entries.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path), "size": path.stat().st_size})
    return manifest_digest(entries)


def lock_set_sha() -> str | None:
    path = ROOT / "governance" / "dependency-lock-manifest.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("lockSetSha256")
    except (OSError, json.JSONDecodeError):
        return None


def write_evidence(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError(f"evidence path already exists and is immutable: {path}")
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["portable", "strict"], required=True)
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--only", nargs="*", help="development diagnostic only; does not establish current release acceptance")
    selector.add_argument("--scope", help="execute a canonical named release scope from contracts/release_gate.json")
    parser.add_argument("--evidence-out", type=Path, help="write immutable gate evidence outside the source root")
    args = parser.parse_args()

    gate = load_gate()
    current_scope = gate.get("current_release_scope")
    is_current_strict = args.profile == "strict" and args.scope == current_scope and args.only is None
    if is_current_strict and args.evidence_out is None:
        print("release gate configuration error — current strict acceptance requires --evidence-out outside the source tree", file=sys.stderr)
        return 2
    if args.evidence_out is not None:
        evidence_path = args.evidence_out.expanduser().resolve()
        if inside_root(evidence_path):
            print("release gate configuration error — evidence must be retained outside the governed source root", file=sys.stderr)
            return 2
    else:
        evidence_path = None

    checks = [c for c in gate["checks"] if args.profile in c["profiles"]]
    if args.scope is not None:
        scopes = gate.get("scopes", {})
        if args.scope not in scopes:
            print(f"release gate configuration error — unknown --scope {args.scope!r}", file=sys.stderr)
            return 2
        wanted_ids = scopes[args.scope].get("checks", [])
        known = {c["id"] for c in checks}
        unknown = sorted(set(wanted_ids) - known)
        if unknown:
            print(f"release gate configuration error — scope {args.scope!r} contains unavailable check(s): {unknown}", file=sys.stderr)
            return 2
        wanted = set(wanted_ids)
        checks = [c for c in checks if c["id"] in wanted]
    elif args.only is not None:
        wanted = set(args.only)
        known = {c["id"] for c in checks}
        unknown = sorted(wanted - known)
        if unknown:
            print(f"release gate configuration error — unknown --only check(s): {unknown}", file=sys.stderr)
            return 2
        checks = [c for c in checks if c["id"] in wanted]

    pre_fp = source_fingerprint(ROOT)
    scope_note = f" scope={args.scope}" if args.scope else ""
    print(f"GEL release gate — profile={args.profile}{scope_note}")
    print(f"source fingerprint: {pre_fp}")
    results: list[Result] = []
    for check in checks:
        print(f"\n== {check['id']} [{check.get('evidence_class', 'structural')}] ==")
        r = execute(check, args.profile, gate)
        results.append(r)
        print(f"{r.status}: {r.detail}")

    post_fp = source_fingerprint(ROOT)
    source_mutated = pre_fp != post_fp
    pass_count = sum(r.status == "PASS" for r in results)
    skip_count = sum(r.status == "SKIP" for r in results)
    fail_count = sum(r.status == "FAIL" for r in results)
    if source_mutated:
        fail_count += 1

    if fail_count:
        structural_status = "FAIL"
        target_status = "TARGET_ACCEPTANCE_REQUIRED"
    elif args.profile == "portable":
        structural_status = "STRUCTURAL_PASS_WITH_SKIPS" if skip_count else "STRUCTURAL_PASS"
        target_status = "TARGET_ACCEPTANCE_REQUIRED"
    elif is_current_strict and skip_count == 0:
        structural_status = "STRUCTURAL_PASS"
        target_status = "STRICT_ACCEPTED"
    else:
        structural_status = "STRUCTURAL_PASS"
        target_status = "TARGET_ACCEPTANCE_REQUIRED"

    print("\nRelease gate summary")
    for r in results:
        print(f"  {r.status:<4} {r.check_id} [{r.evidence_class}]: {r.detail}")
    if source_mutated:
        print("  FAIL source_immutability [acceptance]: governed source fingerprint changed during gate")
    print(f"\nPASS={pass_count} SKIP={skip_count} FAIL={fail_count}")
    print(f"STRUCTURAL STATUS: {structural_status}")
    print(f"TARGET STATUS: {target_status}")

    evidence = {
        "schemaVersion": 1,
        "project": "gel-rust-bootstrap",
        "recordedAtUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "profile": args.profile,
        "scope": args.scope,
        "currentReleaseScope": current_scope,
        "sourceFingerprint": pre_fp,
        "postGateSourceFingerprint": post_fp,
        "sourceMutationDetected": source_mutated,
        "canonicalContractSetSha256": contract_set_digest(),
        "dependencyLockSetSha256": lock_set_sha(),
        "toolchainIdentity": toolchain_identity(),
        "counts": {"PASS": pass_count, "SKIP": skip_count, "FAIL": fail_count},
        "structuralStatus": structural_status,
        "targetStatus": target_status,
        "releaseStatus": target_status,
        "automaticPromotion": False,
        "results": [asdict(r) for r in results],
    }
    if evidence_path is not None:
        try:
            write_evidence(evidence_path, evidence)
            print(f"EVIDENCE: {evidence_path}")
        except (OSError, ValueError) as exc:
            print(f"evidence write failed — {exc}", file=sys.stderr)
            return 1

    if fail_count:
        print("RELEASE GATE: FAIL")
        return 1
    if skip_count:
        print("RELEASE GATE: PASS WITH DECLARED SKIPS")
    else:
        print("RELEASE GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
