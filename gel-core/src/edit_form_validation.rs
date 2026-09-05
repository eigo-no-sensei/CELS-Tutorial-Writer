use crate::gel_fields::{self, EditControlSpec, GelControlKind, GelValueValidationRule};
use crate::models::{
    ControlValidation, EditFormState, EditFormValidationReport, FormControl, ParsedControlStatus,
    ValidatedEditFormState,
};
use chrono::NaiveDate;
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EditFormValidationError {
    pub report: EditFormValidationReport,
}

impl fmt::Display for EditFormValidationError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.report.errors.is_empty() {
            write!(f, "GEL edit-form validation failed")
        } else {
            write!(
                f,
                "GEL edit-form validation failed: {}",
                self.report.errors.join("; ")
            )
        }
    }
}

impl Error for EditFormValidationError {}

/// Validate a raw historical GEL edit form against the canonical form contract.
///
/// The raw parser intentionally records what GEL sent. This validator is the
/// fail-closed boundary: semantic code receives `ValidatedEditFormState` only
/// after every applicable required control has the expected shape.
pub fn validate_edit_form(
    edit: &EditFormState,
) -> Result<ValidatedEditFormState, EditFormValidationError> {
    let type_spec = gel_fields::edit_control_spec(gel_fields::TUTORIAL_TYPE)
        .expect("canonical contract must define ttype edit control");
    let type_status = classify_control(edit, type_spec);

    let mut report = EditFormValidationReport {
        tutorial_type_raw: type_status.raw_value().map(ToOwned::to_owned),
        controls: vec![control_report(type_spec, true, type_status.clone())],
        errors: Vec::new(),
    };

    let tutorial_type_raw = match &type_status {
        ParsedControlStatus::PresentValue { raw_value } => raw_value.clone(),
        ParsedControlStatus::PresentUnset { .. } => {
            report
                .errors
                .push("required GEL tutorial type control is present but unset".to_string());
            return Err(EditFormValidationError { report });
        }
        ParsedControlStatus::Missing => {
            report
                .errors
                .push("required GEL tutorial type control is missing".to_string());
            return Err(EditFormValidationError { report });
        }
        ParsedControlStatus::Malformed { reason } => {
            report
                .errors
                .push(format!("GEL tutorial type control is malformed: {reason}"));
            return Err(EditFormValidationError { report });
        }
    };

    if !matches!(
        tutorial_type_raw.as_str(),
        gel_fields::TTYPE_STANDARD | gel_fields::TTYPE_FINAL | gel_fields::TTYPE_INITIAL
    ) {
        report.errors.push(format!(
            "unknown GEL tutorial type code {tutorial_type_raw:?}"
        ));
        return Err(EditFormValidationError { report });
    }

    let mut controls = BTreeMap::new();
    controls.insert(gel_fields::TUTORIAL_TYPE.to_string(), type_status);

    for spec in gel_fields::EDIT_CONTROL_SPECS {
        if spec.field == gel_fields::TUTORIAL_TYPE {
            continue;
        }

        let applicable = gel_fields::field_applies_to(spec.field, &tutorial_type_raw);
        if !applicable {
            if has_named_control(edit, spec.field) {
                let status = ParsedControlStatus::Malformed {
                    reason: format!(
                        "known GEL control is not applicable to tutorial type {}",
                        tutorial_type_raw
                    ),
                };
                report
                    .controls
                    .push(control_report(spec, false, status.clone()));
                report.errors.push(format!(
                    "{} ({}) is present but not applicable to tutorial type {}",
                    spec.semantic_name, spec.field, tutorial_type_raw
                ));
            }
            continue;
        }

        let status = classify_control(edit, spec);
        let row = control_report(spec, true, status.clone());
        if !row.is_valid() {
            report.errors.push(validation_error_message(spec, &status));
        }
        report.controls.push(row);
        controls.insert(spec.field.to_string(), status);
    }

    if !report.is_valid() {
        return Err(EditFormValidationError { report });
    }

    Ok(ValidatedEditFormState::new(
        edit.clone(),
        tutorial_type_raw,
        controls,
        report,
    ))
}

fn control_report(
    spec: &EditControlSpec,
    applicable: bool,
    status: ParsedControlStatus,
) -> ControlValidation {
    ControlValidation {
        semantic_name: spec.semantic_name.to_string(),
        gel_field: spec.field.to_string(),
        applicable,
        required: spec.required,
        allow_unset: spec.allow_unset,
        status,
    }
}

fn validation_error_message(spec: &EditControlSpec, status: &ParsedControlStatus) -> String {
    match status {
        ParsedControlStatus::PresentValue { .. } => {
            format!("{} ({}) failed validation", spec.semantic_name, spec.field)
        }
        ParsedControlStatus::PresentUnset { .. } => format!(
            "{} ({}) is present but unset and the contract disallows unset",
            spec.semantic_name, spec.field
        ),
        ParsedControlStatus::Missing => {
            format!(
                "required {} ({}) control is missing",
                spec.semantic_name, spec.field
            )
        }
        ParsedControlStatus::Malformed { reason } => {
            format!(
                "{} ({}) is malformed: {reason}",
                spec.semantic_name, spec.field
            )
        }
    }
}

pub(crate) fn has_named_control(edit: &EditFormState, wanted: &str) -> bool {
    edit.controls
        .iter()
        .any(|control| control_name(control) == wanted)
}

fn controls_named<'a>(edit: &'a EditFormState, wanted: &str) -> Vec<&'a FormControl> {
    edit.controls
        .iter()
        .filter(|control| control_name(control) == wanted)
        .collect()
}

fn control_name(control: &FormControl) -> &str {
    match control {
        FormControl::Input { name, .. }
        | FormControl::Select { name, .. }
        | FormControl::Textarea { name, .. }
        | FormControl::ContentEditable { name, .. } => name,
    }
}

pub(crate) fn classify_control(
    edit: &EditFormState,
    spec: &EditControlSpec,
) -> ParsedControlStatus {
    match spec.kind {
        GelControlKind::Hidden => classify_single_input(edit, spec, "hidden"),
        GelControlKind::Text => classify_single_input(edit, spec, "text"),
        GelControlKind::Checkbox => classify_checkbox(edit, spec),
        GelControlKind::Select => classify_select(edit, spec),
        GelControlKind::Textarea => classify_textarea(edit, spec),
        GelControlKind::RadioGroup => classify_radio_group(edit, spec),
        GelControlKind::ContentEditablePlusHidden => classify_contenteditable(edit, spec),
    }
}

fn classify_single_input(
    edit: &EditFormState,
    spec: &EditControlSpec,
    expected_type: &str,
) -> ParsedControlStatus {
    let controls = controls_named(edit, spec.field);
    if controls.is_empty() {
        return ParsedControlStatus::Missing;
    }
    if controls.len() != 1 {
        return malformed(format!(
            "expected exactly one {expected_type} input, found {} named controls",
            controls.len()
        ));
    }
    let FormControl::Input {
        input_type, value, ..
    } = controls[0]
    else {
        return malformed(format!(
            "expected {expected_type} input, found another control kind"
        ));
    };
    if input_type != expected_type {
        return malformed(format!(
            "expected input type {expected_type:?}, found {input_type:?}"
        ));
    }
    classify_scalar_value(spec, value.clone())
}

fn classify_checkbox(edit: &EditFormState, spec: &EditControlSpec) -> ParsedControlStatus {
    let controls = controls_named(edit, spec.field);
    if controls.is_empty() {
        return ParsedControlStatus::Missing;
    }
    if controls.len() != 1 {
        return malformed(format!(
            "expected exactly one checkbox, found {} named controls",
            controls.len()
        ));
    }
    let FormControl::Input {
        input_type,
        checked,
        ..
    } = controls[0]
    else {
        return malformed("expected checkbox input, found another control kind");
    };
    if input_type != "checkbox" {
        return malformed(format!(
            "expected input type \"checkbox\", found {input_type:?}"
        ));
    }
    ParsedControlStatus::PresentValue {
        raw_value: checked.to_string(),
    }
}

fn classify_select(edit: &EditFormState, spec: &EditControlSpec) -> ParsedControlStatus {
    let controls = controls_named(edit, spec.field);
    if controls.is_empty() {
        return ParsedControlStatus::Missing;
    }
    if controls.len() != 1 {
        return malformed(format!(
            "expected exactly one select, found {} named controls",
            controls.len()
        ));
    }
    let FormControl::Select {
        options,
        effective_value,
        ..
    } = controls[0]
    else {
        return malformed("expected select, found another control kind");
    };
    if options.is_empty() {
        return malformed("select has no options");
    }
    if !spec.allowed_values.is_empty() {
        for option in options {
            let value = option.value.trim();
            let is_placeholder = spec
                .placeholder
                .is_some_and(|placeholder| value == placeholder);
            if !is_placeholder && !spec.allowed_values.contains(&value) {
                return malformed(format!(
                    "select option {value:?} is outside the canonical value domain"
                ));
            }
        }
    }
    let selected_count = options
        .iter()
        .filter(|option| option.selected_in_html)
        .count();
    if selected_count > 1 {
        return malformed(format!(
            "single-value select has {selected_count} HTML-selected options"
        ));
    }
    let Some(value) = effective_value.clone() else {
        return malformed("select has options but no browser-effective value");
    };
    if !options.iter().any(|option| option.value == value) {
        return malformed(format!(
            "effective select value {value:?} is not one of the control options"
        ));
    }
    classify_scalar_value(spec, value)
}

fn classify_textarea(edit: &EditFormState, spec: &EditControlSpec) -> ParsedControlStatus {
    let controls = controls_named(edit, spec.field);
    if controls.is_empty() {
        return ParsedControlStatus::Missing;
    }
    if controls.len() != 1 {
        return malformed(format!(
            "expected exactly one textarea, found {} named controls",
            controls.len()
        ));
    }
    let FormControl::Textarea { value, .. } = controls[0] else {
        return malformed("expected textarea, found another control kind");
    };
    classify_scalar_value(spec, value.clone())
}

fn classify_radio_group(edit: &EditFormState, spec: &EditControlSpec) -> ParsedControlStatus {
    let controls = controls_named(edit, spec.field);
    if controls.is_empty() {
        return ParsedControlStatus::Missing;
    }

    let mut values = Vec::new();
    let mut checked = Vec::new();
    for control in controls {
        let FormControl::Input {
            input_type,
            value,
            checked: is_checked,
            ..
        } = control
        else {
            return malformed("radio group contains a non-input control");
        };
        if input_type != "radio" {
            return malformed(format!("radio group contains input type {input_type:?}"));
        }
        values.push(value.clone());
        if *is_checked {
            checked.push(value.clone());
        }
    }

    let unique: BTreeSet<_> = values.iter().cloned().collect();
    if unique.len() != values.len() {
        return malformed("radio group contains duplicate option values");
    }
    if !spec.allowed_values.is_empty() {
        let expected: BTreeSet<String> = spec
            .allowed_values
            .iter()
            .map(|value| (*value).to_string())
            .collect();
        if unique != expected {
            return malformed(format!(
                "radio option set {:?} does not match contract {:?}",
                unique, expected
            ));
        }
    }
    if checked.len() > 1 {
        return malformed(format!("radio group has {} checked options", checked.len()));
    }
    if let Some(value) = checked.into_iter().next() {
        classify_scalar_value(spec, value)
    } else {
        ParsedControlStatus::PresentUnset { raw_value: None }
    }
}

fn classify_contenteditable(edit: &EditFormState, spec: &EditControlSpec) -> ParsedControlStatus {
    let controls = controls_named(edit, spec.field);
    if controls.is_empty() {
        return ParsedControlStatus::Missing;
    }

    let mut hidden_value: Option<&str> = None;
    let mut editor_value: Option<&str> = None;
    let mut editor_id: Option<&str> = None;
    for control in controls {
        match control {
            FormControl::Input {
                input_type, value, ..
            } if input_type == "hidden" => {
                if hidden_value.replace(value.as_str()).is_some() {
                    return malformed("Aims backing hidden input is duplicated");
                }
            }
            FormControl::ContentEditable { id, value, .. } => {
                if editor_value.replace(value.as_str()).is_some() {
                    return malformed("Aims contenteditable is duplicated");
                }
                editor_id = id.as_deref();
            }
            _ => {
                return malformed(
                    "expected one hidden backing input plus one contenteditable editor",
                );
            }
        }
    }

    if hidden_value.is_none() || editor_value.is_none() {
        return malformed("expected both hidden backing input and contenteditable editor");
    }
    if let Some(expected_id) = spec.editor_id {
        if editor_id != Some(expected_id) {
            return malformed(format!(
                "contenteditable id {:?} does not match contract {:?}",
                editor_id, expected_id
            ));
        }
    }

    classify_scalar_value(spec, editor_value.unwrap_or_default().to_string())
}

fn classify_scalar_value(spec: &EditControlSpec, raw_value: String) -> ParsedControlStatus {
    let trimmed = raw_value.trim();
    let is_placeholder = spec
        .placeholder
        .is_some_and(|placeholder| trimmed == placeholder);
    let is_unset = trimmed.is_empty() || is_placeholder;

    if !is_unset && !spec.allowed_values.is_empty() && !spec.allowed_values.contains(&trimmed) {
        return malformed(format!(
            "value {raw_value:?} is outside the canonical value domain"
        ));
    }

    if !is_unset {
        if let Err(reason) = validate_value_rule(spec.validation_rule, trimmed) {
            return malformed(reason);
        }
    }

    if is_unset {
        ParsedControlStatus::PresentUnset {
            raw_value: Some(raw_value),
        }
    } else {
        ParsedControlStatus::PresentValue { raw_value }
    }
}

fn validate_value_rule(rule: GelValueValidationRule, value: &str) -> Result<(), String> {
    match rule {
        GelValueValidationRule::None => Ok(()),
        GelValueValidationRule::PositiveI64 | GelValueValidationRule::PositiveI64Option => {
            let parsed = value
                .parse::<i64>()
                .map_err(|_| format!("expected positive integer value, found {value:?}"))?;
            if parsed <= 0 {
                return Err(format!("expected positive integer value, found {value:?}"));
            }
            Ok(())
        }
        GelValueValidationRule::TutorialTypeCode => {
            if matches!(
                value,
                gel_fields::TTYPE_STANDARD | gel_fields::TTYPE_FINAL | gel_fields::TTYPE_INITIAL
            ) {
                Ok(())
            } else {
                Err(format!("unknown tutorial type code {value:?}"))
            }
        }
        GelValueValidationRule::GelDate => NaiveDate::parse_from_str(value, "%d-%m-%Y")
            .map(|_| ())
            .map_err(|_| format!("expected GEL date DD-MM-YYYY, found {value:?}")),
        GelValueValidationRule::CheckboxBoolean => {
            if matches!(value, "true" | "false") {
                Ok(())
            } else {
                Err(format!(
                    "expected validated checkbox boolean, found {value:?}"
                ))
            }
        }
    }
}

fn malformed(reason: impl Into<String>) -> ParsedControlStatus {
    ParsedControlStatus::Malformed {
        reason: reason.into(),
    }
}
