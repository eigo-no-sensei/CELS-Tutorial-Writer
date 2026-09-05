use chrono::NaiveDate;
use gel_core::gel_fields;
use gel_core::parse_new_tutorial_form;
use gel_core::post_mapper::build_tutorial_post_payload;
use gel_core::semantic::{
    AssessmentValue, BooleanFieldProvenance, CefrLevel, DraftOrigin, ExamIntent, FieldSource,
    SelfAssessment, SkillScores, TeacherRef, TutorialFormProvenance, TutorialFormState,
    TutorialIdentity, TutorialType,
};

fn validated_new_teacher_for_final() -> gel_core::ValidatedNewFormTeacher {
    parse_new_tutorial_form(
        include_str!("../fixtures/synthetic/new_final.html"),
        200,
        "1",
    )
    .unwrap()
    .teacher()
    .clone()
}

fn provenance(absent: bool) -> TutorialFormProvenance {
    TutorialFormProvenance {
        absent: BooleanFieldProvenance {
            authoritative_value: absent,
            authoritative_source: FieldSource::Summary,
            edit_form_value: Some(absent),
            discrepancy: None,
        },
        overall_level_source_raw: Some("B1: intermediate".into()),
        aims_source_html: None,
    }
}

fn base_final(reading: Option<CefrLevel>, absent: bool) -> TutorialFormState {
    let identity = TutorialIdentity {
        tutorial_id: 100,
        student_uid: 200,
        tutorial_ts: 1786000000,
        tutorial_type: TutorialType::Final,
    };
    TutorialFormState {
        origin: DraftOrigin::Revision {
            source: identity,
            source_teacher_id: 326743,
        },
        student_uid: 200,
        tutorial_type: TutorialType::Final,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 6).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(326743),
            teacher_name: Some("Teacher".into()),
        },
        absent,
        overall_level: Some(CefrLevel::B1),
        initial_scores: SkillScores {
            speaking: Some(CefrLevel::A2Minus),
            use_of_english: Some(CefrLevel::A2Minus),
            writing: Some(CefrLevel::A2Minus),
            listening: Some(CefrLevel::A2),
        },
        current_scores: SkillScores {
            speaking: Some(CefrLevel::B1),
            use_of_english: Some(CefrLevel::B1Minus),
            writing: Some(CefrLevel::B1),
            listening: Some(CefrLevel::B1Minus),
        },
        reading,
        self_assessment: SelfAssessment::default(),
        exam: ExamIntent::default(),
        aims: String::new(),
        teacher_comments: "Final comment".into(),
        additional_comments: String::new(),
        provenance: provenance(absent),
    }
}

#[test]
fn final_post_includes_reading_and_revision_source_timestamp() {
    let payload =
        build_tutorial_post_payload(&base_final(Some(CefrLevel::B1Minus), false)).unwrap();
    assert_eq!(
        payload.get(gel_fields::READING).map(String::as_str),
        Some("B1-")
    );
    assert_eq!(
        payload.get(gel_fields::TUTORIAL_TYPE).map(String::as_str),
        Some("1")
    );
    assert_eq!(
        payload
            .get(gel_fields::SOURCE_TIMESTAMP)
            .map(String::as_str),
        Some("1786000000")
    );
    assert!(!payload.contains_key(gel_fields::ABSENT));
}

#[test]
fn final_unset_reading_preserves_gel_select_placeholder() {
    let payload = build_tutorial_post_payload(&base_final(None, false)).unwrap();
    assert_eq!(
        payload.get(gel_fields::READING).map(String::as_str),
        Some(gel_fields::SKILL_PLACEHOLDER)
    );
}

#[test]
fn checked_absent_uses_browser_successful_control_semantics() {
    let payload = build_tutorial_post_payload(&base_final(Some(CefrLevel::A2), true)).unwrap();
    assert_eq!(
        payload.get(gel_fields::ABSENT).map(String::as_str),
        Some("on")
    );
}

#[test]
fn standard_post_uses_numeric_assessment_values_and_escaped_aims_html() {
    let identity = TutorialIdentity {
        tutorial_id: 101,
        student_uid: 201,
        tutorial_ts: 1786100000,
        tutorial_type: TutorialType::Standard,
    };
    let state = TutorialFormState {
        origin: DraftOrigin::Revision {
            source: identity,
            source_teacher_id: 9,
        },
        student_uid: 201,
        tutorial_type: TutorialType::Standard,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 7).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(9),
            teacher_name: Some("Teacher".into()),
        },
        absent: false,
        overall_level: Some(CefrLevel::A2),
        initial_scores: SkillScores::default(),
        current_scores: SkillScores {
            speaking: Some(CefrLevel::A2),
            use_of_english: Some(CefrLevel::A2),
            writing: Some(CefrLevel::A2),
            listening: Some(CefrLevel::A2),
        },
        reading: Some(CefrLevel::A2),
        self_assessment: SelfAssessment {
            listening: Some(AssessmentValue::GoodForCurrentLevel),
            reading: Some(AssessmentValue::OkForCurrentLevel),
            writing: None,
            speaking: Some(AssessmentValue::NeedsMoreWork),
            vocabulary: None,
            grammar: None,
            pronunciation: None,
        },
        exam: ExamIntent::default(),
        aims: "Read <one> & discuss \"it\"\nUse a partner's notes".into(),
        teacher_comments: String::new(),
        additional_comments: String::new(),
        provenance: TutorialFormProvenance {
            aims_source_html: Some("stale <b>source</b>".into()),
            ..provenance(false)
        },
    };

    let payload = build_tutorial_post_payload(&state).unwrap();
    assert_eq!(
        payload
            .get(gel_fields::ASSESSMENT_LISTENING)
            .map(String::as_str),
        Some("3")
    );
    assert_eq!(
        payload
            .get(gel_fields::ASSESSMENT_READING)
            .map(String::as_str),
        Some("2")
    );
    assert_eq!(
        payload
            .get(gel_fields::ASSESSMENT_SPEAKING)
            .map(String::as_str),
        Some("1")
    );
    assert!(!payload.contains_key(gel_fields::ASSESSMENT_WRITING));
    assert_eq!(
        payload.get(gel_fields::AIMS).map(String::as_str),
        Some("Read &lt;one&gt; &amp; discuss &quot;it&quot;<br>Use a partner&#39;s notes")
    );
}

#[test]
fn initial_unset_exam_fields_serialize_gel_placeholder() {
    let identity = TutorialIdentity {
        tutorial_id: 102,
        student_uid: 202,
        tutorial_ts: 1786200000,
        tutorial_type: TutorialType::Initial,
    };
    let state = TutorialFormState {
        origin: DraftOrigin::Revision {
            source: identity,
            source_teacher_id: 9,
        },
        student_uid: 202,
        tutorial_type: TutorialType::Initial,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 8).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(9),
            teacher_name: Some("Teacher".into()),
        },
        absent: false,
        overall_level: None,
        initial_scores: SkillScores::default(),
        current_scores: SkillScores::default(),
        reading: None,
        self_assessment: SelfAssessment::default(),
        exam: ExamIntent::default(),
        aims: String::new(),
        teacher_comments: String::new(),
        additional_comments: String::new(),
        provenance: provenance(false),
    };
    let payload = build_tutorial_post_payload(&state).unwrap();
    for field in [
        gel_fields::EXAM_INTENT,
        gel_fields::EXAM_TYPE,
        gel_fields::EXAM_WHEN,
    ] {
        assert_eq!(
            payload.get(field).map(String::as_str),
            Some(gel_fields::EXAM_PLACEHOLDER)
        );
    }
}

#[test]
fn semantic_overall_level_is_only_post_source_of_truth() {
    let mut state = base_final(Some(CefrLevel::B1Minus), false);
    state.provenance.overall_level_source_raw = Some("B1: intermediate".into());
    state.overall_level = Some(CefrLevel::B2Minus);
    let payload = build_tutorial_post_payload(&state).unwrap();
    assert_eq!(
        payload.get(gel_fields::OVERALL_LEVEL).map(String::as_str),
        Some("B2-: upper-intermediate")
    );

    state.overall_level = None;
    let payload = build_tutorial_post_payload(&state).unwrap();
    assert_eq!(
        payload.get(gel_fields::OVERALL_LEVEL).map(String::as_str),
        Some(gel_fields::OVERALL_PLACEHOLDER)
    );
}

#[test]
fn semantic_aims_text_change_is_not_masked_by_source_html() {
    let identity = TutorialIdentity {
        tutorial_id: 103,
        student_uid: 203,
        tutorial_ts: 1786300000,
        tutorial_type: TutorialType::Standard,
    };
    let mut state = TutorialFormState {
        origin: DraftOrigin::Revision {
            source: identity,
            source_teacher_id: 9,
        },
        student_uid: 203,
        tutorial_type: TutorialType::Standard,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 9).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(9),
            teacher_name: Some("Teacher".into()),
        },
        absent: false,
        overall_level: Some(CefrLevel::A2),
        initial_scores: SkillScores::default(),
        current_scores: SkillScores::default(),
        reading: None,
        self_assessment: SelfAssessment::default(),
        exam: ExamIntent::default(),
        aims: "Old aim".into(),
        teacher_comments: String::new(),
        additional_comments: String::new(),
        provenance: TutorialFormProvenance {
            aims_source_html: Some("Old aim".into()),
            ..provenance(false)
        },
    };
    state.aims = "New aim one\nNew aim two".into();
    let payload = build_tutorial_post_payload(&state).unwrap();
    assert_eq!(
        payload.get(gel_fields::AIMS).map(String::as_str),
        Some("New aim one<br>New aim two")
    );
}

#[test]
fn explicit_new_origin_omits_datetime_entirely() {
    let mut state = base_final(Some(CefrLevel::B1), false);
    let historical = match &state.origin {
        DraftOrigin::Revision { source, .. } => source.clone(),
        DraftOrigin::New { .. } => panic!("fixture should begin as revision"),
    };
    state.origin = DraftOrigin::New {
        prepopulation_source: Some(historical),
        form_teacher: validated_new_teacher_for_final(),
        level_regression_baseline: Default::default(),
    };
    let payload = build_tutorial_post_payload(&state).unwrap();
    assert!(!payload.contains_key(gel_fields::SOURCE_TIMESTAMP));
}

#[test]
fn first_ever_new_without_prepopulation_source_omits_datetime() {
    let mut state = base_final(Some(CefrLevel::B1), false);
    state.origin = DraftOrigin::New {
        prepopulation_source: None,
        form_teacher: validated_new_teacher_for_final(),
        level_regression_baseline: Default::default(),
    };
    let payload = build_tutorial_post_payload(&state).unwrap();
    assert!(!payload.contains_key(gel_fields::SOURCE_TIMESTAMP));
}

#[test]
fn revision_teacher_attribution_cannot_be_changed() {
    let mut state = base_final(Some(CefrLevel::B1), false);
    state.teacher.teacher_id = Some(123456);
    let error = build_tutorial_post_payload(&state).unwrap_err();
    assert!(error
        .to_string()
        .contains("revision teacher attribution is immutable"));
}

#[test]
fn new_teacher_attribution_must_match_form_authority() {
    let mut state = base_final(Some(CefrLevel::B1), false);
    state.origin = DraftOrigin::New {
        prepopulation_source: None,
        form_teacher: validated_new_teacher_for_final(),
        level_regression_baseline: Default::default(),
    };
    state.teacher.teacher_id = Some(123456);
    let error = build_tutorial_post_payload(&state).unwrap_err();
    assert!(error
        .to_string()
        .contains("new tutorial teacher attribution is immutable"));
}

#[test]
fn post_mapper_fails_closed_on_semantically_inapplicable_fields() {
    let mut state = base_final(Some(CefrLevel::B1), false);
    state.aims = "Aims do not apply to Final".into();
    let error = build_tutorial_post_payload(&state).unwrap_err();
    assert!(error.to_string().contains("Final Aims"));
}
