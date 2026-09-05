use crate::edit_form_validation::validate_edit_form;
use crate::gel_fields;
use crate::models::{EditFormState, FormControl};
use crate::parse_edit_form;
use anyhow::{bail, Context, Result};
use chrono::NaiveDate;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ComparisonStatus {
    Ok,
    Mismatch,
    Unavailable,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FieldComparison {
    pub fixture: String,
    pub tutorial_type: String,
    pub field: String,
    pub archive_value: String,
    pub edit_value: Option<String>,
    pub status: ComparisonStatus,
    pub archive_source: String,
    pub edit_source: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct FixtureSummary {
    pub fixture: String,
    pub tutorial_type: String,
    pub total: usize,
    pub ok: usize,
    pub mismatch: usize,
    pub unavailable: usize,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct FixtureComparisonReport {
    pub expected_dir: String,
    pub raw_dir: String,
    pub fixture_count: usize,
    pub field_count: usize,
    pub ok_count: usize,
    pub mismatch_count: usize,
    pub unavailable_count: usize,
    pub fixtures: Vec<FixtureSummary>,
    pub comparisons: Vec<FieldComparison>,
}

#[derive(Debug, Clone)]
struct ExpectedFixture {
    label: String,
    ttype: String,
    db: BTreeMap<String, Value>,
}

#[derive(Debug, Clone)]
struct EditValue {
    present: bool,
    value: String,
    source: String,
}

impl EditValue {
    fn missing(source: impl Into<String>) -> Self {
        Self {
            present: false,
            value: String::new(),
            source: source.into(),
        }
    }

    fn present(value: impl Into<String>, source: impl Into<String>) -> Self {
        Self {
            present: true,
            value: value.into(),
            source: source.into(),
        }
    }
}

#[derive(Debug, Clone, Copy)]
enum CompareKind {
    Text,
    Level,
    Integer,
    Bool,
    Date,
    Assessment,
}

pub fn compare_edit_fixture_dirs(
    expected_dir: &Path,
    raw_dir: &Path,
) -> Result<FixtureComparisonReport> {
    if !expected_dir.is_dir() {
        bail!(
            "expected fixture directory does not exist: {}",
            expected_dir.display()
        );
    }
    if !raw_dir.is_dir() {
        bail!(
            "raw edit-form directory does not exist: {}",
            raw_dir.display()
        );
    }

    let mut expected_files: Vec<PathBuf> = fs::read_dir(expected_dir)
        .with_context(|| format!("read expected fixture directory {}", expected_dir.display()))?
        .filter_map(|entry| entry.ok().map(|e| e.path()))
        .filter(|path| path.extension().and_then(|v| v.to_str()) == Some("json"))
        .collect();
    expected_files.sort();

    if expected_files.is_empty() {
        bail!("no .json edit fixtures found in {}", expected_dir.display());
    }

    let mut report = FixtureComparisonReport {
        expected_dir: expected_dir.display().to_string(),
        raw_dir: raw_dir.display().to_string(),
        ..Default::default()
    };

    for expected_path in expected_files {
        let expected = load_expected_fixture(&expected_path)?;
        let raw_path = raw_dir.join(format!("{}.html", expected.label));
        let html = fs::read_to_string(&raw_path)
            .with_context(|| format!("read raw edit fixture {}", raw_path.display()))?;
        let edit = parse_edit_form(&html)
            .with_context(|| format!("parse raw edit fixture {}", raw_path.display()))?;
        let validated = validate_edit_form(&edit)
            .with_context(|| format!("validate raw edit fixture {}", raw_path.display()))?;
        if validated.tutorial_type_raw != expected.ttype {
            bail!(
                "fixture {} tutorial type differs: expected={} edit={}",
                expected.label,
                expected.ttype,
                validated.tutorial_type_raw
            );
        }

        let mut comparisons = compare_one(&expected, &edit);
        let summary = summarize_fixture(&expected.label, &expected.ttype, &comparisons);

        report.fixture_count += 1;
        report.field_count += summary.total;
        report.ok_count += summary.ok;
        report.mismatch_count += summary.mismatch;
        report.unavailable_count += summary.unavailable;
        report.fixtures.push(summary);
        report.comparisons.append(&mut comparisons);
    }

    Ok(report)
}

fn load_expected_fixture(path: &Path) -> Result<ExpectedFixture> {
    let text = fs::read_to_string(path).with_context(|| format!("read {}", path.display()))?;
    let root: Value =
        serde_json::from_str(&text).with_context(|| format!("parse {}", path.display()))?;

    let spec = root
        .get("spec")
        .and_then(Value::as_object)
        .with_context(|| format!("{} is missing object .spec", path.display()))?;
    let label = spec
        .get("label")
        .and_then(Value::as_str)
        .with_context(|| format!("{} is missing .spec.label", path.display()))?
        .to_string();
    let ttype = spec
        .get(gel_fields::TUTORIAL_TYPE)
        .and_then(value_as_string)
        .with_context(|| format!("{} is missing .spec.ttype", path.display()))?;

    let db_obj = root
        .get("normalized_db_reference")
        .and_then(Value::as_object)
        .with_context(|| {
            format!(
                "{} is missing object .normalized_db_reference",
                path.display()
            )
        })?;
    let db = db_obj.iter().map(|(k, v)| (k.clone(), v.clone())).collect();

    Ok(ExpectedFixture { label, ttype, db })
}

fn compare_one(expected: &ExpectedFixture, edit: &EditFormState) -> Vec<FieldComparison> {
    let mut out = Vec::new();
    let tutorial_type = tutorial_type_label(&expected.ttype).to_string();

    // Common identity and history controls.
    push_control(
        &mut out,
        expected,
        edit,
        &tutorial_type,
        "student_uid",
        "student_uid",
        gel_fields::STUDENT_UID,
        CompareKind::Integer,
    );
    push_control(
        &mut out,
        expected,
        edit,
        &tutorial_type,
        "timestamp",
        "created_at",
        gel_fields::SOURCE_TIMESTAMP,
        CompareKind::Integer,
    );
    push_literal_control(
        &mut out,
        expected,
        edit,
        &tutorial_type,
        gel_fields::TUTORIAL_TYPE,
        expected.ttype.clone(),
        "spec.ttype",
        gel_fields::TUTORIAL_TYPE,
        CompareKind::Integer,
    );
    push_control(
        &mut out,
        expected,
        edit,
        &tutorial_type,
        "tutorial_date",
        "custom_date",
        gel_fields::CUSTOM_DATE,
        CompareKind::Date,
    );

    push_teacher_id(&mut out, expected, edit, &tutorial_type);
    push_teacher_name(&mut out, expected, edit, &tutorial_type);
    push_absent(&mut out, expected, edit, &tutorial_type);

    push_control(
        &mut out,
        expected,
        edit,
        &tutorial_type,
        "overall_level",
        "overall_level",
        gel_fields::OVERALL_LEVEL,
        CompareKind::Text,
    );

    match expected.ttype.as_str() {
        "0" => compare_standard(&mut out, expected, edit, &tutorial_type),
        "1" => compare_final(&mut out, expected, edit, &tutorial_type),
        "2" => compare_initial(&mut out, expected, edit, &tutorial_type),
        _ => {}
    }

    // Teacher comments exist across all three tutorial types. Writer 9 only
    // submits the Final-only additional-comments control, so Initial/Standard omission is not
    // an unavailable-field error.
    push_control(
        &mut out,
        expected,
        edit,
        &tutorial_type,
        "teacher_comments",
        "teacher_comments",
        gel_fields::TEACHER_COMMENTS,
        CompareKind::Text,
    );
    if expected.ttype == "1" {
        push_control(
            &mut out,
            expected,
            edit,
            &tutorial_type,
            "additional_comments",
            "additional_comments",
            gel_fields::ADDITIONAL_COMMENTS,
            CompareKind::Text,
        );
    }

    out
}

fn compare_standard(
    out: &mut Vec<FieldComparison>,
    expected: &ExpectedFixture,
    edit: &EditFormState,
    tutorial_type: &str,
) {
    for (field, db_key, control) in [
        ("speaking", "speaking", gel_fields::SPEAKING),
        (
            "use_of_english",
            "use_of_english",
            gel_fields::USE_OF_ENGLISH,
        ),
        ("writing", "writing", gel_fields::WRITING),
        ("listening", "listening", gel_fields::LISTENING),
        ("reading", "reading", gel_fields::READING),
    ] {
        push_control(
            out,
            expected,
            edit,
            tutorial_type,
            field,
            db_key,
            control,
            CompareKind::Level,
        );
    }

    for (field, db_key, control) in [
        (
            "self_listening",
            "self_listening",
            gel_fields::ASSESSMENT_LISTENING,
        ),
        (
            "self_reading",
            "self_reading",
            gel_fields::ASSESSMENT_READING,
        ),
        (
            "self_writing",
            "self_writing",
            gel_fields::ASSESSMENT_WRITING,
        ),
        (
            "self_speaking",
            "self_speaking",
            gel_fields::ASSESSMENT_SPEAKING,
        ),
        (
            "self_vocabulary",
            "self_vocabulary",
            gel_fields::ASSESSMENT_VOCABULARY,
        ),
        (
            "self_grammar",
            "self_grammar",
            gel_fields::ASSESSMENT_GRAMMAR,
        ),
        (
            "self_pronunciation",
            "self_pronunciation",
            gel_fields::ASSESSMENT_PRONUNCIATION,
        ),
    ] {
        push_control(
            out,
            expected,
            edit,
            tutorial_type,
            field,
            db_key,
            control,
            CompareKind::Assessment,
        );
    }

    push_semantic_control(
        out,
        expected,
        edit,
        tutorial_type,
        "aims",
        "aims",
        gel_fields::AIMS,
        Some(gel_fields::AIMS_EDITOR_ID),
        CompareKind::Text,
    );
}

fn compare_initial(
    out: &mut Vec<FieldComparison>,
    expected: &ExpectedFixture,
    edit: &EditFormState,
    tutorial_type: &str,
) {
    // For Initial tutorials the four initial scores are the tutorial's primary
    // speaking/use_of_english/writing/listening values. The *_before columns
    // are reserved for initial-score snapshots embedded in Final tutorials.
    for (field, db_key, control) in [
        ("initial_speaking", "speaking", gel_fields::INITIAL_SPEAKING),
        (
            "initial_use_of_english",
            "use_of_english",
            gel_fields::INITIAL_USE_OF_ENGLISH,
        ),
        ("initial_writing", "writing", gel_fields::INITIAL_WRITING),
        (
            "initial_listening",
            "listening",
            gel_fields::INITIAL_LISTENING,
        ),
    ] {
        push_control(
            out,
            expected,
            edit,
            tutorial_type,
            field,
            db_key,
            control,
            CompareKind::Level,
        );
    }
    for (field, db_key, control) in [
        ("exam_want", "exam_want", gel_fields::EXAM_INTENT),
        ("exam_which", "exam_which", gel_fields::EXAM_TYPE),
        ("exam_when", "exam_when", gel_fields::EXAM_WHEN),
    ] {
        push_control(
            out,
            expected,
            edit,
            tutorial_type,
            field,
            db_key,
            control,
            CompareKind::Text,
        );
    }
}

fn compare_final(
    out: &mut Vec<FieldComparison>,
    expected: &ExpectedFixture,
    edit: &EditFormState,
    tutorial_type: &str,
) {
    for (field, db_key, control) in [
        (
            "initial_speaking",
            "speaking_before",
            gel_fields::INITIAL_SPEAKING,
        ),
        (
            "initial_use_of_english",
            "uoe_before",
            gel_fields::INITIAL_USE_OF_ENGLISH,
        ),
        (
            "initial_writing",
            "writing_before",
            gel_fields::INITIAL_WRITING,
        ),
        (
            "initial_listening",
            "listening_before",
            gel_fields::INITIAL_LISTENING,
        ),
        ("final_speaking", "speaking", gel_fields::SPEAKING),
        (
            "final_use_of_english",
            "use_of_english",
            gel_fields::USE_OF_ENGLISH,
        ),
        ("final_writing", "writing", gel_fields::WRITING),
        ("final_listening", "listening", gel_fields::LISTENING),
        ("reading", "reading", gel_fields::READING),
    ] {
        push_control(
            out,
            expected,
            edit,
            tutorial_type,
            field,
            db_key,
            control,
            CompareKind::Level,
        );
    }
}

fn push_teacher_id(
    out: &mut Vec<FieldComparison>,
    expected: &ExpectedFixture,
    edit: &EditFormState,
    tutorial_type: &str,
) {
    let archive = db_value(expected, "teacher_id");
    let edit_value = if edit.teacher.tid_select_present {
        EditValue::present(
            edit.teacher
                .teacher_id
                .map(|v| v.to_string())
                .unwrap_or_default(),
            edit.teacher
                .source
                .clone()
                .unwrap_or_else(|| "edit_form_tid".to_string()),
        )
    } else {
        EditValue::missing("select[name=tid]")
    };
    out.push(make_comparison(
        expected,
        tutorial_type,
        "teacher_id",
        archive,
        "normalized_db_reference.teacher_id",
        edit_value,
        CompareKind::Integer,
    ));
}

fn push_teacher_name(
    out: &mut Vec<FieldComparison>,
    expected: &ExpectedFixture,
    edit: &EditFormState,
    tutorial_type: &str,
) {
    let archive = db_value(expected, "teacher_name");
    let edit_value = if edit.teacher.tid_select_present {
        EditValue::present(
            edit.teacher.teacher_name.clone().unwrap_or_default(),
            "teacher option matched by effective tid",
        )
    } else {
        EditValue::missing("select[name=tid]")
    };
    out.push(make_comparison(
        expected,
        tutorial_type,
        "teacher_name",
        archive,
        "normalized_db_reference.teacher_name",
        edit_value,
        CompareKind::Text,
    ));
}

fn push_absent(
    out: &mut Vec<FieldComparison>,
    expected: &ExpectedFixture,
    edit: &EditFormState,
    tutorial_type: &str,
) {
    let archive = db_value(expected, "absent");
    let edit_value = match edit.checkbox_checked(gel_fields::ABSENT) {
        Some(value) => EditValue::present(
            if value { "true" } else { "false" },
            "input[name=absent] checked",
        ),
        None => EditValue::missing("input[name=absent]"),
    };
    out.push(make_comparison(
        expected,
        tutorial_type,
        "absent",
        archive,
        "normalized_db_reference.absent",
        edit_value,
        CompareKind::Bool,
    ));
}

#[allow(clippy::too_many_arguments)]
fn push_control(
    out: &mut Vec<FieldComparison>,
    expected: &ExpectedFixture,
    edit: &EditFormState,
    tutorial_type: &str,
    field: &str,
    db_key: &str,
    control_name: &str,
    kind: CompareKind,
) {
    let archive = db_value(expected, db_key);
    let edit_value = control_value(edit, control_name);
    out.push(make_comparison(
        expected,
        tutorial_type,
        field,
        archive,
        &format!("normalized_db_reference.{db_key}"),
        edit_value,
        kind,
    ));
}

#[allow(clippy::too_many_arguments)]
fn push_semantic_control(
    out: &mut Vec<FieldComparison>,
    expected: &ExpectedFixture,
    edit: &EditFormState,
    tutorial_type: &str,
    field: &str,
    db_key: &str,
    control_name: &str,
    preferred_contenteditable_id: Option<&str>,
    kind: CompareKind,
) {
    let archive = db_value(expected, db_key);
    let edit_value = semantic_control_value(edit, control_name, preferred_contenteditable_id);
    out.push(make_comparison(
        expected,
        tutorial_type,
        field,
        archive,
        &format!("normalized_db_reference.{db_key}"),
        edit_value,
        kind,
    ));
}

#[allow(clippy::too_many_arguments)]
fn push_literal_control(
    out: &mut Vec<FieldComparison>,
    expected: &ExpectedFixture,
    edit: &EditFormState,
    tutorial_type: &str,
    field: &str,
    archive_value: String,
    archive_source: &str,
    control_name: &str,
    kind: CompareKind,
) {
    let edit_value = control_value(edit, control_name);
    out.push(make_comparison(
        expected,
        tutorial_type,
        field,
        archive_value,
        archive_source,
        edit_value,
        kind,
    ));
}

fn make_comparison(
    expected: &ExpectedFixture,
    tutorial_type: &str,
    field: &str,
    archive_value: String,
    archive_source: &str,
    edit_value: EditValue,
    kind: CompareKind,
) -> FieldComparison {
    let status = if !edit_value.present {
        ComparisonStatus::Unavailable
    } else if equivalent(&archive_value, &edit_value.value, kind) {
        ComparisonStatus::Ok
    } else {
        ComparisonStatus::Mismatch
    };

    FieldComparison {
        fixture: expected.label.clone(),
        tutorial_type: tutorial_type.to_string(),
        field: field.to_string(),
        archive_value,
        edit_value: edit_value.present.then_some(edit_value.value),
        status,
        archive_source: archive_source.to_string(),
        edit_source: edit_value.source,
    }
}

fn db_value(expected: &ExpectedFixture, key: &str) -> String {
    expected
        .db
        .get(key)
        .map(value_to_string)
        .unwrap_or_default()
}

fn value_as_string(value: &Value) -> Option<String> {
    match value {
        Value::String(v) => Some(v.clone()),
        Value::Number(v) => Some(v.to_string()),
        Value::Bool(v) => Some(v.to_string()),
        _ => None,
    }
}

fn value_to_string(value: &Value) -> String {
    match value {
        Value::Null => String::new(),
        Value::String(v) => v.clone(),
        Value::Number(v) => v.to_string(),
        Value::Bool(v) => v.to_string(),
        other => other.to_string(),
    }
}

fn control_value(edit: &EditFormState, wanted: &str) -> EditValue {
    let matching: Vec<&FormControl> = edit
        .controls
        .iter()
        .filter(|control| match control {
            FormControl::Input { name, .. }
            | FormControl::Select { name, .. }
            | FormControl::Textarea { name, .. }
            | FormControl::ContentEditable { name, .. } => name == wanted,
        })
        .collect();

    if matching.is_empty() {
        return EditValue::missing(format!("control[name={wanted}]"));
    }

    // Radio groups: no checked member is a real blank state, not a missing control.
    if matching.iter().any(
        |control| matches!(control, FormControl::Input { input_type, .. } if input_type == "radio"),
    ) {
        for control in matching {
            if let FormControl::Input {
                input_type,
                value,
                checked,
                ..
            } = control
            {
                if input_type == "radio" && *checked {
                    return EditValue::present(
                        value.clone(),
                        format!("radio[name={wanted}] checked"),
                    );
                }
            }
        }
        return EditValue::present("", format!("radio[name={wanted}] no checked option"));
    }

    match matching[0] {
        FormControl::Input {
            input_type,
            value,
            checked,
            ..
        } if input_type == "checkbox" => EditValue::present(
            if *checked { "true" } else { "false" },
            format!("checkbox[name={wanted}] checked"),
        ),
        FormControl::Input { value, .. } => {
            EditValue::present(value.clone(), format!("input[name={wanted}]"))
        }
        FormControl::Textarea { value, .. } => {
            EditValue::present(value.clone(), format!("textarea[name={wanted}]"))
        }
        FormControl::Select {
            effective_value,
            options,
            value_source,
            ..
        } => {
            if let Some(value) = effective_value {
                EditValue::present(
                    value.clone(),
                    format!(
                        "select[name={wanted}] {}",
                        value_source.as_deref().unwrap_or("effective_value")
                    ),
                )
            } else if let Some(first) = options.first() {
                // Browser HTML semantics select the first option when no option has
                // a selected attribute. This matters for exact raw-form parity.
                EditValue::present(
                    first.value.clone(),
                    format!("select[name={wanted}] browser_first_option"),
                )
            } else {
                EditValue::present("", format!("select[name={wanted}] empty"))
            }
        }
        FormControl::ContentEditable { value, id, .. } => EditValue::present(
            value.clone(),
            id.as_deref()
                .map(|id| format!("contenteditable#{id}[name={wanted}]"))
                .unwrap_or_else(|| format!("contenteditable[name={wanted}]")),
        ),
    }
}

fn semantic_control_value(
    edit: &EditFormState,
    wanted: &str,
    preferred_contenteditable_id: Option<&str>,
) -> EditValue {
    if let Some(id) = preferred_contenteditable_id {
        if let Some(value) = edit.contenteditable_value_for_id(id) {
            return EditValue::present(
                value,
                format!("contenteditable#{id}[name={wanted}] semantic_editor"),
            );
        }
    }
    if let Some(value) = edit.contenteditable_value_for_name(wanted) {
        return EditValue::present(
            value,
            format!("contenteditable[name={wanted}] semantic_editor"),
        );
    }
    control_value(edit, wanted)
}

fn equivalent(archive: &str, edit: &str, kind: CompareKind) -> bool {
    match kind {
        CompareKind::Text => normalize_text(archive) == normalize_text(edit),
        CompareKind::Level => normalize_level(archive) == normalize_level(edit),
        CompareKind::Integer => normalize_integer(archive) == normalize_integer(edit),
        CompareKind::Bool => normalize_bool(archive) == normalize_bool(edit),
        CompareKind::Date => normalize_date(archive) == normalize_date(edit),
        CompareKind::Assessment => normalize_assessment(archive) == normalize_assessment(edit),
    }
}

fn normalize_text(value: &str) -> String {
    value.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn normalize_level(value: &str) -> String {
    let trimmed = value.trim();
    match trimmed.to_ascii_lowercase().as_str() {
        "" | "none" | "null" | "please choose level" => String::new(),
        _ => {
            let token = trimmed.split(':').next().unwrap_or(trimmed).trim();
            if token.eq_ignore_ascii_case("Ao") {
                "A0".to_string()
            } else {
                token.to_string()
            }
        }
    }
}

fn normalize_integer(value: &str) -> String {
    value
        .trim()
        .parse::<i64>()
        .map(|v| v.to_string())
        .unwrap_or_else(|_| value.trim().to_string())
}

fn normalize_bool(value: &str) -> String {
    match value.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" | "checked" => "true".to_string(),
        "0" | "false" | "no" | "off" | "" => "false".to_string(),
        other => other.to_string(),
    }
}

fn normalize_date(value: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        return String::new();
    }
    for pattern in ["%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"] {
        if let Ok(date) = NaiveDate::parse_from_str(trimmed, pattern) {
            return date.format("%Y-%m-%d").to_string();
        }
    }
    trimmed.to_string()
}

fn normalize_assessment(value: &str) -> String {
    let trimmed = value.trim();
    match trimmed {
        "1" => return "needs_more_work".to_string(),
        "2" => return "ok_current_level".to_string(),
        "3" => return "good_current_level".to_string(),
        "" => return String::new(),
        _ => {}
    }

    let lower = normalize_text(trimmed).to_ascii_lowercase();
    if lower.contains("need") && lower.contains("work") {
        "needs_more_work".to_string()
    } else if lower.contains("ok") {
        "ok_current_level".to_string()
    } else if lower.contains("good") {
        "good_current_level".to_string()
    } else {
        lower
    }
}

fn tutorial_type_label(ttype: &str) -> &'static str {
    match ttype {
        "0" => "Standard",
        "1" => "Final",
        "2" => "Initial",
        _ => "Unknown",
    }
}

fn summarize_fixture(label: &str, ttype: &str, comparisons: &[FieldComparison]) -> FixtureSummary {
    let mut summary = FixtureSummary {
        fixture: label.to_string(),
        tutorial_type: tutorial_type_label(ttype).to_string(),
        total: comparisons.len(),
        ..Default::default()
    };
    for comparison in comparisons {
        match comparison.status {
            ComparisonStatus::Ok => summary.ok += 1,
            ComparisonStatus::Mismatch => summary.mismatch += 1,
            ComparisonStatus::Unavailable => summary.unavailable += 1,
        }
    }
    summary
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn assessment_numeric_values_match_archived_labels() {
        assert!(equivalent("Needs more work", "1", CompareKind::Assessment));
        assert!(equivalent(
            "OK for the current level",
            "2",
            CompareKind::Assessment
        ));
        assert!(equivalent(
            "Good for the current level",
            "3",
            CompareKind::Assessment
        ));
        assert!(equivalent("", "", CompareKind::Assessment));
    }

    #[test]
    fn unset_levels_match_gel_placeholders() {
        assert!(equivalent(
            "none",
            "Please choose level",
            CompareKind::Level
        ));
        assert!(equivalent("", "Please choose level", CompareKind::Level));
        assert!(equivalent("B1-", "B1-", CompareKind::Level));
    }

    #[test]
    fn dates_compare_across_gel_and_iso_layouts() {
        assert!(equivalent("2026-06-16", "16-06-2026", CompareKind::Date));
    }

    #[test]
    fn booleans_compare_sqlite_and_checkbox_representations() {
        assert!(equivalent("1", "true", CompareKind::Bool));
        assert!(equivalent("0", "false", CompareKind::Bool));
        assert!(!equivalent("0", "true", CompareKind::Bool));
    }
}
