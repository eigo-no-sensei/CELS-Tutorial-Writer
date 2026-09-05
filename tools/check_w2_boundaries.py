#!/usr/bin/env python3
"""check:w2-boundaries — structural boundary verification for Phase W2 live submission transport."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CheckError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def read(rel: str) -> str:
    path = ROOT / rel
    require(path.is_file(), f"missing {rel}")
    return path.read_text(encoding="utf-8")


def load(rel: str) -> dict:
    return json.loads(read(rel))


def main() -> int:
    try:
        comp = load("contracts/component_boundaries.json")
        own = load("contracts/state_ownership.json")
        ui1 = load("contracts/ui1_writer.json")
        n2a = load("contracts/n2a_semantic_post_authority.json")
        gate = load("contracts/release_gate.json")
        identity = load("contracts/release_identity.json")

        require(comp["contract_version"] == 30, "component_boundaries contract_version must be 30")
        require(len(comp.get("planned_not_active", [])) == 0, "planned_not_active must be empty after W2 activation")

        comps = {c["id"]: c for c in comp["components"]}
        require("live_submission_transport" in comps, "live_submission_transport component missing")
        lst = comps["live_submission_transport"]
        require(lst["status"] == "active_w2", "live_submission_transport status must be active_w2")
        require("normalized_local_archive" in lst["must_not_write"], "live_submission_transport must not write normalized_local_archive")
        require("live_submission_response" in lst["writes"], "live_submission_transport must write live_submission_response")

        states = {s["id"]: s for s in own["state_classes"]}
        require("live_submission_response" in states, "live_submission_response missing from state_ownership")
        require("live_submission_transport" in states["tutorial_post_payload"]["readers"], "tutorial_post_payload must be readable by live_submission_transport")

        require(ui1["contract_version"] == 14, "ui1_writer contract_version must be 14")
        require(ui1["status"] in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "ui1_writer status must be active_w2_pending_strict_acceptance")
        require("ui1_submit_draft" in ui1["initial_command_allowlist"], "ui1_submit_draft must be present in command allowlist")

        require(n2a["contract_version"] == 3, "n2a_semantic_post_authority contract_version must be 3")
        require(n2a["network_write_authority"] is True, "n2a network_write_authority must be true for W2")
        require(len(n2a.get("deferred_non_blocking", [])) == 0, "n2a deferred_non_blocking must be retired for W2")

        require(gate["contract_version"] == 25, "release_gate contract_version must be 25")
        require(gate["current_release_scope"] == "w2", "release_gate current_release_scope must be w2")
        require(len(gate["scopes"]["w2"]["checks"]) == 47, "w2 scope must contain 46 checks")

        require(identity["contract_version"] == 6, "release_identity contract_version must be 6")
        require(identity["strict_acceptance"]["required_scope"] == "w2", "release_identity required_scope must be w2")
        require(identity["strict_acceptance"]["prerequisite_scope"] == "ui1e", "release_identity prerequisite_scope must be ui1e")

    except (CheckError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"check:w2-boundaries FAIL — {exc}", file=sys.stderr)
        return 1

    print("check:w2-boundaries PASS — live submission transport activated + command allowlist updated + W2 scope verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
