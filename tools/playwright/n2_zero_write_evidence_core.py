#!/usr/bin/env python3
"""Pure helpers for the N2-PW1 zero-write Playwright evidence harness.

This module deliberately has no Playwright dependency.  It owns only privacy-safe
normalization, request-evidence extraction, aliases, hashes and prepopulation
classification so the release gate can exercise those rules offline.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from urllib.parse import parse_qs, urlparse

TUTORIAL_TYPE_BY_CODE = {"0": "standard", "1": "final", "2": "initial"}
TUTORIAL_CODE_BY_TYPE = {value: key for key, value in TUTORIAL_TYPE_BY_CODE.items()}
EXPECTED_FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"
ALLOWED_SUBMISSION_FIELDS = {"tid", "ttype", "customdate", "datetime"}

def network_origin_authority(url: str) -> str:
    """Classify request authority without inspecting query/body/header data."""
    parsed = urlparse(url)
    if parsed.netloc == "learn2.guidedelearning.net":
        return "gel" if parsed.scheme == "https" else "gel_invalid_transport"
    return "third_party"


# These keys must never appear in a persisted PW1 evidence document.  The live
# harness is allowed to hold some corresponding values transiently in memory,
# but the evidence writer must reduce them to aliases/booleans/hashes first.
FORBIDDEN_PERSISTED_KEY_FRAGMENTS = {
    "password",
    "username",
    "cookie",
    "authorization",
    "csrf",
    "form_token",
    "form_build_id",
    "raw_html",
    "post_data",
    "post_body",
    "request_body",
    "request_headers",
    "student_uid",
    "teacher_id",
    "teacher_name",
    "tid_value",
}

DATE_RE = re.compile(r"^\d{2}-\d{2}-\d{4}$")


_DIAGNOSTIC_SAFE_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._~-]+$")
_DIAGNOSTIC_LONG_HEX_RE = re.compile(r"^[A-Fa-f0-9]{20,}$")


def redact_network_path(path: str) -> str:
    """Return a route-diagnostic path with likely dynamic/sensitive segments redacted.

    Query parameters are deliberately not accepted by this helper; callers pass
    only the parsed URL path. The result is suitable for immediate terminal
    diagnostics but is not a persistence format.
    """
    segments: list[str] = []
    for segment in path.split("/"):
        if not segment:
            segments.append("")
            continue
        if segment.isdigit():
            segments.append("{id}")
        elif (
            "@" in segment
            or len(segment) > 64
            or _DIAGNOSTIC_LONG_HEX_RE.fullmatch(segment)
            or not _DIAGNOSTIC_SAFE_SEGMENT_RE.fullmatch(segment)
        ):
            segments.append("{redacted}")
        else:
            segments.append(segment)
    redacted = "/".join(segments)
    return redacted if redacted.startswith("/") else "/" + redacted


def safe_network_diagnostic(phase: str, method: str, url: str) -> dict[str, str]:
    """Reduce a blocked request to the four fields safe for terminal diagnosis.

    The query string, request body, headers, cookies and form values are never
    returned. This helper exists so the privacy rule is executable offline.
    """
    parsed = urlparse(url)
    origin = (
        f"{parsed.scheme}://{parsed.netloc}"
        if parsed.scheme and parsed.netloc
        else "{unknown_origin}"
    )
    return {
        "phase": str(phase),
        "method": str(method).upper(),
        "origin": origin,
        "redacted_path": redact_network_path(parsed.path or "/"),
    }


class EvidenceContractError(RuntimeError):
    """A zero-write evidence invariant or privacy rule was violated."""


def _one(values: dict[str, list[str]], key: str) -> str | None:
    current = values.get(key)
    if not current:
        return None
    if len(current) != 1:
        raise EvidenceContractError(f"expected exactly one {key!r} value")
    return current[0]


def normalize_scalar(value: Any) -> str:
    """Stable in-memory comparison normalization; never a persistence format."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


@dataclass
class TeacherAliasBook:
    """Map transient numeric GEL teacher ids to non-identifying run-local aliases."""

    _aliases: dict[str, str] = field(default_factory=dict)

    def alias(self, raw_value: str | int | None) -> str | None:
        if raw_value is None:
            return None
        raw = str(raw_value).strip()
        if not raw:
            return None
        if not raw.isdigit() or int(raw) <= 0:
            raise EvidenceContractError("teacher control contained a non-positive/non-numeric value")
        if raw not in self._aliases:
            self._aliases[raw] = f"T{len(self._aliases) + 1}"
        return self._aliases[raw]

    def same(self, left: str | int | None, right: str | int | None) -> bool:
        if left is None or right is None:
            return False
        return str(left).strip() == str(right).strip()


def parse_urlencoded_submission_evidence(
    body: str,
    content_type: str | None,
    aliases: TeacherAliasBook,
    *,
    expected_revision_timestamp: int | None = None,
    expected_selected_teacher: str | None = None,
) -> dict[str, Any]:
    """Reduce a transient real GEL tutorial POST body to privacy-safe evidence.

    The caller must abort the network request regardless of whether this parser
    succeeds.  No raw body, comments, aims, levels, form tokens or headers are
    returned.
    """

    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type != EXPECTED_FORM_CONTENT_TYPE:
        raise EvidenceContractError(
            f"unexpected tutorial submission content type {normalized_type or '<missing>'!r}"
        )

    values = parse_qs(body, keep_blank_values=True, strict_parsing=False)
    teacher_raw = _one(values, "tid")
    tutorial_type = _one(values, "ttype")
    customdate = _one(values, "customdate")
    datetime_raw = _one(values, "datetime") if "datetime" in values else None

    if teacher_raw is None:
        raise EvidenceContractError("tutorial submission omitted tid")
    teacher_alias = aliases.alias(teacher_raw)
    if tutorial_type not in TUTORIAL_TYPE_BY_CODE:
        raise EvidenceContractError("tutorial submission contained unknown ttype")

    datetime_present = "datetime" in values
    datetime_positive = False
    datetime_matches_existing: bool | None = None
    if datetime_present:
        if datetime_raw is None or not datetime_raw.isdigit() or int(datetime_raw) <= 0:
            raise EvidenceContractError("tutorial datetime was present but not a positive integer")
        datetime_positive = True
        if expected_revision_timestamp is not None:
            datetime_matches_existing = int(datetime_raw) == int(expected_revision_timestamp)
    elif expected_revision_timestamp is not None:
        datetime_matches_existing = False

    selected_matches_submission: bool | None = None
    if expected_selected_teacher is not None:
        selected_matches_submission = str(expected_selected_teacher).strip() == str(teacher_raw).strip()

    return {
        "teacher_alias": teacher_alias,
        "selected_teacher_matches_submission": selected_matches_submission,
        "tutorial_type": TUTORIAL_TYPE_BY_CODE[tutorial_type],
        "customdate_present": customdate is not None,
        "customdate_well_formed": bool(customdate and DATE_RE.fullmatch(customdate)),
        "datetime_present": datetime_present,
        "datetime_positive": datetime_positive,
        "datetime_matches_existing": datetime_matches_existing,
        "allowlisted_fields_observed": sorted(ALLOWED_SUBMISSION_FIELDS & set(values)),
    }


def locator_digest(locators: list[tuple[int, str]]) -> str:
    """Hash a student-free tutorial locator projection (timestamp + type only)."""
    canonical = json.dumps(sorted((int(ts), str(ttype)) for ts, ttype in locators), separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def semantic_digest(snapshot: dict[str, Any]) -> str:
    normalized = {key: normalize_scalar(value) for key, value in sorted(snapshot.items())}
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_unset(value: Any, placeholders: set[str]) -> bool:
    text = normalize_scalar(value)
    return not text or text in placeholders


def classify_prepopulation(
    source: dict[str, Any],
    target: dict[str, Any],
    *,
    placeholders: set[str],
    requested_type: str,
    authenticated_teacher_raw: str | None,
    current_date: date,
) -> dict[str, Any]:
    """Classify New-form field behaviour from the already-established latest source.

    Values are compared in memory.  Only semantic field names and relational
    classifications are returned.
    """

    result: dict[str, Any] = {
        "source_rule": "latest_tutorial",
        "requested_type": requested_type,
        "identity_rules": {
            "subject": "route_identity",
            "teacher": "unresolved_until_target_compared",
        },
        "fields": {},
    }

    source_norm = {k: normalize_scalar(v) for k, v in source.items()}
    target_norm = {k: normalize_scalar(v) for k, v in target.items()}

    for field_name, target_value in sorted(target_norm.items()):
        if field_name == "source_timestamp":
            result["fields"][field_name] = "absent_for_new" if not target_value else "contract_drift_present"
            continue
        if field_name == "tutorial_type":
            result["fields"][field_name] = "derived_from_requested_type"
            continue
        if field_name == "teacher_id":
            # Teacher identity is deliberately excluded from the persisted
            # field map.  PW1 records only the relationship, never an identity-
            # bearing semantic key/value pair.  The raw value remains transient.
            if authenticated_teacher_raw is not None and target_value == normalize_scalar(authenticated_teacher_raw):
                result["identity_rules"]["teacher"] = "derived_from_authenticated_session"
            else:
                result["identity_rules"]["teacher"] = "contract_drift_teacher_default"
            continue
        if field_name == "tutorial_date":
            expected = current_date.strftime("%d-%m-%Y")
            result["fields"][field_name] = (
                "derived_from_current_date" if target_value == expected else "new_specific_or_transformed"
            )
            continue
        if field_name == "student_uid":
            # Student route identity is already represented by the pseudonymous
            # subject_ref (S1); do not persist an identity-bearing semantic key.
            continue

        # N2a: field identity is authoritative. Compare only the same semantic
        # field name. Equal values in unrelated skills never establish
        # provenance (for example Initial Listening may not be inferred from
        # Speaking merely because both happen to contain the same CEFR value).
        source_same = source_norm.get(field_name)
        if source_same is not None:
            if target_value == source_same:
                result["fields"][field_name] = "copied_unchanged"
            elif is_unset(target_value, placeholders) and not is_unset(source_same, placeholders):
                result["fields"][field_name] = "reset_for_new"
            else:
                result["fields"][field_name] = "new_specific_or_transformed"
            continue

        if is_unset(target_value, placeholders):
            result["fields"][field_name] = "unset_or_not_carried_from_source_type"
        else:
            result["fields"][field_name] = "new_specific_or_transformed"

    return result


def assert_privacy_safe_evidence(value: Any, path: str = "$") -> None:
    """Reject accidental persistence of credential/session/personal raw state."""
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.lower()
            for forbidden in FORBIDDEN_PERSISTED_KEY_FRAGMENTS:
                if forbidden in lowered:
                    raise EvidenceContractError(f"forbidden persisted evidence key at {path}.{key}")
            assert_privacy_safe_evidence(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_privacy_safe_evidence(child, f"{path}[{index}]")
    elif isinstance(value, str):
        # Evidence values must not contain obvious absolute GEL tutorial/student
        # routes, which would embed the real student UID/timestamp in persisted data.
        if re.search(r"/study/tutorials/(?:add|summary|print)/\d+", value):
            raise EvidenceContractError(f"raw GEL tutorial route leaked into persisted evidence at {path}")
        if re.search(r"/staff/students/\d+", value):
            raise EvidenceContractError(f"raw GEL student API route leaked into persisted evidence at {path}")



def initial_evidence_document() -> dict[str, Any]:
    """Return the privacy-safe persisted evidence preamble.

    Keep negative capture-policy assertions in names that do not themselves
    resemble forbidden raw-data fields; the global privacy guard remains strict.
    """
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "phase": "N2-PW1",
        "mode": "zero_write",
        "subject_ref": "S1",
        "privacy": {
            "authentication": "manual_browser_only",
            "login_body_inspected": False,
            "credential_values_read_by_harness": False,
            "browser_storage_state_persisted": False,
            "page_source_capture_enabled": False,
            "submission_payload_capture_enabled": False,
            "network_header_capture_enabled": False,
            "staff_display_label_capture_enabled": False,
            "student_identity_persisted": False,
        },
        "authority": {
            "prepopulation_source": "latest_tutorial_established_before_PW1",
            "teacher_reassignment_server_semantics": "unresolved",
        },
        "new_forms": {},
    }
    assert_privacy_safe_evidence(evidence)
    return evidence

def evidence_json_bytes(value: dict[str, Any]) -> bytes:
    assert_privacy_safe_evidence(value)
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
