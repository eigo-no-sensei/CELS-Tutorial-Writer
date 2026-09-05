#!/usr/bin/env python3
"""check:n2a-semantic-post — dependency-minimal N2a authority checker."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CheckError(Exception):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise CheckError(message)


def load(name: str) -> dict:
    return json.loads((ROOT / "contracts" / name).read_text(encoding="utf-8"))


def between(text: str, start: str, end: str) -> str:
    a = text.find(start)
    require(a >= 0, f"missing source marker: {start}")
    b = text.find(end, a + len(start))
    require(b >= 0, f"missing source end marker: {end}")
    return text[a:b]


def main() -> int:
    try:
        n2a = load("n2a_semantic_post_authority.json")
        fields = load("gel_tutorial_fields.json")
        app = load("tutorial_form_applicability.json")
        pw1 = load("n2_playwright_zero_write_evidence.json")

        require(n2a.get("contract_id") == "n2a_semantic_post_authority", "bad N2a contract id")
        require(n2a.get("contract_version") == 3, "N2a contract version must be 3 for W2")
        require(n2a.get("status") == "active", "N2a contract must be active")
        require(n2a.get("network_write_authority") is True, "N2a network_write_authority must be true under W2")
        require(n2a["resolved_preconditions"]["teacher_serialization_residual"].lower().find("non-blocking") >= 0, "teacher serialization residual must be non-blocking")

        expected = {
            264: ("initial_speaking", "speaking", "initial"),
            265: ("initial_use_of_english", "use_of_english", "initial"),
            266: ("initial_writing", "writing", "initial"),
            267: ("initial_listening", "listening", "initial"),
            233: ("speaking", "speaking", "current"),
            234: ("use_of_english", "use_of_english", "current"),
            235: ("writing", "writing", "current"),
            236: ("listening", "listening", "current"),
            476: ("reading", "reading", "current"),
        }
        actual = {}
        for field in fields["fields"]:
            if "gel_field_id" not in field:
                continue
            role = field["semantic_level_role"]
            actual[int(field["gel_field_id"])] = (
                field["semantic_name"], role["dimension"], role["phase"]
            )
            require(field.get("provenance_rule") == "field_identity_only_no_cross_field_value_inference", f"field {field['semantic_name']} permits cross-field inference")
        require(actual == expected, f"canonical GEL level field map drifted: {actual!r}")
        require("reading" in app["semantic_fields"]["final"], "Final Reading applicability must remain established")
        require("reading" in app["semantic_fields"]["standard"], "Standard Reading applicability must remain established")
        require("reading" not in app["semantic_fields"]["initial"], "Initial must not gain Reading")

        sem = (ROOT / "gel-core/src/semantic.rs").read_text(encoding="utf-8")
        post = (ROOT / "gel-core/src/post_mapper.rs").read_text(encoding="utf-8")
        tests = (ROOT / "gel-core/tests/post_mapper.rs").read_text(encoding="utf-8")
        pw_core = (ROOT / "tools/playwright/n2_zero_write_evidence_core.py").read_text(encoding="utf-8")

        require("provisional_source_timestamp_for_post" not in sem + post, "legacy provisional New timestamp path remains")
        require("pub struct NewTutorialSubmission" in post, "missing NewTutorialSubmission")
        require("pub struct RevisionTutorialSubmission" in post, "missing RevisionTutorialSubmission")
        new_builder = between(post, "pub fn build_new_tutorial_post_payload", "pub fn build_revision_tutorial_post_payload")
        rev_builder = between(post, "pub fn build_revision_tutorial_post_payload", "/// Compatibility entry point")
        require("SOURCE_TIMESTAMP" not in new_builder and "datetime" not in new_builder, "New builder can serialize datetime")
        require("gel_fields::SOURCE_TIMESTAMP" in rev_builder, "Revision builder must emit datetime")
        require("source.tutorial_ts" in rev_builder, "Revision datetime must derive from source TutorialIdentity")
        require("source_teacher_id" in sem and "form_teacher: ValidatedNewFormTeacher" in sem, "DraftOrigin must bind teacher authority")
        require("pub struct ValidatedNewFormTeacher" in sem and "pub(crate) fn from_validated_hidden_control" in sem, "N2b must refine New teacher to opaque validated form authority")
        require("pub teacher_id: i64" not in sem, "opaque New teacher must not expose a public raw-ID field")
        require("revision teacher attribution is immutable" in sem, "Revision teacher immutability validation missing")
        require("new tutorial teacher attribution is immutable" in sem, "New teacher immutability validation missing")
        require("pub fn authoritative_identity" in sem, "authoritative identity API missing")
        require("prepopulation_source: Option<TutorialIdentity>" in sem, "first-ever New optional source support missing")
        require("reqwest" not in post and "ureq" not in post and "TcpStream" not in post, "POST mapper must remain offline")

        for test_name in [
            "explicit_new_origin_omits_datetime_entirely",
            "first_ever_new_without_prepopulation_source_omits_datetime",
            "revision_teacher_attribution_cannot_be_changed",
            "new_teacher_attribution_must_match_form_authority",
        ]:
            require(f"fn {test_name}" in tests, f"missing N2a regression test {test_name}")

        require("copied_from_source_field" not in pw_core, "PW1 still contains ambiguous cross-field provenance classification")
        require("matching_source_fields" not in pw_core, "PW1 still searches unrelated equal-valued fields")
        residual = pw1.get("residual_status", {})
        require(residual.get("submit_serialization_observation") == "deferred_non_blocking", "PW1 changed-teacher serialization must be deferred non-blocking")
        require(residual.get("n2_gate") is False, "PW1 changed-teacher residual must not gate N2")

    except (CheckError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"check:n2a-semantic-post FAIL — {exc}", file=sys.stderr)
        return 1
    print("check:n2a-semantic-post PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
