use chrono::NaiveDate;
use gel_core::build_tutorial_post_payload;
use gel_core::gel_fields;
use gel_core::semantic::{
    AssessmentValue, BooleanFieldProvenance, CefrLevel, Discrepancy, DraftOrigin, ExamIntent,
    FieldSource, SelfAssessment, SkillScores, TeacherRef, TutorialFormProvenance,
    TutorialFormState, TutorialIdentity, TutorialType,
};
use std::collections::BTreeSet;

fn provenance(absent: bool) -> TutorialFormProvenance {
    TutorialFormProvenance {
        absent: BooleanFieldProvenance {
            authoritative_value: absent,
            authoritative_source: FieldSource::Summary,
            edit_form_value: Some(absent),
            discrepancy: None,
        },
        overall_level_source_raw: Some("A2: pre-intermediate".into()),
        aims_source_html: Some("source aims".into()),
    }
}

fn identity(tutorial_type: TutorialType) -> TutorialIdentity {
    TutorialIdentity {
        tutorial_id: 700,
        student_uid: 800,
        tutorial_ts: 1_786_500_000,
        tutorial_type,
    }
}

fn initial_state() -> TutorialFormState {
    TutorialFormState {
        origin: DraftOrigin::Revision {
            source: identity(TutorialType::Initial),
            source_teacher_id: 9,
        },
        student_uid: 800,
        tutorial_type: TutorialType::Initial,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 10).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(9),
            teacher_name: Some("Teacher".into()),
        },
        absent: false,
        overall_level: Some(CefrLevel::A2),
        initial_scores: SkillScores {
            speaking: Some(CefrLevel::A2),
            use_of_english: Some(CefrLevel::A2),
            writing: Some(CefrLevel::A2),
            listening: Some(CefrLevel::A2),
        },
        current_scores: SkillScores::default(),
        reading: None,
        self_assessment: SelfAssessment::default(),
        exam: ExamIntent {
            intent: Some("Yes".into()),
            exam_type: Some("IELTS".into()),
            when: Some("December".into()),
        },
        aims: String::new(),
        teacher_comments: "Initial comment".into(),
        additional_comments: String::new(),
        provenance: provenance(false),
    }
}

fn standard_state() -> TutorialFormState {
    TutorialFormState {
        origin: DraftOrigin::Revision {
            source: identity(TutorialType::Standard),
            source_teacher_id: 9,
        },
        student_uid: 800,
        tutorial_type: TutorialType::Standard,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 11).unwrap(),
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
            listening: Some(AssessmentValue::NeedsMoreWork),
            reading: Some(AssessmentValue::NeedsMoreWork),
            writing: Some(AssessmentValue::NeedsMoreWork),
            speaking: Some(AssessmentValue::NeedsMoreWork),
            vocabulary: Some(AssessmentValue::NeedsMoreWork),
            grammar: Some(AssessmentValue::NeedsMoreWork),
            pronunciation: Some(AssessmentValue::NeedsMoreWork),
        },
        exam: ExamIntent::default(),
        aims: "Aim one".into(),
        teacher_comments: "Standard comment".into(),
        additional_comments: String::new(),
        provenance: provenance(false),
    }
}

fn final_state() -> TutorialFormState {
    TutorialFormState {
        origin: DraftOrigin::Revision {
            source: identity(TutorialType::Final),
            source_teacher_id: 9,
        },
        student_uid: 800,
        tutorial_type: TutorialType::Final,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 12).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(9),
            teacher_name: Some("Teacher".into()),
        },
        absent: false,
        overall_level: Some(CefrLevel::B1),
        initial_scores: SkillScores {
            speaking: Some(CefrLevel::A2),
            use_of_english: Some(CefrLevel::A2),
            writing: Some(CefrLevel::A2),
            listening: Some(CefrLevel::A2),
        },
        current_scores: SkillScores {
            speaking: Some(CefrLevel::B1),
            use_of_english: Some(CefrLevel::B1),
            writing: Some(CefrLevel::B1),
            listening: Some(CefrLevel::B1),
        },
        reading: Some(CefrLevel::B1),
        self_assessment: SelfAssessment::default(),
        exam: ExamIntent::default(),
        aims: String::new(),
        teacher_comments: "Final comment".into(),
        additional_comments: "Accommodation".into(),
        provenance: provenance(false),
    }
}

fn changed_keys(before: &TutorialFormState, after: &TutorialFormState) -> BTreeSet<String> {
    let before_payload = build_tutorial_post_payload(before).unwrap();
    let after_payload = build_tutorial_post_payload(after).unwrap();
    before_payload
        .keys()
        .chain(after_payload.keys())
        .filter(|key| before_payload.get(*key) != after_payload.get(*key))
        .cloned()
        .collect()
}

fn assert_only<F>(base: TutorialFormState, expected_field: &str, mutate: F)
where
    F: FnOnce(&mut TutorialFormState),
{
    let mut changed = base.clone();
    mutate(&mut changed);
    assert_eq!(
        changed_keys(&base, &changed),
        BTreeSet::from([expected_field.to_string()])
    );
}

#[test]
fn common_editable_mutations_change_only_their_gel_field() {
    let base = standard_state();
    assert_only(base.clone(), gel_fields::ABSENT, |state| {
        state.absent = true
    });
    assert_only(base.clone(), gel_fields::OVERALL_LEVEL, |state| {
        state.overall_level = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::CUSTOM_DATE, |state| {
        state.tutorial_date = NaiveDate::from_ymd_opt(2026, 8, 20).unwrap()
    });
    assert_only(base, gel_fields::TEACHER_COMMENTS, |state| {
        state.teacher_comments = "Changed comment".into()
    });
}

#[test]
fn initial_mutations_are_isolated_to_initial_and_exam_fields() {
    let base = initial_state();
    assert_only(base.clone(), gel_fields::INITIAL_SPEAKING, |state| {
        state.initial_scores.speaking = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::INITIAL_USE_OF_ENGLISH, |state| {
        state.initial_scores.use_of_english = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::INITIAL_WRITING, |state| {
        state.initial_scores.writing = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::INITIAL_LISTENING, |state| {
        state.initial_scores.listening = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::EXAM_INTENT, |state| {
        state.exam.intent = Some("No".into())
    });
    assert_only(base.clone(), gel_fields::EXAM_TYPE, |state| {
        state.exam.exam_type = Some("FCE".into())
    });
    assert_only(base, gel_fields::EXAM_WHEN, |state| {
        state.exam.when = Some("June".into())
    });
}

#[test]
fn standard_mutations_are_isolated_to_current_assessment_reading_and_aims_fields() {
    let base = standard_state();
    assert_only(base.clone(), gel_fields::SPEAKING, |state| {
        state.current_scores.speaking = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::USE_OF_ENGLISH, |state| {
        state.current_scores.use_of_english = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::WRITING, |state| {
        state.current_scores.writing = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::LISTENING, |state| {
        state.current_scores.listening = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::READING, |state| {
        state.reading = Some(CefrLevel::B1)
    });
    assert_only(base.clone(), gel_fields::ASSESSMENT_LISTENING, |state| {
        state.self_assessment.listening = Some(AssessmentValue::GoodForCurrentLevel)
    });
    assert_only(base.clone(), gel_fields::ASSESSMENT_READING, |state| {
        state.self_assessment.reading = Some(AssessmentValue::GoodForCurrentLevel)
    });
    assert_only(base.clone(), gel_fields::ASSESSMENT_WRITING, |state| {
        state.self_assessment.writing = Some(AssessmentValue::GoodForCurrentLevel)
    });
    assert_only(base.clone(), gel_fields::ASSESSMENT_SPEAKING, |state| {
        state.self_assessment.speaking = Some(AssessmentValue::GoodForCurrentLevel)
    });
    assert_only(base.clone(), gel_fields::ASSESSMENT_VOCABULARY, |state| {
        state.self_assessment.vocabulary = Some(AssessmentValue::GoodForCurrentLevel)
    });
    assert_only(base.clone(), gel_fields::ASSESSMENT_GRAMMAR, |state| {
        state.self_assessment.grammar = Some(AssessmentValue::GoodForCurrentLevel)
    });
    assert_only(
        base.clone(),
        gel_fields::ASSESSMENT_PRONUNCIATION,
        |state| state.self_assessment.pronunciation = Some(AssessmentValue::GoodForCurrentLevel),
    );
    assert_only(base, gel_fields::AIMS, |state| {
        state.aims = "Changed aim".into()
    });
}

#[test]
fn final_mutations_are_isolated_and_include_final_reading() {
    let base = final_state();
    assert_only(base.clone(), gel_fields::INITIAL_SPEAKING, |state| {
        state.initial_scores.speaking = Some(CefrLevel::A2Plus)
    });
    assert_only(base.clone(), gel_fields::INITIAL_USE_OF_ENGLISH, |state| {
        state.initial_scores.use_of_english = Some(CefrLevel::A2Plus)
    });
    assert_only(base.clone(), gel_fields::INITIAL_WRITING, |state| {
        state.initial_scores.writing = Some(CefrLevel::A2Plus)
    });
    assert_only(base.clone(), gel_fields::INITIAL_LISTENING, |state| {
        state.initial_scores.listening = Some(CefrLevel::A2Plus)
    });
    assert_only(base.clone(), gel_fields::SPEAKING, |state| {
        state.current_scores.speaking = Some(CefrLevel::B1Plus)
    });
    assert_only(base.clone(), gel_fields::USE_OF_ENGLISH, |state| {
        state.current_scores.use_of_english = Some(CefrLevel::B1Plus)
    });
    assert_only(base.clone(), gel_fields::WRITING, |state| {
        state.current_scores.writing = Some(CefrLevel::B1Plus)
    });
    assert_only(base.clone(), gel_fields::LISTENING, |state| {
        state.current_scores.listening = Some(CefrLevel::B1Plus)
    });
    assert_only(base.clone(), gel_fields::READING, |state| {
        state.reading = Some(CefrLevel::B1Plus)
    });
    assert_only(base, gel_fields::ADDITIONAL_COMMENTS, |state| {
        state.additional_comments = "Changed accommodation".into()
    });
}

#[test]
fn provenance_only_mutations_do_not_change_post_payload() {
    let base = standard_state();
    let mut changed = base.clone();
    changed.provenance.overall_level_source_raw = Some("C2: very advanced".into());
    changed.provenance.aims_source_html = Some("<b>stale source</b>".into());
    changed.provenance.absent.edit_form_value = Some(true);
    changed.provenance.absent.discrepancy = Some(Discrepancy::HistoricalEditAbsentMismatch);
    assert!(changed_keys(&base, &changed).is_empty());
}
