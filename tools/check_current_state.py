#!/usr/bin/env python3
"""Validate the generated current-state projection and its non-authority semantics."""
from __future__ import annotations

import json
import subprocess
import sys

from release_common import ROOT


class StateError(Exception):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise StateError(msg)


def main() -> int:
    try:
        proc = subprocess.run([sys.executable, str(ROOT / "tools" / "generate_current_state.py"), "--check"], cwd=ROOT)
        require(proc.returncode == 0, "generated current-state projection is stale")
        schema = json.loads((ROOT / "governance" / "current-state.schema.json").read_text(encoding="utf-8"))
        state = json.loads((ROOT / "governance" / "current-state.json").read_text(encoding="utf-8"))
        require(schema.get("properties", {}).get("project", {}).get("const") == "gel-rust-bootstrap", "current-state schema project constant drifted")
        require(state.get("schemaVersion") == 3 and state.get("project") == "gel-rust-bootstrap", "current-state identity drifted")
        require(state.get("artifactType") in {"working-tree", "source-candidate", "accepted-release"}, "invalid artifactType")
        require(state.get("releaseStatus") in {"STRUCTURAL_PASS", "STRUCTURAL_PASS_WITH_SKIPS", "TARGET_ACCEPTANCE_REQUIRED", "STRICT_ACCEPTED", "RELEASE_ARTIFACT_VERIFIED"}, "invalid release status")
        require(state.get("requiredGate") == "w2", "current candidate must require the W2 gate")
        agent = state.get("agentGovernance", {})
        require(agent.get("protocolId") == "ai-governance-protocol" and agent.get("protocolVersion") == "1.1.0", "current-state agent protocol identity drifted")
        require(agent.get("profileId") == "gel-tutorial-writer" and agent.get("profileVersion") == "1.1.0", "current-state GEL profile identity drifted")
        require(agent.get("runtimeAuthority") is False, "current-state must not promote agent protocol/profile to runtime authority")
        lock_exception = state.get("dependencyLockExceptionPolicy", {})
        require(lock_exception == {"id":"LOCK_GENERATOR_UNAVAILABLE","portableResult":"SKIP","strictResult":"FAIL","automaticDetectionOnly":True,"promotionCeiling":"FAST_VERIFIED"}, "current-state lock exception policy drifted")
        require(isinstance(state.get("unresolvedBlockers"), list), "unresolvedBlockers must be a list")
        require(state.get("lastStrictAcceptance", {}).get("scope") in {"ui1e", "w2"}, "candidate must retain ui1e or w2 as the last strict acceptance")
        require(str(state.get("lastStrictAcceptance", {}).get("result", "")).startswith("PASS="), "strict predecessor result drifted")
        identity = json.loads((ROOT / "contracts" / "release_identity.json").read_text(encoding="utf-8"))
        require(identity.get("current_state_projection", {}).get("must_not_be_runtime_authority") is True, "release identity must explicitly deny current-state runtime authority")
    except (StateError, OSError, json.JSONDecodeError) as exc:
        print(f"Current state: FAIL — {exc}", file=sys.stderr)
        return 1
    print(f"Current state: PASS — {state['releaseStatus']} / locks={state['dependencyLockStatus']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
