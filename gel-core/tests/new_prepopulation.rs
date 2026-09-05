use chrono::NaiveDate;
use gel_core::models::HistoricalStateAuthority;
use gel_core::parse_new_tutorial_form;
use gel_core::semantic::{
    build_new_form_state, ArchivedTutorial, AssessmentValue, CefrLevel, ExamIntent, RichTextValue,
    SelfAssessment, SkillScores, TeacherRef, TutorialIdentity, TutorialType,
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
                    speaking: Some(CefrLevel::A1),
                    use_of_english: Some(CefrLevel::A1Plus),
                    writing: Some(CefrLevel::A2Minus),
                    listening: Some(CefrLevel::A2),
                },
                SkillScores::default(),
                None,
                SelfAssessment::default(),
                ExamIntent {
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
                    speaking: Some(CefrLevel::B1Minus),
                    use_of_english: Some(CefrLevel::B1),
                    writing: Some(CefrLevel::B1Plus),
                    listening: Some(CefrLevel::B2Minus),
                },
                Some(CefrLevel::B2),
                SelfAssessment {
                    listening: Some(AssessmentValue::NeedsMoreWork),
                    reading: Some(AssessmentValue::OkForCurrentLevel),
                    writing: Some(AssessmentValue::GoodForCurrentLevel),
                    speaking: Some(AssessmentValue::NeedsMoreWork),
                    vocabulary: Some(AssessmentValue::OkForCurrentLevel),
                    grammar: Some(AssessmentValue::GoodForCurrentLevel),
                    pronunciation: Some(AssessmentValue::NeedsMoreWork),
                },
                ExamIntent::default(),
                RichTextValue {
                    html: "<p>source aims</p>".into(),
                    text: "source aims".into(),
                },
                String::new(),
            ),
            TutorialType::Final => (
                SkillScores {
                    speaking: Some(CefrLevel::A1),
                    use_of_english: Some(CefrLevel::A1Plus),
                    writing: Some(CefrLevel::A2Minus),
                    listening: Some(CefrLevel::A2),
                },
                SkillScores {
                    speaking: Some(CefrLevel::B1Minus),
                    use_of_english: Some(CefrLevel::B1),
                    writing: Some(CefrLevel::B1Plus),
                    listening: Some(CefrLevel::B2Minus),
                },
                Some(CefrLevel::B2),
                SelfAssessment::default(),
                ExamIntent::default(),
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
        absent: true,
        overall_level_raw: "B2: upper-intermediate".into(),
        initial_scores,
        current_scores,
        reading,
        self_assessment,
        exam,
        aims,
        teacher_comments: "source comments".into(),
        additional_comments,
    }
}

#[test]
fn initial_from_standard_keeps_new_form_defaults_for_unavailable_initial_role_fields() {
    let state = build_new_form_state(
        Some(&source(TutorialType::Standard)),
        &parsed_form(TutorialType::Initial),
    )
    .unwrap();
    assert_eq!(state.initial_scores.speaking, Some(CefrLevel::A2));
    assert_eq!(state.initial_scores.use_of_english, Some(CefrLevel::A2));
    assert_eq!(state.initial_scores.writing, Some(CefrLevel::A2));
    assert_eq!(state.initial_scores.listening, Some(CefrLevel::A2));
    assert_eq!(state.current_scores, SkillScores::default());
    assert_eq!(
        state.exam,
        ExamIntent::default(),
        "non-Initial source must not populate Initial-only exam state"
    );
}

#[test]
fn standard_from_initial_keeps_new_form_defaults_for_unavailable_current_role_fields() {
    let state = build_new_form_state(
        Some(&source(TutorialType::Initial)),
        &parsed_form(TutorialType::Standard),
    )
    .unwrap();
    assert_eq!(state.current_scores.speaking, Some(CefrLevel::B1));
    assert_eq!(state.current_scores.use_of_english, Some(CefrLevel::B1));
    assert_eq!(state.current_scores.writing, Some(CefrLevel::B1));
    assert_eq!(state.current_scores.listening, Some(CefrLevel::B1));
    assert_eq!(state.initial_scores, SkillScores::default());
    assert_eq!(
        state.aims, "",
        "Initial source has no Standard Aims authority; New-form default remains blank"
    );
}

#[test]
fn final_from_standard_copies_current_roles_and_keeps_initial_new_form_defaults() {
    let state = build_new_form_state(
        Some(&source(TutorialType::Standard)),
        &parsed_form(TutorialType::Final),
    )
    .unwrap();
    assert_eq!(state.initial_scores.speaking, Some(CefrLevel::A2));
    assert_eq!(state.initial_scores.use_of_english, Some(CefrLevel::A2));
    assert_eq!(state.initial_scores.writing, Some(CefrLevel::A2));
    assert_eq!(state.initial_scores.listening, Some(CefrLevel::A2));
    assert_eq!(state.current_scores.speaking, Some(CefrLevel::B1Minus));
    assert_eq!(state.current_scores.use_of_english, Some(CefrLevel::B1));
    assert_eq!(state.current_scores.writing, Some(CefrLevel::B1Plus));
    assert_eq!(state.current_scores.listening, Some(CefrLevel::B2Minus));
    assert_eq!(state.reading, Some(CefrLevel::B2));
    assert_eq!(state.additional_comments, "");
}

#[test]
fn final_from_initial_copies_initial_roles_and_keeps_current_new_form_defaults() {
    let state = build_new_form_state(
        Some(&source(TutorialType::Initial)),
        &parsed_form(TutorialType::Final),
    )
    .unwrap();
    assert_eq!(state.initial_scores.speaking, Some(CefrLevel::A1));
    assert_eq!(state.initial_scores.use_of_english, Some(CefrLevel::A1Plus));
    assert_eq!(state.initial_scores.writing, Some(CefrLevel::A2Minus));
    assert_eq!(state.initial_scores.listening, Some(CefrLevel::A2));
    assert_eq!(state.current_scores.speaking, Some(CefrLevel::B1));
    assert_eq!(state.current_scores.use_of_english, Some(CefrLevel::B1));
    assert_eq!(state.current_scores.writing, Some(CefrLevel::B1));
    assert_eq!(state.current_scores.listening, Some(CefrLevel::B1));
}

#[test]
fn final_source_preserves_distinct_initial_and_current_roles_without_cross_role_inference() {
    let state = build_new_form_state(
        Some(&source(TutorialType::Final)),
        &parsed_form(TutorialType::Final),
    )
    .unwrap();
    assert_eq!(state.initial_scores.speaking, Some(CefrLevel::A1));
    assert_eq!(state.initial_scores.use_of_english, Some(CefrLevel::A1Plus));
    assert_eq!(state.initial_scores.writing, Some(CefrLevel::A2Minus));
    assert_eq!(state.initial_scores.listening, Some(CefrLevel::A2));
    assert_eq!(state.current_scores.speaking, Some(CefrLevel::B1Minus));
    assert_eq!(state.current_scores.use_of_english, Some(CefrLevel::B1));
    assert_eq!(state.current_scores.writing, Some(CefrLevel::B1Plus));
    assert_eq!(state.current_scores.listening, Some(CefrLevel::B2Minus));
    assert_eq!(state.additional_comments, "source additional");
}

#[test]
fn standard_source_preserves_standard_only_assessment_aims_and_provenance() {
    let src = source(TutorialType::Standard);
    let state = build_new_form_state(Some(&src), &parsed_form(TutorialType::Standard)).unwrap();
    assert_eq!(state.self_assessment, src.self_assessment);
    assert_eq!(state.aims, "source aims");
    assert_eq!(state.reading, Some(CefrLevel::B2));
    assert_eq!(
        state.provenance.aims_source_html.as_deref(),
        Some("<p>source aims</p>")
    );
}

#[test]
fn common_fields_copy_latest_but_date_and_teacher_come_from_new_form() {
    let src = source(TutorialType::Standard);
    let form = parsed_form(TutorialType::Standard);
    let state = build_new_form_state(Some(&src), &form).unwrap();
    assert!(state.absent);
    assert_eq!(state.overall_level, Some(CefrLevel::B2));
    assert_eq!(state.teacher_comments, "source comments");
    assert_eq!(
        state.tutorial_date,
        NaiveDate::from_ymd_opt(2026, 8, 27).unwrap()
    );
    assert_eq!(state.teacher.teacher_id, Some(326743));
    assert_eq!(
        state.provenance.overall_level_source_raw.as_deref(),
        Some("B2: upper-intermediate")
    );
    assert_eq!(
        state.origin.prepopulation_source().unwrap().tutorial_id,
        src.identity.tutorial_id
    );
    assert!(state.origin.authoritative_identity().is_none());
}

#[test]
fn first_ever_new_uses_validated_form_defaults_and_invents_no_source() {
    let state = build_new_form_state(None, &parsed_form(TutorialType::Standard)).unwrap();
    assert!(!state.absent);
    assert_eq!(state.overall_level, Some(CefrLevel::B1));
    assert_eq!(state.current_scores.speaking, Some(CefrLevel::B1));
    assert_eq!(
        state.self_assessment.listening,
        Some(AssessmentValue::OkForCurrentLevel)
    );
    assert!(state.origin.prepopulation_source().is_none());
    assert!(state.origin.authoritative_identity().is_none());
}

#[test]
fn source_student_mismatch_fails_closed() {
    let mut src = source(TutorialType::Standard);
    src.identity.student_uid = 999;
    assert!(build_new_form_state(Some(&src), &parsed_form(TutorialType::Standard)).is_err());
}
