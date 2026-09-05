use chrono::NaiveDate;
use gel_core::models::HistoricalStateAuthority;
use gel_core::semantic::{
    apply_tutorial_draft_edit, build_new_form_state, build_revision_form_state,
    initial_course_type_state, ArchivedTutorial, AssessmentSkill, AssessmentValue, CefrLevel,
    DraftOrigin, DraftValidationCode, ExamIntent, FourSkill, InitialCourseType,
    InitialCourseTypeState, RichTextValue, SelfAssessment, SkillScores, TeacherRef,
    TutorialDraftEdit, TutorialIdentity, TutorialSemanticField, TutorialType,
};
use gel_core::{parse_edit_form, parse_new_tutorial_form, validate_edit_form};

fn parsed_new_form(ttype: TutorialType) -> gel_core::ValidatedNewTutorialForm {
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
                    speaking: Some(CefrLevel::B2),
                    use_of_english: Some(CefrLevel::B1),
                    writing: Some(CefrLevel::B1),
                    listening: Some(CefrLevel::B1),
                },
                Some(CefrLevel::B1),
                SelfAssessment {
                    listening: Some(AssessmentValue::NeedsMoreWork),
                    reading: Some(AssessmentValue::OkForCurrentLevel),
                    writing: Some(AssessmentValue::GoodForCurrentLevel),
                    speaking: Some(AssessmentValue::OkForCurrentLevel),
                    vocabulary: Some(AssessmentValue::NeedsMoreWork),
                    grammar: Some(AssessmentValue::GoodForCurrentLevel),
                    pronunciation: Some(AssessmentValue::OkForCurrentLevel),
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
fn new_standard_reconstructs_standard_state_and_all_assessment_edits_are_typed() {
    let src = source(TutorialType::Standard);
    let state = build_new_form_state(Some(&src), &parsed_new_form(TutorialType::Standard)).unwrap();

    assert_eq!(state.tutorial_type, TutorialType::Standard);
    assert_eq!(state.current_scores, src.current_scores);
    assert_eq!(state.reading, src.reading);
    assert_eq!(state.self_assessment, src.self_assessment);
    assert_eq!(state.aims, "source aims");
    assert_eq!(state.initial_scores, SkillScores::default());
    assert_eq!(state.exam, ExamIntent::default());
    assert!(matches!(state.origin, DraftOrigin::New { .. }));

    let edits = [
        AssessmentSkill::Listening,
        AssessmentSkill::Reading,
        AssessmentSkill::Writing,
        AssessmentSkill::Speaking,
        AssessmentSkill::Vocabulary,
        AssessmentSkill::Grammar,
        AssessmentSkill::Pronunciation,
    ];
    let mut candidate = state.clone();
    for skill in edits {
        candidate = apply_tutorial_draft_edit(
            &candidate,
            TutorialDraftEdit::SetAssessment {
                skill,
                value: Some("good_for_this_level".into()),
            },
        )
        .unwrap();
    }
    assert_eq!(
        candidate.self_assessment.listening,
        Some(AssessmentValue::GoodForCurrentLevel)
    );
    assert_eq!(
        candidate.self_assessment.reading,
        Some(AssessmentValue::GoodForCurrentLevel)
    );
    assert_eq!(
        candidate.self_assessment.writing,
        Some(AssessmentValue::GoodForCurrentLevel)
    );
    assert_eq!(
        candidate.self_assessment.speaking,
        Some(AssessmentValue::GoodForCurrentLevel)
    );
    assert_eq!(
        candidate.self_assessment.vocabulary,
        Some(AssessmentValue::GoodForCurrentLevel)
    );
    assert_eq!(
        candidate.self_assessment.grammar,
        Some(AssessmentValue::GoodForCurrentLevel)
    );
    assert_eq!(
        candidate.self_assessment.pronunciation,
        Some(AssessmentValue::GoodForCurrentLevel)
    );
}

#[test]
fn new_initial_reconstructs_initial_state_and_preserves_hidden_storage() {
    let src = source(TutorialType::Initial);
    let state = build_new_form_state(Some(&src), &parsed_new_form(TutorialType::Initial)).unwrap();

    assert_eq!(state.initial_scores, src.initial_scores);
    assert_eq!(state.current_scores, SkillScores::default());
    assert_eq!(state.reading, None);
    assert_eq!(state.exam, src.exam);
    assert_eq!(state.teacher_comments, src.teacher_comments);
    assert_eq!(
        initial_course_type_state(&state.teacher_comments),
        InitialCourseTypeState::UnrecognizedPreserved {
            raw: src.teacher_comments.clone()
        }
    );

    let changed = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetTutorialDate {
            value: "2026-08-31".into(),
        },
    )
    .unwrap();
    assert_eq!(changed.exam, src.exam);
    assert_eq!(changed.teacher_comments, src.teacher_comments);

    let replaced = apply_tutorial_draft_edit(
        &changed,
        TutorialDraftEdit::SetInitialCourseType {
            value: "G15".into(),
        },
    )
    .unwrap();
    assert_eq!(replaced.exam, src.exam);
    assert_eq!(
        initial_course_type_state(&replaced.teacher_comments),
        InitialCourseTypeState::Recognized {
            value: InitialCourseType::G15
        }
    );
}

#[test]
fn new_final_keeps_initial_and_current_roles_independent() {
    let src = source(TutorialType::Final);
    let state = build_new_form_state(Some(&src), &parsed_new_form(TutorialType::Final)).unwrap();

    assert_eq!(state.initial_scores, src.initial_scores);
    assert_eq!(state.current_scores, src.current_scores);
    assert_eq!(state.reading, src.reading);
    assert_eq!(state.additional_comments, "source additional");
    assert_eq!(state.self_assessment, SelfAssessment::default());
    assert_eq!(state.exam, ExamIntent::default());

    let initial_changed = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetInitialLevel {
            skill: FourSkill::Speaking,
            value: Some("B1+".into()),
        },
    )
    .unwrap();
    assert_eq!(
        initial_changed.initial_scores.speaking,
        Some(CefrLevel::B1Plus)
    );
    assert_eq!(initial_changed.current_scores.speaking, Some(CefrLevel::B2));

    let current_changed = apply_tutorial_draft_edit(
        &initial_changed,
        TutorialDraftEdit::SetCurrentLevel {
            skill: FourSkill::Speaking,
            value: Some("B2+".into()),
        },
    )
    .unwrap();
    assert_eq!(
        current_changed.initial_scores.speaking,
        Some(CefrLevel::B1Plus)
    );
    assert_eq!(
        current_changed.current_scores.speaking,
        Some(CefrLevel::B2Plus)
    );
}

#[test]
fn rejected_new_regression_is_structured_and_leaves_prior_state_unchanged() {
    let src = source(TutorialType::Final);
    let state = build_new_form_state(Some(&src), &parsed_new_form(TutorialType::Initial)).unwrap();
    let before = state.clone();

    let issue = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetInitialLevel {
            skill: FourSkill::Speaking,
            value: Some("A2".into()),
        },
    )
    .unwrap_err();

    assert_eq!(state, before);
    assert_eq!(issue.code, DraftValidationCode::LevelRegression);
    assert_eq!(issue.field, Some(TutorialSemanticField::InitialSpeaking));
    assert_eq!(issue.prior_value.as_deref(), Some("B1"));
    assert_eq!(issue.candidate_value.as_deref(), Some("A2"));
    assert!(!issue.message.is_empty());
}

#[test]
fn revision_reconstruction_keeps_source_identity_and_teacher_immutable_without_new_regression() {
    let archive = source(TutorialType::Standard);
    let html = r##"<form>
      <select name="tid" id="tid"><option value="100">Source Teacher</option></select><script>$("#tid").val("100");</script>
      <input type="hidden" name="uid" value="200"><input type="hidden" name="datetime" value="1780000000"><input type="hidden" name="ttype" value="0">
      <input name="absent" type="checkbox"><input name="customdate" value="01-08-2026">
      <select name="dropdown-475"><option value="B2: upper-intermediate" selected>B2</option></select>
      <select name="dropdown-233"><option value="B2" selected>B2</option></select>
      <select name="dropdown-234"><option value="B1" selected>B1</option></select>
      <select name="dropdown-235"><option value="B1" selected>B1</option></select>
      <select name="dropdown-236"><option value="B1" selected>B1</option></select>
      <select name="dropdown-476"><option value="B1" selected>B1</option></select>
      <input type="radio" name="sl-89" value="1"><input type="radio" name="sl-89" value="2"><input type="radio" name="sl-89" value="3">
      <input type="radio" name="sr-89" value="1"><input type="radio" name="sr-89" value="2"><input type="radio" name="sr-89" value="3">
      <input type="radio" name="sw-89" value="1"><input type="radio" name="sw-89" value="2"><input type="radio" name="sw-89" value="3">
      <input type="radio" name="ss-89" value="1"><input type="radio" name="ss-89" value="2"><input type="radio" name="ss-89" value="3">
      <input type="radio" name="sv-89" value="1"><input type="radio" name="sv-89" value="2"><input type="radio" name="sv-89" value="3">
      <input type="radio" name="sg-89" value="1"><input type="radio" name="sg-89" value="2"><input type="radio" name="sg-89" value="3">
      <input type="radio" name="sp-89" value="1"><input type="radio" name="sp-89" value="2"><input type="radio" name="sp-89" value="3">
      <input type="hidden" name="trecs-79" value=""><div id="tcinput" name="trecs-79" contenteditable="true">source aims</div>
      <textarea name="text-225">revision comment</textarea>
    </form>"##;
    let edit = validate_edit_form(&parse_edit_form(html).unwrap()).unwrap();
    let state = build_revision_form_state(&archive, &edit).unwrap();
    let origin = state.origin.clone();
    let teacher = state.teacher.clone();

    let lowered = apply_tutorial_draft_edit(
        &state,
        TutorialDraftEdit::SetCurrentLevel {
            skill: FourSkill::Speaking,
            value: Some("A2".into()),
        },
    )
    .unwrap();

    assert_eq!(lowered.origin, origin);
    assert_eq!(lowered.teacher, teacher);
    assert_eq!(lowered.current_scores.speaking, Some(CefrLevel::A2));
    assert!(matches!(lowered.origin, DraftOrigin::Revision { .. }));
    assert!(lowered.origin.level_regression_baseline().is_none());
}
