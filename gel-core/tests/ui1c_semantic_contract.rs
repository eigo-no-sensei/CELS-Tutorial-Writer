use chrono::NaiveDate;
use gel_core::models::HistoricalStateAuthority;
use gel_core::parse_new_tutorial_form;
use gel_core::semantic::{
    apply_tutorial_draft_edit, build_new_form_state, initial_course_type_state,
    tutorial_field_disposition, ArchivedTutorial, AssessmentValue, CefrLevel, DraftValidationCode,
    FieldDisposition, FourSkill, InitialCourseType, InitialCourseTypeState, RichTextValue,
    SelfAssessment, SkillScores, TeacherRef, TutorialDraftEdit, TutorialIdentity,
    TutorialSemanticField, TutorialType,
};

fn parsed_form(ttype: TutorialType) -> gel_core::ValidatedNewTutorialForm {
    let (raw, html) = match ttype {
        TutorialType::Standard => ("0", include_str!("../fixtures/synthetic/new_standard.html")),
        TutorialType::Final => ("1", include_str!("../fixtures/synthetic/new_final.html")),
        TutorialType::Initial => ("2", include_str!("../fixtures/synthetic/new_initial.html")),
    };
    parse_new_tutorial_form(html, 200, raw).unwrap()
}

fn source(ttype: TutorialType) -> ArchivedTutorial {
    let (initial_scores, current_scores, reading, self_assessment, exam, aims, additional_comments) =
        match ttype {
            TutorialType::Initial => (
                SkillScores {
                    speaking: Some(CefrLevel::B1),
                    use_of_english: Some(CefrLevel::A2),
                    writing: Some(CefrLevel::A2),
                    listening: Some(CefrLevel::A2),
                },
                SkillScores::default(),
                None,
                SelfAssessment::default(),
                gel_core::semantic::ExamIntent {
                    intent: Some("intent-source".into()),
                    exam_type: Some("exam-source".into()),
                    when: Some("when-source".into()),
                },
                RichTextValue::default(),
                String::new(),
            ),
            TutorialType::Standard => (
                SkillScores::default(),
                SkillScores {
                    speaking: Some(CefrLevel::B2),
                    use_of_english: Some(CefrLevel::B1),
                    writing: Some(CefrLevel::B1),
                    listening: Some(CefrLevel::B1),
                },
                Some(CefrLevel::B1),
                SelfAssessment {
                    listening: Some(AssessmentValue::NeedsMoreWork),
                    ..Default::default()
                },
                Default::default(),
                RichTextValue {
                    html: "<p>source aims</p>".into(),
                    text: "source aims".into(),
                },
                String::new(),
            ),
            TutorialType::Final => (
                SkillScores {
                    speaking: Some(CefrLevel::B1),
                    use_of_english: Some(CefrLevel::A2),
                    writing: Some(CefrLevel::A2),
                    listening: Some(CefrLevel::A2),
                },
                SkillScores {
                    speaking: Some(CefrLevel::B2),
                    use_of_english: Some(CefrLevel::B1),
                    writing: Some(CefrLevel::B1),
                    listening: Some(CefrLevel::B1),
                },
                Some(CefrLevel::B1),
                Default::default(),
                Default::default(),
                RichTextValue::default(),
                "source additional".into(),
            ),
        };

    ArchivedTutorial {
        identity: TutorialIdentity {
            tutorial_id: 900 + ttype.ttype().parse::<i64>().unwrap(),
            student_uid: 200,
            tutorial_ts: 1_780_000_000 + ttype.ttype().parse::<i64>().unwrap(),
            tutorial_type: ttype,
        },
        state_authority: HistoricalStateAuthority::proven(),
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 1).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(100),
            teacher_name: Some("Source Teacher".into()),
        },
        absent: false,
        overall_level_raw: "B2: upper-intermediate".into(),
        initial_scores,
        current_scores,
        reading,
        self_assessment,
        exam,
        aims,
        teacher_comments: "legacy free-text Initial storage".into(),
        additional_comments,
    }
}

#[test]
fn ui1c_field_matrix_distinguishes_editable_hidden_preserved_and_inapplicable() {
    assert_eq!(
        tutorial_field_disposition(TutorialType::Standard, TutorialSemanticField::Absent),
        FieldDisposition::Editable
    );
    assert_eq!(
        tutorial_field_disposition(TutorialType::Initial, TutorialSemanticField::Absent),
        FieldDisposition::HiddenPreserved
    );
    assert_eq!(
        tutorial_field_disposition(
            TutorialType::Initial,
            TutorialSemanticField::TeacherComments
        ),
        FieldDisposition::HiddenPreserved
    );
    assert_eq!(
        tutorial_field_disposition(
            TutorialType::Initial,
            TutorialSemanticField::InitialCourseType
        ),
        FieldDisposition::Editable
    );
    assert_eq!(
        tutorial_field_disposition(TutorialType::Initial, TutorialSemanticField::ExamIntent),
        FieldDisposition::HiddenPreserved
    );
    assert_eq!(
        tutorial_field_disposition(TutorialType::Final, TutorialSemanticField::Aims),
        FieldDisposition::Inapplicable
    );
    assert_eq!(
        tutorial_field_disposition(TutorialType::Final, TutorialSemanticField::TeacherReadOnly),
        FieldDisposition::ReadOnly
    );
}

#[test]
fn initial_course_type_adapter_preserves_unknown_storage_until_explicit_replacement() {
    let src = source(TutorialType::Standard);
    let state = build_new_form_state(Some(&src), &parsed_form(TutorialType::Initial)).unwrap();
    assert_eq!(
        initial_course_type_state(&state.teacher_comments),
        InitialCourseTypeState::UnrecognizedPreserved {
            raw: "legacy free-text Initial storage".into()
        }
    );

    let changed = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetTutorialDate {
            value: "2026-08-29".into(),
        },
    )
    .unwrap();
    assert_eq!(changed.teacher_comments, state.teacher_comments);

    let direct_comment_edit = apply_tutorial_draft_edit(
        &changed,
        TutorialDraftEdit::SetTeacherComments {
            value: "destroy legacy storage".into(),
        },
    )
    .unwrap_err();
    assert_eq!(
        direct_comment_edit.code,
        DraftValidationCode::FieldNotApplicable
    );
    assert_eq!(
        direct_comment_edit.field,
        Some(TutorialSemanticField::TeacherComments)
    );

    let replaced = apply_tutorial_draft_edit(
        &changed,
        TutorialDraftEdit::SetInitialCourseType {
            value: InitialCourseType::Hsp.storage_value().into(),
        },
    )
    .unwrap();
    assert_eq!(replaced.teacher_comments, "HSP");
    assert_eq!(
        initial_course_type_state(&replaced.teacher_comments),
        InitialCourseTypeState::Recognized {
            value: InitialCourseType::Hsp
        }
    );
}

#[test]
fn hidden_initial_exam_fields_survive_unrelated_ui1c_edits() {
    let src = source(TutorialType::Initial);
    let state = build_new_form_state(Some(&src), &parsed_form(TutorialType::Initial)).unwrap();
    let exam_before = state.exam.clone();
    let changed = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetInitialCourseType {
            value: "G21".into(),
        },
    )
    .unwrap();
    assert_eq!(changed.exam, exam_before);
}

#[test]
fn new_same_role_level_regression_is_structured_and_blocking() {
    let src = source(TutorialType::Final);
    let state = build_new_form_state(Some(&src), &parsed_form(TutorialType::Initial)).unwrap();
    let issue = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetInitialLevel {
            skill: FourSkill::Speaking,
            value: Some("A2".into()),
        },
    )
    .unwrap_err();
    assert_eq!(issue.code, DraftValidationCode::LevelRegression);
    assert_eq!(issue.field, Some(TutorialSemanticField::InitialSpeaking));
    assert_eq!(issue.prior_value.as_deref(), Some("B1"));
    assert_eq!(issue.candidate_value.as_deref(), Some("A2"));
}

#[test]
fn new_regression_never_compares_current_source_role_to_initial_candidate_role() {
    let src = source(TutorialType::Standard);
    let state = build_new_form_state(Some(&src), &parsed_form(TutorialType::Initial)).unwrap();
    let changed = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetInitialLevel {
            skill: FourSkill::Speaking,
            value: Some("A1".into()),
        },
    )
    .unwrap();
    assert_eq!(changed.initial_scores.speaking, Some(CefrLevel::A1));
}

#[test]
fn first_ever_new_has_no_regression_floor() {
    let state = build_new_form_state(None, &parsed_form(TutorialType::Initial)).unwrap();
    assert!(state
        .origin
        .level_regression_baseline()
        .expect("New origin has baseline container")
        .is_empty());
    assert!(apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetInitialLevel {
            skill: FourSkill::Speaking,
            value: Some("A1".into()),
        }
    )
    .is_ok());
}

#[test]
fn structured_invalid_option_issue_has_stable_code_and_field() {
    let state = build_new_form_state(None, &parsed_form(TutorialType::Standard)).unwrap();
    let issue = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetOverallLevel {
            value: Some("not-a-level".into()),
        },
    )
    .unwrap_err();
    assert_eq!(issue.code, DraftValidationCode::InvalidOption);
    assert_eq!(issue.field, Some(TutorialSemanticField::OverallLevel));
    assert_eq!(issue.candidate_value.as_deref(), Some("not-a-level"));
}
