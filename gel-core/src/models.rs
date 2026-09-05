use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SummaryEntry {
    pub datetime_label: String,
    pub tutorial_ts: i64,
    pub ttype_raw: String,
    pub ttype_label: String,
    pub print_url: String,
    pub edit_url: String,
    pub fields: BTreeMap<String, String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SelectOption {
    pub value: String,
    pub text: String,
    pub selected_in_html: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum FormControl {
    Input {
        name: String,
        id: Option<String>,
        input_type: String,
        value: String,
        checked: bool,
    },
    Select {
        name: String,
        id: Option<String>,
        options: Vec<SelectOption>,
        html_selected_value: Option<String>,
        effective_value: Option<String>,
        value_source: Option<String>,
    },
    Textarea {
        name: String,
        id: Option<String>,
        value: String,
    },
    /// GEL's Standard Aims editor is a contenteditable `<div>` rather than a
    /// browser-successful form control. The historical value is displayed here
    /// while the hidden Aims backing input can remain blank until JavaScript copies
    /// the editor contents during submission.
    ContentEditable {
        name: String,
        id: Option<String>,
        /// Normalized plain-text editor value.
        value: String,
        /// Literal inner HTML from GEL's contenteditable editor.
        html: String,
    },
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct TeacherSelection {
    pub teacher_id: Option<i64>,
    pub teacher_name: Option<String>,
    pub source: Option<String>,
    pub tid_select_present: bool,
    pub teacher_option_found: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct EditFormState {
    pub controls: Vec<FormControl>,
    pub js_values_by_id: BTreeMap<String, String>,
    pub teacher: TeacherSelection,
}

impl EditFormState {
    /// Return the effective value of a browser form control. Contenteditable
    /// nodes are intentionally excluded because browsers do not submit them.
    pub fn value_for_name(&self, wanted: &str) -> Option<String> {
        for control in &self.controls {
            match control {
                FormControl::Input {
                    name,
                    value,
                    checked,
                    input_type,
                    ..
                } if name == wanted => {
                    if matches!(input_type.as_str(), "checkbox" | "radio") && !checked {
                        continue;
                    }
                    return Some(value.clone());
                }
                FormControl::Select {
                    name,
                    effective_value,
                    ..
                } if name == wanted => {
                    return effective_value.clone();
                }
                FormControl::Textarea { name, value, .. } if name == wanted => {
                    return Some(value.clone());
                }
                _ => {}
            }
        }
        None
    }

    /// Return the visible historical editor value for a named contenteditable
    /// control. This is the authoritative edit-page representation for Standard
    /// Aims (the named contenteditable editor).
    pub fn contenteditable_value_for_name(&self, wanted: &str) -> Option<String> {
        self.controls.iter().find_map(|control| match control {
            FormControl::ContentEditable { name, value, .. } if name == wanted => {
                Some(value.clone())
            }
            _ => None,
        })
    }

    pub fn contenteditable_value_for_id(&self, wanted: &str) -> Option<String> {
        self.controls.iter().find_map(|control| match control {
            FormControl::ContentEditable { id, value, .. } if id.as_deref() == Some(wanted) => {
                Some(value.clone())
            }
            _ => None,
        })
    }

    /// Semantic editor value: prefer the visible contenteditable state, then
    /// fall back to the underlying named form control.
    pub fn semantic_value_for_name(&self, wanted: &str) -> Option<String> {
        self.contenteditable_value_for_name(wanted)
            .or_else(|| self.value_for_name(wanted))
    }

    pub fn checkbox_checked(&self, wanted: &str) -> Option<bool> {
        self.controls.iter().find_map(|control| match control {
            FormControl::Input {
                name,
                input_type,
                checked,
                ..
            } if name == wanted && input_type == "checkbox" => Some(*checked),
            _ => None,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum ParsedControlStatus {
    PresentValue { raw_value: String },
    PresentUnset { raw_value: Option<String> },
    Missing,
    Malformed { reason: String },
}

impl ParsedControlStatus {
    pub fn is_failure(&self) -> bool {
        matches!(self, Self::Missing | Self::Malformed { .. })
    }

    pub fn raw_value(&self) -> Option<&str> {
        match self {
            Self::PresentValue { raw_value } => Some(raw_value),
            Self::PresentUnset { raw_value } => raw_value.as_deref(),
            Self::Missing | Self::Malformed { .. } => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ControlValidation {
    pub semantic_name: String,
    pub gel_field: String,
    pub applicable: bool,
    pub required: bool,
    pub allow_unset: bool,
    pub status: ParsedControlStatus,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct EditFormValidationReport {
    pub tutorial_type_raw: Option<String>,
    pub controls: Vec<ControlValidation>,
    pub errors: Vec<String>,
}

impl ControlValidation {
    pub fn is_valid(&self) -> bool {
        match &self.status {
            ParsedControlStatus::PresentValue { .. } => true,
            ParsedControlStatus::PresentUnset { .. } => self.allow_unset,
            ParsedControlStatus::Missing => !self.required,
            ParsedControlStatus::Malformed { .. } => false,
        }
    }
}

impl EditFormValidationReport {
    pub fn is_valid(&self) -> bool {
        self.errors.is_empty() && self.controls.iter().all(ControlValidation::is_valid)
    }

    pub fn control(&self, field: &str) -> Option<&ControlValidation> {
        self.controls
            .iter()
            .find(|control| control.gel_field == field)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ValidatedEditFormState {
    raw: EditFormState,
    pub tutorial_type_raw: String,
    pub controls: BTreeMap<String, ParsedControlStatus>,
    pub report: EditFormValidationReport,
}

impl ValidatedEditFormState {
    pub(crate) fn new(
        raw: EditFormState,
        tutorial_type_raw: String,
        controls: BTreeMap<String, ParsedControlStatus>,
        report: EditFormValidationReport,
    ) -> Self {
        Self {
            raw,
            tutorial_type_raw,
            controls,
            report,
        }
    }

    /// Return a value only when the validated control is semantically set.
    pub fn value_for_name(&self, wanted: &str) -> Option<&str> {
        match self.controls.get(wanted)? {
            ParsedControlStatus::PresentValue { raw_value } => Some(raw_value),
            ParsedControlStatus::PresentUnset { .. }
            | ParsedControlStatus::Missing
            | ParsedControlStatus::Malformed { .. } => None,
        }
    }

    /// Return the browser/source value even when the contract classifies it as
    /// an intentional unset placeholder or blank.
    pub fn raw_value_for_name(&self, wanted: &str) -> Option<&str> {
        self.controls.get(wanted)?.raw_value()
    }

    pub fn is_unset(&self, wanted: &str) -> bool {
        matches!(
            self.controls.get(wanted),
            Some(ParsedControlStatus::PresentUnset { .. })
        )
    }

    pub fn checkbox_checked(&self, wanted: &str) -> Option<bool> {
        match self.controls.get(wanted)? {
            ParsedControlStatus::PresentValue { raw_value } => match raw_value.as_str() {
                "true" => Some(true),
                "false" => Some(false),
                _ => None,
            },
            _ => None,
        }
    }

    pub fn teacher(&self) -> &TeacherSelection {
        &self.raw.teacher
    }

    pub fn contenteditable_value_for_id(&self, wanted: &str) -> Option<String> {
        self.raw.contenteditable_value_for_id(wanted)
    }

    pub fn contenteditable_html_for_id(&self, wanted: &str) -> Option<String> {
        self.raw.controls.iter().find_map(|control| match control {
            FormControl::ContentEditable { id, html, .. } if id.as_deref() == Some(wanted) => {
                Some(html.clone())
            }
            _ => None,
        })
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ApiTutorial {
    pub id: i64,
    pub timestamp: i64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CollisionStateKind {
    IdenticalState,
    DivergentState,
    IncompleteEvidence,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HistoricalStateAuthorityStatus {
    ProvenPerTutorial,
    SharedIdenticalCollision,
    AmbiguousDivergentCollision,
    IncompleteCollisionEvidence,
    AmbiguousCollisionUnknown,
    UnmatchedSourceState,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HistoricalStateAuthority {
    pub status: HistoricalStateAuthorityStatus,
    pub reconciliation_key: Option<String>,
}

impl HistoricalStateAuthority {
    pub fn proven() -> Self {
        Self {
            status: HistoricalStateAuthorityStatus::ProvenPerTutorial,
            reconciliation_key: None,
        }
    }

    pub fn for_collision(
        status: HistoricalStateAuthorityStatus,
        student_uid: i64,
        tutorial_ts: i64,
    ) -> Self {
        Self {
            status,
            reconciliation_key: Some(format!("{student_uid}:{tutorial_ts}")),
        }
    }

    pub fn unmatched() -> Self {
        Self {
            status: HistoricalStateAuthorityStatus::UnmatchedSourceState,
            reconciliation_key: None,
        }
    }

    pub fn permits_revision_by_id(&self) -> bool {
        matches!(
            self.status,
            HistoricalStateAuthorityStatus::ProvenPerTutorial
                | HistoricalStateAuthorityStatus::SharedIdenticalCollision
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReconciliationStatus {
    Matched,
    CollisionIdenticalState,
    CollisionDivergentState,
    CollisionIncompleteEvidence,
    UnmatchedSummary,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum MatchMethod {
    ExactTimestamp,
    SameDateFallback,
    CollisionGroup,
    Unmatched,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CollisionGroup {
    pub student_uid: i64,
    pub tutorial_ts: i64,
    pub reconciliation_key: String,
    pub api_tutorial_ids: Vec<i64>,
    /// Candidate source states remain group-owned. They are deliberately not
    /// positionally assigned to API tutorial IDs.
    pub summary_entries: Vec<SummaryEntry>,
    pub collision_kind: CollisionStateKind,
}

impl CollisionGroup {
    pub fn shared_summary_state(&self) -> Option<&SummaryEntry> {
        if self.collision_kind == CollisionStateKind::IdenticalState {
            self.summary_entries.first()
        } else {
            None
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PairedTutorial {
    pub api: ApiTutorial,
    /// Present only when reconciliation proves a per-tutorial source-state
    /// association. Collision-group candidates remain on `CollisionGroup`.
    pub summary: Option<SummaryEntry>,
    pub match_method: MatchMethod,
    pub reconciliation_status: ReconciliationStatus,
    pub state_authority: HistoricalStateAuthority,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RevisionBlockReason {
    DivergentCollision,
    IncompleteCollisionEvidence,
    AmbiguousCollisionUnknown,
    UnmatchedSourceState,
    TutorialIdNotFound,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RevisionStateEvidence {
    pub tutorial_id: i64,
    pub summary: SummaryEntry,
    pub authority: HistoricalStateAuthority,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RevisionStateError {
    pub tutorial_id: i64,
    pub reason: RevisionBlockReason,
    pub reconciliation_key: Option<String>,
}

impl std::fmt::Display for RevisionStateError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "revision state unavailable for tutorial {}: {:?}",
            self.tutorial_id, self.reason
        )
    }
}

impl std::error::Error for RevisionStateError {}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct ReconciliationResult {
    pub pairs: Vec<PairedTutorial>,
    pub unmatched_summary_count: usize,
    pub collisions: Vec<CollisionGroup>,
}

impl ReconciliationResult {
    pub fn revision_state_for(
        &self,
        tutorial_id: i64,
    ) -> Result<RevisionStateEvidence, RevisionStateError> {
        let Some(pair) = self.pairs.iter().find(|pair| pair.api.id == tutorial_id) else {
            return Err(RevisionStateError {
                tutorial_id,
                reason: RevisionBlockReason::TutorialIdNotFound,
                reconciliation_key: None,
            });
        };

        match pair.state_authority.status {
            HistoricalStateAuthorityStatus::ProvenPerTutorial => {
                let Some(summary) = pair.summary.clone() else {
                    return Err(RevisionStateError {
                        tutorial_id,
                        reason: RevisionBlockReason::UnmatchedSourceState,
                        reconciliation_key: pair.state_authority.reconciliation_key.clone(),
                    });
                };
                Ok(RevisionStateEvidence {
                    tutorial_id,
                    summary,
                    authority: pair.state_authority.clone(),
                })
            }
            HistoricalStateAuthorityStatus::SharedIdenticalCollision => {
                let key = pair.state_authority.reconciliation_key.clone();
                let group = self
                    .collisions
                    .iter()
                    .find(|group| Some(group.reconciliation_key.as_str()) == key.as_deref());
                let summary = group
                    .and_then(|group| group.shared_summary_state())
                    .cloned();
                match summary {
                    Some(summary) => Ok(RevisionStateEvidence {
                        tutorial_id,
                        summary,
                        authority: pair.state_authority.clone(),
                    }),
                    None => Err(RevisionStateError {
                        tutorial_id,
                        reason: RevisionBlockReason::IncompleteCollisionEvidence,
                        reconciliation_key: key,
                    }),
                }
            }
            HistoricalStateAuthorityStatus::AmbiguousDivergentCollision => {
                Err(RevisionStateError {
                    tutorial_id,
                    reason: RevisionBlockReason::DivergentCollision,
                    reconciliation_key: pair.state_authority.reconciliation_key.clone(),
                })
            }
            HistoricalStateAuthorityStatus::IncompleteCollisionEvidence => {
                Err(RevisionStateError {
                    tutorial_id,
                    reason: RevisionBlockReason::IncompleteCollisionEvidence,
                    reconciliation_key: pair.state_authority.reconciliation_key.clone(),
                })
            }
            HistoricalStateAuthorityStatus::AmbiguousCollisionUnknown => Err(RevisionStateError {
                tutorial_id,
                reason: RevisionBlockReason::AmbiguousCollisionUnknown,
                reconciliation_key: pair.state_authority.reconciliation_key.clone(),
            }),
            HistoricalStateAuthorityStatus::UnmatchedSourceState => Err(RevisionStateError {
                tutorial_id,
                reason: RevisionBlockReason::UnmatchedSourceState,
                reconciliation_key: pair.state_authority.reconciliation_key.clone(),
            }),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct PrintRecord {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub teacher_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub student_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub custom_date: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub print_text: Option<String>,
    #[serde(skip_serializing_if = "BTreeMap::is_empty", default)]
    pub fields: BTreeMap<String, String>,
    /// Python-v4.9 compatibility projection: every recognized print label is
    /// repeated at the top level, plus the historical `Tutorial Type` ->
    /// `Type` alias. `serde(flatten)` keeps inspect/parity JSON byte-shape
    /// compatible without making these labels Rust struct-field authority.
    #[serde(flatten, default)]
    pub direct_fields: BTreeMap<String, String>,
}
