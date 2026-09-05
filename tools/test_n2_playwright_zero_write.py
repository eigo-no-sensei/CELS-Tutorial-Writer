#!/usr/bin/env python3
"""Offline behavioural tests for N2-PW1 privacy-safe evidence reduction."""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "tools" / "playwright" / "n2_zero_write_evidence_core.py"
spec = importlib.util.spec_from_file_location("n2_zero_write_evidence_core", CORE_PATH)
core = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = core
spec.loader.exec_module(core)


class N2ZeroWriteCoreTests(unittest.TestCase):
    def test_urlencoded_reduction_keeps_only_allowlisted_relations(self):
        aliases = core.TeacherAliasBook()
        body = (
            "tid=326752&ttype=0&customdate=27-08-2026&"
            "text-225=PRIVATE+COMMENT&trecs-79=PRIVATE+AIMS&form_token=SECRET"
        )
        evidence = core.parse_urlencoded_submission_evidence(
            body,
            "application/x-www-form-urlencoded; charset=UTF-8",
            aliases,
            expected_selected_teacher="326752",
        )
        encoded = json.dumps(evidence)
        self.assertEqual(evidence["teacher_alias"], "T1")
        self.assertTrue(evidence["selected_teacher_matches_submission"])
        self.assertFalse(evidence["datetime_present"])
        self.assertNotIn("PRIVATE", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("326752", encoded)
        self.assertNotIn("form_token", encoded)
        self.assertEqual(
            evidence["allowlisted_fields_observed"],
            ["customdate", "tid", "ttype"],
        )

    def test_revision_datetime_is_compared_without_persisting_timestamp(self):
        aliases = core.TeacherAliasBook()
        evidence = core.parse_urlencoded_submission_evidence(
            "tid=11&ttype=2&customdate=01-01-2026&datetime=1770000123&text-225=private",
            "application/x-www-form-urlencoded",
            aliases,
            expected_revision_timestamp=1770000123,
        )
        self.assertTrue(evidence["datetime_present"])
        self.assertTrue(evidence["datetime_matches_existing"])
        self.assertNotIn("1770000123", json.dumps(evidence))

    def test_unknown_submission_encoding_fails_closed(self):
        with self.assertRaises(core.EvidenceContractError):
            core.parse_urlencoded_submission_evidence(
                "tid=11&ttype=0",
                "multipart/form-data; boundary=x",
                core.TeacherAliasBook(),
            )

    def test_prepopulation_uses_established_latest_source_without_values(self):
        source = {
            "teacher_id": "11",
            "student_uid": "44",
            "source_timestamp": "1770000000",
            "tutorial_type": "0",
            "tutorial_date": "26-08-2026",
            "overall_level": "A2",
            "speaking": "A2",
            "teacher_comments": "private text",
        }
        target = {
            "teacher_id": "22",
            "student_uid": "44",
            "source_timestamp": "",
            "tutorial_type": "1",
            "tutorial_date": "27-08-2026",
            "overall_level": "A2",
            "speaking": "A2",
            "teacher_comments": "",
        }
        evidence = core.classify_prepopulation(
            source,
            target,
            placeholders={"Choose...", "Please choose level", "Please choose:"},
            requested_type="final",
            authenticated_teacher_raw="22",
            current_date=date(2026, 8, 27),
        )
        encoded = json.dumps(evidence)
        self.assertEqual(evidence["source_rule"], "latest_tutorial")
        self.assertEqual(evidence["fields"]["overall_level"], "copied_unchanged")
        self.assertEqual(evidence["fields"]["teacher_comments"], "reset_for_new")
        self.assertEqual(evidence["identity_rules"]["teacher"], "derived_from_authenticated_session")
        self.assertEqual(evidence["identity_rules"]["subject"], "route_identity")
        self.assertEqual(evidence["fields"]["source_timestamp"], "absent_for_new")
        self.assertNotIn("student_uid", encoded)
        self.assertNotIn("teacher_id", encoded)
        self.assertNotIn("private text", encoded)
        self.assertNotIn("1770000000", encoded)
        self.assertNotIn("22", encoded)
        core.assert_privacy_safe_evidence({"prepopulation": evidence})

    def test_prepopulation_never_infers_cross_field_provenance_from_equal_values(self):
        source = {
            "speaking": "A2",
            "use_of_english": "A2",
            "writing": "A2",
            "listening": "A2",
        }
        target = {
            "initial_speaking": "A2",
            "initial_use_of_english": "A2",
            "initial_writing": "A2",
            "initial_listening": "A2",
        }
        evidence = core.classify_prepopulation(
            source,
            target,
            placeholders={"Choose...", "Please choose level", "Please choose:"},
            requested_type="initial",
            authenticated_teacher_raw=None,
            current_date=date(2026, 8, 27),
        )
        self.assertEqual(evidence["fields"]["initial_speaking"], "new_specific_or_transformed")
        self.assertEqual(evidence["fields"]["initial_use_of_english"], "new_specific_or_transformed")
        self.assertEqual(evidence["fields"]["initial_writing"], "new_specific_or_transformed")
        self.assertEqual(evidence["fields"]["initial_listening"], "new_specific_or_transformed")
        encoded = json.dumps(evidence)
        self.assertNotIn("copied_from_source_field", encoded)
        self.assertNotIn("matching_source_fields", encoded)

    def test_initial_evidence_document_passes_complete_privacy_guard(self):
        evidence = core.initial_evidence_document()
        core.assert_privacy_safe_evidence(evidence)
        encoded = json.dumps(evidence)
        self.assertNotIn("raw_html_persisted", encoded)
        self.assertNotIn("request_headers_persisted", encoded)
        self.assertNotIn("teacher_names_persisted", encoded)
        self.assertFalse(evidence["privacy"]["page_source_capture_enabled"])
        self.assertFalse(evidence["privacy"]["submission_payload_capture_enabled"])
        self.assertFalse(evidence["privacy"]["network_header_capture_enabled"])
        self.assertFalse(evidence["privacy"]["staff_display_label_capture_enabled"])

    def test_privacy_checker_allows_boolean_credential_capture_metadata(self):
        core.assert_privacy_safe_evidence({
            "privacy": {
                "credential_values_read_by_harness": False,
                "submission_payload_capture_enabled": False,
            }
        })

    def test_privacy_checker_rejects_identity_and_raw_body_keys(self):
        for bad in [
            {"student_uid": 123},
            {"request_body": "x"},
            {"password_value": "x"},
            {"teacher_id": 99},
        ]:
            with self.assertRaises(core.EvidenceContractError):
                core.assert_privacy_safe_evidence(bad)

    def test_safe_network_diagnostic_omits_query_and_redacts_dynamic_path_segments(self):
        diagnostic = core.safe_network_diagnostic(
            "authentication",
            "post",
            "https://learn2.guidedelearning.net/corelogin/463963/0123456789abcdef0123456789abcdef?username=PRIVATE&password=SECRET",
        )
        self.assertEqual(diagnostic["phase"], "authentication")
        self.assertEqual(diagnostic["method"], "POST")
        self.assertEqual(diagnostic["origin"], "https://learn2.guidedelearning.net")
        self.assertEqual(diagnostic["redacted_path"], "/corelogin/{id}/{redacted}")
        encoded = json.dumps(diagnostic)
        self.assertNotIn("PRIVATE", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("username", encoded)
        self.assertNotIn("password", encoded)

    def test_network_origin_authority_distinguishes_gel_from_third_party(self):
        self.assertEqual(
            core.network_origin_authority("https://learn2.guidedelearning.net/study/tutorials/process"),
            "gel",
        )
        self.assertEqual(
            core.network_origin_authority("https://www.google-analytics.com/j/collect?v=1"),
            "third_party",
        )
        self.assertEqual(
            core.network_origin_authority("http://learn2.guidedelearning.net/study/tutorials/process"),
            "gel_invalid_transport",
        )

    def test_third_party_analytics_diagnostic_is_query_free(self):
        diagnostic = core.safe_network_diagnostic(
            "authentication",
            "POST",
            "https://www.google-analytics.com/j/collect?v=1&cid=PRIVATE&uid=SECRET",
        )
        self.assertEqual(diagnostic["origin"], "https://www.google-analytics.com")
        self.assertEqual(diagnostic["redacted_path"], "/j/collect")
        encoded = json.dumps(diagnostic)
        self.assertNotIn("PRIVATE", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertNotIn("cid", encoded)
        self.assertNotIn("uid", encoded)

    def test_locator_digest_is_student_free_and_deterministic(self):
        first = core.locator_digest([(20, "0"), (10, "2")])
        second = core.locator_digest([(10, "2"), (20, "0")])
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
