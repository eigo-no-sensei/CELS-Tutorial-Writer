//! N2b validated GEL New-tutorial source-form boundary.
//!
//! New forms are not historical Revision edit forms. They omit `datetime`,
//! carry the authenticated teacher as a hidden `tid`, and have no GEL tutorial
//! identity yet. This module validates that distinct source structure and never
//! owns network-write authority.

use crate::edit_form_validation::{classify_control, has_named_control};
use crate::form_parser_common::parse_form_controls;
use crate::gel_fields;
use crate::models::{EditFormState, FormControl, ParsedControlStatus, TeacherSelection};
use crate::semantic::ValidatedNewFormTeacher;
use chrono::NaiveDate;
use scraper::{Html, Selector};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NewTutorialFormFailureKind {
    MalformedForm,
    ContractDrift,
    RequestedTypeMismatch,
    StudentMismatch,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NewTutorialFormError {
    pub kind: NewTutorialFormFailureKind,
    pub detail: String,
}

impl NewTutorialFormError {
    fn new(kind: NewTutorialFormFailureKind, detail: impl Into<String>) -> Self {
        Self {
            kind,
            detail: detail.into(),
        }
    }
}

impl fmt::Display for NewTutorialFormError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "GEL New-tutorial form validation failed ({:?})",
            self.kind
        )
    }
}

impl Error for NewTutorialFormError {}

/// Validated, immutable source authority for one fetched GEL New-tutorial form.
/// Raw HTML and teacher display labels are deliberately not retained.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidatedNewTutorialForm {
    student_uid: i64,
    tutorial_type_raw: String,
    teacher: ValidatedNewFormTeacher,
    default_date: NaiveDate,
    controls: BTreeMap<String, ParsedControlStatus>,
    source_fingerprint: String,
}

impl ValidatedNewTutorialForm {
    pub fn student_uid(&self) -> i64 {
        self.student_uid
    }

    pub fn tutorial_type_raw(&self) -> &str {
        &self.tutorial_type_raw
    }

    pub fn teacher(&self) -> &ValidatedNewFormTeacher {
        &self.teacher
    }

    pub fn default_date(&self) -> NaiveDate {
        self.default_date
    }

    pub fn source_fingerprint(&self) -> &str {
        &self.source_fingerprint
    }

    pub(crate) fn control_status(&self, field: &str) -> Option<&ParsedControlStatus> {
        self.controls.get(field)
    }
}

/// Parse and validate one fetched New-tutorial form against the requested route.
pub fn parse_new_tutorial_form(
    html: &str,
    expected_student_uid: i64,
    expected_ttype_raw: &str,
) -> Result<ValidatedNewTutorialForm, NewTutorialFormError> {
    if expected_student_uid <= 0 {
        return Err(NewTutorialFormError::new(
            NewTutorialFormFailureKind::StudentMismatch,
            "requested student UID must be positive",
        ));
    }
    if !valid_ttype(expected_ttype_raw) {
        return Err(NewTutorialFormError::new(
            NewTutorialFormFailureKind::RequestedTypeMismatch,
            "requested tutorial type is not canonical",
        ));
    }

    let (method, action) = tutorial_form_meta(html)?;
    if method != gel_fields::NEW_FORM_METHOD || action != gel_fields::NEW_FORM_ACTION_PATH {
        return Err(NewTutorialFormError::new(
            NewTutorialFormFailureKind::ContractDrift,
            "New tutorial form method/action differs from canonical contract",
        ));
    }

    let (controls, js_values_by_id) = parse_form_controls(html).map_err(|_| {
        NewTutorialFormError::new(
            NewTutorialFormFailureKind::MalformedForm,
            "New tutorial form controls could not be parsed",
        )
    })?;
    let raw = EditFormState {
        controls,
        js_values_by_id,
        teacher: TeacherSelection::default(),
    };

    // Route/form type agreement is an identity-level contract and must be
    // checked before type-specific applicability. Otherwise a complete form
    // for another canonical tutorial type can be misclassified as generic
    // contract drift merely because its valid controls differ from the
    // requested type. Unknown/malformed ttype still fails closed.
    let type_spec = gel_fields::new_control_spec(gel_fields::TUTORIAL_TYPE)
        .expect("canonical New-form ttype spec must exist");
    let actual_ttype = match classify_control(&raw, type_spec) {
        ParsedControlStatus::PresentValue { raw_value } => raw_value,
        ParsedControlStatus::PresentUnset { .. } | ParsedControlStatus::Missing => {
            return Err(NewTutorialFormError::new(
                NewTutorialFormFailureKind::MalformedForm,
                "required New-form ttype is missing or unset",
            ));
        }
        ParsedControlStatus::Malformed { .. } => {
            return Err(NewTutorialFormError::new(
                NewTutorialFormFailureKind::MalformedForm,
                "New-form ttype is outside the canonical tutorial-type domain",
            ));
        }
    };
    if actual_ttype != expected_ttype_raw {
        return Err(NewTutorialFormError::new(
            NewTutorialFormFailureKind::RequestedTypeMismatch,
            "returned New form tutorial type does not match requested type",
        ));
    }

    for field in gel_fields::NEW_FORBIDDEN_FIELDS {
        if has_named_control(&raw, field) {
            return Err(NewTutorialFormError::new(
                NewTutorialFormFailureKind::ContractDrift,
                format!("forbidden New-form field {field} is present"),
            ));
        }
    }

    let mut validated = BTreeMap::new();
    for spec in gel_fields::NEW_CONTROL_SPECS {
        let applicable = gel_fields::field_applies_to(spec.field, expected_ttype_raw);
        if !applicable {
            if has_named_control(&raw, spec.field) {
                return Err(NewTutorialFormError::new(
                    NewTutorialFormFailureKind::ContractDrift,
                    format!(
                        "known GEL field {} is present but inapplicable to requested type",
                        spec.field
                    ),
                ));
            }
            continue;
        }

        let status = classify_control(&raw, spec);
        let valid = match &status {
            ParsedControlStatus::PresentValue { .. } => true,
            ParsedControlStatus::PresentUnset { .. } => spec.allow_unset,
            ParsedControlStatus::Missing => !spec.required,
            ParsedControlStatus::Malformed { .. } => false,
        };
        if !valid {
            let kind = if spec.field == gel_fields::TEACHER_ID {
                NewTutorialFormFailureKind::ContractDrift
            } else {
                NewTutorialFormFailureKind::MalformedForm
            };
            return Err(NewTutorialFormError::new(
                kind,
                format!("governed New-form field {} failed validation", spec.field),
            ));
        }
        validated.insert(spec.field.to_string(), status);
    }

    let actual_uid = required_value(&validated, gel_fields::STUDENT_UID)?
        .parse::<i64>()
        .map_err(|_| {
            NewTutorialFormError::new(
                NewTutorialFormFailureKind::MalformedForm,
                "validated New-form uid is not numeric",
            )
        })?;
    if actual_uid != expected_student_uid {
        return Err(NewTutorialFormError::new(
            NewTutorialFormFailureKind::StudentMismatch,
            "returned New form student UID does not match requested route",
        ));
    }

    let teacher_id = required_value(&validated, gel_fields::TEACHER_ID)?
        .parse::<i64>()
        .map_err(|_| {
            NewTutorialFormError::new(
                NewTutorialFormFailureKind::ContractDrift,
                "validated hidden New-form tid is not numeric",
            )
        })?;
    let teacher = ValidatedNewFormTeacher::from_validated_hidden_control(
        teacher_id,
        expected_student_uid,
        expected_ttype_raw,
    )
    .map_err(|_| {
        NewTutorialFormError::new(
            NewTutorialFormFailureKind::ContractDrift,
            "validated hidden New-form tid is not positive",
        )
    })?;

    let default_date = NaiveDate::parse_from_str(
        required_value(&validated, gel_fields::CUSTOM_DATE)?,
        "%d-%m-%Y",
    )
    .map_err(|_| {
        NewTutorialFormError::new(
            NewTutorialFormFailureKind::MalformedForm,
            "validated New-form customdate is not a GEL date",
        )
    })?;

    let source_fingerprint = fingerprint_new_form(
        &raw,
        expected_ttype_raw,
        teacher.teacher_id(),
        default_date,
        &validated,
    );

    Ok(ValidatedNewTutorialForm {
        student_uid: expected_student_uid,
        tutorial_type_raw: expected_ttype_raw.to_string(),
        teacher,
        default_date,
        controls: validated,
        source_fingerprint,
    })
}

fn required_value<'a>(
    controls: &'a BTreeMap<String, ParsedControlStatus>,
    field: &str,
) -> Result<&'a str, NewTutorialFormError> {
    match controls.get(field) {
        Some(ParsedControlStatus::PresentValue { raw_value }) => Ok(raw_value.as_str()),
        _ => Err(NewTutorialFormError::new(
            NewTutorialFormFailureKind::MalformedForm,
            format!("required validated New-form field {field} has no value"),
        )),
    }
}

fn valid_ttype(value: &str) -> bool {
    [
        gel_fields::TTYPE_STANDARD,
        gel_fields::TTYPE_FINAL,
        gel_fields::TTYPE_INITIAL,
    ]
    .contains(&value)
}

fn tutorial_form_meta(html: &str) -> Result<(String, String), NewTutorialFormError> {
    let document = Html::parse_document(html);
    let form_selector = Selector::parse("form").expect("static form selector must parse");
    let type_selector =
        Selector::parse(r#"[name="ttype"]"#).expect("static tutorial type selector must parse");
    let mut matches = document
        .select(&form_selector)
        .filter(|form| form.select(&type_selector).next().is_some());
    let Some(form) = matches.next() else {
        return Err(NewTutorialFormError::new(
            NewTutorialFormFailureKind::MalformedForm,
            "tutorial form containing ttype was not found",
        ));
    };
    if matches.next().is_some() {
        return Err(NewTutorialFormError::new(
            NewTutorialFormFailureKind::MalformedForm,
            "multiple tutorial forms containing ttype were found",
        ));
    }
    let method = form
        .value()
        .attr("method")
        .unwrap_or("GET")
        .trim()
        .to_ascii_uppercase();
    let action = normalized_action_path(form.value().attr("action").unwrap_or(""));
    Ok((method, action))
}

fn normalized_action_path(action: &str) -> String {
    let without_query = action.split('?').next().unwrap_or("");
    if let Some(scheme_pos) = without_query.find("://") {
        let after_scheme = &without_query[scheme_pos + 3..];
        if let Some(path_pos) = after_scheme.find('/') {
            return after_scheme[path_pos..].to_string();
        }
        return "/".to_string();
    }
    if without_query.starts_with('/') {
        without_query.to_string()
    } else if without_query.is_empty() {
        String::new()
    } else {
        format!("/{without_query}")
    }
}

fn fingerprint_new_form(
    raw: &EditFormState,
    tutorial_type_raw: &str,
    teacher_id: i64,
    default_date: NaiveDate,
    validated: &BTreeMap<String, ParsedControlStatus>,
) -> String {
    let mut hasher = Sha256::new();
    hash_part(&mut hasher, "method", gel_fields::NEW_FORM_METHOD);
    hash_part(&mut hasher, "action", gel_fields::NEW_FORM_ACTION_PATH);
    hash_part(&mut hasher, "ttype", tutorial_type_raw);
    hash_part(&mut hasher, "teacher", &teacher_id.to_string());
    hash_part(
        &mut hasher,
        "default_date",
        &default_date.format("%Y-%m-%d").to_string(),
    );

    for (field, status) in validated {
        match status {
            ParsedControlStatus::PresentValue { raw_value } => {
                hash_part(&mut hasher, field, "value");
                hash_part(&mut hasher, field, raw_value);
            }
            ParsedControlStatus::PresentUnset { raw_value } => {
                hash_part(&mut hasher, field, "unset");
                hash_part(&mut hasher, field, raw_value.as_deref().unwrap_or(""));
            }
            ParsedControlStatus::Missing => hash_part(&mut hasher, field, "missing"),
            ParsedControlStatus::Malformed { reason } => {
                hash_part(&mut hasher, field, "malformed");
                hash_part(&mut hasher, field, reason);
            }
        }
    }

    // Option *values* are source semantics; display labels are deliberately
    // excluded so teacher names and presentation prose never enter the hash.
    let governed: BTreeSet<String> = gel_fields::NEW_CONTROL_SPECS
        .iter()
        .filter(|spec| gel_fields::field_applies_to(spec.field, tutorial_type_raw))
        .map(|spec| spec.field.to_string())
        .collect();
    let mut option_domains: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for control in &raw.controls {
        match control {
            FormControl::Select { name, options, .. } if governed.contains(name) => {
                option_domains
                    .entry(name.clone())
                    .or_default()
                    .extend(options.iter().map(|option| option.value.trim().to_string()));
            }
            FormControl::Input {
                name,
                input_type,
                value,
                ..
            } if governed.contains(name) && input_type == "radio" => {
                option_domains
                    .entry(name.clone())
                    .or_default()
                    .push(value.trim().to_string());
            }
            _ => {}
        }
    }
    for (name, mut values) in option_domains {
        values.sort();
        hash_part(&mut hasher, &name, &values.join("\u{1f}"));
    }

    format!("sha256:{:x}", hasher.finalize())
}

fn hash_part(hasher: &mut Sha256, key: &str, value: &str) {
    hasher.update(key.as_bytes());
    hasher.update([0]);
    hasher.update(value.as_bytes());
    hasher.update([0xff]);
}
