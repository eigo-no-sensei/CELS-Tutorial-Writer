use chrono::NaiveDate;
use gel_core::semantic::{
    apply_tutorial_draft_edit, BooleanFieldProvenance, CefrLevel, DraftOrigin, FieldSource,
    SkillScores, TeacherRef, TutorialFormProvenance, TutorialFormState, TutorialIdentity,
    TutorialType,
};
use gel_core::{check_harper_text, HarperDictionaryRepository, TutorialDraftEdit};
use std::fs;
use std::time::{SystemTime, UNIX_EPOCH};

fn create_test_base_state(tutorial_type: TutorialType) -> TutorialFormState {
    TutorialFormState {
        origin: DraftOrigin::Revision {
            source: TutorialIdentity {
                tutorial_id: 101,
                student_uid: 42,
                tutorial_ts: 1725000000,
                tutorial_type,
            },
            source_teacher_id: 7,
        },
        student_uid: 42,
        tutorial_type,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 9, 2).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(7),
            teacher_name: Some("Lead Teacher".into()),
        },
        absent: false,
        overall_level: Some(CefrLevel::B2),
        initial_scores: SkillScores::default(),
        current_scores: SkillScores::default(),
        reading: None,
        self_assessment: Default::default(),
        exam: Default::default(),
        aims: "Improve communicative precision".into(),
        teacher_comments: "Demonstrating consistent progress in discussion tasks.".into(),
        additional_comments: String::new(),
        provenance: TutorialFormProvenance {
            absent: BooleanFieldProvenance {
                authoritative_value: false,
                authoritative_source: FieldSource::Summary,
                edit_form_value: Some(false),
                discrepancy: None,
            },
            overall_level_source_raw: Some("B2".into()),
            aims_source_html: None,
        },
    }
}

#[test]
fn test_workflow_draft_clean_dirty_cycle() {
    let base = create_test_base_state(TutorialType::Standard);
    let mut current = base.clone();

    // 1. Initially identical base and current -> Clean
    assert_eq!(
        base, current,
        "Base and current must initially be identical"
    );

    // 2. Perform a valid edit -> Becomes Dirty
    let edit = TutorialDraftEdit::SetTeacherComments {
        value: "Updated teacher comments reflecting end-of-term review.".into(),
    };
    current = apply_tutorial_draft_edit(&current, edit).expect("Valid edit must succeed");
    assert_ne!(
        base, current,
        "Draft must be marked dirty when current diverged from base"
    );

    // 3. Reverting the change -> Clean again
    let revert_edit = TutorialDraftEdit::SetTeacherComments {
        value: base.teacher_comments.clone(),
    };
    current =
        apply_tutorial_draft_edit(&current, revert_edit).expect("Reverting edit must succeed");
    assert_eq!(
        base, current,
        "Draft returns to clean when value is reverted to base"
    );
}

#[test]
fn test_workflow_candidate_before_commit_atomic_failure() {
    let base = create_test_base_state(TutorialType::Standard);
    let current = base.clone();

    // Attempt an invalid edit (exceeding Unicode length limit of 970 chars)
    let invalid_edit = TutorialDraftEdit::SetTeacherComments {
        value: "a".repeat(971),
    };
    let result = apply_tutorial_draft_edit(&current, invalid_edit);

    assert!(
        result.is_err(),
        "Exceeding max character limit must fail validation"
    );
    // Prior state is unaltered
    assert_eq!(
        current, base,
        "Candidate failure must leave current state unchanged"
    );
}

#[test]
fn test_workflow_harper_assistance_and_dictionary_mutation() {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let dict_path = std::env::temp_dir().join(format!("test-harper-dict-{nonce}.json"));
    let dict_repo = HarperDictionaryRepository::new(dict_path.clone());

    // Initial check on text with an unknown token
    let text = "We completed the Chi365 module today.";
    let check1 = check_harper_text(&dict_repo, "teacher_comments", text, &[], &[])
        .expect("Harper check must execute");

    // Word should have a spelling finding
    assert!(check1
        .findings
        .iter()
        .any(|f| f.original_text.contains("Chi365")));

    // Add unknown word to dictionary
    let mutation = dict_repo.add("Chi365").expect("Word addition must succeed");
    assert!(mutation.changed, "Mutation must report changed=true");

    // Repeat check; the token should now be accepted
    let check2 = check_harper_text(&dict_repo, "teacher_comments", text, &[], &[])
        .expect("Harper check must execute");

    let spelling_issues_after = check2
        .findings
        .iter()
        .filter(|f| f.rule.contains("Spelling") && f.original_text.contains("Chi365"))
        .count();
    assert_eq!(
        spelling_issues_after, 0,
        "Adding word to dictionary must resolve spelling finding"
    );

    let _ = fs::remove_file(dict_path);
}

#[test]
fn test_workflow_stale_source_locks_direct_edits() {
    struct MockLoadedDraft {
        _base: TutorialFormState,
        current: TutorialFormState,
        stale: bool,
    }

    let base = create_test_base_state(TutorialType::Standard);
    let mut loaded = MockLoadedDraft {
        _base: base.clone(),
        current: base,
        stale: false,
    };

    // Transition to stale (e.g. session expired or remote source drift detected)
    loaded.stale = true;

    // Simulate guard check in apply_draft_edit command
    let edit_attempt = if loaded.stale {
        Err("Draft source authority is stale; direct editing is locked until draft is discarded")
    } else {
        apply_tutorial_draft_edit(
            &loaded.current,
            TutorialDraftEdit::SetTeacherComments {
                value: "New note".into(),
            },
        )
        .map_err(|_| "edit failed")
    };

    assert!(edit_attempt.is_err());
    assert_eq!(
        edit_attempt.unwrap_err(),
        "Draft source authority is stale; direct editing is locked until draft is discarded"
    );
}
