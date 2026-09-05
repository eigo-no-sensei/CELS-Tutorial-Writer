use crate::gel_fields;
use crate::models::{HistoricalStateAuthority, ParsedControlStatus, ValidatedEditFormState};
use crate::new_form_parser::ValidatedNewTutorialForm;
use anyhow::{bail, Context, Result};
use chrono::NaiveDate;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TutorialType {
    Standard,
    Final,
    Initial,
}

impl TutorialType {
    pub fn ttype(self) -> &'static str {
        match self {
            Self::Standard => gel_fields::TTYPE_STANDARD,
            Self::Final => gel_fields::TTYPE_FINAL,
            Self::Initial => gel_fields::TTYPE_INITIAL,
        }
    }

    pub fn from_ttype(value: &str) -> Result<Self> {
        match value.trim() {
            gel_fields::TTYPE_STANDARD => Ok(Self::Standard),
            gel_fields::TTYPE_FINAL => Ok(Self::Final),
            gel_fields::TTYPE_INITIAL => Ok(Self::Initial),
            other => bail!("unknown GEL tutorial type: {other}"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum CefrLevel {
    A0,
    A1Minus,
    A1,
    A1Plus,
    A2Minus,
    A2,
    A2Plus,
    B1Minus,
    B1,
    B1Plus,
    B2Minus,
    B2,
    B2Plus,
    C1Minus,
    C1,
    C1Plus,
    C2Minus,
    C2,
    C2Plus,
}

impl CefrLevel {
    pub const fn all() -> &'static [Self] {
        &[
            Self::A0,
            Self::A1Minus,
            Self::A1,
            Self::A1Plus,
            Self::A2Minus,
            Self::A2,
            Self::A2Plus,
            Self::B1Minus,
            Self::B1,
            Self::B1Plus,
            Self::B2Minus,
            Self::B2,
            Self::B2Plus,
            Self::C1Minus,
            Self::C1,
            Self::C1Plus,
            Self::C2Minus,
            Self::C2,
            Self::C2Plus,
        ]
    }

    pub fn form_value(self) -> &'static str {
        match self {
            Self::A0 => "A0",
            Self::A1Minus => "A1-",
            Self::A1 => "A1",
            Self::A1Plus => "A1+",
            Self::A2Minus => "A2-",
            Self::A2 => "A2",
            Self::A2Plus => "A2+",
            Self::B1Minus => "B1-",
            Self::B1 => "B1",
            Self::B1Plus => "B1+",
            Self::B2Minus => "B2-",
            Self::B2 => "B2",
            Self::B2Plus => "B2+",
            Self::C1Minus => "C1-",
            Self::C1 => "C1",
            Self::C1Plus => "C1+",
            Self::C2Minus => "C2-",
            Self::C2 => "C2",
            Self::C2Plus => "C2+",
        }
    }

    pub fn overall_form_value(self) -> &'static str {
        match self {
            Self::A0 => "Ao: beginner", // GEL's observed spelling uses letter 'o'.
            Self::A1Minus => "A1-: elementary",
            Self::A1 => "A1: elementary",
            Self::A1Plus => "A1+: elementary",
            Self::A2Minus => "A2-: pre-intermediate",
            Self::A2 => "A2: pre-intermediate",
            Self::A2Plus => "A2+: pre-intermediate",
            Self::B1Minus => "B1-: intermediate",
            Self::B1 => "B1: intermediate",
            Self::B1Plus => "B1+: intermediate",
            Self::B2Minus => "B2-: upper-intermediate",
            Self::B2 => "B2: upper-intermediate",
            Self::B2Plus => "B2+: upper-intermediate",
            Self::C1Minus => "C1-: advanced",
            Self::C1 => "C1: advanced",
            Self::C1Plus => "C1+: advanced",
            Self::C2Minus => "C2-: very advanced",
            Self::C2 => "C2: very advanced",
            Self::C2Plus => "C2+: very advanced",
        }
    }

    pub fn parse(raw: &str) -> Option<Self> {
        let trimmed = raw.trim();
        if is_unset_level_text(trimmed) {
            return None;
        }
        let token = trimmed.split(':').next().unwrap_or(trimmed).trim();
        let token = if token.eq_ignore_ascii_case("Ao") {
            "A0"
        } else {
            token
        };
        match token {
            "A0" => Some(Self::A0),
            "A1-" => Some(Self::A1Minus),
            "A1" => Some(Self::A1),
            "A1+" => Some(Self::A1Plus),
            "A2-" => Some(Self::A2Minus),
            "A2" => Some(Self::A2),
            "A2+" => Some(Self::A2Plus),
            "B1-" => Some(Self::B1Minus),
            "B1" => Some(Self::B1),
            "B1+" => Some(Self::B1Plus),
            "B2-" => Some(Self::B2Minus),
            "B2" => Some(Self::B2),
            "B2+" => Some(Self::B2Plus),
            "C1-" => Some(Self::C1Minus),
            "C1" => Some(Self::C1),
            "C1+" => Some(Self::C1Plus),
            "C2-" => Some(Self::C2Minus),
            "C2" => Some(Self::C2),
            "C2+" => Some(Self::C2Plus),
            _ => None,
        }
    }
}

pub fn is_unset_level_text(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "" | "none" | "null" | "please choose level" | "choose..."
    )
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct SkillScores {
    pub speaking: Option<CefrLevel>,
    pub use_of_english: Option<CefrLevel>,
    pub writing: Option<CefrLevel>,
    pub listening: Option<CefrLevel>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AssessmentValue {
    NeedsMoreWork = 1,
    OkForCurrentLevel = 2,
    GoodForCurrentLevel = 3,
}

impl AssessmentValue {
    pub const fn all() -> &'static [Self] {
        &[
            Self::NeedsMoreWork,
            Self::OkForCurrentLevel,
            Self::GoodForCurrentLevel,
        ]
    }

    pub fn ui_value(self) -> &'static str {
        match self {
            Self::NeedsMoreWork => "needs_work",
            Self::OkForCurrentLevel => "ok",
            Self::GoodForCurrentLevel => "good_for_this_level",
        }
    }

    pub fn display_label(self) -> &'static str {
        match self {
            Self::NeedsMoreWork => "Needs work",
            Self::OkForCurrentLevel => "OK for the current level",
            Self::GoodForCurrentLevel => "Good for this level",
        }
    }

    pub fn form_value(self) -> &'static str {
        match self {
            Self::NeedsMoreWork => "1",
            Self::OkForCurrentLevel => "2",
            Self::GoodForCurrentLevel => "3",
        }
    }

    pub fn parse(value: &str) -> Option<Self> {
        let normalized = value.split_whitespace().collect::<Vec<_>>().join(" ");
        let lower = normalized.to_ascii_lowercase();
        match lower.as_str() {
            "" => None,
            "1" => Some(Self::NeedsMoreWork),
            "2" => Some(Self::OkForCurrentLevel),
            "3" => Some(Self::GoodForCurrentLevel),
            _ if lower.contains("need") && lower.contains("work") => Some(Self::NeedsMoreWork),
            _ if lower.contains("ok") => Some(Self::OkForCurrentLevel),
            _ if lower.contains("good") => Some(Self::GoodForCurrentLevel),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct SelfAssessment {
    pub listening: Option<AssessmentValue>,
    pub reading: Option<AssessmentValue>,
    pub writing: Option<AssessmentValue>,
    pub speaking: Option<AssessmentValue>,
    pub vocabulary: Option<AssessmentValue>,
    pub grammar: Option<AssessmentValue>,
    pub pronunciation: Option<AssessmentValue>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct ExamIntent {
    pub intent: Option<String>,
    pub exam_type: Option<String>,
    pub when: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum InitialCourseType {
    #[serde(rename = "HSP")]
    Hsp,
    #[serde(rename = "G21")]
    G21,
    #[serde(rename = "G15")]
    G15,
}

impl InitialCourseType {
    pub const fn all() -> &'static [Self] {
        &[Self::Hsp, Self::G21, Self::G15]
    }

    pub fn storage_value(self) -> &'static str {
        match self {
            Self::Hsp => "HSP",
            Self::G21 => "G21",
            Self::G15 => "G15",
        }
    }

    pub fn parse_exact(value: &str) -> Option<Self> {
        match value {
            "HSP" => Some(Self::Hsp),
            "G21" => Some(Self::G21),
            "G15" => Some(Self::G15),
            _ => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum InitialCourseTypeState {
    Unset,
    Recognized { value: InitialCourseType },
    UnrecognizedPreserved { raw: String },
}

pub fn initial_course_type_state(teacher_comments: &str) -> InitialCourseTypeState {
    if teacher_comments.trim().is_empty() {
        InitialCourseTypeState::Unset
    } else if let Some(value) = InitialCourseType::parse_exact(teacher_comments) {
        InitialCourseTypeState::Recognized { value }
    } else {
        InitialCourseTypeState::UnrecognizedPreserved {
            raw: teacher_comments.to_string(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum TutorialSemanticField {
    TutorialDate,
    OverallLevel,
    TeacherReadOnly,
    Absent,
    InitialSpeaking,
    InitialUseOfEnglish,
    InitialWriting,
    InitialListening,
    CurrentSpeaking,
    CurrentUseOfEnglish,
    CurrentWriting,
    CurrentListening,
    Reading,
    AssessmentListening,
    AssessmentReading,
    AssessmentWriting,
    AssessmentSpeaking,
    AssessmentVocabulary,
    AssessmentGrammar,
    AssessmentPronunciation,
    Aims,
    TeacherComments,
    AdditionalComments,
    InitialCourseType,
    ExamIntent,
    ExamType,
    ExamWhen,
}

pub const UI1C_FORM_FIELDS: &[TutorialSemanticField] = &[
    TutorialSemanticField::TutorialDate,
    TutorialSemanticField::OverallLevel,
    TutorialSemanticField::TeacherReadOnly,
    TutorialSemanticField::Absent,
    TutorialSemanticField::InitialSpeaking,
    TutorialSemanticField::InitialUseOfEnglish,
    TutorialSemanticField::InitialWriting,
    TutorialSemanticField::InitialListening,
    TutorialSemanticField::CurrentSpeaking,
    TutorialSemanticField::CurrentUseOfEnglish,
    TutorialSemanticField::CurrentWriting,
    TutorialSemanticField::CurrentListening,
    TutorialSemanticField::Reading,
    TutorialSemanticField::AssessmentListening,
    TutorialSemanticField::AssessmentReading,
    TutorialSemanticField::AssessmentWriting,
    TutorialSemanticField::AssessmentSpeaking,
    TutorialSemanticField::AssessmentVocabulary,
    TutorialSemanticField::AssessmentGrammar,
    TutorialSemanticField::AssessmentPronunciation,
    TutorialSemanticField::Aims,
    TutorialSemanticField::TeacherComments,
    TutorialSemanticField::AdditionalComments,
    TutorialSemanticField::InitialCourseType,
    TutorialSemanticField::ExamIntent,
    TutorialSemanticField::ExamType,
    TutorialSemanticField::ExamWhen,
];

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FieldDisposition {
    Editable,
    ReadOnly,
    HiddenPreserved,
    Inapplicable,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct TutorialFieldRule {
    pub field: TutorialSemanticField,
    pub disposition: FieldDisposition,
}

pub fn tutorial_field_disposition(
    tutorial_type: TutorialType,
    field: TutorialSemanticField,
) -> FieldDisposition {
    use FieldDisposition::{Editable, HiddenPreserved, Inapplicable, ReadOnly};
    use TutorialSemanticField::*;

    match field {
        TutorialDate | OverallLevel => Editable,
        TeacherReadOnly => ReadOnly,
        Absent => match tutorial_type {
            TutorialType::Standard => Editable,
            TutorialType::Initial | TutorialType::Final => HiddenPreserved,
        },
        InitialSpeaking | InitialUseOfEnglish | InitialWriting | InitialListening => {
            match tutorial_type {
                TutorialType::Initial | TutorialType::Final => Editable,
                TutorialType::Standard => Inapplicable,
            }
        }
        CurrentSpeaking | CurrentUseOfEnglish | CurrentWriting | CurrentListening | Reading => {
            match tutorial_type {
                TutorialType::Standard | TutorialType::Final => Editable,
                TutorialType::Initial => Inapplicable,
            }
        }
        AssessmentListening
        | AssessmentReading
        | AssessmentWriting
        | AssessmentSpeaking
        | AssessmentVocabulary
        | AssessmentGrammar
        | AssessmentPronunciation
        | Aims => match tutorial_type {
            TutorialType::Standard => Editable,
            TutorialType::Initial | TutorialType::Final => Inapplicable,
        },
        TeacherComments => match tutorial_type {
            TutorialType::Standard | TutorialType::Final => Editable,
            TutorialType::Initial => HiddenPreserved,
        },
        AdditionalComments => match tutorial_type {
            TutorialType::Final => Editable,
            TutorialType::Initial | TutorialType::Standard => Inapplicable,
        },
        InitialCourseType => match tutorial_type {
            TutorialType::Initial => Editable,
            TutorialType::Standard | TutorialType::Final => Inapplicable,
        },
        ExamIntent | ExamType | ExamWhen => match tutorial_type {
            TutorialType::Initial => HiddenPreserved,
            TutorialType::Standard | TutorialType::Final => Inapplicable,
        },
    }
}

pub fn tutorial_field_rules(tutorial_type: TutorialType) -> Vec<TutorialFieldRule> {
    UI1C_FORM_FIELDS
        .iter()
        .copied()
        .map(|field| TutorialFieldRule {
            field,
            disposition: tutorial_field_disposition(tutorial_type, field),
        })
        .collect()
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum DraftValidationCode {
    InvalidDate,
    InvalidOption,
    FieldNotApplicable,
    TextTooLong,
    LevelRegression,
    InvariantViolation,
    NoActiveDraft,
    InternalStateError,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DraftValidationSeverity {
    Error,
    Warning,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DraftValidationIssue {
    pub code: DraftValidationCode,
    pub field: Option<TutorialSemanticField>,
    pub severity: DraftValidationSeverity,
    pub message: String,
    pub prior_value: Option<String>,
    pub candidate_value: Option<String>,
}

impl DraftValidationIssue {
    pub fn error(
        code: DraftValidationCode,
        field: Option<TutorialSemanticField>,
        message: impl Into<String>,
        prior_value: Option<String>,
        candidate_value: Option<String>,
    ) -> Self {
        Self {
            code,
            field,
            severity: DraftValidationSeverity::Error,
            message: message.into(),
            prior_value,
            candidate_value,
        }
    }

    pub fn internal(message: impl Into<String>) -> Self {
        Self::error(
            DraftValidationCode::InternalStateError,
            None,
            message,
            None,
            None,
        )
    }

    pub fn no_active_draft() -> Self {
        Self::error(
            DraftValidationCode::NoActiveDraft,
            None,
            "no active tutorial draft",
            None,
            None,
        )
    }
}

impl std::fmt::Display for DraftValidationIssue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.message)
    }
}

impl std::error::Error for DraftValidationIssue {}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct LevelRegressionBaseline {
    pub overall_level: Option<CefrLevel>,
    pub initial_scores: SkillScores,
    pub current_scores: SkillScores,
    pub reading: Option<CefrLevel>,
}

impl LevelRegressionBaseline {
    pub fn is_empty(&self) -> bool {
        self.overall_level.is_none()
            && self.initial_scores == SkillScores::default()
            && self.current_scores == SkillScores::default()
            && self.reading.is_none()
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct TeacherRef {
    pub teacher_id: Option<i64>,
    pub teacher_name: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct RichTextValue {
    /// Source/editor HTML retained by archival/source models for fidelity.
    pub html: String,
    /// Normalized plain text retained by archival/source models.
    pub text: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TutorialIdentity {
    /// Canonical identity from GEL's tutorial-list API.
    pub tutorial_id: i64,
    pub student_uid: i64,
    pub tutorial_ts: i64,
    pub tutorial_type: TutorialType,
}

/// Opaque New-form teacher authority. Production code can obtain this only
/// from the validated N2b New-form parser; there is deliberately no public
/// integer constructor or mutation API.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ValidatedNewFormTeacher {
    teacher_id: i64,
    student_uid: i64,
    tutorial_type_raw: String,
}

impl ValidatedNewFormTeacher {
    pub(crate) fn from_validated_hidden_control(
        teacher_id: i64,
        student_uid: i64,
        tutorial_type_raw: &str,
    ) -> Result<Self> {
        if teacher_id <= 0 || student_uid <= 0 {
            bail!("validated New-form teacher authority must bind positive IDs");
        }
        Ok(Self {
            teacher_id,
            student_uid,
            tutorial_type_raw: tutorial_type_raw.to_string(),
        })
    }

    pub fn teacher_id(&self) -> i64 {
        self.teacher_id
    }

    pub fn student_uid(&self) -> i64 {
        self.student_uid
    }

    pub fn tutorial_type_raw(&self) -> &str {
        &self.tutorial_type_raw
    }
}

/// Explicit origin of an editable tutorial draft.
///
/// `Revision` means the draft reconstructs one historical GEL tutorial. `New`
/// means it is a new tutorial draft and any `prepopulation_source` is provenance
/// only; it is not the identity of the tutorial that will eventually be created.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum DraftOrigin {
    /// A Revision is bound to the historical tutorial identity and teacher.
    /// Both values are immutable submission authority: editing the semantic
    /// `teacher` field cannot change attribution because validation requires it
    /// to remain equal to `source_teacher_id`.
    Revision {
        source: TutorialIdentity,
        source_teacher_id: i64,
    },
    /// A New tutorial has no authoritative created GEL identity yet.  The
    /// optional prepopulation source is provenance only (and is absent for a
    /// first-ever tutorial).  Teacher authority comes from the validated New
    /// form fetched under the authenticated session.
    New {
        prepopulation_source: Option<TutorialIdentity>,
        form_teacher: ValidatedNewFormTeacher,
        level_regression_baseline: LevelRegressionBaseline,
    },
}

impl DraftOrigin {
    pub fn revision_source(&self) -> Option<&TutorialIdentity> {
        match self {
            Self::Revision { source, .. } => Some(source),
            Self::New { .. } => None,
        }
    }

    pub fn prepopulation_source(&self) -> Option<&TutorialIdentity> {
        match self {
            Self::New {
                prepopulation_source,
                ..
            } => prepopulation_source.as_ref(),
            Self::Revision { .. } => None,
        }
    }

    pub fn level_regression_baseline(&self) -> Option<&LevelRegressionBaseline> {
        match self {
            Self::New {
                level_regression_baseline,
                ..
            } => Some(level_regression_baseline),
            Self::Revision { .. } => None,
        }
    }

    /// Authoritative created GEL identity. New drafts deliberately have none
    /// until a future successful create is followed by fresh server readback.
    pub fn authoritative_identity(&self) -> Option<&TutorialIdentity> {
        self.revision_source()
    }

    /// Immutable teacher attribution authority bound to this draft origin.
    pub fn authoritative_teacher_id(&self) -> i64 {
        match self {
            Self::Revision {
                source_teacher_id, ..
            } => *source_teacher_id,
            Self::New { form_teacher, .. } => form_teacher.teacher_id(),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FieldSource {
    Summary,
    EditForm,
    EditFormInlineJs,
    EditFormContentEditable,
    NewForm,
    PrepopulationSource,
    Derived,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Discrepancy {
    HistoricalEditAbsentMismatch,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct BooleanFieldProvenance {
    pub authoritative_value: bool,
    pub authoritative_source: FieldSource,
    pub edit_form_value: Option<bool>,
    pub discrepancy: Option<Discrepancy>,
}

/// Source-only metadata retained alongside the editable semantic values.
///
/// These fields are provenance, not alternate editable values. POST mapping
/// must never read them to decide the submitted semantic value.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TutorialFormProvenance {
    pub absent: BooleanFieldProvenance,
    pub overall_level_source_raw: Option<String>,
    pub aims_source_html: Option<String>,
}

/// Normalized archived state supplied to the revision constructor.
///
/// This is deliberately semantic: SQL column names and opaque GEL form IDs do
/// not leak into the domain model. The future SQLite repository is responsible
/// for constructing this value from the archive schema.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArchivedTutorial {
    pub identity: TutorialIdentity,
    /// Authority for associating this normalized historical state with the
    /// canonical tutorial ID. Divergent/unknown collision state is never
    /// sufficient for revision-by-ID.
    pub state_authority: HistoricalStateAuthority,
    pub tutorial_date: NaiveDate,
    pub teacher: TeacherRef,
    pub absent: bool,
    pub overall_level_raw: String,
    pub initial_scores: SkillScores,
    pub current_scores: SkillScores,
    pub reading: Option<CefrLevel>,
    pub self_assessment: SelfAssessment,
    pub exam: ExamIntent,
    pub aims: RichTextValue,
    pub teacher_comments: String,
    pub additional_comments: String,
}

/// Editable semantic state.
///
/// A semantic value has exactly one writable representation here. Literal GEL
/// source spellings/HTML live only in `provenance` and are never fallback input
/// to POST serialization.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TutorialFormState {
    pub origin: DraftOrigin,
    pub student_uid: i64,
    pub tutorial_type: TutorialType,
    pub tutorial_date: NaiveDate,
    pub teacher: TeacherRef,
    pub absent: bool,
    pub overall_level: Option<CefrLevel>,
    pub initial_scores: SkillScores,
    pub current_scores: SkillScores,
    /// Current Reading level. Applies to Standard and Final. GEL has no
    /// corresponding Initial Reading field.
    pub reading: Option<CefrLevel>,
    pub self_assessment: SelfAssessment,
    pub exam: ExamIntent,
    /// Editable Aims value is plain text. Source editor HTML is provenance only.
    pub aims: String,
    pub teacher_comments: String,
    pub additional_comments: String,
    pub provenance: TutorialFormProvenance,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FourSkill {
    Speaking,
    UseOfEnglish,
    Writing,
    Listening,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AssessmentSkill {
    Listening,
    Reading,
    Writing,
    Speaking,
    Vocabulary,
    Grammar,
    Pronunciation,
}

/// UI-safe semantic edit allowlist. This intentionally has no teacher, origin,
/// tutorial identity/timestamp, student identity, tutorial-type, opaque GEL field,
/// raw POST, or hidden legacy exam-field mutation variant.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum TutorialDraftEdit {
    SetTutorialDate {
        value: String,
    },
    SetAbsent {
        value: bool,
    },
    SetOverallLevel {
        value: Option<String>,
    },
    SetInitialLevel {
        skill: FourSkill,
        value: Option<String>,
    },
    SetCurrentLevel {
        skill: FourSkill,
        value: Option<String>,
    },
    SetReading {
        value: Option<String>,
    },
    SetAssessment {
        skill: AssessmentSkill,
        value: Option<String>,
    },
    SetAims {
        value: String,
    },
    SetTeacherComments {
        value: String,
    },
    SetAdditionalComments {
        value: String,
    },
    SetInitialCourseType {
        value: String,
    },
}

impl TutorialDraftEdit {
    pub fn semantic_field(&self) -> TutorialSemanticField {
        match self {
            Self::SetTutorialDate { .. } => TutorialSemanticField::TutorialDate,
            Self::SetAbsent { .. } => TutorialSemanticField::Absent,
            Self::SetOverallLevel { .. } => TutorialSemanticField::OverallLevel,
            Self::SetInitialLevel { skill, .. } => match skill {
                FourSkill::Speaking => TutorialSemanticField::InitialSpeaking,
                FourSkill::UseOfEnglish => TutorialSemanticField::InitialUseOfEnglish,
                FourSkill::Writing => TutorialSemanticField::InitialWriting,
                FourSkill::Listening => TutorialSemanticField::InitialListening,
            },
            Self::SetCurrentLevel { skill, .. } => match skill {
                FourSkill::Speaking => TutorialSemanticField::CurrentSpeaking,
                FourSkill::UseOfEnglish => TutorialSemanticField::CurrentUseOfEnglish,
                FourSkill::Writing => TutorialSemanticField::CurrentWriting,
                FourSkill::Listening => TutorialSemanticField::CurrentListening,
            },
            Self::SetReading { .. } => TutorialSemanticField::Reading,
            Self::SetAssessment { skill, .. } => match skill {
                AssessmentSkill::Listening => TutorialSemanticField::AssessmentListening,
                AssessmentSkill::Reading => TutorialSemanticField::AssessmentReading,
                AssessmentSkill::Writing => TutorialSemanticField::AssessmentWriting,
                AssessmentSkill::Speaking => TutorialSemanticField::AssessmentSpeaking,
                AssessmentSkill::Vocabulary => TutorialSemanticField::AssessmentVocabulary,
                AssessmentSkill::Grammar => TutorialSemanticField::AssessmentGrammar,
                AssessmentSkill::Pronunciation => TutorialSemanticField::AssessmentPronunciation,
            },
            Self::SetAims { .. } => TutorialSemanticField::Aims,
            Self::SetTeacherComments { .. } => TutorialSemanticField::TeacherComments,
            Self::SetAdditionalComments { .. } => TutorialSemanticField::AdditionalComments,
            Self::SetInitialCourseType { .. } => TutorialSemanticField::InitialCourseType,
        }
    }
}

/// Apply one typed user edit to a semantic draft using candidate-before-commit
/// semantics. The input is never mutated; callers receive a fully validated new
/// state or one stable structured issue.
pub fn apply_tutorial_draft_edit(
    current: &TutorialFormState,
    edit: TutorialDraftEdit,
) -> std::result::Result<TutorialFormState, DraftValidationIssue> {
    let field = edit.semantic_field();
    let disposition = tutorial_field_disposition(current.tutorial_type, field);
    if disposition != FieldDisposition::Editable {
        return Err(DraftValidationIssue::error(
            DraftValidationCode::FieldNotApplicable,
            Some(field),
            format!(
                "field {field:?} is not editable for {:?} tutorials ({disposition:?})",
                current.tutorial_type
            ),
            semantic_field_value(current, field),
            edit_candidate_value(&edit),
        ));
    }

    let prior_value = semantic_field_value(current, field);
    let mut candidate = current.clone();
    match edit {
        TutorialDraftEdit::SetTutorialDate { value } => {
            candidate.tutorial_date =
                NaiveDate::parse_from_str(&value, "%Y-%m-%d").map_err(|_| {
                    DraftValidationIssue::error(
                        DraftValidationCode::InvalidDate,
                        Some(field),
                        "tutorial date must be YYYY-MM-DD",
                        prior_value.clone(),
                        Some(value),
                    )
                })?;
        }
        TutorialDraftEdit::SetAbsent { value } => candidate.absent = value,
        TutorialDraftEdit::SetOverallLevel { value } => {
            candidate.overall_level = parse_edit_level(field, prior_value.clone(), value)?;
        }
        TutorialDraftEdit::SetInitialLevel { skill, value } => {
            let parsed = parse_edit_level(field, prior_value.clone(), value)?;
            set_edit_skill_level(&mut candidate.initial_scores, skill, parsed);
        }
        TutorialDraftEdit::SetCurrentLevel { skill, value } => {
            let parsed = parse_edit_level(field, prior_value.clone(), value)?;
            set_edit_skill_level(&mut candidate.current_scores, skill, parsed);
        }
        TutorialDraftEdit::SetReading { value } => {
            candidate.reading = parse_edit_level(field, prior_value.clone(), value)?;
        }
        TutorialDraftEdit::SetAssessment { skill, value } => {
            let parsed = parse_edit_assessment(field, prior_value.clone(), value)?;
            match skill {
                AssessmentSkill::Listening => candidate.self_assessment.listening = parsed,
                AssessmentSkill::Reading => candidate.self_assessment.reading = parsed,
                AssessmentSkill::Writing => candidate.self_assessment.writing = parsed,
                AssessmentSkill::Speaking => candidate.self_assessment.speaking = parsed,
                AssessmentSkill::Vocabulary => candidate.self_assessment.vocabulary = parsed,
                AssessmentSkill::Grammar => candidate.self_assessment.grammar = parsed,
                AssessmentSkill::Pronunciation => candidate.self_assessment.pronunciation = parsed,
            }
        }
        TutorialDraftEdit::SetAims { value } => candidate.aims = value,
        TutorialDraftEdit::SetTeacherComments { value } => {
            if value.chars().count() > gel_fields::TEACHER_COMMENTS_MAX_CHARS {
                return Err(DraftValidationIssue::error(
                    DraftValidationCode::TextTooLong,
                    Some(field),
                    format!(
                        "teacher comments are limited to {} Unicode scalar values",
                        gel_fields::TEACHER_COMMENTS_MAX_CHARS
                    ),
                    prior_value,
                    Some(value),
                ));
            }
            candidate.teacher_comments = value;
        }
        TutorialDraftEdit::SetAdditionalComments { value } => {
            if value.chars().count() > gel_fields::ADDITIONAL_COMMENTS_MAX_CHARS {
                return Err(DraftValidationIssue::error(
                    DraftValidationCode::TextTooLong,
                    Some(field),
                    format!(
                        "additional comments are limited to {} Unicode scalar values",
                        gel_fields::ADDITIONAL_COMMENTS_MAX_CHARS
                    ),
                    prior_value,
                    Some(value),
                ));
            }
            candidate.additional_comments = value;
        }
        TutorialDraftEdit::SetInitialCourseType { value } => {
            let course_type = InitialCourseType::parse_exact(&value).ok_or_else(|| {
                DraftValidationIssue::error(
                    DraftValidationCode::InvalidOption,
                    Some(field),
                    format!("unknown Initial course type: {value}"),
                    prior_value.clone(),
                    Some(value.clone()),
                )
            })?;
            candidate.teacher_comments = course_type.storage_value().to_string();
        }
    }

    validate_semantic_form_state(&candidate).map_err(|error| {
        DraftValidationIssue::error(
            DraftValidationCode::InvariantViolation,
            Some(field),
            format!("semantic draft invariant rejected edit: {error}"),
            prior_value.clone(),
            semantic_field_value(&candidate, field),
        )
    })?;
    validate_new_level_regression(current, &candidate, field)?;
    Ok(candidate)
}

fn parse_edit_level(
    field: TutorialSemanticField,
    prior_value: Option<String>,
    value: Option<String>,
) -> std::result::Result<Option<CefrLevel>, DraftValidationIssue> {
    let Some(value) = normalized_edit_text(value) else {
        return Ok(None);
    };
    CefrLevel::parse(&value).map(Some).ok_or_else(|| {
        DraftValidationIssue::error(
            DraftValidationCode::InvalidOption,
            Some(field),
            format!("unknown CEFR level: {value}"),
            prior_value,
            Some(value),
        )
    })
}

fn parse_edit_assessment(
    field: TutorialSemanticField,
    prior_value: Option<String>,
    value: Option<String>,
) -> std::result::Result<Option<AssessmentValue>, DraftValidationIssue> {
    let Some(value) = normalized_edit_text(value) else {
        return Ok(None);
    };
    AssessmentValue::parse(&value).map(Some).ok_or_else(|| {
        DraftValidationIssue::error(
            DraftValidationCode::InvalidOption,
            Some(field),
            format!("unknown assessment value: {value}"),
            prior_value,
            Some(value),
        )
    })
}

fn normalized_edit_text(value: Option<String>) -> Option<String> {
    value
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn set_edit_skill_level(scores: &mut SkillScores, skill: FourSkill, value: Option<CefrLevel>) {
    match skill {
        FourSkill::Speaking => scores.speaking = value,
        FourSkill::UseOfEnglish => scores.use_of_english = value,
        FourSkill::Writing => scores.writing = value,
        FourSkill::Listening => scores.listening = value,
    }
}

fn edit_candidate_value(edit: &TutorialDraftEdit) -> Option<String> {
    match edit {
        TutorialDraftEdit::SetTutorialDate { value }
        | TutorialDraftEdit::SetAims { value }
        | TutorialDraftEdit::SetTeacherComments { value }
        | TutorialDraftEdit::SetAdditionalComments { value }
        | TutorialDraftEdit::SetInitialCourseType { value } => Some(value.clone()),
        TutorialDraftEdit::SetAbsent { value } => Some(value.to_string()),
        TutorialDraftEdit::SetOverallLevel { value }
        | TutorialDraftEdit::SetInitialLevel { value, .. }
        | TutorialDraftEdit::SetCurrentLevel { value, .. }
        | TutorialDraftEdit::SetReading { value }
        | TutorialDraftEdit::SetAssessment { value, .. } => value.clone(),
    }
}

fn semantic_field_value(state: &TutorialFormState, field: TutorialSemanticField) -> Option<String> {
    use TutorialSemanticField::*;
    match field {
        TutorialDate => Some(state.tutorial_date.format("%Y-%m-%d").to_string()),
        OverallLevel => state
            .overall_level
            .map(|value| value.form_value().to_string()),
        TeacherReadOnly => state.teacher.teacher_name.clone(),
        Absent => Some(state.absent.to_string()),
        InitialSpeaking => state.initial_scores.speaking.map(level_string),
        InitialUseOfEnglish => state.initial_scores.use_of_english.map(level_string),
        InitialWriting => state.initial_scores.writing.map(level_string),
        InitialListening => state.initial_scores.listening.map(level_string),
        CurrentSpeaking => state.current_scores.speaking.map(level_string),
        CurrentUseOfEnglish => state.current_scores.use_of_english.map(level_string),
        CurrentWriting => state.current_scores.writing.map(level_string),
        CurrentListening => state.current_scores.listening.map(level_string),
        Reading => state.reading.map(level_string),
        AssessmentListening => state.self_assessment.listening.map(assessment_string),
        AssessmentReading => state.self_assessment.reading.map(assessment_string),
        AssessmentWriting => state.self_assessment.writing.map(assessment_string),
        AssessmentSpeaking => state.self_assessment.speaking.map(assessment_string),
        AssessmentVocabulary => state.self_assessment.vocabulary.map(assessment_string),
        AssessmentGrammar => state.self_assessment.grammar.map(assessment_string),
        AssessmentPronunciation => state.self_assessment.pronunciation.map(assessment_string),
        Aims => Some(state.aims.clone()),
        TeacherComments => Some(state.teacher_comments.clone()),
        AdditionalComments => Some(state.additional_comments.clone()),
        InitialCourseType => match initial_course_type_state(&state.teacher_comments) {
            InitialCourseTypeState::Unset => None,
            InitialCourseTypeState::Recognized { value } => Some(value.storage_value().to_string()),
            InitialCourseTypeState::UnrecognizedPreserved { raw } => Some(raw),
        },
        ExamIntent => state.exam.intent.clone(),
        ExamType => state.exam.exam_type.clone(),
        ExamWhen => state.exam.when.clone(),
    }
}

fn level_string(value: CefrLevel) -> String {
    value.form_value().to_string()
}

fn assessment_string(value: AssessmentValue) -> String {
    value.ui_value().to_string()
}

fn validate_new_level_regression(
    current: &TutorialFormState,
    candidate: &TutorialFormState,
    field: TutorialSemanticField,
) -> std::result::Result<(), DraftValidationIssue> {
    let Some(baseline) = current.origin.level_regression_baseline() else {
        return Ok(());
    };
    let Some(floor) = baseline_level_for_field(baseline, field) else {
        return Ok(());
    };
    let Some(candidate_level) = semantic_level_for_field(candidate, field) else {
        return Ok(());
    };
    if candidate_level < floor {
        return Err(DraftValidationIssue::error(
            DraftValidationCode::LevelRegression,
            Some(field),
            format!(
                "New tutorial level regression: {} cannot be lower than latest authoritative {} for the same semantic field-role",
                candidate_level.form_value(),
                floor.form_value()
            ),
            Some(floor.form_value().to_string()),
            Some(candidate_level.form_value().to_string()),
        ));
    }
    Ok(())
}

fn baseline_level_for_field(
    baseline: &LevelRegressionBaseline,
    field: TutorialSemanticField,
) -> Option<CefrLevel> {
    use TutorialSemanticField::*;
    match field {
        OverallLevel => baseline.overall_level,
        InitialSpeaking => baseline.initial_scores.speaking,
        InitialUseOfEnglish => baseline.initial_scores.use_of_english,
        InitialWriting => baseline.initial_scores.writing,
        InitialListening => baseline.initial_scores.listening,
        CurrentSpeaking => baseline.current_scores.speaking,
        CurrentUseOfEnglish => baseline.current_scores.use_of_english,
        CurrentWriting => baseline.current_scores.writing,
        CurrentListening => baseline.current_scores.listening,
        Reading => baseline.reading,
        _ => None,
    }
}

fn semantic_level_for_field(
    state: &TutorialFormState,
    field: TutorialSemanticField,
) -> Option<CefrLevel> {
    use TutorialSemanticField::*;
    match field {
        OverallLevel => state.overall_level,
        InitialSpeaking => state.initial_scores.speaking,
        InitialUseOfEnglish => state.initial_scores.use_of_english,
        InitialWriting => state.initial_scores.writing,
        InitialListening => state.initial_scores.listening,
        CurrentSpeaking => state.current_scores.speaking,
        CurrentUseOfEnglish => state.current_scores.use_of_english,
        CurrentWriting => state.current_scores.writing,
        CurrentListening => state.current_scores.listening,
        Reading => state.reading,
        _ => None,
    }
}

/// Enforce tutorial-type and origin invariants independently of HTML parsing.
/// This protects later UI and POST layers from constructing cross-type state
/// that a valid GEL form could never represent.
pub fn validate_semantic_form_state(state: &TutorialFormState) -> Result<()> {
    if state.student_uid <= 0 {
        bail!(
            "semantic tutorial state has invalid student_uid {}",
            state.student_uid
        );
    }
    let teacher_id = state
        .teacher
        .teacher_id
        .context("semantic tutorial state has no teacher_id")?;
    if teacher_id <= 0 {
        bail!("semantic tutorial state has invalid teacher_id {teacher_id}");
    }

    match &state.origin {
        DraftOrigin::Revision {
            source,
            source_teacher_id,
        } => {
            if source.tutorial_id <= 0 || source.tutorial_ts <= 0 {
                bail!("revision source identity must contain positive tutorial_id and tutorial_ts");
            }
            if *source_teacher_id <= 0 {
                bail!("revision source teacher authority must be a positive teacher ID");
            }
            if source.student_uid != state.student_uid {
                bail!(
                    "revision source student UID mismatch: source={}, state={}",
                    source.student_uid,
                    state.student_uid
                );
            }
            if source.tutorial_type != state.tutorial_type {
                bail!(
                    "revision source tutorial type mismatch: source={:?}, state={:?}",
                    source.tutorial_type,
                    state.tutorial_type
                );
            }
            if teacher_id != *source_teacher_id {
                bail!(
                    "revision teacher attribution is immutable: source={}, state={}",
                    source_teacher_id,
                    teacher_id
                );
            }
        }
        DraftOrigin::New {
            prepopulation_source,
            form_teacher,
            level_regression_baseline,
        } => {
            if teacher_id != form_teacher.teacher_id() {
                bail!(
                    "new tutorial teacher attribution is immutable: form={}, state={}",
                    form_teacher.teacher_id(),
                    teacher_id
                );
            }
            if form_teacher.student_uid() != state.student_uid {
                bail!(
                    "new-form teacher authority student mismatch: form={}, state={}",
                    form_teacher.student_uid(),
                    state.student_uid
                );
            }
            if form_teacher.tutorial_type_raw() != state.tutorial_type.ttype() {
                bail!(
                    "new-form teacher authority tutorial type mismatch: form={}, state={}",
                    form_teacher.tutorial_type_raw(),
                    state.tutorial_type.ttype()
                );
            }
            if prepopulation_source.is_none() && !level_regression_baseline.is_empty() {
                bail!("first-ever New draft cannot carry a level-regression source baseline");
            }
            if let Some(source) = prepopulation_source {
                match source.tutorial_type {
                    TutorialType::Initial => {
                        require_empty_scores(
                            &level_regression_baseline.current_scores,
                            "Initial source regression current scores",
                        )?;
                        require_none(
                            level_regression_baseline.reading,
                            "Initial source regression Reading",
                        )?;
                    }
                    TutorialType::Standard => {
                        require_empty_scores(
                            &level_regression_baseline.initial_scores,
                            "Standard source regression initial scores",
                        )?;
                    }
                    TutorialType::Final => {}
                }
                if source.student_uid != state.student_uid {
                    bail!(
                        "new-draft prepopulation source student UID mismatch: source={}, state={}",
                        source.student_uid,
                        state.student_uid
                    );
                }
                if source.tutorial_id <= 0 || source.tutorial_ts <= 0 {
                    bail!("new-draft prepopulation source identity must be canonical when present");
                }
            }
        }
    }

    match state.tutorial_type {
        TutorialType::Initial => {
            require_empty_scores(&state.current_scores, "Initial current scores")?;
            require_none(state.reading, "Initial Reading")?;
            require_empty_assessment(&state.self_assessment, "Initial self-assessment")?;
            require_empty_text(&state.aims, "Initial Aims")?;
            require_empty_text(&state.additional_comments, "Initial additional comments")?;
        }
        TutorialType::Standard => {
            require_empty_scores(&state.initial_scores, "Standard initial scores")?;
            require_empty_exam(&state.exam, "Standard exam fields")?;
            require_empty_text(&state.additional_comments, "Standard additional comments")?;
        }
        TutorialType::Final => {
            require_empty_assessment(&state.self_assessment, "Final self-assessment")?;
            require_empty_exam(&state.exam, "Final exam fields")?;
            require_empty_text(&state.aims, "Final Aims")?;
        }
    }

    Ok(())
}

/// Construct semantic revision state only from a C1-validated historical edit
/// form. Raw parser output is deliberately not accepted at this boundary.
pub fn build_revision_form_state(
    archive: &ArchivedTutorial,
    edit: &ValidatedEditFormState,
) -> Result<TutorialFormState> {
    if !archive.state_authority.permits_revision_by_id() {
        let key = archive
            .state_authority
            .reconciliation_key
            .as_deref()
            .unwrap_or("none");
        bail!(
            "revision-by-ID blocked by historical state authority {:?} (reconciliation_key={key})",
            archive.state_authority.status
        );
    }

    let parsed_type = TutorialType::from_ttype(&edit.tutorial_type_raw)?;
    if parsed_type != archive.identity.tutorial_type {
        bail!(
            "tutorial type mismatch: archive={:?}, edit={:?}",
            archive.identity.tutorial_type,
            parsed_type
        );
    }

    let form_uid = edit
        .value_for_name(gel_fields::STUDENT_UID)
        .and_then(|value| value.parse::<i64>().ok())
        .context("validated historical edit form is missing a valid uid")?;
    if form_uid != archive.identity.student_uid {
        bail!(
            "student UID mismatch: archive={}, edit={}",
            archive.identity.student_uid,
            form_uid
        );
    }

    let tutorial_date_raw = edit
        .value_for_name(gel_fields::CUSTOM_DATE)
        .context("validated historical edit form is missing customdate")?;
    let tutorial_date = NaiveDate::parse_from_str(tutorial_date_raw, "%d-%m-%Y")
        .context("validated GEL customdate did not parse as DD-MM-YYYY")?;

    let edit_teacher = edit.teacher();
    let teacher_id = edit_teacher
        .teacher_id
        .context("validated historical edit form is missing teacher ID")?;
    let teacher = TeacherRef {
        teacher_id: Some(teacher_id),
        teacher_name: edit_teacher
            .teacher_name
            .clone()
            .or_else(|| archive.teacher.teacher_name.clone()),
    };

    let overall_level_source_raw = edit
        .raw_value_for_name(gel_fields::OVERALL_LEVEL)
        .context("validated historical edit form is missing overall level control")?
        .to_string();
    let overall_level = CefrLevel::parse(&overall_level_source_raw);

    let initial_scores = match parsed_type {
        TutorialType::Initial | TutorialType::Final => SkillScores {
            speaking: select_level(edit, gel_fields::INITIAL_SPEAKING),
            use_of_english: select_level(edit, gel_fields::INITIAL_USE_OF_ENGLISH),
            writing: select_level(edit, gel_fields::INITIAL_WRITING),
            listening: select_level(edit, gel_fields::INITIAL_LISTENING),
        },
        TutorialType::Standard => SkillScores::default(),
    };

    let current_scores = match parsed_type {
        TutorialType::Standard | TutorialType::Final => SkillScores {
            speaking: select_level(edit, gel_fields::SPEAKING),
            use_of_english: select_level(edit, gel_fields::USE_OF_ENGLISH),
            writing: select_level(edit, gel_fields::WRITING),
            listening: select_level(edit, gel_fields::LISTENING),
        },
        TutorialType::Initial => SkillScores::default(),
    };

    let reading = if gel_fields::field_applies_to(gel_fields::READING, parsed_type.ttype()) {
        select_level(edit, gel_fields::READING)
    } else {
        None
    };

    let self_assessment = if parsed_type == TutorialType::Standard {
        SelfAssessment {
            listening: assessment(edit, gel_fields::ASSESSMENT_LISTENING),
            reading: assessment(edit, gel_fields::ASSESSMENT_READING),
            writing: assessment(edit, gel_fields::ASSESSMENT_WRITING),
            speaking: assessment(edit, gel_fields::ASSESSMENT_SPEAKING),
            vocabulary: assessment(edit, gel_fields::ASSESSMENT_VOCABULARY),
            grammar: assessment(edit, gel_fields::ASSESSMENT_GRAMMAR),
            pronunciation: assessment(edit, gel_fields::ASSESSMENT_PRONUNCIATION),
        }
    } else {
        SelfAssessment::default()
    };

    let exam = if parsed_type == TutorialType::Initial {
        ExamIntent {
            intent: semantic_select_text(edit, gel_fields::EXAM_INTENT),
            exam_type: semantic_select_text(edit, gel_fields::EXAM_TYPE),
            when: semantic_select_text(edit, gel_fields::EXAM_WHEN),
        }
    } else {
        ExamIntent::default()
    };

    let (aims, aims_source_html) = if parsed_type == TutorialType::Standard {
        let source = edit_rich_text(edit, gel_fields::AIMS_EDITOR_ID)
            .context("validated Standard edit form is missing Aims editor")?;
        (source.text, Some(source.html))
    } else {
        (String::new(), None)
    };

    let teacher_comments = edit
        .raw_value_for_name(gel_fields::TEACHER_COMMENTS)
        .context("validated historical edit form is missing teacher comments")?
        .to_string();
    let additional_comments = if parsed_type == TutorialType::Final {
        edit.raw_value_for_name(gel_fields::ADDITIONAL_COMMENTS)
            .context("validated Final edit form is missing additional comments")?
            .to_string()
    } else {
        String::new()
    };

    // The 14-fixture audit established that the historical edit route is
    // intermittently wrong for `absent`. Summary/archive is authoritative for
    // revisions while the literal edit value remains visible in provenance.
    let edit_absent = edit
        .checkbox_checked(gel_fields::ABSENT)
        .context("validated historical edit form is missing absent checkbox state")?;
    let discrepancy =
        (edit_absent != archive.absent).then_some(Discrepancy::HistoricalEditAbsentMismatch);
    let absent_provenance = BooleanFieldProvenance {
        authoritative_value: archive.absent,
        authoritative_source: FieldSource::Summary,
        edit_form_value: Some(edit_absent),
        discrepancy,
    };

    let state = TutorialFormState {
        origin: DraftOrigin::Revision {
            source: archive.identity.clone(),
            source_teacher_id: teacher_id,
        },
        student_uid: archive.identity.student_uid,
        tutorial_type: parsed_type,
        tutorial_date,
        teacher,
        absent: archive.absent,
        overall_level,
        initial_scores,
        current_scores,
        reading,
        self_assessment,
        exam,
        aims,
        teacher_comments,
        additional_comments,
        provenance: TutorialFormProvenance {
            absent: absent_provenance,
            overall_level_source_raw: Some(overall_level_source_raw),
            aims_source_html,
        },
    };
    validate_semantic_form_state(&state)?;
    Ok(state)
}

/// Build a New semantic draft from the canonical N2c field-by-field
/// prepopulation contract. The latest tutorial, when present, is the source of
/// carried state; the validated New form supplies immutable teacher/type
/// authority, the New date default, and defaults for fields unavailable on the
/// source tutorial type.
pub fn build_new_form_state(
    latest: Option<&ArchivedTutorial>,
    form: &ValidatedNewTutorialForm,
) -> Result<TutorialFormState> {
    let tutorial_type = TutorialType::from_ttype(form.tutorial_type_raw())?;
    let student_uid = form.student_uid();

    if let Some(source) = latest {
        if source.identity.student_uid != student_uid {
            bail!(
                "new-draft latest source student UID mismatch: source={}, form={}",
                source.identity.student_uid,
                student_uid
            );
        }
        if source.identity.tutorial_id <= 0 || source.identity.tutorial_ts <= 0 {
            bail!("new-draft latest source identity must be canonical when present");
        }
    }

    let form_absent = new_form_bool(form, gel_fields::ABSENT)?;
    let form_overall = new_form_level(form, gel_fields::OVERALL_LEVEL);
    let form_initial = SkillScores {
        speaking: new_form_level(form, gel_fields::INITIAL_SPEAKING),
        use_of_english: new_form_level(form, gel_fields::INITIAL_USE_OF_ENGLISH),
        writing: new_form_level(form, gel_fields::INITIAL_WRITING),
        listening: new_form_level(form, gel_fields::INITIAL_LISTENING),
    };
    let form_current = SkillScores {
        speaking: new_form_level(form, gel_fields::SPEAKING),
        use_of_english: new_form_level(form, gel_fields::USE_OF_ENGLISH),
        writing: new_form_level(form, gel_fields::WRITING),
        listening: new_form_level(form, gel_fields::LISTENING),
    };
    let form_reading = new_form_level(form, gel_fields::READING);
    let form_assessment = SelfAssessment {
        listening: new_form_assessment(form, gel_fields::ASSESSMENT_LISTENING),
        reading: new_form_assessment(form, gel_fields::ASSESSMENT_READING),
        writing: new_form_assessment(form, gel_fields::ASSESSMENT_WRITING),
        speaking: new_form_assessment(form, gel_fields::ASSESSMENT_SPEAKING),
        vocabulary: new_form_assessment(form, gel_fields::ASSESSMENT_VOCABULARY),
        grammar: new_form_assessment(form, gel_fields::ASSESSMENT_GRAMMAR),
        pronunciation: new_form_assessment(form, gel_fields::ASSESSMENT_PRONUNCIATION),
    };
    let form_exam = ExamIntent {
        intent: new_form_text(form, gel_fields::EXAM_INTENT),
        exam_type: new_form_text(form, gel_fields::EXAM_TYPE),
        when: new_form_text(form, gel_fields::EXAM_WHEN),
    };
    let form_aims = new_form_text(form, gel_fields::AIMS).unwrap_or_default();
    let form_comments = new_form_text(form, gel_fields::TEACHER_COMMENTS).unwrap_or_default();
    let form_additional = new_form_text(form, gel_fields::ADDITIONAL_COMMENTS).unwrap_or_default();

    let overall_level = latest
        .and_then(|source| CefrLevel::parse(&source.overall_level_raw))
        .or(form_overall);
    let absent = latest.map_or(form_absent, |source| source.absent);
    let teacher_comments = latest
        .map(|source| source.teacher_comments.clone())
        .unwrap_or(form_comments);

    let (initial_scores, current_scores, reading, self_assessment, exam, aims, additional_comments) =
        match tutorial_type {
            TutorialType::Initial => {
                let initial = latest
                    .map(|source| project_initial_scores(source, &form_initial))
                    .unwrap_or(form_initial);
                let exam = match latest {
                    Some(source) if source.identity.tutorial_type == TutorialType::Initial => {
                        source.exam.clone()
                    }
                    _ => form_exam,
                };
                (
                    initial,
                    SkillScores::default(),
                    None,
                    SelfAssessment::default(),
                    exam,
                    String::new(),
                    String::new(),
                )
            }
            TutorialType::Standard => {
                let current = latest
                    .map(|source| project_current_scores(source, &form_current))
                    .unwrap_or(form_current);
                let reading = latest.and_then(|source| source.reading).or(form_reading);
                let self_assessment = match latest {
                    Some(source) if source.identity.tutorial_type == TutorialType::Standard => {
                        source.self_assessment.clone()
                    }
                    _ => form_assessment,
                };
                let aims = match latest {
                    Some(source) if source.identity.tutorial_type == TutorialType::Standard => {
                        source.aims.text.clone()
                    }
                    _ => form_aims,
                };
                (
                    SkillScores::default(),
                    current,
                    reading,
                    self_assessment,
                    ExamIntent::default(),
                    aims,
                    String::new(),
                )
            }
            TutorialType::Final => {
                let initial = latest
                    .map(|source| project_initial_scores(source, &form_initial))
                    .unwrap_or(form_initial);
                let current = latest
                    .map(|source| project_current_scores(source, &form_current))
                    .unwrap_or(form_current);
                let reading = latest.and_then(|source| source.reading).or(form_reading);
                let additional = match latest {
                    Some(source) if source.identity.tutorial_type == TutorialType::Final => {
                        source.additional_comments.clone()
                    }
                    _ => form_additional,
                };
                (
                    initial,
                    current,
                    reading,
                    SelfAssessment::default(),
                    ExamIntent::default(),
                    String::new(),
                    additional,
                )
            }
        };

    let teacher_id = form.teacher().teacher_id();
    let state = TutorialFormState {
        origin: DraftOrigin::New {
            prepopulation_source: latest.map(|source| source.identity.clone()),
            form_teacher: form.teacher().clone(),
            level_regression_baseline: latest
                .map(level_regression_baseline_from_source)
                .unwrap_or_default(),
        },
        student_uid,
        tutorial_type,
        tutorial_date: form.default_date(),
        teacher: TeacherRef {
            teacher_id: Some(teacher_id),
            teacher_name: None,
        },
        absent,
        overall_level,
        initial_scores,
        current_scores,
        reading,
        self_assessment,
        exam,
        aims,
        teacher_comments,
        additional_comments,
        provenance: TutorialFormProvenance {
            absent: BooleanFieldProvenance {
                authoritative_value: absent,
                authoritative_source: if latest.is_some() {
                    FieldSource::PrepopulationSource
                } else {
                    FieldSource::NewForm
                },
                edit_form_value: None,
                discrepancy: None,
            },
            overall_level_source_raw: latest
                .map(|source| source.overall_level_raw.clone())
                .or_else(|| new_form_raw(form, gel_fields::OVERALL_LEVEL).map(ToString::to_string)),
            aims_source_html: match latest {
                Some(source) if source.identity.tutorial_type == TutorialType::Standard => {
                    Some(source.aims.html.clone())
                }
                _ => None,
            },
        },
    };
    validate_semantic_form_state(&state)?;
    Ok(state)
}

fn level_regression_baseline_from_source(source: &ArchivedTutorial) -> LevelRegressionBaseline {
    let initial_scores = if matches!(
        source.identity.tutorial_type,
        TutorialType::Initial | TutorialType::Final
    ) {
        source.initial_scores.clone()
    } else {
        SkillScores::default()
    };
    let current_scores = if matches!(
        source.identity.tutorial_type,
        TutorialType::Standard | TutorialType::Final
    ) {
        source.current_scores.clone()
    } else {
        SkillScores::default()
    };
    let reading = if matches!(
        source.identity.tutorial_type,
        TutorialType::Standard | TutorialType::Final
    ) {
        source.reading
    } else {
        None
    };
    LevelRegressionBaseline {
        overall_level: CefrLevel::parse(&source.overall_level_raw),
        initial_scores,
        current_scores,
        reading,
    }
}

fn project_initial_scores(source: &ArchivedTutorial, defaults: &SkillScores) -> SkillScores {
    if !matches!(
        source.identity.tutorial_type,
        TutorialType::Initial | TutorialType::Final
    ) {
        return defaults.clone();
    }

    SkillScores {
        speaking: source.initial_scores.speaking.or(defaults.speaking),
        use_of_english: source
            .initial_scores
            .use_of_english
            .or(defaults.use_of_english),
        writing: source.initial_scores.writing.or(defaults.writing),
        listening: source.initial_scores.listening.or(defaults.listening),
    }
}

fn project_current_scores(source: &ArchivedTutorial, defaults: &SkillScores) -> SkillScores {
    if !matches!(
        source.identity.tutorial_type,
        TutorialType::Standard | TutorialType::Final
    ) {
        return defaults.clone();
    }

    SkillScores {
        speaking: source.current_scores.speaking.or(defaults.speaking),
        use_of_english: source
            .current_scores
            .use_of_english
            .or(defaults.use_of_english),
        writing: source.current_scores.writing.or(defaults.writing),
        listening: source.current_scores.listening.or(defaults.listening),
    }
}

fn new_form_raw<'a>(form: &'a ValidatedNewTutorialForm, field: &str) -> Option<&'a str> {
    form.control_status(field)
        .and_then(ParsedControlStatus::raw_value)
}

fn new_form_level(form: &ValidatedNewTutorialForm, field: &str) -> Option<CefrLevel> {
    new_form_raw(form, field).and_then(CefrLevel::parse)
}

fn new_form_assessment(form: &ValidatedNewTutorialForm, field: &str) -> Option<AssessmentValue> {
    new_form_raw(form, field).and_then(AssessmentValue::parse)
}

fn new_form_text(form: &ValidatedNewTutorialForm, field: &str) -> Option<String> {
    match form.control_status(field) {
        Some(ParsedControlStatus::PresentValue { raw_value }) => {
            let value = raw_value.trim();
            (!value.is_empty()).then(|| value.to_string())
        }
        Some(ParsedControlStatus::PresentUnset { .. })
        | Some(ParsedControlStatus::Missing)
        | Some(ParsedControlStatus::Malformed { .. })
        | None => None,
    }
}

fn new_form_bool(form: &ValidatedNewTutorialForm, field: &str) -> Result<bool> {
    match new_form_raw(form, field) {
        Some("true") => Ok(true),
        Some("false") => Ok(false),
        other => bail!("validated New-form boolean {field} has unexpected value {other:?}"),
    }
}

fn require_empty_scores(scores: &SkillScores, label: &str) -> Result<()> {
    if scores != &SkillScores::default() {
        bail!("{label} must be empty for this tutorial type");
    }
    Ok(())
}

fn require_empty_assessment(assessment: &SelfAssessment, label: &str) -> Result<()> {
    if assessment != &SelfAssessment::default() {
        bail!("{label} must be empty for this tutorial type");
    }
    Ok(())
}

fn require_empty_exam(exam: &ExamIntent, label: &str) -> Result<()> {
    if exam != &ExamIntent::default() {
        bail!("{label} must be empty for this tutorial type");
    }
    Ok(())
}

fn require_none<T>(value: Option<T>, label: &str) -> Result<()> {
    if value.is_some() {
        bail!("{label} is not applicable to this tutorial type");
    }
    Ok(())
}

fn require_empty_text(value: &str, label: &str) -> Result<()> {
    if !value.is_empty() {
        bail!("{label} must be empty for this tutorial type");
    }
    Ok(())
}

fn select_level(edit: &ValidatedEditFormState, field: &str) -> Option<CefrLevel> {
    edit.value_for_name(field).and_then(CefrLevel::parse)
}

fn assessment(edit: &ValidatedEditFormState, field: &str) -> Option<AssessmentValue> {
    edit.value_for_name(field).and_then(AssessmentValue::parse)
}

fn semantic_select_text(edit: &ValidatedEditFormState, field: &str) -> Option<String> {
    edit.value_for_name(field)
        .map(|value| value.trim().to_string())
}

fn edit_rich_text(edit: &ValidatedEditFormState, editor_id: &str) -> Option<RichTextValue> {
    Some(RichTextValue {
        html: edit.contenteditable_html_for_id(editor_id)?,
        text: edit.contenteditable_value_for_id(editor_id)?,
    })
}
