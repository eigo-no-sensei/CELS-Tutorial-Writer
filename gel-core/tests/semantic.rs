use chrono::NaiveDate;
use gel_core::models::{HistoricalStateAuthority, HistoricalStateAuthorityStatus};
use gel_core::semantic::{
    build_revision_form_state, validate_semantic_form_state, ArchivedTutorial, CefrLevel,
    Discrepancy, DraftOrigin, ExamIntent, RichTextValue, SelfAssessment, SkillScores, TeacherRef,
    TutorialFormProvenance, TutorialFormState, TutorialIdentity, TutorialType,
};
use gel_core::{parse_edit_form, parse_new_tutorial_form, validate_edit_form};

fn validated_new_teacher(
    student_uid: i64,
    ttype: &str,
    teacher_id: i64,
) -> gel_core::ValidatedNewFormTeacher {
    let base = match ttype {
        "0" => include_str!("../fixtures/synthetic/new_standard.html"),
        "1" => include_str!("../fixtures/synthetic/new_final.html"),
        "2" => include_str!("../fixtures/synthetic/new_initial.html"),
        _ => panic!("test helper received invalid ttype"),
    };
    let html = base
        .replace(
            "name=\"uid\" value=\"200\"",
            &format!("name=\"uid\" value=\"{student_uid}\""),
        )
        .replace(
            "name=\"tid\" value=\"326743\"",
            &format!("name=\"tid\" value=\"{teacher_id}\""),
        );
    parse_new_tutorial_form(&html, student_uid, ttype)
        .unwrap()
        .teacher()
        .clone()
}

fn final_archive(absent: bool) -> ArchivedTutorial {
    ArchivedTutorial {
        identity: TutorialIdentity {
            tutorial_id: 1234,
            student_uid: 55,
            tutorial_ts: 1780000000,
            tutorial_type: TutorialType::Final,
        },
        state_authority: HistoricalStateAuthority::proven(),
        tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 5).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(9),
            teacher_name: Some("Historical Teacher".to_string()),
        },
        absent,
        overall_level_raw: "B1: intermediate".to_string(),
        initial_scores: SkillScores::default(),
        current_scores: SkillScores::default(),
        reading: None,
        self_assessment: SelfAssessment::default(),
        exam: ExamIntent::default(),
        aims: RichTextValue::default(),
        teacher_comments: "archive comment".to_string(),
        additional_comments: String::new(),
    }
}

#[test]
fn revision_uses_summary_absent_final_reading_and_explicit_revision_origin() {
    let html = r##"<form>
      <select name="tid" id="tid"><option value="9">Historical Teacher</option></select>
      <script>$("#tid").val("9");</script>
      <input type="hidden" name="uid" value="55"><input type="hidden" name="datetime" value="1780000000"><input type="hidden" name="ttype" value="1">
      <input name="absent" type="checkbox" checked>
      <input name="customdate" value="05-08-2026">
      <select name="dropdown-475"><option value="B1: intermediate" selected>B1</option></select>
      <select name="dropdown-264"><option value="A2-" selected>A2-</option></select>
      <select name="dropdown-265"><option value="A2" selected>A2</option></select>
      <select name="dropdown-266"><option value="A2" selected>A2</option></select>
      <select name="dropdown-267"><option value="A2" selected>A2</option></select>
      <select name="dropdown-233"><option value="B1" selected>B1</option></select>
      <select name="dropdown-234"><option value="B1-" selected>B1-</option></select>
      <select name="dropdown-235"><option value="B1" selected>B1</option></select>
      <select name="dropdown-236"><option value="B1-" selected>B1-</option></select>
      <select name="dropdown-476"><option value="B1-" selected>B1-</option></select>
      <textarea name="text-225">edit comment</textarea>
      <textarea name="text-226">accommodation</textarea>
    </form>"##;

    let raw = parse_edit_form(html).unwrap();
    let edit = validate_edit_form(&raw).unwrap();
    let state = build_revision_form_state(&final_archive(false), &edit).unwrap();

    assert!(
        !state.absent,
        "summary/archive must win over bad historical checkbox"
    );
    assert_eq!(state.reading, Some(CefrLevel::B1Minus));
    assert_eq!(state.teacher.teacher_id, Some(9));
    assert_eq!(state.teacher_comments, "edit comment");
    assert_eq!(state.additional_comments, "accommodation");
    assert!(matches!(
        &state.origin,
        DraftOrigin::Revision {
            source,
            source_teacher_id,
        } if source.tutorial_id == 1234 && *source_teacher_id == 9
    ));
    assert_eq!(
        state.provenance.absent.discrepancy,
        Some(Discrepancy::HistoricalEditAbsentMismatch)
    );
    assert_eq!(state.provenance.absent.edit_form_value, Some(true));
    assert_eq!(
        state.provenance.overall_level_source_raw.as_deref(),
        Some("B1: intermediate")
    );
}

#[test]
fn final_unset_reading_is_semantic_none() {
    let html = r##"<form>
      <select name="tid" id="tid"><option value="9">Historical Teacher</option></select>
      <script>$("#tid").val("9");</script>
      <input type="hidden" name="uid" value="55"><input type="hidden" name="datetime" value="1780000000"><input type="hidden" name="ttype" value="1">
      <input name="absent" type="checkbox"><input name="customdate" value="05-08-2026">
      <select name="dropdown-475"><option value="B1: intermediate" selected>B1</option></select>
      <select name="dropdown-264"><option value="A2" selected>A2</option></select>
      <select name="dropdown-265"><option value="A2" selected>A2</option></select>
      <select name="dropdown-266"><option value="A2" selected>A2</option></select>
      <select name="dropdown-267"><option value="A2" selected>A2</option></select>
      <select name="dropdown-233"><option value="B1" selected>B1</option></select>
      <select name="dropdown-234"><option value="B1" selected>B1</option></select>
      <select name="dropdown-235"><option value="B1" selected>B1</option></select>
      <select name="dropdown-236"><option value="B1" selected>B1</option></select>
      <select name="dropdown-476"><option value="Please choose level">Please choose level</option><option value="B1">B1</option></select>
      <textarea name="text-225"></textarea><textarea name="text-226"></textarea>
    </form>"##;

    let raw = parse_edit_form(html).unwrap();
    let edit = validate_edit_form(&raw).unwrap();
    let state = build_revision_form_state(&final_archive(false), &edit).unwrap();
    assert_eq!(state.reading, None);
    assert_eq!(state.provenance.absent.discrepancy, None);
}

#[test]
fn standard_aims_have_one_editable_text_value_and_source_html_only_in_provenance() {
    let archive = ArchivedTutorial {
        identity: TutorialIdentity {
            tutorial_id: 77,
            student_uid: 66,
            tutorial_ts: 1770000000,
            tutorial_type: TutorialType::Standard,
        },
        state_authority: HistoricalStateAuthority::proven(),
        tutorial_date: NaiveDate::from_ymd_opt(2026, 6, 1).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(9),
            teacher_name: Some("Teacher".into()),
        },
        absent: false,
        overall_level_raw: "A2: pre-intermediate".into(),
        initial_scores: SkillScores::default(),
        current_scores: SkillScores::default(),
        reading: Some(CefrLevel::A2),
        self_assessment: SelfAssessment::default(),
        exam: ExamIntent::default(),
        aims: RichTextValue::default(),
        teacher_comments: String::new(),
        additional_comments: String::new(),
    };
    let html = r##"<form>
      <select name="tid" id="tid"><option value="9">Teacher</option></select><script>$("#tid").val("9");</script>
      <input type="hidden" name="uid" value="66"><input type="hidden" name="datetime" value="1770000000"><input type="hidden" name="ttype" value="0">
      <input name="absent" type="checkbox"><input name="customdate" value="01-06-2026">
      <select name="dropdown-475"><option value="A2: pre-intermediate" selected>A2</option></select>
      <select name="dropdown-233"><option value="A2" selected>A2</option></select>
      <select name="dropdown-234"><option value="A2" selected>A2</option></select>
      <select name="dropdown-235"><option value="A2" selected>A2</option></select>
      <select name="dropdown-236"><option value="A2" selected>A2</option></select>
      <select name="dropdown-476"><option value="A2" selected>A2</option></select>
      <input type="radio" name="sl-89" value="1"><input type="radio" name="sl-89" value="2"><input type="radio" name="sl-89" value="3">
      <input type="radio" name="sr-89" value="1"><input type="radio" name="sr-89" value="2"><input type="radio" name="sr-89" value="3">
      <input type="radio" name="sw-89" value="1"><input type="radio" name="sw-89" value="2"><input type="radio" name="sw-89" value="3">
      <input type="radio" name="ss-89" value="1"><input type="radio" name="ss-89" value="2"><input type="radio" name="ss-89" value="3">
      <input type="radio" name="sv-89" value="1"><input type="radio" name="sv-89" value="2"><input type="radio" name="sv-89" value="3">
      <input type="radio" name="sg-89" value="1"><input type="radio" name="sg-89" value="2"><input type="radio" name="sg-89" value="3">
      <input type="radio" name="sp-89" value="1"><input type="radio" name="sp-89" value="2"><input type="radio" name="sp-89" value="3">
      <input type="hidden" name="trecs-79" value="">
      <div id="tcinput" name="trecs-79" contenteditable="true">Read one book<br><div>Speak to another student</div></div>
      <textarea name="text-225"></textarea>
    </form>"##;
    let raw = parse_edit_form(html).unwrap();
    let edit = validate_edit_form(&raw).unwrap();
    let state = build_revision_form_state(&archive, &edit).unwrap();
    assert_eq!(state.aims, "Read one book\nSpeak to another student");
    let source_html = state.provenance.aims_source_html.as_deref().unwrap();
    assert!(source_html.contains("Read one book"));
    assert!(source_html.contains("Speak to another student"));
}

#[test]
fn semantic_type_invariants_reject_inapplicable_state() {
    let identity = TutorialIdentity {
        tutorial_id: 90,
        student_uid: 66,
        tutorial_ts: 1770000001,
        tutorial_type: TutorialType::Initial,
    };
    let state = TutorialFormState {
        origin: DraftOrigin::Revision {
            source: identity.clone(),
            source_teacher_id: 9,
        },
        student_uid: identity.student_uid,
        tutorial_type: TutorialType::Initial,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 6, 1).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(9),
            teacher_name: Some("Teacher".into()),
        },
        absent: false,
        overall_level: Some(CefrLevel::A2),
        initial_scores: SkillScores::default(),
        current_scores: SkillScores::default(),
        reading: Some(CefrLevel::A2),
        self_assessment: SelfAssessment::default(),
        exam: ExamIntent::default(),
        aims: String::new(),
        teacher_comments: String::new(),
        additional_comments: String::new(),
        provenance: empty_provenance(),
    };

    let error = validate_semantic_form_state(&state).unwrap_err();
    assert!(error.to_string().contains("Initial Reading"));
}

#[test]
fn new_and_revision_origins_are_structurally_distinct() {
    let source = TutorialIdentity {
        tutorial_id: 91,
        student_uid: 66,
        tutorial_ts: 1770000002,
        tutorial_type: TutorialType::Initial,
    };
    let revision = DraftOrigin::Revision {
        source: source.clone(),
        source_teacher_id: 9,
    };
    let new = DraftOrigin::New {
        prepopulation_source: Some(source),
        form_teacher: validated_new_teacher(66, "2", 11),
        level_regression_baseline: Default::default(),
    };
    let first_ever_new = DraftOrigin::New {
        prepopulation_source: None,
        form_teacher: validated_new_teacher(66, "2", 11),
        level_regression_baseline: Default::default(),
    };

    assert!(revision.revision_source().is_some());
    assert!(revision.authoritative_identity().is_some());
    assert_eq!(revision.authoritative_teacher_id(), 9);
    assert!(new.revision_source().is_none());
    assert!(new.authoritative_identity().is_none());
    assert!(new.prepopulation_source().is_some());
    assert_eq!(new.authoritative_teacher_id(), 11);
    assert!(first_ever_new.prepopulation_source().is_none());
    assert!(first_ever_new.authoritative_identity().is_none());
}

#[test]
fn new_origin_has_no_authoritative_created_identity_even_with_prepopulation() {
    let origin = DraftOrigin::New {
        prepopulation_source: Some(TutorialIdentity {
            tutorial_id: 92,
            student_uid: 66,
            tutorial_ts: 1770000003,
            tutorial_type: TutorialType::Standard,
        }),
        form_teacher: validated_new_teacher(66, "0", 11),
        level_regression_baseline: Default::default(),
    };
    assert!(origin.authoritative_identity().is_none());
    assert_eq!(origin.prepopulation_source().unwrap().tutorial_id, 92);
}

fn empty_provenance() -> TutorialFormProvenance {
    TutorialFormProvenance {
        absent: gel_core::semantic::BooleanFieldProvenance {
            authoritative_value: false,
            authoritative_source: gel_core::semantic::FieldSource::Derived,
            edit_form_value: None,
            discrepancy: None,
        },
        overall_level_source_raw: None,
        aims_source_html: None,
    }
}

#[test]
fn divergent_collision_authority_blocks_revision_before_state_construction() {
    let mut archive = final_archive(false);
    archive.state_authority = HistoricalStateAuthority {
        status: HistoricalStateAuthorityStatus::AmbiguousDivergentCollision,
        reconciliation_key: Some("55:1780000000".to_string()),
    };

    let html = r##"<form>
      <select name="tid" id="tid"><option value="9">Historical Teacher</option></select>
      <script>$("#tid").val("9");</script>
      <input type="hidden" name="uid" value="55"><input type="hidden" name="datetime" value="1780000000"><input type="hidden" name="ttype" value="1">
      <input name="absent" type="checkbox"><input name="customdate" value="05-08-2026">
      <select name="dropdown-475"><option value="B1: intermediate" selected>B1</option></select>
      <select name="dropdown-264"><option value="A2" selected>A2</option></select>
      <select name="dropdown-265"><option value="A2" selected>A2</option></select>
      <select name="dropdown-266"><option value="A2" selected>A2</option></select>
      <select name="dropdown-267"><option value="A2" selected>A2</option></select>
      <select name="dropdown-233"><option value="B1" selected>B1</option></select>
      <select name="dropdown-234"><option value="B1" selected>B1</option></select>
      <select name="dropdown-235"><option value="B1" selected>B1</option></select>
      <select name="dropdown-236"><option value="B1" selected>B1</option></select>
      <select name="dropdown-476"><option value="B1" selected>B1</option></select>
      <textarea name="text-225"></textarea><textarea name="text-226"></textarea>
    </form>"##;

    let raw = parse_edit_form(html).unwrap();
    let edit = validate_edit_form(&raw).unwrap();
    let error = build_revision_form_state(&archive, &edit).unwrap_err();
    assert!(error
        .to_string()
        .contains("revision-by-ID blocked by historical state authority"));
}

#[test]
fn shared_identical_collision_authority_can_construct_revision() {
    let mut archive = final_archive(false);
    archive.state_authority = HistoricalStateAuthority {
        status: HistoricalStateAuthorityStatus::SharedIdenticalCollision,
        reconciliation_key: Some("55:1780000000".to_string()),
    };

    let html = r##"<form>
      <select name="tid" id="tid"><option value="9">Historical Teacher</option></select>
      <script>$("#tid").val("9");</script>
      <input type="hidden" name="uid" value="55"><input type="hidden" name="datetime" value="1780000000"><input type="hidden" name="ttype" value="1">
      <input name="absent" type="checkbox"><input name="customdate" value="05-08-2026">
      <select name="dropdown-475"><option value="B1: intermediate" selected>B1</option></select>
      <select name="dropdown-264"><option value="A2" selected>A2</option></select>
      <select name="dropdown-265"><option value="A2" selected>A2</option></select>
      <select name="dropdown-266"><option value="A2" selected>A2</option></select>
      <select name="dropdown-267"><option value="A2" selected>A2</option></select>
      <select name="dropdown-233"><option value="B1" selected>B1</option></select>
      <select name="dropdown-234"><option value="B1" selected>B1</option></select>
      <select name="dropdown-235"><option value="B1" selected>B1</option></select>
      <select name="dropdown-236"><option value="B1" selected>B1</option></select>
      <select name="dropdown-476"><option value="B1" selected>B1</option></select>
      <textarea name="text-225"></textarea><textarea name="text-226"></textarea>
    </form>"##;

    let raw = parse_edit_form(html).unwrap();
    let edit = validate_edit_form(&raw).unwrap();
    let state = build_revision_form_state(&archive, &edit).unwrap();
    assert!(matches!(state.origin, DraftOrigin::Revision { .. }));
}
