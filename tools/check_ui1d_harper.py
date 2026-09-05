#!/usr/bin/env python3
"""Structural UI1d gate: Rust Harper service, dictionary ownership and UI boundary.

v2 (2026-09-01) — upgraded to assert the inline-highlighting + richer React
interface ported from CELS-Report-Generator:
- engine bumped to harper-core 2.8.0 (organized_lints API);
- HarperFindingDto carries span_start/span_end/rule;
- HarperSuggestionDto carries a human-readable label;
- ui1_harper_check accepts disabled_rules/suppressed_kinds;
- HarperFieldAssistant supports variant="inline" (mirror-div wavy underlines)
  and variant="side-panel" (original behavior preserved for aims);
- finding cards render suggestion labels, Add-to-dictionary, Disable-rule,
  Skip-issue actions;
- session suppression state (harper_disabled_rules, harper_ignored_findings)
  hoisted to App.

All v1 invariants (350ms debounce, requestId/sourceSnapshot race guards,
sourceText !== value, no localStorage, no npm @harper*, sole-writer dictionary,
43-check strict scope) are preserved.
"""
from __future__ import annotations

import json
import re
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
        contract = load("contracts/ui1d_harper.json")
        ui1 = load("contracts/ui1_writer.json")
        ownership = load("contracts/state_ownership.json")
        components = load("contracts/component_boundaries.json")
        gate = load("contracts/release_gate.json")
        plan = load("development_plan.json")
        core_cargo = read("gel-core/Cargo.toml")
        core_lib = read("gel-core/src/lib.rs")
        harper = read("gel-core/src/harper.rs")
        tauri = read("writer-ui/src-tauri/src/lib.rs")
        api = read("writer-ui/src/api.ts")
        types = read("writer-ui/src/types.ts")
        assistant = read("writer-ui/src/components/HarperFieldAssistant.tsx")
        dictionary_ui = read("writer-ui/src/components/HarperDictionaryPanel.tsx")
        foundation = read("writer-ui/src/components/DraftFoundationPanel.tsx")
        type_fields = read("writer-ui/src/components/TutorialTypeFields.tsx")
        app_tsx = read("writer-ui/src/App.tsx")
        css = read("writer-ui/src/styles/app.css")
        behavior = read("gel-core/tests/ui1d_harper.rs")

        # Contract identity (v2 after the inline-highlighting port).
        require(contract["contract_id"] == "ui1d_harper" and contract["contract_version"] == 2, "UI1d contract identity drifted")
        require(contract["status"] == "active_ui1d_pending_strict_acceptance", "UI1d contract status drifted")
        require(contract["engine"] == {
            "crate": "harper-core",
            "version": "2.8.0",
            "dialect": "British",
            "document_parser": "Markdown default parser with the same merged dictionary supplied to the linter",
            "lint_group": "curated",
        }, "Harper engine identity drifted")
        require(set(contract["fields"]) == {"aims", "teacher_comments", "additional_comments"}, "Harper field scope drifted")
        require(set(contract["tauri_commands"]) == {
            "ui1_harper_check", "ui1_harper_dictionary_list", "ui1_harper_dictionary_add", "ui1_harper_dictionary_remove"
        }, "UI1d Tauri command contract drifted")
        require(set(contract["command_parameters"]["ui1_harper_check"]) == {
            "field", "text", "disabled_rules", "suppressed_kinds"
        }, "ui1_harper_check must accept field/text/disabled_rules/suppressed_kinds")
        require(set(contract["dto"]["finding_fields"]) == {
            "lint_kind", "rule", "message", "original_text", "span_start", "span_end", "suggestions"
        }, "HarperFindingDto field set drifted")
        require(set(contract["dto"]["suggestion_fields"]) == {
            "label", "replacement_text"
        }, "HarperSuggestionDto field set drifted")

        # Rust source presence.
        require('harper-core = "=2.8.0"' in core_cargo, "gel-core must pin harper-core 2.8.0")
        require("pub mod harper;" in core_lib and "HarperDictionaryRepository" in core_lib, "Harper module must be exported by gel-core")
        for token in [
            "HarperDictionaryRepository",
            "HARPER_DICTIONARY_SCHEMA_VERSION",
            "HARPER_DICTIONARY_ENV",
            "MutableDictionary::new()",
            "MergedDictionary::new()",
            "FstDictionary::curated()",
            "Dialect::British",
            "Document::new_markdown_default",
            "LintGroup::new_curated",
            "suggestion.apply",
            "future schema",
            "create_new(true)",
            "organized_lints",
            "user_dictionary_covers_span",
            "span_start",
            "span_end",
            "label: suggestion.to_string()",
            "HARPER_VERSION",
        ]:
            require(token in harper, f"Harper Rust implementation missing {token}")

        # Tauri command surface.
        require("HarperDictionaryRepository" in tauri and "writer_operation" in tauri, "Tauri must use the Rust dictionary repository and operation lock")
        for command in contract["tauri_commands"]:
            require(re.search(rf"fn\s+{re.escape(command)}\s*\(", tauri), f"missing Tauri command {command}")
            require(f'"{command}"' in api, f"missing frontend invoke {command}")
        # ui1_harper_check must accept disabled_rules and suppressed_kinds.
        require("disabled_rules" in tauri and "suppressed_kinds" in tauri, "ui1_harper_check Tauri signature must accept disabled_rules/suppressed_kinds")
        require("disabledRules" in api and "suppressedKinds" in api, "harperCheck frontend wrapper must accept disabledRules/suppressedKinds")

        # TypeScript DTO projections.
        require("HarperCheckDto" in types and "HarperFindingDto" in types and "HarperSuggestionDto" in types, "Harper DTO projections missing")
        require("spanStart" in types and "spanEnd" in types, "HarperFindingDto must expose spanStart/spanEnd")
        require("lintKind" in types and "rule" in types, "HarperFindingDto must expose lintKind/rule")
        require("label" in types and "replacementText" in types, "HarperSuggestionDto must expose label/replacementText")

        # UI invariants — the v1 contract required all four of these literals;
        # v2 preserves them (the debounce/stale-safe pattern is unchanged).
        require("requestId" in assistant and "sourceSnapshot" in assistant and "350" in assistant, "Harper UI must be debounced and stale-result-safe")
        require("sourceText !== value" in assistant, "Harper UI must reject stale source snapshots")

        # New v2 UI patterns: inline highlighting (mirror div + textarea) and
        # lint cards with suggestion labels / action buttons.
        require("comment-editor__surface" in assistant and "comment-editor__highlights" in assistant, "Inline HarperFieldAssistant must render the comment-editor surface + mirror div")
        require("comment-editor__highlight--spelling" in assistant and "comment-editor__highlight--grammar" in assistant, "Inline HarperFieldAssistant must distinguish spelling/grammar color variants")
        require("comment-editor__highlight--active" in assistant, "Inline HarperFieldAssistant must support active-highlight coupling")
        require("variant" in assistant and "inline" in assistant and "side-panel" in assistant, "HarperFieldAssistant must support variant=inline|side-panel")
        require("harper-lint" in assistant and "harper-lint__topline" in assistant and "harper-lint__actions" in assistant, "HarperFieldAssistant must render lint cards with topline + actions")
        require("harper-lint__kind" in assistant and "harper-lint__rule" in assistant, "HarperFieldAssistant must render lint kind and rule name")
        require("Add to dictionary" in assistant and "Disable rule" in assistant and "Skip issue" in assistant, "HarperFieldAssistant must offer Add-to-dictionary / Disable-rule / Skip-issue actions")
        require("dictionaryCandidate" in assistant, "HarperFieldAssistant must gate Add-to-dictionary on a single-token candidate")
        require("dictionaryRevision" in assistant, "HarperFieldAssistant must accept a dictionaryRevision prop")
        require("disabledRules" in assistant and "ignoredFindingKeys" in assistant, "HarperFieldAssistant must accept disabledRules/ignoredFindingKeys props")
        require("onDisableRule" in assistant and "onIgnoreFinding" in assistant and "onAddDictionaryTerm" in assistant, "HarperFieldAssistant must accept onDisableRule/onIgnoreFinding/onAddDictionaryTerm callbacks")

        # Typed-edit acceptance: the structural gate originally required
        # set_aims and set_additional_comments to appear in TutorialTypeFields;
        # v2 keeps the same assertion.
        require("set_aims" in type_fields and "set_additional_comments" in type_fields, "Aims/Final comments must accept only typed semantic edits")

        # DraftFoundationPanel must still wire both Harper components and pass
        # through the session suppression state.
        require("HarperFieldAssistant" in foundation and "HarperDictionaryPanel" in foundation, "Writer editor must wire Harper checking and dictionary UI")
        require("disabledHarperRules" in foundation and "ignoredHarperFindings" in foundation, "DraftFoundationPanel must accept disabledHarperRules/ignoredHarperFindings")
        require("onDisableHarperRule" in foundation and "onIgnoreHarperFinding" in foundation, "DraftFoundationPanel must accept onDisableHarperRule/onIgnoreHarperFinding")
        require("variant=\"inline\"" in foundation, "DraftFoundationPanel must use variant=inline for at least one Harper-aware field")

        # App.tsx must own the session suppression state (hoisted).
        require("disabledHarperRules" in app_tsx and "ignoredHarperFindings" in app_tsx, "App must own disabledHarperRules/ignoredHarperFindings session state")
        require("handleDisableHarperRule" in app_tsx and "handleIgnoreHarperFinding" in app_tsx, "App must expose handleDisableHarperRule/handleIgnoreHarperFinding")
        require("handleAddHarperDictionaryTerm" in app_tsx and "harperDictionaryRevision" in app_tsx, "App must own harperDictionaryRevision and handleAddHarperDictionaryTerm")

        # Dictionary panel still uses the same Tauri commands.
        require("harperDictionaryAdd" in dictionary_ui and "harperDictionaryRemove" in dictionary_ui and "harperDictionaryList" in dictionary_ui, "dictionary UI operations missing")
        require("onMutation" in dictionary_ui, "HarperDictionaryPanel must accept an onMutation callback")

        # CSS must define the inline highlight styles + lint card styles.
        require("comment-editor__surface" in css and "comment-editor__highlights" in css, "CSS must define the comment-editor surface + mirror div")
        require("comment-editor__highlight--spelling" in css and "comment-editor__highlight--grammar" in css, "CSS must define spelling/grammar color variants")
        require("comment-editor__highlight--active" in css, "CSS must define the active highlight variant")
        require("wavy" in css, "CSS must use wavy underline decoration for inline highlights")
        require("harper-lint" in css and "harper-lint--active" in css, "CSS must define harper-lint card and active variant")
        require("harper-lint__actions" in css and "harper-lint__suggestions" in css, "CSS must define harper-lint actions and suggestions rows")

        # No browser persistence; no npm @harper.
        require("localStorage" not in assistant + dictionary_ui and "sessionStorage" not in assistant + dictionary_ui, "Harper UI must not persist through browser storage")
        require("@harper" not in read("writer-ui/package.json").lower(), "Harper must be integrated in Rust rather than the React dependency graph")

        # State-ownership: dictionary is canonical, check result is ephemeral,
        # and v2 adds two new ephemeral session-only classes.
        states = {item["id"]: item for item in ownership["state_classes"]}
        dictionary = states["harper_user_dictionary"]
        result = states["harper_check_result"]
        require(dictionary["canonical"] is True and dictionary["permitted_writers"] == ["harper_dictionary_repository"], "dictionary ownership contract drifted")
        require(result["canonical"] is False and result["permitted_writers"] == ["writer_harper_service"], "check-result ownership contract drifted")
        require("exact source snapshot" in result["retention"].lower(), "check result must retain source-snapshot semantics")
        # The two new session-only state classes must exist.
        for session_state in ("harper_disabled_rules", "harper_ignored_findings"):
            require(session_state in states, f"state_ownership must define {session_state} as an ephemeral session class")
            session_obj = states[session_state]
            require(session_obj["canonical"] is False, f"{session_state} must be non-canonical session state")
            require(session_obj["class"] == "ephemeral_runtime_derived", f"{session_state} must be ephemeral_runtime_derived")

        # Component boundaries.
        component_ids = {item["id"] for item in components["components"]}
        require({"writer_harper_service", "harper_dictionary_repository"} <= component_ids, "UI1d components must be active")
        require("writer_harper_service" not in components.get("planned_not_active", []), "Harper service remains incorrectly planned")
        require("harper_dictionary_repository" not in components.get("planned_not_active", []), "dictionary repository remains incorrectly planned")
        require("2.8.0" in json.dumps(components), "component boundaries must reference harper-core 2.8.0")

        # Release gate scope.
        ui1d_scope = gate["scopes"]["ui1d"]["checks"]
        require(len(ui1d_scope) == 43, "UI1d scope must contain 43 checks")
        require(ui1d_scope[:41] == gate["scopes"]["ui1c5"]["checks"], "UI1d must preserve UI1c5 check ordering as prefix")
        require(ui1d_scope[-2:] == ["ui1d_harper", "ui1d_harper_behavior"], "UI1d dedicated checks must be appended")
        require(gate["current_release_scope"] == "w2", "current release scope must be w2")

        # Development plan + UI1 writer contract status.
        ui1_phase = next(item for item in plan["phases"] if item["id"] == "UI1")
        require(ui1_phase["status"] in {"ui1e_implemented_pending_strict_acceptance", "complete_strictly_accepted"}, "development plan UI1e status drifted")
        require(ui1_phase["ui1d"]["release_scope"] == "ui1d", "development plan UI1d scope drifted")
        require(ui1_phase["ui1d"]["status"] == "complete_strictly_accepted", "development plan UI1d status drifted")
        require(ui1["contract_version"] == 14 and ui1["status"] in {"active_w2_pending_strict_acceptance", "complete_strictly_accepted"}, "UI1 Writer contract must be v14/W2-active")

        # Behavioral tests — the original six v1 tests must still exist, plus
        # the v2 additions (span coordinates, suggestion labels, rule names,
        # user-dictionary cover-span, empty-text short-circuit, disabled-rules
        # suppression, suppressed-kinds filtering).
        for name in [
            "british_engine_returns_complete_field_replacement_for_color",
            "user_dictionary_word_is_used_by_document_and_linter",
            "dictionary_mutations_are_case_insensitive_and_persistent",
            "legacy_dictionary_is_migrated_to_schema_v1",
            "future_dictionary_schema_fails_closed_and_does_not_downgrade",
            "unsupported_field_fails_closed",
            "findings_carry_span_coordinates_for_inline_highlight",
            "suggestions_carry_human_readable_labels",
            "findings_carry_stable_rule_names_for_disable_action",
            "user_dictionary_covers_subspan_for_mixed_alphanumeric_term",
            "empty_text_short_circuits_to_no_findings",
            "disabled_rules_are_suppressed_for_session",
            "suppressed_kinds_are_filtered",
        ]:
            require(re.search(rf"fn\s+{re.escape(name)}\s*\(", behavior), f"UI1d behavioral test missing {name}")

        print("check:ui1d-harper PASS — Rust Harper 2.8.0/British service + span-aware DTO + inline-highlight UI + sole-writer dictionary + stale-result-safe UI + 43-check strict scope")
        return 0
    except (CheckError, OSError, json.JSONDecodeError, StopIteration) as exc:
        print(f"check:ui1d-harper FAIL — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
