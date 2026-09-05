use chrono::NaiveDate;
use gel_core::semantic::{
    apply_tutorial_draft_edit, BooleanFieldProvenance, CefrLevel, DraftOrigin, FieldSource,
    FourSkill, SkillScores, TeacherRef, TutorialDraftEdit, TutorialFormProvenance,
    TutorialFormState, TutorialIdentity, TutorialType,
};

fn standard_revision() -> TutorialFormState {
    TutorialFormState {
        origin: DraftOrigin::Revision {
            source: TutorialIdentity {
                tutorial_id: 11,
                student_uid: 22,
                tutorial_ts: 33,
                tutorial_type: TutorialType::Standard,
            },
            source_teacher_id: 44,
        },
        student_uid: 22,
        tutorial_type: TutorialType::Standard,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 28).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(44),
            teacher_name: Some("Historical Teacher".into()),
        },
        absent: false,
        overall_level: Some(CefrLevel::B1),
        initial_scores: SkillScores::default(),
        current_scores: SkillScores::default(),
        reading: None,
        self_assessment: Default::default(),
        exam: Default::default(),
        aims: String::new(),
        teacher_comments: String::new(),
        additional_comments: String::new(),
        provenance: TutorialFormProvenance {
            absent: BooleanFieldProvenance {
                authoritative_value: false,
                authoritative_source: FieldSource::Summary,
                edit_form_value: Some(false),
                discrepancy: None,
            },
            overall_level_source_raw: Some("B1".into()),
            aims_source_html: None,
        },
    }
}

#[test]
fn ui1_typed_edit_preserves_revision_identity_and_teacher() {
    let state = standard_revision();
    let origin = state.origin.clone();
    let teacher = state.teacher.clone();
    let changed = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetTeacherComments {
            value: "Updated comment".into(),
        },
    )
    .unwrap();
    assert_eq!(changed.origin, origin);
    assert_eq!(changed.teacher, teacher);
    assert_eq!(changed.teacher_comments, "Updated comment");
}

#[test]
fn ui1_invalid_cross_type_edit_fails_without_mutating_input() {
    let state = standard_revision();
    let original = state.clone();
    let result = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetInitialLevel {
            skill: FourSkill::Speaking,
            value: Some("B1".into()),
        },
    );
    assert!(result.is_err());
    assert_eq!(state, original);
}

#[test]
fn ui1_comment_limit_is_authoritative_in_rust() {
    let state = standard_revision();
    assert!(apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetTeacherComments {
            value: "é".repeat(gel_core::gel_fields::TEACHER_COMMENTS_MAX_CHARS),
        },
    )
    .is_ok());
    assert!(apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetTeacherComments {
            value: "é".repeat(gel_core::gel_fields::TEACHER_COMMENTS_MAX_CHARS + 1),
        },
    )
    .is_err());
}
