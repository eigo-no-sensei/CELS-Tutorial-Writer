#!/usr/bin/env python3
"""Validate high-value invariants are bound to semantic/acceptance checks."""
from __future__ import annotations

import json
import sys

from release_common import ROOT


class VerificationError(Exception):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise VerificationError(msg)


def main() -> int:
    try:
        contract = json.loads((ROOT / "contracts" / "verification_semantics.json").read_text(encoding="utf-8"))
        gate = json.loads((ROOT / "contracts" / "release_gate.json").read_text(encoding="utf-8"))
        require(contract.get("contract_id") == "verification_semantics" and contract.get("contract_version") == 1, "verification contract identity drifted")
        require(contract.get("automatic_promotion") is False, "verification evidence must never auto-promote")
        allowed = set(contract.get("evidence_classes", []))
        require(allowed == {"lint", "structural", "behavioral", "acceptance"}, "evidence-class taxonomy drifted")
        check_by_id = {c["id"]: c for c in gate.get("checks", [])}
        for check in check_by_id.values():
            require(check.get("evidence_class") in allowed, f"release check {check['id']} missing/invalid evidence_class")
        for invariant in contract.get("high_value_invariants", []):
            semantic = invariant.get("semantic_checks", [])
            require(semantic, f"high-value invariant {invariant['id']} has no semantic checks")
            for check_id in invariant.get("structural_checks", []) + semantic:
                require(check_id in check_by_id, f"invariant {invariant['id']} references unknown check {check_id}")
            require(any(check_by_id[c]["evidence_class"] in {"behavioral", "acceptance"} for c in semantic), f"invariant {invariant['id']} lacks behavioral/acceptance evidence")
    except (VerificationError, OSError, json.JSONDecodeError) as exc:
        print(f"Verification semantics: FAIL — {exc}", file=sys.stderr)
        return 1
    print(f"Verification semantics: PASS — {len(contract['high_value_invariants'])} high-value invariants semantically bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
