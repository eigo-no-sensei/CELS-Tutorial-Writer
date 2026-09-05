#!/usr/bin/env python3
"""D2 archive repository contract/boundary check.

Runs under Python -S. It validates the executable Rust repository boundary and
its parity with D1's source-state fingerprint contract without importing the
live GEL archiver runtime.
"""
from __future__ import annotations

import ast
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "archive_repository.json"
SCHEMA_CONTRACT = ROOT / "contracts" / "archive_schema_v2.json"
MIGRATOR = ROOT / "python-oracle" / "archive_schema_v2.py"
CARGO = ROOT / "gel-core" / "Cargo.toml"
LIB = ROOT / "gel-core" / "src" / "lib.rs"
READ = ROOT / "gel-core" / "src" / "archive_repository.rs"
WRITE = ROOT / "gel-core" / "src" / "archive_sync_repository.rs"
TEST = ROOT / "gel-core" / "tests" / "archive_repository.rs"
RELEASE = ROOT / "contracts" / "release_gate.json"


class CheckError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def literal_assignment(module: ast.Module, name: str):
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise CheckError(f"missing literal assignment {name} in {MIGRATOR.relative_to(ROOT)}")


def main() -> int:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_CONTRACT.read_text(encoding="utf-8"))
    release = json.loads(RELEASE.read_text(encoding="utf-8"))

    require(contract.get("contract_id") == "archive_repository", "D2 contract_id drifted")
    require(contract.get("contract_version") == 2, "A2 archive repository contract_version must be 2")
    require(contract.get("schema_ref") == "archive_schema_v2", "D2 must reference D1 schema contract")
    require(contract.get("schema_version") == schema.get("schema_version") == 2, "D2/D1 schema version mismatch")

    for path in [CARGO, LIB, READ, WRITE, TEST]:
        require(path.exists(), f"missing D2 artifact {path.relative_to(ROOT)}")

    cargo = tomllib.loads(CARGO.read_text(encoding="utf-8"))
    deps = cargo.get("dependencies", {})
    rusqlite = deps.get("rusqlite")
    require(isinstance(rusqlite, dict), "D2 requires structured rusqlite dependency")
    require("bundled" in rusqlite.get("features", []), "D2 rusqlite must use bundled SQLite for deterministic repository semantics")
    require("sha2" in deps, "D2 requires sha2 for D1-compatible source-state fingerprints")

    lib_src = LIB.read_text(encoding="utf-8")
    read_src = READ.read_text(encoding="utf-8")
    write_src = WRITE.read_text(encoding="utf-8")
    test_src = TEST.read_text(encoding="utf-8")

    require(re.search(r"(?m)^pub mod archive_repository;\s*$", lib_src) is not None, "public read-only archive_repository module missing")
    require(re.search(r"(?m)^mod archive_sync_repository;\s*$", lib_src) is not None, "archive_sync_repository must be crate-private")
    require("pub mod archive_sync_repository" not in lib_src, "archive sync write module must not be public")
    require("pub use archive_sync_repository" not in lib_src, "archive sync writer must not be publicly re-exported")
    require("ArchiveSyncRepository" not in lib_src, "archive sync writer type escaped crate root public surface")

    public_write_sql = re.compile(r"(?i)\b(INSERT\s+INTO|UPDATE\s+\w+|DELETE\s+FROM|REPLACE\s+INTO|CREATE\s+TABLE|DROP\s+TABLE)\b")
    hits = [m.group(0) for m in public_write_sql.finditer(read_src)]
    require(not hits, f"public repository contains canonical-history write SQL: {hits}")
    require("SQLITE_OPEN_READ_ONLY" in read_src, "public repository must open SQLite read-only")
    require("PRAGMA query_only=ON" in read_src, "public repository must set PRAGMA query_only=ON")
    require("pub fn open_read_only" in read_src, "public read-only repository constructor missing")
    require("pub fn revision_source" in read_src, "public fail-closed revision read API missing")

    require("SQLITE_OPEN_READ_WRITE" in write_src, "crate-private archive sync writer must explicitly open read-write")
    require("SQLITE_OPEN_CREATE" not in write_src, "D2 archive sync writer must not create databases implicitly")
    escaped_public = re.findall(r"(?m)^pub\s+(?:struct|enum|fn|trait|mod)\s+([A-Za-z0-9_]+)", write_src)
    require(not escaped_public, f"crate-private write module exposes public items: {escaped_public}")
    require("pub(crate) struct ArchiveSyncRepository" in write_src, "crate-private writer type missing")
    require("transaction()" in write_src, "D2 repository materialization must use a SQLite transaction")
    require("status='complete'" in write_src and "invalidate_unseen" in write_src, "D2 success/invalidation transition missing")
    require("transaction.rollback()" in write_src and "mark_run_failed" in write_src, "D2 rollback/failure semantics missing")
    require("canonical tutorial_id" in write_src and "cannot be re-keyed" in write_src, "D2 canonical tutorial identity immutability guard missing")
    require("validate_repository_semantics" in write_src and "PRAGMA foreign_key_check" in write_src, "D2 pre-commit semantic/FK audit missing")

    migrator_module = ast.parse(MIGRATOR.read_text(encoding="utf-8"), filename=str(MIGRATOR))
    state_columns = literal_assignment(migrator_module, "STATE_COLUMNS")
    excluded = set(contract["source_state_fingerprint"]["excluded_provenance_fields"])
    expected_state_fields = [name for name in state_columns if name not in excluded]
    require(
        contract["source_state_fingerprint"]["include_state_fields"] == expected_state_fields,
        "D2 fingerprint field projection differs from D1 legacy_state_fingerprint projection",
    )
    require(
        contract["source_state_fingerprint"]["include_identity_fields"] == ["student_uid", "tutorial_ts"],
        "D2 fingerprint identity projection drifted",
    )
    require("80837a0539106a7d770938d86845b175ffdadcbc5934332525650f4f7b3c6211" in write_src, "D2 fingerprint parity regression vector missing")

    ownership = contract.get("ownership", {})
    require(ownership.get("production_canonical_writer_after_A2") == "rust_archive_sync_repository", "A2 canonical archive writer must be Rust")
    require(ownership.get("production_orchestrator") == "gel-core/src/archiver.rs#RustArchiver", "A2 production orchestrator drifted")
    require(ownership.get("python_v49_status_after_A2") == "historical_reference", "A2 must demote Python archiver to historical/reference")
    require(ownership.get("a2_cutover") is True and ownership.get("cutover_phase") == "A2", "A2 cutover boundary drifted")

    check_ids = [item.get("id") for item in release.get("checks", [])]
    require("archive_repository" in check_ids, "release gate missing D2 archive_repository check")
    check = next(item for item in release["checks"] if item.get("id") == "archive_repository")
    require(check.get("command") == ["python", "-S", "tools/check_archive_repository.py"], "D2 release gate command must run under python -S")
    require(set(check.get("profiles", [])) == {"portable", "strict"}, "D2 repository boundary check must run in both profiles")

    require("public_repository_opens_v2_read_only_and_exposes_navigation_models" in test_src, "D2 public repository navigation regression test missing")
    require("public_repository_rejects_non_v2_database" in test_src, "D2 schema-version rejection test missing")
    for test_name in [
        "failed_full_sync_rolls_back_writes_and_never_invalidates_prior_history",
        "completed_full_sync_invalidates_unseen_without_deleting_history",
        "canonical_tutorial_id_cannot_be_rekeyed",
        "divergent_collision_is_persisted_group_owned_and_read_side_blocks_revision",
        "proven_state_is_read_back_as_semantic_archived_tutorial",
    ]:
        require(test_name in write_src, f"D2 repository behavioural test missing: {test_name}")

    print("check:archive-repository PASS — read-only public API + crate-private transactional sync writer + D1 fingerprint/authority parity")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CheckError as exc:
        print(f"check:archive-repository FAIL — {exc}", file=sys.stderr)
        raise SystemExit(1)
