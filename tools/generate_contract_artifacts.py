#!/usr/bin/env python3
"""Generate Rust constants and human-readable contract docs from canonical JSON contracts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
RUST_FIELDS = ROOT / "gel-core" / "src" / "gel_fields.rs"
GENERATED_DIR = ROOT / "docs" / "generated"
GENERATED_DOC = GENERATED_DIR / "GEL_TUTORIAL_CONTRACTS.md"
GENERATED_INDEX = GENERATED_DIR / "CONTRACT_INDEX.md"

CONTRACT_FILES = sorted(path.name for path in CONTRACTS.glob("*.json"))


def load(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def rust_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def rust_string_slice(values: list[str], indent: str = "        ") -> str:
    """Render contract value arrays in the same stable shape rustfmt uses here.

    Short arrays remain inline. Domains containing long labels use one item per
    line; compact CEFR-like domains use rustfmt-style greedy mixed packing up to
    the default 100-column width. This keeps the generated Rust itself canonical
    under `cargo fmt --check`.
    """
    rendered = [rust_string(value) for value in values]
    inline = "&[" + ", ".join(rendered) + "]"
    if len(indent) + len("allowed_values: ") + len(inline) <= 100:
        return inline

    item_indent = indent + "    "
    if any(len(value) > 20 for value in rendered):
        inner = "\n".join(f"{item_indent}{value}," for value in rendered)
        return "&[\n" + inner + f"\n{indent}]"

    lines: list[str] = []
    current = item_indent
    for value in rendered:
        token = f"{value},"
        candidate = token if current == item_indent else f" {token}"
        if len(current) + len(candidate) > 100 and current != item_indent:
            lines.append(current)
            current = item_indent + token
        else:
            current += candidate
    if current != item_indent:
        lines.append(current)
    return "&[\n" + "\n".join(lines) + f"\n{indent}]"


def render_rust(fields: dict[str, Any], types: dict[str, Any], new_form: dict[str, Any]) -> str:
    lines = [
        "//! @generated from canonical JSON contracts by tools/generate_contract_artifacts.py.",
        "//! DO NOT EDIT BY HAND. Run `python tools/generate_contract_artifacts.py`.",
        "//!",
        "//! Opaque GEL field IDs belong here rather than in archive/domain/UI layers.",
        "",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub enum GelControlKind {",
        "    Hidden,",
        "    Text,",
        "    Checkbox,",
        "    Select,",
        "    Textarea,",
        "    RadioGroup,",
        "    ContentEditablePlusHidden,",
        "}",
        "",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub enum GelValueValidationRule {",
        "    None,",
        "    PositiveI64,",
        "    PositiveI64Option,",
        "    TutorialTypeCode,",
        "    GelDate,",
        "    CheckboxBoolean,",
        "}",
        "",
        "#[derive(Debug, Clone, Copy)]",
        "pub struct EditControlSpec {",
        "    pub semantic_name: &'static str,",
        "    pub field: &'static str,",
        "    pub kind: GelControlKind,",
        "    pub required: bool,",
        "    pub allow_unset: bool,",
        "    pub placeholder: Option<&'static str>,",
        "    pub allowed_values: &'static [&'static str],",
        "    pub validation_rule: GelValueValidationRule,",
        "    pub editor_id: Option<&'static str>,",
        "}",
        "",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub enum SkillDimension {",
        "    Speaking,",
        "    UseOfEnglish,",
        "    Writing,",
        "    Listening,",
        "    Reading,",
        "}",
        "",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub enum SkillPhase {",
        "    Initial,",
        "    Current,",
        "}",
        "",
        "#[derive(Debug, Clone, Copy, PartialEq, Eq)]",
        "pub struct LevelFieldSpec {",
        "    pub semantic_name: &'static str,",
        "    pub field: &'static str,",
        "    pub gel_field_id: u16,",
        "    pub dimension: SkillDimension,",
        "    pub phase: SkillPhase,",
        "}",
        "",
    ]

    for item in types["types"]:
        const = f"TTYPE_{item['semantic'].upper()}"
        lines.append(f"pub const {const}: &str = {rust_string(item['ttype'])};")
    lines.append("")

    for field in fields["fields"]:
        lines.append(f"pub const {field['rust_const']}: &str = {rust_string(field['gel_name'])};")
        if field.get("rust_editor_const"):
            lines.append(
                f"pub const {field['rust_editor_const']}: &str = {rust_string(field['editor_id'])};"
            )
    lines.append("")

    placeholders = fields["placeholders"]
    lines.extend(
        [
            f"pub const SKILL_PLACEHOLDER: &str = {rust_string(placeholders['skill'])};",
            f"pub const OVERALL_PLACEHOLDER: &str = {rust_string(placeholders['overall'])};",
            f"pub const EXAM_PLACEHOLDER: &str = {rust_string(placeholders['exam'])};",
            "",
        ]
    )

    for field in fields["fields"]:
        if field.get("rust_max_const"):
            lines.append(f"pub const {field['rust_max_const']}: usize = {int(field['max_chars'])};")
    lines.append("")

    lines.append("pub const SUMMARY_ACTIONS: &str = \"Actions\";")
    rows = ",\n    ".join(rust_string(row) for row in fields["summary_rows_in_observed_order"])
    lines.append("pub const SUMMARY_ROWS_OBSERVED: &[&str] = &[")
    lines.append(f"    {rows},")
    lines.append("];\n")

    kind_map = {
        "hidden": "GelControlKind::Hidden",
        "text": "GelControlKind::Text",
        "checkbox": "GelControlKind::Checkbox",
        "select": "GelControlKind::Select",
        "textarea": "GelControlKind::Textarea",
        "radio_group": "GelControlKind::RadioGroup",
        "contenteditable_plus_hidden": "GelControlKind::ContentEditablePlusHidden",
    }
    rule_map = {
        "none": "GelValueValidationRule::None",
        "positive_i64": "GelValueValidationRule::PositiveI64",
        "positive_i64_option": "GelValueValidationRule::PositiveI64Option",
        "tutorial_type_code": "GelValueValidationRule::TutorialTypeCode",
        "gel_date": "GelValueValidationRule::GelDate",
        "checkbox_boolean": "GelValueValidationRule::CheckboxBoolean",
    }
    value_domains = fields.get("value_domains", {})
    edit_fields = []
    for field in fields["fields"]:
        roles = set(field.get("source_roles", []))
        if not ({"edit_form", "edit_form_contenteditable"} & roles):
            continue
        edit_fields.append(field)

    lines.append("/// Contract-derived historical edit-form validation metadata.")
    lines.append("pub const EDIT_CONTROL_SPECS: &[EditControlSpec] = &[")
    for field in edit_fields:
        placeholder = "None"
        if field.get("placeholder_ref"):
            placeholder = f"Some({rust_string(placeholders[field['placeholder_ref']])})"
        allowed = []
        if field.get("value_domain_ref"):
            allowed.extend(value_domains[field["value_domain_ref"]])
        if field.get("values"):
            allowed.extend(field["values"].keys())
        allowed_expr = rust_string_slice(allowed)
        editor_id = f"Some({rust_string(field['editor_id'])})" if field.get("editor_id") else "None"
        lines.extend([
            "    EditControlSpec {",
            f"        semantic_name: {rust_string(field['semantic_name'])},",
            f"        field: {field['rust_const']},",
            f"        kind: {kind_map[field['control_kind']]},",
            f"        required: {'true' if field.get('required_control') else 'false'},",
            f"        allow_unset: {'true' if field.get('allow_unset') else 'false'},",
            f"        placeholder: {placeholder},",
            f"        allowed_values: {allowed_expr},",
            f"        validation_rule: {rule_map[field.get('validation_rule', 'none')]},",
            f"        editor_id: {editor_id},",
            "    },",
        ])
    lines.append("];\n")

    lines.append("pub fn edit_control_spec(field: &str) -> Option<&'static EditControlSpec> {")
    lines.append("    EDIT_CONTROL_SPECS.iter().find(|spec| spec.field == field)")
    lines.append("}\n")

    forbidden = set(new_form["form_contract"]["forbidden_fields"])
    overrides = new_form["form_contract"].get("overrides", {})
    new_fields = [field for field in edit_fields if field["gel_name"] not in forbidden]
    lines.append("/// Contract-derived New-tutorial form validation metadata.")
    lines.append("/// New remains structurally distinct from Revision: datetime is forbidden and tid is hidden.")
    lines.append("pub const NEW_CONTROL_SPECS: &[EditControlSpec] = &[")
    for field in new_fields:
        override = overrides.get(field["gel_name"], {})
        placeholder = "None"
        if field.get("placeholder_ref"):
            placeholder = f"Some({rust_string(placeholders[field['placeholder_ref']])})"
        allowed = []
        if field.get("value_domain_ref"):
            allowed.extend(value_domains[field["value_domain_ref"]])
        if field.get("values"):
            allowed.extend(field["values"].keys())
        allowed_expr = rust_string_slice(allowed)
        editor_id = f"Some({rust_string(field['editor_id'])})" if field.get("editor_id") else "None"
        control_kind = override.get("control_kind", field["control_kind"])
        validation_rule = override.get("validation_rule", field.get("validation_rule", "none"))
        lines.extend([
            "    EditControlSpec {",
            f"        semantic_name: {rust_string(field['semantic_name'])},",
            f"        field: {field['rust_const']},",
            f"        kind: {kind_map[control_kind]},",
            f"        required: {'true' if field.get('required_control') else 'false'},",
            f"        allow_unset: {'true' if field.get('allow_unset') else 'false'},",
            f"        placeholder: {placeholder},",
            f"        allowed_values: {allowed_expr},",
            f"        validation_rule: {rule_map[validation_rule]},",
            f"        editor_id: {editor_id},",
            "    },",
        ])
    lines.append("];\n")
    lines.append("pub fn new_control_spec(field: &str) -> Option<&'static EditControlSpec> {")
    lines.append("    NEW_CONTROL_SPECS.iter().find(|spec| spec.field == field)")
    lines.append("}\n")
    forbidden_consts = [next(field["rust_const"] for field in fields["fields"] if field["gel_name"] == name) for name in new_form["form_contract"]["forbidden_fields"]]
    if len(forbidden_consts) == 1:
        lines.append(f"pub const NEW_FORBIDDEN_FIELDS: &[&str] = &[{forbidden_consts[0]}];\n")
    else:
        lines.append("pub const NEW_FORBIDDEN_FIELDS: &[&str] = &[")
        for const in forbidden_consts:
            lines.append(f"    {const},")
        lines.append("];\n")
    lines.append(f"pub const NEW_FORM_ACTION_PATH: &str = {rust_string(new_form['form_contract']['action_path'])};")
    lines.append(f"pub const NEW_FORM_METHOD: &str = {rust_string(new_form['form_contract']['method'])};")
    lines.append("")

    dimension_map = {
        "speaking": "SkillDimension::Speaking",
        "use_of_english": "SkillDimension::UseOfEnglish",
        "writing": "SkillDimension::Writing",
        "listening": "SkillDimension::Listening",
        "reading": "SkillDimension::Reading",
    }
    phase_map = {"initial": "SkillPhase::Initial", "current": "SkillPhase::Current"}
    level_fields = [field for field in fields["fields"] if field.get("semantic_level_role")]
    lines.append("/// Canonical field-identity map for CEFR level controls. Semantic provenance")
    lines.append("/// is determined by field ID/role only, never by equality of field values.")
    lines.append("pub const LEVEL_FIELD_SPECS: &[LevelFieldSpec] = &[")
    for field in level_fields:
        role = field["semantic_level_role"]
        lines.extend([
            "    LevelFieldSpec {",
            f"        semantic_name: {rust_string(field['semantic_name'])},",
            f"        field: {field['rust_const']},",
            f"        gel_field_id: {int(field['gel_field_id'])},",
            f"        dimension: {dimension_map[role['dimension']]},",
            f"        phase: {phase_map[role['phase']]},",
            "    },",
        ])
    lines.append("];\n")
    lines.append("pub fn level_field_spec(field: &str) -> Option<&'static LevelFieldSpec> {")
    lines.append("    LEVEL_FIELD_SPECS.iter().find(|spec| spec.field == field)")
    lines.append("}\n")

    lines.append("/// Contract-derived applicability for GEL form controls.")
    lines.append("pub fn field_applies_to(field: &str, ttype: &str) -> bool {")
    lines.append("    match field {")
    for field in fields["fields"]:
        ttypes = []
        for semantic_type in field["applies_to"]:
            match = next(x for x in types["types"] if x["semantic"] == semantic_type)
            ttypes.append(match["ttype"])
        pattern = " | ".join(rust_string(x) for x in ttypes)
        lines.append(f"        {field['rust_const']} => matches!(ttype, {pattern}),")
    lines.append("        _ => false,")
    lines.append("    }")
    lines.append("}")
    lines.append("")
    return "\n".join(lines)

def render_doc(
    fields: dict[str, Any],
    types: dict[str, Any],
    app: dict[str, Any],
    anomalies: dict[str, Any],
    evidence: dict[str, Any],
    semantics: dict[str, Any],
    reconciliation: dict[str, Any],
    round_trip: dict[str, Any],
    archive_schema: dict[str, Any],
    archive_repository: dict[str, Any],
    gel_session: dict[str, Any],
    n2_pw: dict[str, Any],
    n2a: dict[str, Any],
    new_form: dict[str, Any],
) -> str:
    out = [
        "# GEL tutorial contracts (generated)",
        "",
        "> Generated from `contracts/*.json`. Do not edit this file directly.",
        "",
        "## Tutorial types",
        "",
        "| Semantic type | GEL `ttype` | Display |",
        "| --- | ---: | --- |",
    ]
    for item in types["types"]:
        out.append(f"| `{item['semantic']}` | `{item['ttype']}` | {item['display']} |")

    out.extend([
        "",
        "Canonical identity is `tutorial_id` from the tutorial-list API. `(student_uid, tutorial_ts, tutorial_type)` is only a locator/reconciliation key.",
        "",
        "## Form fields",
        "",
        "| Semantic field | GEL field | Control | Applies to | Required edit control | Unset allowed | Validation | Summary label |",
        "| --- | --- | --- | --- | ---: | ---: | --- | --- |",
    ])
    for field in fields["fields"]:
        summary = field.get("summary_label") or "—"
        applies = ", ".join(field["applies_to"])
        roles = set(field.get("source_roles", []))
        is_edit = bool({"edit_form", "edit_form_contenteditable"} & roles)
        required = "yes" if is_edit and field.get("required_control") else ("no" if is_edit else "—")
        allow_unset = "yes" if is_edit and field.get("allow_unset") else ("no" if is_edit else "—")
        validation = field.get("validation_rule", "—") if is_edit else "—"
        if field.get("value_domain_ref"):
            validation = f"{validation}; domain={field['value_domain_ref']}"
        out.append(
            f"| `{field['semantic_name']}` | `{field['gel_name']}` | `{field['control_kind']}` | {applies} | {required} | {allow_unset} | `{validation}` | {summary} |"
        )

    out.extend(["", "## Semantic applicability", ""])
    for key in ["common", "initial", "standard", "final"]:
        vals = ", ".join(f"`{v}`" for v in app["semantic_fields"][key])
        out.append(f"**{key.title()}:** {vals}")
        out.append("")

    out.extend(["## Active source anomalies", ""])
    for anomaly in anomalies["anomalies"]:
        out.append(f"### {anomaly['id']} — `{anomaly['field']}`")
        out.append("")
        out.append(anomaly["observation"])
        out.append("")
        out.append(f"**Authority rule:** {anomaly['authority_rule']}")
        out.append("")
        if anomaly.get("failure_rule"):
            out.append(f"**Failure rule:** {anomaly['failure_rule']}")
            out.append("")

    out.extend(["## Semantic form authority", ""])
    out.append("Draft origins are explicit: `revision` requires a historical source identity; `new` may retain an optional prepopulation source but is not a revision identity.")
    out.append("")
    out.append("Editable source-of-truth rules:")
    out.append("")
    for name, rule in semantics["editable_source_of_truth"].items():
        out.append(f"- `{name}`: `{rule}`")
    out.append("")
    out.append("Provenance-only values are diagnostics/fidelity data and must not drive POST payload values:")
    out.append("")
    for name, rule in semantics["provenance_only"].items():
        out.append(f"- `{name}`: {rule}")
    out.append("")
    out.append(f"Aims POST encoding: `{semantics['post_serialization']['aims_text_encoding']}`.")
    out.append("")
    out.append(semantics["revision_state_authority"]["rule"])
    out.append("")

    out.extend(["## Collision authority", ""])
    out.append(reconciliation["identity_rule"])
    out.append("")
    out.append(reconciliation["association_rule"])
    out.append("")
    for name, rule in reconciliation["collision_classes"].items():
        out.append(f"### `{name}`")
        out.append("")
        out.append(rule["definition"])
        out.append("")
        out.append(f"Per-ID association: **{rule['per_id_association']}**.")
        out.append("")
        out.append(f"Revision rule: {rule['revision_rule']}")
        out.append("")
    out.append(f"Timestamp-route rule: {reconciliation['timestamp_route_rule']}")
    out.append("")
    out.append(f"Legacy archive rule: {reconciliation['legacy_archive_rule']}")
    out.append("")

    out.extend(["## Offline POST round trip", ""])
    out.append(round_trip["exact_payload_rule"])
    out.append("")
    suite = round_trip["fixture_suite"]
    out.append(
        f"Strict C4 evidence requires {suite['required_fixture_count']} revision fixtures, "
        f"including {suite['required_final_fixture_count']} Final fixtures and "
        f"{suite['required_absent_source_discrepancy_count']} governed absent source discrepancies."
    )
    out.append("")
    out.append(f"Historical absent rule: {round_trip['historical_anomaly_rule']}")
    out.append("")
    out.append(f"Mutation isolation: {round_trip['mutation_isolation']['rule']}")
    out.append("")
    out.append(f"Network rule: {round_trip['network_rule']}")
    out.append("")

    out.extend(["## Archive schema v2", ""])
    out.append(archive_schema["authority_rule"])
    out.append("")
    out.append(f"Executable schema: `{archive_schema['executable_schema']}`; schema version: **{archive_schema['schema_version']}**.")
    out.append("")
    out.append("Key executable invariants:")
    out.append("")
    out.append("- `tutorial_identities` owns canonical API tutorial IDs; `tutorial_source_states` owns candidate historical states; `tutorial_state_associations` carries governed authority.")
    out.append("- Blocked authority statuses persist no `source_state_id`, so ambiguous collision candidates cannot be falsely attributed to an API ID.")
    out.append("- `students.class_id` is replaced by `class_memberships`.")
    out.append("- `source_present`, `first_seen`, and `last_seen` preserve history while representing current-source presence; `presence_checked_run_id` may invalidate presence only against a completed sync run.")
    out.append("- Foreign keys are mandatory and `INSERT OR REPLACE` is forbidden in favor of explicit `ON CONFLICT` UPSERTs.")
    out.append("- v2 stores no legacy `raw_json` or email field; migration extracts only minimal field-presence provenance.")
    out.append("")
    out.append(f"Runtime cutover: `{archive_schema['current_runtime_cutover']}`.")
    out.append("")

    out.extend(["## Rust archive repository (D2)", ""])
    out.append(archive_repository["evaluation"]["summary"])
    out.append("")
    out.append(f"Public read surface: `{archive_repository['public_read_surface']['module']}` using `{archive_repository['public_read_surface']['open_mode']}`.")
    out.append("")
    out.append(f"Archive-sync write surface: `{archive_repository['archive_sync_write_surface']['module']}`; visibility `{archive_repository['archive_sync_write_surface']['visibility']}`; runtime status `{archive_repository['archive_sync_write_surface']['runtime_status']}`.")
    out.append("")
    out.append(f"Transaction rule: {archive_repository['transaction_semantics']['materialization']}")
    out.append("")
    out.append(f"Full invalidation: {archive_repository['scope_invalidation']['full']}")
    out.append("")
    out.append(f"Targeted invalidation: {archive_repository['scope_invalidation']['targeted']}")
    out.append("")
    out.append(f"Production writer after A2: `{archive_repository['ownership']['production_canonical_writer_after_A2']}` via `{archive_repository['ownership']['production_orchestrator']}`; Python v4.9 status is `{archive_repository['ownership']['python_v49_status_after_A2']}`.")
    out.append("")

    out.extend(["## Rust GEL read-only session (N1)", ""])
    out.append(gel_session["evaluation"]["summary"])
    out.append("")
    out.append(
        f"Canonical origins: `{gel_session['origins']['api_base']}` and "
        f"`{gel_session['origins']['learn2_base']}`."
    )
    out.append("")
    out.append(
        f"Authentication uses exactly {gel_session['authentication']['login_post_count']} login POSTs; "
        f"credential retention is `{gel_session['authentication']['credential_retention']}`."
    )
    out.append("")
    out.append("Fixed read surface:")
    out.append("")
    for operation in gel_session["read_surface"]:
        out.append(
            f"- `{operation['method']} {operation['path_template']}` -> `{operation['response']}`"
        )
    out.append("")
    out.append(gel_session["network_authority"]["rule"])
    out.append("")
    out.append(gel_session["privacy"]["rule"])
    out.append("")
    out.append(
        "Live acceptance is deliberately manual: the automated release gate performs no credentialed network access."
    )
    out.append("")

    out.extend(["## N2-PW1 zero-write browser evidence", ""])
    out.append(n2_pw["role"])
    out.append("")
    out.append(
        "The mutation firewall is installed before login; the login request body/headers are never inspected. "
        "During evidence collection, the authentic tutorial process POST is reduced to allowlisted structural "
        "relationships and always aborted before reaching GEL."
    )
    out.append("")
    out.append(
        f"Prepopulation source: `{n2_pw['prepopulation']['source']}` "
        f"(`{n2_pw['prepopulation']['source_status']}`)."
    )
    out.append("")
    out.append(
        "Teacher-selection client serialization may be observed, but server acceptance/authorization of "
        "reassignment remains explicitly unresolved and PW1 cannot enable production reassignment."
    )
    out.append("")
    out.append(
        f"Offline release check: `{n2_pw['acceptance']['offline_release_check']}`. "
        "The release gate never executes credentialed Playwright network activity."
    )
    out.append("")

    out.extend(["## N2a semantic / POST authority", ""])
    out.append(n2a["scope"])
    out.append("")
    out.append("Origin rules:")
    out.append("")
    out.append(f"- New datetime: `{n2a['origin_authority']['new']['datetime_post']}`; teacher: `{n2a['origin_authority']['new']['teacher']}`.")
    out.append(f"- Revision datetime: `{n2a['origin_authority']['revision']['datetime_post']}`; teacher: `{n2a['origin_authority']['revision']['teacher']}`.")
    out.append("")
    out.append(n2a["type_safety"]["rule"])
    out.append("")
    out.append(f"Network write authority: `{n2a['network_write_authority']}`.")
    out.append("")

    out.extend(["## N2b New-tutorial form authority", ""])
    out.append(new_form["role"])
    out.append("")
    out.append(f"Fixed acquisition: `{new_form['acquisition']['method']} {new_form['acquisition']['path_template']}`.")
    out.append("")
    out.append(
        f"New form source contract: `{new_form['form_contract']['method']} {new_form['form_contract']['action_path']}`; "
        f"forbidden fields: `{', '.join(new_form['form_contract']['forbidden_fields'])}`."
    )
    out.append("")
    out.append(
        "Teacher authority is a validated hidden `tid` supplied by the fetched New form; "
        "no public teacher mutation/constructor is authorized."
    )
    out.append("")
    out.append(f"Network write authority: `{new_form['network_write_authority']}`.")
    out.append("")

    out.extend(["## Frozen evidence", ""])
    for obs in evidence["observations"]:
        out.append(f"- **{obs['id']} ({obs['status']}):** {obs['description']}")
    nxt = evidence["expected_next_strict_fixture_baseline"]
    out.extend([
        "",
        "### Strict private-fixture baseline",
        "",
        f"Status: **{nxt['status']}**.",
        "",
        nxt["reason"],
        "",
        f"Expected: {nxt['fixture_count']} fixtures, {nxt['field_count']} fields, {nxt['expected_ok']} OK, {nxt['expected_mismatch']} known mismatches, {nxt['expected_unavailable']} unavailable.",
        "",
    ])
    return "\n".join(out)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_index() -> str:
    rows = []
    for name in CONTRACT_FILES:
        p = CONTRACTS / name
        rows.append(f"| `{name}` | `{sha256(p)}` |")
    schema_path = ROOT / "schema" / "archive_v2.sql"
    return "\n".join([
        "# Contract index (generated)",
        "",
        "> Generated by `tools/generate_contract_artifacts.py`.",
        "",
        "| Canonical contract | SHA-256 |",
        "| --- | --- |",
        *rows,
        f"| `schema/archive_v2.sql` | `{sha256(schema_path)}` |",
        "",
        "Generated artifacts:",
        "",
        "- `gel-core/src/gel_fields.rs`",
        "- `docs/generated/GEL_TUTORIAL_CONTRACTS.md`",
        "- `docs/generated/CONTRACT_INDEX.md`",
        "",
    ])


def write_or_check(path: Path, content: str, check: bool) -> bool:
    content = content.rstrip() + "\n"
    if check:
        if not path.exists():
            print(f"STALE: missing generated artifact {path.relative_to(ROOT)}")
            return False
        current = path.read_text(encoding="utf-8")
        if current != content:
            print(f"STALE: {path.relative_to(ROOT)} differs from canonical contracts")
            return False
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"generated {path.relative_to(ROOT)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated artifacts are stale")
    args = parser.parse_args()

    fields = load("gel_tutorial_fields.json")
    types = load("tutorial_types.json")
    app = load("tutorial_form_applicability.json")
    anomalies = load("known_source_anomalies.json")
    evidence = load("evidence_baseline.json")
    semantics = load("tutorial_form_semantics.json")
    reconciliation = load("reconciliation_authority.json")
    round_trip = load("offline_post_round_trip.json")
    archive_schema = load("archive_schema_v2.json")
    archive_repository = load("archive_repository.json")
    gel_session = load("gel_read_only_session.json")
    n2_pw = load("n2_playwright_zero_write_evidence.json")
    n2a = load("n2a_semantic_post_authority.json")
    new_form = load("new_tutorial_form.json")

    ok = True
    ok &= write_or_check(RUST_FIELDS, render_rust(fields, types, new_form), args.check)
    ok &= write_or_check(
        GENERATED_DOC,
        render_doc(
            fields,
            types,
            app,
            anomalies,
            evidence,
            semantics,
            reconciliation,
            round_trip,
            archive_schema,
            archive_repository,
            gel_session,
            n2_pw,
            n2a,
            new_form,
        ),
        args.check,
    )
    ok &= write_or_check(GENERATED_INDEX, render_index(), args.check)
    if args.check and ok:
        print("generated contract artifacts: CURRENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
