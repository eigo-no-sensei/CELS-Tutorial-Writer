#!/usr/bin/env python3
"""Structural release-control invariants for GRI."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from release_common import ROOT


class ReleaseControlError(Exception):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ReleaseControlError(msg)


def main() -> int:
    try:
        identity = json.loads((ROOT / "contracts" / "release_identity.json").read_text(encoding="utf-8"))
        gate = json.loads((ROOT / "contracts" / "release_gate.json").read_text(encoding="utf-8"))
        workspace = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
        packager = (ROOT / "tools" / "package_release.py").read_text(encoding="utf-8")
        verifier = (ROOT / "tools" / "verify_release_archive.py").read_text(encoding="utf-8")

        require(identity.get("contract_id") == "release_identity" and identity.get("contract_version") == 6, "release_identity contract drifted")
        require(identity.get("strict_acceptance", {}).get("required_scope") == "w2", "W2 must be the strict release scope")
        require(identity["strict_acceptance"].get("automatic_promotion") is False, "release candidates must never auto-promote")
        require(identity["strict_acceptance"].get("package_after_acceptance_may_not_rebuild") is True, "post-acceptance rebuild must be forbidden")
        require(identity["strict_acceptance"].get("package_must_revalidate_source_fingerprint") is True, "packaging must revalidate strict-accepted source fingerprint")
        require(identity["current_state_projection"].get("must_not_be_runtime_authority") is True, "current-state projection must not become runtime authority")
        require(identity.get("agent_governance_identity", {}).get("runtime_authority") is False, "agent governance protocol/profile must not become runtime authority")
        require(identity["dependency_identity"].get("single_rust_workspace_lock") is True, "single Rust workspace lock must be authoritative")
        require(identity["dependency_identity"].get("frontend_install_command") == ["npm", "ci", "--no-audit", "--no-fund"], "frontend release install must be npm ci")
        lock_exc = identity["dependency_identity"].get("portable_tool_unavailable_exception", {})
        require(lock_exc == {"result":"SKIP","strict_result":"FAIL","automatic_detection_only":True,"manual_override_allowed":False,"promotion_ceiling":"FAST_VERIFIED"}, "release identity lock-generator exception drifted")
        require(identity["dependency_identity"].get("policy_contract") == "contracts/dependency_lock_policy.json", "release identity must bind lock policy")
        require("[workspace]" in workspace and '"gel-core"' in workspace and '"writer-ui/src-tauri"' in workspace, "root Cargo workspace must include both Rust crates")

        checks = {c["id"]: c for c in gate.get("checks", [])}
        require(gate.get("current_release_scope") == "w2", "current release scope must be w2")
        require(checks["rust_workspace_clippy"].get("command") == ["cargo", "clippy", "--workspace", "--all-targets", "--locked", "--", "-D", "warnings"], "workspace clippy must be --locked")
        require(checks["rust_workspace_tests"].get("command") == ["cargo", "test", "--workspace", "--locked"], "workspace tests must be --locked")
        require(checks["frontend_dependencies"].get("command") == ["npm", "ci", "--no-audit", "--no-fund"], "release gate must install frontend with npm ci")
        require(checks["dependency_locks"].get("kind") == "dependency_locks", "dependency lock check must be profile-aware")
        require(checks["dependency_locks"].get("portable_tool_unavailable_policy") == "skip" and checks["dependency_locks"].get("strict_tool_unavailable_policy") == "fail", "lock-generator exception must be portable SKIP / strict FAIL")
        require(set(gate.get("acceptance_status_taxonomy", {})) >= {"STRUCTURAL_PASS_WITH_SKIPS", "TARGET_ACCEPTANCE_REQUIRED", "STRICT_ACCEPTED", "RELEASE_ARTIFACT_VERIFIED"}, "release status taxonomy incomplete")

        # Packaging is deliberately source-only. Builds happen in the strict gate, not after acceptance.
        forbidden_build_fragments = ["cargo build", "cargo tauri", "npm run build", "npm ci", "npm install"]
        lower = packager.lower()
        require(all(fragment not in lower for fragment in forbidden_build_fragments), "package_release.py must not build/install after strict acceptance")
        require("source_fingerprint(ROOT)" in packager and "source tree changed since strict acceptance" in packager, "packager must fail closed on source-fingerprint drift")
        require("STRICT_ACCEPTED" in packager and 'get("SKIP") == 0' in packager, "packager must require zero-skip strict evidence")
        require("testzip()" in packager and "checksums.sha256" in packager, "packager must verify ZIP/checksum integrity before receipt")
        require("testzip()" in verifier and "internal checksum" in verifier.lower(), "release verifier must validate archive bytes/checksums")
        require("rebuild" not in verifier.lower() or "rebuildPerformed" in verifier, "release verifier must not rebuild")
    except (ReleaseControlError, OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"Release control: FAIL — {exc}", file=sys.stderr)
        return 1
    print("Release control: PASS — exact-source, locked, no-rebuild artifact boundary")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
