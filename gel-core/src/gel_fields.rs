//! @generated from canonical JSON contracts by tools/generate_contract_artifacts.py.
//! DO NOT EDIT BY HAND. Run `python tools/generate_contract_artifacts.py`.
//!
//! Opaque GEL field IDs belong here rather than in archive/domain/UI layers.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GelControlKind {
    Hidden,
    Text,
    Checkbox,
    Select,
    Textarea,
    RadioGroup,
    ContentEditablePlusHidden,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum GelValueValidationRule {
    None,
    PositiveI64,
    PositiveI64Option,
    TutorialTypeCode,
    GelDate,
    CheckboxBoolean,
}

#[derive(Debug, Clone, Copy)]
pub struct EditControlSpec {
    pub semantic_name: &'static str,
    pub field: &'static str,
    pub kind: GelControlKind,
    pub required: bool,
    pub allow_unset: bool,
    pub placeholder: Option<&'static str>,
    pub allowed_values: &'static [&'static str],
    pub validation_rule: GelValueValidationRule,
    pub editor_id: Option<&'static str>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SkillDimension {
    Speaking,
    UseOfEnglish,
    Writing,
    Listening,
    Reading,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SkillPhase {
    Initial,
    Current,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LevelFieldSpec {
    pub semantic_name: &'static str,
    pub field: &'static str,
    pub gel_field_id: u16,
    pub dimension: SkillDimension,
    pub phase: SkillPhase,
}

pub const TTYPE_STANDARD: &str = "0";
pub const TTYPE_FINAL: &str = "1";
pub const TTYPE_INITIAL: &str = "2";

pub const TEACHER_ID: &str = "tid";
pub const STUDENT_UID: &str = "uid";
pub const SOURCE_TIMESTAMP: &str = "datetime";
pub const TUTORIAL_TYPE: &str = "ttype";
pub const LANGUAGE: &str = "lang";
pub const ABSENT: &str = "absent";
pub const CUSTOM_DATE: &str = "customdate";
pub const OVERALL_LEVEL: &str = "dropdown-475";
pub const INITIAL_SPEAKING: &str = "dropdown-264";
pub const INITIAL_USE_OF_ENGLISH: &str = "dropdown-265";
pub const INITIAL_WRITING: &str = "dropdown-266";
pub const INITIAL_LISTENING: &str = "dropdown-267";
pub const SPEAKING: &str = "dropdown-233";
pub const USE_OF_ENGLISH: &str = "dropdown-234";
pub const WRITING: &str = "dropdown-235";
pub const LISTENING: &str = "dropdown-236";
pub const READING: &str = "dropdown-476";
pub const ASSESSMENT_LISTENING: &str = "sl-89";
pub const ASSESSMENT_READING: &str = "sr-89";
pub const ASSESSMENT_WRITING: &str = "sw-89";
pub const ASSESSMENT_SPEAKING: &str = "ss-89";
pub const ASSESSMENT_VOCABULARY: &str = "sv-89";
pub const ASSESSMENT_GRAMMAR: &str = "sg-89";
pub const ASSESSMENT_PRONUNCIATION: &str = "sp-89";
pub const AIMS: &str = "trecs-79";
pub const AIMS_EDITOR_ID: &str = "tcinput";
pub const TEACHER_COMMENTS: &str = "text-225";
pub const ADDITIONAL_COMMENTS: &str = "text-226";
pub const EXAM_INTENT: &str = "dropdown-413";
pub const EXAM_TYPE: &str = "dropdown-414";
pub const EXAM_WHEN: &str = "dropdown-415";

pub const SKILL_PLACEHOLDER: &str = "Please choose level";
pub const OVERALL_PLACEHOLDER: &str = "Choose...";
pub const EXAM_PLACEHOLDER: &str = "Please choose:";

pub const TEACHER_COMMENTS_MAX_CHARS: usize = 970;
pub const ADDITIONAL_COMMENTS_MAX_CHARS: usize = 600;

pub const SUMMARY_ACTIONS: &str = "Actions";
pub const SUMMARY_ROWS_OBSERVED: &[&str] = &[
    "Name",
    "ID",
    "Teacher",
    "Type",
    "absent",
    "Tutorial Overall Level",
    "Tutorial",
    "Initial Speaking",
    "Speaking",
    "Initial Use of English",
    "Use of English",
    "Initial Writing",
    "Writing",
    "Initial Listening",
    "Listening",
    "Reading",
    "Assessment",
    "Aims",
    "Teacher's Comments",
    "Additional Comments/Accommodation (under 18s only)",
    "Do you want to take an English proficiency exam?",
    "If yes, which exam?",
    "If yes, when do you want to take the exam?",
    "Actions",
];

/// Contract-derived historical edit-form validation metadata.
pub const EDIT_CONTROL_SPECS: &[EditControlSpec] = &[
    EditControlSpec {
        semantic_name: "teacher_id",
        field: TEACHER_ID,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::PositiveI64Option,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "student_uid",
        field: STUDENT_UID,
        kind: GelControlKind::Hidden,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::PositiveI64,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "source_timestamp",
        field: SOURCE_TIMESTAMP,
        kind: GelControlKind::Hidden,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::PositiveI64,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "tutorial_type",
        field: TUTORIAL_TYPE,
        kind: GelControlKind::Hidden,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::TutorialTypeCode,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "absent",
        field: ABSENT,
        kind: GelControlKind::Checkbox,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::CheckboxBoolean,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "tutorial_date",
        field: CUSTOM_DATE,
        kind: GelControlKind::Text,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::GelDate,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "overall_level",
        field: OVERALL_LEVEL,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Choose..."),
        allowed_values: &[
            "Ao: beginner",
            "A1-: elementary",
            "A1: elementary",
            "A1+: elementary",
            "A2-: pre-intermediate",
            "A2: pre-intermediate",
            "A2+: pre-intermediate",
            "B1-: intermediate",
            "B1: intermediate",
            "B1+: intermediate",
            "B2-: upper-intermediate",
            "B2: upper-intermediate",
            "B2+: upper-intermediate",
            "C1-: advanced",
            "C1: advanced",
            "C1+: advanced",
            "C2-: very advanced",
            "C2: very advanced",
            "C2+: very advanced",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "initial_speaking",
        field: INITIAL_SPEAKING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "initial_use_of_english",
        field: INITIAL_USE_OF_ENGLISH,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "initial_writing",
        field: INITIAL_WRITING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "initial_listening",
        field: INITIAL_LISTENING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "speaking",
        field: SPEAKING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "use_of_english",
        field: USE_OF_ENGLISH,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "writing",
        field: WRITING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "listening",
        field: LISTENING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "reading",
        field: READING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_listening",
        field: ASSESSMENT_LISTENING,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_reading",
        field: ASSESSMENT_READING,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_writing",
        field: ASSESSMENT_WRITING,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_speaking",
        field: ASSESSMENT_SPEAKING,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_vocabulary",
        field: ASSESSMENT_VOCABULARY,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_grammar",
        field: ASSESSMENT_GRAMMAR,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_pronunciation",
        field: ASSESSMENT_PRONUNCIATION,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "aims",
        field: AIMS,
        kind: GelControlKind::ContentEditablePlusHidden,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: Some("tcinput"),
    },
    EditControlSpec {
        semantic_name: "teacher_comments",
        field: TEACHER_COMMENTS,
        kind: GelControlKind::Textarea,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "additional_comments",
        field: ADDITIONAL_COMMENTS,
        kind: GelControlKind::Textarea,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "exam_intent",
        field: EXAM_INTENT,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose:"),
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "exam_type",
        field: EXAM_TYPE,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose:"),
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "exam_when",
        field: EXAM_WHEN,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose:"),
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
];

pub fn edit_control_spec(field: &str) -> Option<&'static EditControlSpec> {
    EDIT_CONTROL_SPECS.iter().find(|spec| spec.field == field)
}

/// Contract-derived New-tutorial form validation metadata.
/// New remains structurally distinct from Revision: datetime is forbidden and tid is hidden.
pub const NEW_CONTROL_SPECS: &[EditControlSpec] = &[
    EditControlSpec {
        semantic_name: "teacher_id",
        field: TEACHER_ID,
        kind: GelControlKind::Hidden,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::PositiveI64,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "student_uid",
        field: STUDENT_UID,
        kind: GelControlKind::Hidden,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::PositiveI64,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "tutorial_type",
        field: TUTORIAL_TYPE,
        kind: GelControlKind::Hidden,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::TutorialTypeCode,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "absent",
        field: ABSENT,
        kind: GelControlKind::Checkbox,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::CheckboxBoolean,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "tutorial_date",
        field: CUSTOM_DATE,
        kind: GelControlKind::Text,
        required: true,
        allow_unset: false,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::GelDate,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "overall_level",
        field: OVERALL_LEVEL,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Choose..."),
        allowed_values: &[
            "Ao: beginner",
            "A1-: elementary",
            "A1: elementary",
            "A1+: elementary",
            "A2-: pre-intermediate",
            "A2: pre-intermediate",
            "A2+: pre-intermediate",
            "B1-: intermediate",
            "B1: intermediate",
            "B1+: intermediate",
            "B2-: upper-intermediate",
            "B2: upper-intermediate",
            "B2+: upper-intermediate",
            "C1-: advanced",
            "C1: advanced",
            "C1+: advanced",
            "C2-: very advanced",
            "C2: very advanced",
            "C2+: very advanced",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "initial_speaking",
        field: INITIAL_SPEAKING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "initial_use_of_english",
        field: INITIAL_USE_OF_ENGLISH,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "initial_writing",
        field: INITIAL_WRITING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "initial_listening",
        field: INITIAL_LISTENING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "speaking",
        field: SPEAKING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "use_of_english",
        field: USE_OF_ENGLISH,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "writing",
        field: WRITING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "listening",
        field: LISTENING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "reading",
        field: READING,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose level"),
        allowed_values: &[
            "A0", "A1-", "A1", "A1+", "A2-", "A2", "A2+", "B1-", "B1", "B1+", "B2-", "B2", "B2+",
            "C1-", "C1", "C1+", "C2-", "C2", "C2+",
        ],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_listening",
        field: ASSESSMENT_LISTENING,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_reading",
        field: ASSESSMENT_READING,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_writing",
        field: ASSESSMENT_WRITING,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_speaking",
        field: ASSESSMENT_SPEAKING,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_vocabulary",
        field: ASSESSMENT_VOCABULARY,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_grammar",
        field: ASSESSMENT_GRAMMAR,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "assessment_pronunciation",
        field: ASSESSMENT_PRONUNCIATION,
        kind: GelControlKind::RadioGroup,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &["1", "2", "3"],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "aims",
        field: AIMS,
        kind: GelControlKind::ContentEditablePlusHidden,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: Some("tcinput"),
    },
    EditControlSpec {
        semantic_name: "teacher_comments",
        field: TEACHER_COMMENTS,
        kind: GelControlKind::Textarea,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "additional_comments",
        field: ADDITIONAL_COMMENTS,
        kind: GelControlKind::Textarea,
        required: true,
        allow_unset: true,
        placeholder: None,
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "exam_intent",
        field: EXAM_INTENT,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose:"),
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "exam_type",
        field: EXAM_TYPE,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose:"),
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
    EditControlSpec {
        semantic_name: "exam_when",
        field: EXAM_WHEN,
        kind: GelControlKind::Select,
        required: true,
        allow_unset: true,
        placeholder: Some("Please choose:"),
        allowed_values: &[],
        validation_rule: GelValueValidationRule::None,
        editor_id: None,
    },
];

pub fn new_control_spec(field: &str) -> Option<&'static EditControlSpec> {
    NEW_CONTROL_SPECS.iter().find(|spec| spec.field == field)
}

pub const NEW_FORBIDDEN_FIELDS: &[&str] = &[SOURCE_TIMESTAMP];

pub const NEW_FORM_ACTION_PATH: &str = "/study/tutorials/process";
pub const NEW_FORM_METHOD: &str = "POST";

/// Canonical field-identity map for CEFR level controls. Semantic provenance
/// is determined by field ID/role only, never by equality of field values.
pub const LEVEL_FIELD_SPECS: &[LevelFieldSpec] = &[
    LevelFieldSpec {
        semantic_name: "initial_speaking",
        field: INITIAL_SPEAKING,
        gel_field_id: 264,
        dimension: SkillDimension::Speaking,
        phase: SkillPhase::Initial,
    },
    LevelFieldSpec {
        semantic_name: "initial_use_of_english",
        field: INITIAL_USE_OF_ENGLISH,
        gel_field_id: 265,
        dimension: SkillDimension::UseOfEnglish,
        phase: SkillPhase::Initial,
    },
    LevelFieldSpec {
        semantic_name: "initial_writing",
        field: INITIAL_WRITING,
        gel_field_id: 266,
        dimension: SkillDimension::Writing,
        phase: SkillPhase::Initial,
    },
    LevelFieldSpec {
        semantic_name: "initial_listening",
        field: INITIAL_LISTENING,
        gel_field_id: 267,
        dimension: SkillDimension::Listening,
        phase: SkillPhase::Initial,
    },
    LevelFieldSpec {
        semantic_name: "speaking",
        field: SPEAKING,
        gel_field_id: 233,
        dimension: SkillDimension::Speaking,
        phase: SkillPhase::Current,
    },
    LevelFieldSpec {
        semantic_name: "use_of_english",
        field: USE_OF_ENGLISH,
        gel_field_id: 234,
        dimension: SkillDimension::UseOfEnglish,
        phase: SkillPhase::Current,
    },
    LevelFieldSpec {
        semantic_name: "writing",
        field: WRITING,
        gel_field_id: 235,
        dimension: SkillDimension::Writing,
        phase: SkillPhase::Current,
    },
    LevelFieldSpec {
        semantic_name: "listening",
        field: LISTENING,
        gel_field_id: 236,
        dimension: SkillDimension::Listening,
        phase: SkillPhase::Current,
    },
    LevelFieldSpec {
        semantic_name: "reading",
        field: READING,
        gel_field_id: 476,
        dimension: SkillDimension::Reading,
        phase: SkillPhase::Current,
    },
];

pub fn level_field_spec(field: &str) -> Option<&'static LevelFieldSpec> {
    LEVEL_FIELD_SPECS.iter().find(|spec| spec.field == field)
}

/// Contract-derived applicability for GEL form controls.
pub fn field_applies_to(field: &str, ttype: &str) -> bool {
    match field {
        TEACHER_ID => matches!(ttype, "2" | "0" | "1"),
        STUDENT_UID => matches!(ttype, "2" | "0" | "1"),
        SOURCE_TIMESTAMP => matches!(ttype, "2" | "0" | "1"),
        TUTORIAL_TYPE => matches!(ttype, "2" | "0" | "1"),
        LANGUAGE => matches!(ttype, "2" | "0" | "1"),
        ABSENT => matches!(ttype, "2" | "0" | "1"),
        CUSTOM_DATE => matches!(ttype, "2" | "0" | "1"),
        OVERALL_LEVEL => matches!(ttype, "2" | "0" | "1"),
        INITIAL_SPEAKING => matches!(ttype, "2" | "1"),
        INITIAL_USE_OF_ENGLISH => matches!(ttype, "2" | "1"),
        INITIAL_WRITING => matches!(ttype, "2" | "1"),
        INITIAL_LISTENING => matches!(ttype, "2" | "1"),
        SPEAKING => matches!(ttype, "0" | "1"),
        USE_OF_ENGLISH => matches!(ttype, "0" | "1"),
        WRITING => matches!(ttype, "0" | "1"),
        LISTENING => matches!(ttype, "0" | "1"),
        READING => matches!(ttype, "0" | "1"),
        ASSESSMENT_LISTENING => matches!(ttype, "0"),
        ASSESSMENT_READING => matches!(ttype, "0"),
        ASSESSMENT_WRITING => matches!(ttype, "0"),
        ASSESSMENT_SPEAKING => matches!(ttype, "0"),
        ASSESSMENT_VOCABULARY => matches!(ttype, "0"),
        ASSESSMENT_GRAMMAR => matches!(ttype, "0"),
        ASSESSMENT_PRONUNCIATION => matches!(ttype, "0"),
        AIMS => matches!(ttype, "0"),
        TEACHER_COMMENTS => matches!(ttype, "2" | "0" | "1"),
        ADDITIONAL_COMMENTS => matches!(ttype, "1"),
        EXAM_INTENT => matches!(ttype, "2"),
        EXAM_TYPE => matches!(ttype, "2"),
        EXAM_WHEN => matches!(ttype, "2"),
        _ => false,
    }
}
