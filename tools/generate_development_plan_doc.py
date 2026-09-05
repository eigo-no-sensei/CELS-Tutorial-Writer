#!/usr/bin/env python3
"""Generate docs/DEVELOPMENT_PLAN.md from development_plan.json."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "development_plan.json"
TARGET = ROOT / "docs" / "DEVELOPMENT_PLAN.md"


def render(plan: dict) -> str:
    md = [
        "# GEL Tutorial Writer development plan",
        "",
        "> Generated from `development_plan.json`. Edit the JSON plan, then regenerate this document.",
        "",
        f"**Plan version:** {plan['plan_version']}  ",
        f"**Date:** {plan['date']}  ",
        f"**Evaluation:** {plan['evaluation']['status'].replace('_', ' ')}",
        "",
        plan["evaluation"]["summary"],
        "",
        "## Documentation authority",
        "",
    ]
    for i, item in enumerate(plan["documentation_authority_order"], 1):
        md.append(f"{i}. {item}")

    md.extend(["", "## Global invariants", ""])
    md.extend(f"- {item}" for item in plan["global_invariants"])

    md.extend([
        "",
        "## Phase map",
        "",
        "| Phase | Name | Priority | Status | Depends on |",
        "| --- | --- | --- | --- | --- |",
    ])
    for phase in plan["phases"]:
        deps = ", ".join(phase["depends_on"]) or "—"
        md.append(f"| {phase['id']} | {phase['name']} | {phase['priority']} | **{phase['status']}** | {deps} |")

    for phase in plan["phases"]:
        md.extend([
            "",
            f"## {phase['id']} — {phase['name']}",
            "",
            f"**Priority:** {phase['priority']}  ",
            f"**Status:** {phase['status']}  ",
            f"**Depends on:** {', '.join(phase['depends_on']) or 'none'}",
            "",
            "**Scope**",
            "",
        ])
        md.extend(f"- {item}" for item in phase["scope"])
        if phase.get("evaluation"):
            md.extend([
                "",
                "**Phase evaluation**",
                "",
                f"Status: **{phase['evaluation']['status'].replace('_', ' ')}**.",
                "",
                phase['evaluation']['summary'],
            ])
        if phase.get("evidence_basis"):
            evidence = phase["evidence_basis"]
            md.extend(["", "**Evidence basis**", ""])
            if evidence.get("bundle"):
                md.append(f"- Bundle: `{evidence['bundle']}`")
            if evidence.get("raw_source_archive_sha256"):
                md.append(f"- Raw source archive SHA-256: `{evidence['raw_source_archive_sha256']}`")
            for claim in evidence.get("accepted_claims", []):
                md.append(f"- `{claim['id']}` ({claim['confidence']}): {claim['use']}")
            if evidence.get("product_authority_override"):
                md.append(f"- Product authority: {evidence['product_authority_override']}")
            for item in evidence.get("not_established_by_bundle", []):
                md.append(f"- Not established by bundle: {item}")
        if phase.get("implementation_order"):
            md.extend(["", "**Implementation order**", ""])
            md.extend(f"- {item}" for item in phase["implementation_order"])
        if phase.get("non_goals"):
            md.extend(["", "**Non-goals**", ""])
            md.extend(f"- {item}" for item in phase["non_goals"])
        if phase.get("residual_questions"):
            md.extend(["", "**Residual questions**", ""])
            md.extend(f"- {item}" for item in phase["residual_questions"])
        if phase.get("implementation_notes"):
            md.extend(["", "**Implementation notes**", ""])
            md.extend(f"- {item}" for item in phase["implementation_notes"])
        if phase.get("artifacts"):
            md.extend(["", "**Artifacts**", ""])
            md.extend(f"- `{item}`" for item in phase["artifacts"])
        md.extend(["", "**Exit conditions**", ""])
        md.extend(f"- {item}" for item in phase["exit_conditions"])
        if phase.get("result"):
            md.extend(["", f"**Result:** {phase['result']}"])

    gate = plan["release_gate_policy"]
    md.extend([
        "",
        "## Gate policy",
        "",
        f"Portable gate: {gate['portable']}",
        "",
        f"Strict gate: {gate['strict']}",
        "",
        f"Live write rule: {gate['live_write_rule']}",
        "",
    ])
    return "\n".join(md).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plan = json.loads(SOURCE.read_text(encoding="utf-8"))
    expected = render(plan)
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != expected:
            print("STALE: docs/DEVELOPMENT_PLAN.md differs from development_plan.json")
            return 1
        print("development plan document: CURRENT")
        return 0
    TARGET.write_text(expected, encoding="utf-8")
    print("generated docs/DEVELOPMENT_PLAN.md")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
