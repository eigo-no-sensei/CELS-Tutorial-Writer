#!/usr/bin/env python3
"""N2-PW1: privacy-safe, zero-write GEL browser evidence harness.

The operator authenticates manually in a fresh headed Chromium context.  This
program never receives, queries, logs or persists username/password values.
A mutation firewall is installed before the first navigation. GEL mutation
authority is fail-closed: during evidence the only recognized tutorial POST is
reduced to allowlisted structural evidence and then aborted. Third-party
mutating telemetry is also aborted, but cannot invalidate GEL evidence because
it has no GEL state-writing authority.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Page, Route, sync_playwright

from n2_zero_write_evidence_core import (
    EvidenceContractError,
    TeacherAliasBook,
    TUTORIAL_CODE_BY_TYPE,
    TUTORIAL_TYPE_BY_CODE,
    assert_privacy_safe_evidence,
    classify_prepopulation,
    evidence_json_bytes,
    initial_evidence_document,
    locator_digest,
    network_origin_authority,
    parse_urlencoded_submission_evidence,
    semantic_digest,
    safe_network_diagnostic,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "contracts" / "gel_tutorial_fields.json"
DEFAULT_EVIDENCE_DIR = ROOT / "evidence-private" / "n2-playwright"
LEARN2_ORIGIN = "https://learn2.guidedelearning.net"
LOGIN_PAGE_URL = f"{LEARN2_ORIGIN}/corelogin/"
LOGIN_FORM_PAGE_URL = f"{LEARN2_ORIGIN}/user/login"
LOGIN_POST_PATH = "/user/login"
TUTORIAL_PROCESS_PATH = "/study/tutorials/process"
LONDON = ZoneInfo("Europe/London")
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
TYPE_ORDER = ["standard", "initial", "final"]


class Phase(str, Enum):
    AUTHENTICATION = "authentication"
    EVIDENCE = "evidence"
    VERIFY = "verify"
    CLOSED = "closed"


@dataclass
class ArmedProbe:
    label: str
    expected_revision_timestamp: int | None
    expected_selected_teacher: str | None


class MutationFirewall:
    """Fail-closed context-wide network mutation authority."""

    def __init__(self, aliases: TeacherAliasBook) -> None:
        self.phase = Phase.AUTHENTICATION
        self.aliases = aliases
        self.login_posts_forwarded = 0
        self.expected_tutorial_posts_aborted = 0
        self.unexpected_gel_mutations_aborted = 0
        self.third_party_mutations_aborted = 0
        self.forwarded_mutations_after_authentication = 0
        self.failures: list[str] = []
        self.active_probe: ArmedProbe | None = None
        self.last_probe_result: dict[str, Any] | None = None

    def set_phase(self, phase: Phase) -> None:
        self.phase = phase

    def arm_probe(
        self,
        label: str,
        *,
        expected_revision_timestamp: int | None = None,
        expected_selected_teacher: str | None = None,
    ) -> None:
        if self.phase != Phase.EVIDENCE:
            raise EvidenceContractError("tutorial probe can be armed only in EVIDENCE phase")
        if self.active_probe is not None:
            raise EvidenceContractError("another tutorial probe is already armed")
        self.active_probe = ArmedProbe(label, expected_revision_timestamp, expected_selected_teacher)
        self.last_probe_result = None

    def disarm_without_request(self) -> None:
        self.active_probe = None

    def consume_probe_result(self) -> dict[str, Any] | None:
        result = self.last_probe_result
        self.last_probe_result = None
        return result

    def handle(self, route: Route) -> None:
        request = route.request
        method = request.method.upper()
        parsed = urlparse(request.url)

        if method in {"GET", "HEAD", "OPTIONS"}:
            route.continue_()
            return

        # Third-party analytics/telemetry has no GEL write authority. Block any
        # non-read third-party request without inspecting its body/headers and
        # without turning the GEL evidence run into a false failure.
        origin_authority = network_origin_authority(request.url)
        if origin_authority == "third_party":
            self._abort_third_party(route, method)
            return

        if method not in MUTATING_METHODS:
            self._abort_unexpected_gel(route, method, "unsupported_method")
            return

        if origin_authority != "gel":
            self._abort_unexpected_gel(route, method, "invalid_gel_transport")
            return

        if self.phase == Phase.AUTHENTICATION:
            self._handle_authentication_mutation(route, method, parsed)
            return

        if (
            self.phase == Phase.EVIDENCE
            and method == "POST"
            and parsed.scheme == "https"
            and parsed.netloc == "learn2.guidedelearning.net"
            and parsed.path == TUTORIAL_PROCESS_PATH
            and self.active_probe is not None
        ):
            self._handle_expected_tutorial_submission(route)
            return

        self._abort_unexpected_gel(route, method, "mutation_not_authorized")

    def _handle_authentication_mutation(self, route: Route, method: str, parsed: Any) -> None:
        """Allow only the canonical login POST; deliberately inspect no body/header data."""
        if (
            method == "POST"
            and parsed.scheme == "https"
            and parsed.netloc == "learn2.guidedelearning.net"
            and parsed.path == LOGIN_POST_PATH
        ):
            self.login_posts_forwarded += 1
            route.continue_()
            return
        self._abort_unexpected_gel(route, method, "non_login_mutation_during_authentication")

    def _handle_expected_tutorial_submission(self, route: Route) -> None:
        """Extract allowlisted evidence and *always* abort the tutorial mutation."""
        request = route.request
        probe = self.active_probe
        self.active_probe = None
        try:
            # The content-type and request body are read only here, after manual
            # authentication, for the exact known tutorial process route.
            content_type = request.header_value("content-type")
            body = request.post_data or ""
            reduced = parse_urlencoded_submission_evidence(
                body,
                content_type,
                self.aliases,
                expected_revision_timestamp=probe.expected_revision_timestamp if probe else None,
                expected_selected_teacher=probe.expected_selected_teacher if probe else None,
            )
            self.last_probe_result = {
                "label": probe.label if probe else "unknown",
                "intercepted": True,
                "forwarded": False,
                **reduced,
            }
        except Exception as exc:  # the request is still aborted below
            self.last_probe_result = {
                "label": probe.label if probe else "unknown",
                "intercepted": True,
                "forwarded": False,
                "classification": "contract_drift_or_unparseable_submission",
            }
            self.failures.append(f"expected_submission_parse:{type(exc).__name__}")
        finally:
            # Critical invariant: no expected tutorial POST has a continue branch.
            self.expected_tutorial_posts_aborted += 1
            route.abort("blockedbyclient")

    def _emit_blocked_diagnostic(self, method: str, url: str) -> None:
        """Print only a privacy-safe route diagnostic for an auth-phase block."""
        diagnostic = safe_network_diagnostic(self.phase.value, method, url)
        print("PW1 authentication firewall blocked a mutation:", file=sys.stderr, flush=True)
        print(f"  phase: {diagnostic['phase']}", file=sys.stderr, flush=True)
        print(f"  method: {diagnostic['method']}", file=sys.stderr, flush=True)
        print(f"  origin: {diagnostic['origin']}", file=sys.stderr, flush=True)
        print(f"  path: {diagnostic['redacted_path']}", file=sys.stderr, flush=True)

    def _abort_third_party(self, route: Route, method: str) -> None:
        """Block third-party mutation/telemetry without making it GEL contract drift."""
        self.third_party_mutations_aborted += 1
        diagnostic = safe_network_diagnostic(self.phase.value, method, route.request.url)
        print("PW1 blocked third-party mutation (non-fatal):", file=sys.stderr, flush=True)
        print(f"  phase: {diagnostic['phase']}", file=sys.stderr, flush=True)
        print(f"  method: {diagnostic['method']}", file=sys.stderr, flush=True)
        print(f"  origin: {diagnostic['origin']}", file=sys.stderr, flush=True)
        print(f"  path: {diagnostic['redacted_path']}", file=sys.stderr, flush=True)
        route.abort("blockedbyclient")

    def _abort_unexpected_gel(self, route: Route, method: str, reason: str) -> None:
        self.unexpected_gel_mutations_aborted += 1
        diagnostic = safe_network_diagnostic(self.phase.value, method, route.request.url)
        self.failures.append(f"{reason}:{method}:{diagnostic['redacted_path']}")
        if self.phase == Phase.AUTHENTICATION:
            self._emit_blocked_diagnostic(method, route.request.url)
        route.abort("blockedbyclient")

    def summary(self) -> dict[str, Any]:
        return {
            "login_mutations_forwarded_before_evidence": self.login_posts_forwarded,
            "expected_tutorial_mutations_aborted": self.expected_tutorial_posts_aborted,
            "unexpected_gel_mutations_aborted": self.unexpected_gel_mutations_aborted,
            "third_party_mutations_aborted": self.third_party_mutations_aborted,
            "forwarded_mutations_during_evidence": self.forwarded_mutations_after_authentication,
            "failure_categories": sorted(set(self.failures)),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="N2-PW1 zero-write GEL browser evidence; credentials are entered only in GEL's browser page."
    )
    parser.add_argument("--student-uid", required=True, type=int, help="numeric GEL student UID; never written to evidence")
    parser.add_argument(
        "--types",
        default="all",
        choices=["all", "standard", "initial", "final"],
        help="new-form types to inspect; default all",
    )
    parser.add_argument("--output", type=Path, help="privacy-safe evidence JSON path")
    parser.add_argument(
        "--no-teacher-change-probe",
        action="store_true",
        help="inspect teacher controls but do not locally select an alternate teacher before intercepted submission",
    )
    return parser.parse_args()


def load_field_contract() -> tuple[list[dict[str, Any]], set[str]]:
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    fields = data["fields"]
    placeholders = set(data.get("placeholders", {}).values())
    return fields, placeholders


def is_authenticated_page(page: Page) -> bool:
    parsed = urlparse(page.url)
    if parsed.netloc != "learn2.guidedelearning.net":
        return False
    if parsed.path.startswith("/user/login") or parsed.path.startswith("/corelogin"):
        return False
    # Existence is safe to inspect; the harness never reads a password value.
    return page.locator('input[type="password"]').count() == 0




def _safe_page_category(url: str) -> dict[str, str]:
    diagnostic = safe_network_diagnostic("authentication", "GET", url)
    return {
        "origin": diagnostic["origin"],
        "path": diagnostic["redacted_path"],
    }


def verify_learn2_session(context: BrowserContext) -> dict[str, Any]:
    """Verify the browser's Learn2 session using a GET only.

    No response body, headers, cookies, form values or query parameters are
    persisted or printed.  A separate page preserves the operator's login page.
    """
    probe = context.new_page()
    try:
        probe.goto(
            f"{LEARN2_ORIGIN}/administration/students",
            wait_until="domcontentloaded",
            timeout=30_000,
        )
        probe.wait_for_timeout(250)
        category = _safe_page_category(probe.url)
        authenticated_path = category["origin"] == LEARN2_ORIGIN and (
            category["path"] == "/administration/students"
            or category["path"].startswith("/administration/students/")
        )
        authenticated = authenticated_path and is_authenticated_page(probe)
        return {
            "authenticated": authenticated,
            "final_origin": category["origin"],
            "final_path": category["path"],
            "password_control_present": probe.locator('input[type="password"]').count() > 0,
        }
    finally:
        probe.close()


def print_authentication_verification(label: str, firewall: MutationFirewall, result: dict[str, Any]) -> None:
    """Emit only non-secret authentication state needed to diagnose the handshake."""
    print(f"PW1 authentication verification ({label}):")
    print(f"  login POSTs forwarded: {firewall.login_posts_forwarded}")
    print(f"  Learn2 authenticated GET: {'YES' if result['authenticated'] else 'NO'}")
    print(f"  final origin: {result['final_origin']}")
    print(f"  final path: {result['final_path']}")
    print(f"  password control present: {'YES' if result['password_control_present'] else 'NO'}")


def announce_stage(stage: str) -> None:
    """Emit a static/privacy-safe progress marker; never include identities or values."""
    allowed = {
        "authenticated",
        "baseline_summary",
        "latest_revision_snapshot",
        "new_form_standard",
        "new_form_initial",
        "new_form_final",
        "revision_probe",
        "final_verification",
        "evidence_evaluation",
        "privacy_validation",
        "evidence_written",
    }
    if stage not in allowed:
        raise EvidenceContractError("unknown PW1 diagnostic stage")
    print(f"PW1 stage: {stage}", flush=True)


def goto_get(page: Page, path: str) -> None:
    if not path.startswith("/"):
        raise EvidenceContractError("internal GEL path must be absolute")
    page.goto(f"{LEARN2_ORIGIN}{path}", wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(250)
    if not is_authenticated_page(page):
        raise EvidenceContractError("authenticated GEL GET returned login/unexpected page")


def tutorial_locators_from_summary(page: Page, student_uid: int) -> list[tuple[int, str]]:
    hrefs = page.locator('a[href*="/study/tutorials/add/"]').evaluate_all(
        "els => els.map(el => el.href)"
    )
    found: list[tuple[int, str]] = []
    pattern = re.compile(rf"^/study/tutorials/add/{student_uid}/(\d+)/(0|1|2)$")
    for href in hrefs:
        parsed = urlparse(str(href))
        if parsed.netloc and parsed.netloc != "learn2.guidedelearning.net":
            continue
        match = pattern.match(parsed.path)
        if match and int(match.group(1)) > 0:
            found.append((int(match.group(1)), match.group(2)))
    if not found:
        raise EvidenceContractError("no historical tutorial edit locators found in authenticated summary")
    return sorted(found)


def _value_for_control(page: Page, gel_name: str, kind: str, editor_id: str | None = None) -> str:
    if kind == "contenteditable_plus_hidden":
        if editor_id and page.locator(f"#{editor_id}").count():
            return page.locator(f"#{editor_id}").first.inner_text()
        hidden = page.locator(f'[name="{gel_name}"]')
        return hidden.first.input_value() if hidden.count() else ""
    if kind == "radio_group":
        checked = page.locator(f'input[type="radio"][name="{gel_name}"]:checked')
        return checked.first.get_attribute("value") or "" if checked.count() else ""
    if kind == "checkbox":
        locator = page.locator(f'input[name="{gel_name}"]')
        return "1" if locator.count() and locator.first.is_checked() else "0"
    if kind == "select":
        locator = page.locator(f'select[name="{gel_name}"]')
        if locator.count():
            return locator.first.input_value()
        # New-form historical evidence shows tid can be hidden even though the
        # revision field contract describes it as a select.
        hidden = page.locator(f'input[name="{gel_name}"]')
        return hidden.first.input_value() if hidden.count() else ""
    locator = page.locator(f'[name="{gel_name}"]')
    return locator.first.input_value() if locator.count() else ""


def semantic_snapshot(page: Page, fields: list[dict[str, Any]], tutorial_type: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in fields:
        if tutorial_type not in field.get("applies_to", []):
            continue
        if field["semantic_name"] == "language":
            continue
        result[field["semantic_name"]] = _value_for_control(
            page,
            field["gel_name"],
            field.get("control_kind", ""),
            field.get("editor_id"),
        )
    return result


def teacher_structure(page: Page, aliases: TeacherAliasBook) -> tuple[dict[str, Any], str | None, list[str]]:
    hidden = page.locator('input[name="tid"]')
    selects = page.locator('select[name="tid"]')
    raw_current: str | None = None
    control_kinds: list[str] = []
    if hidden.count():
        control_kinds.append("hidden")
        raw_current = hidden.first.input_value()
    option_values: list[str] = []
    editable_selector = False
    if selects.count():
        control_kinds.append("select")
        select = selects.first
        raw_current = select.input_value()
        editable_selector = select.is_enabled()
        option_values = [
            str(value).strip()
            for value in select.locator("option").evaluate_all("els => els.map(el => el.value)")
            if str(value).strip().isdigit() and int(str(value).strip()) > 0
        ]
    alias = aliases.alias(raw_current) if raw_current else None
    structure = {
        "control_kinds": sorted(set(control_kinds)) or ["absent"],
        "current_teacher_alias": alias,
        "editable_selector": editable_selector,
        "positive_option_count": len(set(option_values)),
    }
    return structure, raw_current, option_values


def form_structure(page: Page, aliases: TeacherAliasBook) -> tuple[dict[str, Any], str | None, list[str]]:
    teacher, teacher_raw, options = teacher_structure(page, aliases)
    form = page.locator('form:has([name="ttype"])')
    if not form.count():
        raise EvidenceContractError("tutorial form containing ttype was not found")
    form = form.first
    action = form.get_attribute("action") or ""
    action_path = urlparse(action).path if action else ""
    method = (form.get_attribute("method") or "GET").upper()
    customdate = page.locator('[name="customdate"]')
    current_date = datetime.now(LONDON).strftime("%d-%m-%Y")
    return (
        {
            "form_method": method,
            "form_action": "tutorial_process" if action_path == TUTORIAL_PROCESS_PATH else "unexpected_action",
            "teacher": teacher,
            "datetime_present": page.locator('[name="datetime"]').count() > 0,
            "customdate_present": customdate.count() > 0,
            "customdate_matches_current_london_date": bool(
                customdate.count() and customdate.first.input_value() == current_date
            ),
            "ttype_present": page.locator('[name="ttype"]').count() > 0,
        },
        teacher_raw,
        options,
    )


def choose_alternate_teacher(page: Page, current: str | None, options: list[str]) -> str | None:
    if current is None:
        return None
    select = page.locator('select[name="tid"]')
    if not select.count() or not select.first.is_enabled():
        return None
    alternative = next((value for value in options if value != str(current)), None)
    if alternative is None:
        return None
    select.first.select_option(value=alternative)
    if select.first.input_value() != alternative:
        raise EvidenceContractError("teacher selector did not retain the local alternate selection")
    return alternative


def trigger_real_submit(page: Page, firewall: MutationFirewall) -> dict[str, Any]:
    form = page.locator('form:has([name="ttype"])').first
    buttons = form.locator('input[type="submit"]:visible, button[type="submit"]:visible, button:not([type]):visible')
    if not buttons.count():
        firewall.disarm_without_request()
        return {"status": "no_real_submit_control"}
    try:
        buttons.first.click(timeout=5_000)
    except PlaywrightError:
        # Aborting a navigation request can surface as a browser-level failure;
        # the firewall result is authoritative about whether interception occurred.
        pass
    page.wait_for_timeout(1_000)
    captured = firewall.consume_probe_result()
    if captured is not None:
        return {"status": "intercepted_and_aborted", "submission": captured}
    firewall.disarm_without_request()
    try:
        valid = bool(form.evaluate("form => form.checkValidity()"))
    except PlaywrightError:
        valid = True
    return {"status": "client_blocked_before_request" if not valid else "no_request_observed"}


def safe_output_path(explicit: Path | None) -> Path:
    base = DEFAULT_EVIDENCE_DIR.resolve()
    if explicit is not None:
        resolved = explicit.expanduser().resolve()
        if not resolved.is_relative_to(base):
            raise EvidenceContractError("PW1 evidence output must remain under evidence-private/n2-playwright")
        return resolved
    stamp = datetime.now(LONDON).strftime("%Y%m%dT%H%M%S%z")
    return base / f"n2-pw1-{stamp}.json"


def run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.student_uid <= 0:
        raise EvidenceContractError("student UID must be a positive integer")
    fields, placeholders = load_field_contract()
    aliases = TeacherAliasBook()
    output = safe_output_path(args.output)
    requested_types = TYPE_ORDER if args.types == "all" else [args.types]

    evidence = initial_evidence_document()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        # Non-persistent context + service-worker blocking ensures all relevant
        # browser traffic remains inside the context-wide routing firewall.
        context: BrowserContext = browser.new_context(service_workers="block")
        firewall = MutationFirewall(aliases)
        context.route("**/*", firewall.handle)
        page = context.new_page()

        page.goto(LOGIN_PAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        print("Stage 1/2: complete the GEL /corelogin/ login attempt in the browser.")
        print("This harness does not read or store the username/password fields.")
        input("After submitting the /corelogin/ form, press Enter here: ")

        first_auth = verify_learn2_session(context)
        print_authentication_verification("after corelogin", firewall, first_auth)

        if not first_auth["authenticated"]:
            if firewall.login_posts_forwarded == 0:
                raise EvidenceContractError(
                    "no canonical GEL login POST was observed from /corelogin/; authentication cannot continue safely"
                )
            print("Learn2 session is not established yet; GEL historical evidence shows a second /user/login step.")
            print("Stage 2/2: the harness will open that GEL page in the same ephemeral browser context.")
            page.goto(LOGIN_FORM_PAGE_URL, wait_until="domcontentloaded", timeout=30_000)
            print("Complete the /user/login form manually in the browser; credentials remain browser-only.")
            input("After submitting the /user/login form, press Enter here: ")
            second_auth = verify_learn2_session(context)
            print_authentication_verification("after user/login", firewall, second_auth)
            if not second_auth["authenticated"]:
                raise EvidenceContractError(
                    "two-stage manual GEL login did not establish an authenticated Learn2 session"
                )

        firewall.set_phase(Phase.EVIDENCE)
        announce_stage("authenticated")

        # Baseline and latest source are obtained only from authenticated GETs.
        announce_stage("baseline_summary")
        goto_get(page, f"/study/tutorials/summary/{args.student_uid}")
        baseline_locators = tutorial_locators_from_summary(page, args.student_uid)
        baseline_digest = locator_digest(baseline_locators)
        latest_ts, latest_code = max(baseline_locators, key=lambda item: item[0])
        latest_type = TUTORIAL_TYPE_BY_CODE[latest_code]

        announce_stage("latest_revision_snapshot")
        goto_get(page, f"/study/tutorials/add/{args.student_uid}/{latest_ts}/{latest_code}")
        source_snapshot = semantic_snapshot(page, fields, latest_type)
        source_digest = semantic_digest(source_snapshot)
        source_structure, source_teacher_raw, source_options = form_structure(page, aliases)
        evidence["baseline"] = {
            "tutorial_locator_count": len(baseline_locators),
            "tutorial_locator_digest": baseline_digest,
            "latest_tutorial_type": latest_type,
            "latest_state_digest": source_digest,
            "latest_teacher_matches_authenticated_teacher": None,
        }
        evidence["revision_form"] = {
            "structure": source_structure,
        }

        authenticated_teacher_raw: str | None = None

        for tutorial_type in requested_types:
            announce_stage(f"new_form_{tutorial_type}")
            code = TUTORIAL_CODE_BY_TYPE[tutorial_type]
            goto_get(page, f"/study/tutorials/add/{args.student_uid}/0/{code}")
            structure, teacher_raw, teacher_options = form_structure(page, aliases)
            if authenticated_teacher_raw is None and teacher_raw:
                # Historical TEACHER-1 establishes that the GEL-provided New tid
                # is the authenticated teacher. PW1 uses it only as an in-memory
                # comparison anchor and persists an alias/relationship, not the id.
                authenticated_teacher_raw = teacher_raw
            new_snapshot = semantic_snapshot(page, fields, tutorial_type)
            structure["teacher"]["matches_authenticated_teacher"] = bool(
                authenticated_teacher_raw and teacher_raw == authenticated_teacher_raw
            )
            prepopulation = classify_prepopulation(
                source_snapshot,
                new_snapshot,
                placeholders=placeholders,
                requested_type=tutorial_type,
                authenticated_teacher_raw=authenticated_teacher_raw,
                current_date=datetime.now(LONDON).date(),
            )

            selected_teacher = teacher_raw
            teacher_change = {
                "attempted": False,
                "selector_available": bool(
                    "select" in structure["teacher"]["control_kinds"]
                    and structure["teacher"]["editable_selector"]
                    and structure["teacher"]["positive_option_count"] >= 2
                ),
            }
            if teacher_change["selector_available"] and not args.no_teacher_change_probe:
                alternate = choose_alternate_teacher(page, teacher_raw, teacher_options)
                if alternate is not None:
                    teacher_change["attempted"] = True
                    teacher_change["selection_changed_in_browser"] = True
                    teacher_change["selected_teacher_alias"] = aliases.alias(alternate)
                    selected_teacher = alternate

            firewall.arm_probe(
                f"new_{tutorial_type}",
                expected_selected_teacher=selected_teacher,
            )
            submit_probe = trigger_real_submit(page, firewall)
            if submit_probe.get("submission"):
                submission = submit_probe["submission"]
                submit_probe["historical_datetime_contract_confirmed"] = submission.get("datetime_present") is False
                submit_probe["teacher_selection_survived_serialization"] = submission.get(
                    "selected_teacher_matches_submission"
                )

            # Independent server-state check after every aborted create attempt.
            goto_get(page, f"/study/tutorials/summary/{args.student_uid}")
            after_locators = tutorial_locators_from_summary(page, args.student_uid)
            after_digest = locator_digest(after_locators)

            evidence["new_forms"][tutorial_type] = {
                "structure": structure,
                "teacher_change_probe": teacher_change,
                "submission_probe": submit_probe,
                "prepopulation": prepopulation,
                "server_verification": {
                    "tutorial_locator_count_unchanged": len(after_locators) == len(baseline_locators),
                    "tutorial_locator_digest_unchanged": after_digest == baseline_digest,
                },
            }

        if authenticated_teacher_raw is not None and source_teacher_raw is not None:
            evidence["baseline"]["latest_teacher_matches_authenticated_teacher"] = (
                source_teacher_raw == authenticated_teacher_raw
            )

        # Existing-tutorial serialization probe. The request is always aborted.
        announce_stage("revision_probe")
        goto_get(page, f"/study/tutorials/add/{args.student_uid}/{latest_ts}/{latest_code}")
        revision_structure, revision_teacher_raw, revision_options = form_structure(page, aliases)
        selected_revision_teacher = revision_teacher_raw
        revision_teacher_change = {
            "attempted": False,
            "selector_available": bool(
                "select" in revision_structure["teacher"]["control_kinds"]
                and revision_structure["teacher"]["editable_selector"]
                and revision_structure["teacher"]["positive_option_count"] >= 2
            ),
        }
        if revision_teacher_change["selector_available"] and not args.no_teacher_change_probe:
            alternate = choose_alternate_teacher(page, revision_teacher_raw, revision_options)
            if alternate is not None:
                revision_teacher_change["attempted"] = True
                revision_teacher_change["selection_changed_in_browser"] = True
                revision_teacher_change["selected_teacher_alias"] = aliases.alias(alternate)
                selected_revision_teacher = alternate

        firewall.arm_probe(
            "revision_latest",
            expected_revision_timestamp=latest_ts,
            expected_selected_teacher=selected_revision_teacher,
        )
        revision_submit = trigger_real_submit(page, firewall)
        if revision_submit.get("submission"):
            submission = revision_submit["submission"]
            revision_submit["historical_datetime_contract_confirmed"] = bool(
                submission.get("datetime_present") and submission.get("datetime_matches_existing")
            )
            revision_submit["teacher_selection_survived_serialization"] = submission.get(
                "selected_teacher_matches_submission"
            )

        # Fresh GET proves an aborted revision did not change semantic form state.
        announce_stage("final_verification")
        firewall.set_phase(Phase.VERIFY)
        goto_get(page, f"/study/tutorials/add/{args.student_uid}/{latest_ts}/{latest_code}")
        after_revision_snapshot = semantic_snapshot(page, fields, latest_type)
        after_revision_digest = semantic_digest(after_revision_snapshot)
        goto_get(page, f"/study/tutorials/summary/{args.student_uid}")
        final_locators = tutorial_locators_from_summary(page, args.student_uid)
        final_locator_digest = locator_digest(final_locators)

        evidence["revision_probe"] = {
            "structure": revision_structure,
            "teacher_change_probe": revision_teacher_change,
            "submission_probe": revision_submit,
            "server_verification": {
                "semantic_state_digest_unchanged": after_revision_digest == source_digest,
                "tutorial_locator_digest_unchanged": final_locator_digest == baseline_digest,
            },
        }
        evidence["network_firewall"] = firewall.summary()
        firewall.set_phase(Phase.CLOSED)
        context.close()
        browser.close()

    announce_stage("evidence_evaluation")
    failures: list[str] = []
    if evidence["network_firewall"]["forwarded_mutations_during_evidence"] != 0:
        failures.append("forwarded_mutation")
    if evidence["network_firewall"]["unexpected_gel_mutations_aborted"] != 0:
        failures.append("unexpected_gel_mutation_attempt")
    if evidence["network_firewall"]["failure_categories"]:
        failures.append("firewall_or_submission_contract_drift")
    if not evidence["revision_probe"]["server_verification"]["semantic_state_digest_unchanged"]:
        failures.append("revision_state_changed")
    if not evidence["revision_probe"]["server_verification"]["tutorial_locator_digest_unchanged"]:
        failures.append("tutorial_locator_set_changed")

    inconclusive = False
    for form_evidence in evidence["new_forms"].values():
        structure = form_evidence["structure"]
        if structure["datetime_present"]:
            failures.append("new_form_datetime_contract_drift")
        if not structure["customdate_present"] or not structure["ttype_present"]:
            failures.append("new_form_required_structure_missing")
        if not form_evidence["server_verification"]["tutorial_locator_digest_unchanged"]:
            failures.append("create_probe_changed_server_state")
        submit_status = form_evidence["submission_probe"]["status"]
        if submit_status != "intercepted_and_aborted":
            inconclusive = True
        elif not form_evidence["submission_probe"].get("historical_datetime_contract_confirmed"):
            failures.append("new_submission_datetime_contract_drift")

    revision_status = evidence["revision_probe"]["submission_probe"]["status"]
    if revision_status != "intercepted_and_aborted":
        inconclusive = True
    elif not evidence["revision_probe"]["submission_probe"].get("historical_datetime_contract_confirmed"):
        failures.append("revision_datetime_contract_drift")

    if failures:
        evidence["result"] = "FAIL"
        evidence["failure_categories"] = sorted(set(failures))
        exit_code = 1
    elif inconclusive:
        evidence["result"] = "INCONCLUSIVE"
        evidence["failure_categories"] = []
        exit_code = 2
    else:
        evidence["result"] = "PASS"
        evidence["failure_categories"] = []
        exit_code = 0

    announce_stage("privacy_validation")
    assert_privacy_safe_evidence(evidence)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(evidence_json_bytes(evidence))
    announce_stage("evidence_written")
    print(f"N2-PW1 zero-write evidence: {evidence['result']}")
    print(f"  evidence file: {output}")
    print(f"  new form types inspected: {len(evidence['new_forms'])}")
    print(f"  expected tutorial mutations aborted: {evidence['network_firewall']['expected_tutorial_mutations_aborted']}")
    print(f"  unexpected GEL mutations aborted: {evidence['network_firewall']['unexpected_gel_mutations_aborted']}")
    print(f"  third-party mutations blocked (non-fatal): {evidence['network_firewall']['third_party_mutations_aborted']}")
    print("  GEL tutorial mutations forwarded during evidence: 0")
    print("  credential values captured by harness: NO")
    return evidence, exit_code


def main() -> int:
    try:
        _evidence, code = run(parse_args())
        return code
    except KeyboardInterrupt:
        print("N2-PW1 cancelled; no tutorial mutation authority was granted.", file=sys.stderr)
        return 130
    except Exception as exc:
        # Do not echo Playwright/request exception text: it may contain live URLs
        # or page-derived data.  The exception class is enough for safe diagnosis.
        print(
            f"N2-PW1 failed closed ({type(exc).__name__}); no raw browser/network data printed.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
