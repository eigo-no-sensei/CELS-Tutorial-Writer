#!/usr/bin/env python3
"""fix_w2_test.py — Update gel-core/tests/submission_transport.rs to use public fixture constructors."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

test_content = """use chrono::NaiveDate;
use gel_core::gel_fields;
use gel_core::parse_new_tutorial_form;
use gel_core::post_mapper::build_tutorial_post_payload;
use gel_core::semantic::{
    build_new_form_state, BooleanFieldProvenance, DraftOrigin, FieldSource, TeacherRef,
    TutorialFormProvenance, TutorialFormState, TutorialIdentity, TutorialType,
};

fn mock_new_draft() -> TutorialFormState {
    let html = include_str!("../fixtures/synthetic/new_standard.html");
    let form = parse_new_tutorial_form(html, 200, "0").expect("valid synthetic new form");
    build_new_form_state(None, &form).expect("valid new draft state")
}

fn mock_revision_draft() -> TutorialFormState {
    TutorialFormState {
        origin: DraftOrigin::Revision {
            source: TutorialIdentity {
                tutorial_id: 154306,
                student_uid: 464954,
                tutorial_ts: 1781609897,
                tutorial_type: TutorialType::Standard,
            },
            source_teacher_id: 326743,
        },
        student_uid: 464954,
        tutorial_type: TutorialType::Standard,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 9, 3).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(326743),
            teacher_name: Some("Historical Teacher".into()),
        },
        absent: false,
        overall_level: None,
        initial_scores: Default::default(),
        current_scores: Default::default(),
        reading: None,
        self_assessment: Default::default(),
        exam: Default::default(),
        aims: "Revised aims".into(),
        teacher_comments: "Revised comment".into(),
        additional_comments: String::new(),
        provenance: TutorialFormProvenance {
            absent: BooleanFieldProvenance {
                authoritative_value: false,
                authoritative_source: FieldSource::Summary,
                edit_form_value: Some(false),
                discrepancy: None,
            },
            overall_level_source_raw: None,
            aims_source_html: None,
        },
    }
}

#[test]
fn new_submission_payload_strictly_omits_datetime_and_preserves_authenticated_teacher() {
    let draft = mock_new_draft();
    let payload = build_tutorial_post_payload(&draft).expect("valid new payload");
    assert!(!payload.contains_key(gel_fields::SOURCE_TIMESTAMP));
    assert_eq!(payload.get(gel_fields::TEACHER_ID).map(|s| s.as_str()), Some("326743"));
    assert_eq!(payload.get(gel_fields::STUDENT_UID).map(|s| s.as_str()), Some("200"));
    assert_eq!(payload.get(gel_fields::TUTORIAL_TYPE).map(|s| s.as_str()), Some("0"));
    assert_eq!(payload.get(gel_fields::CUSTOM_DATE).map(|s| s.as_str()), Some("27-08-2026"));
}

#[test]
fn revision_submission_payload_strictly_preserves_source_timestamp_and_teacher() {
    let draft = mock_revision_draft();
    let payload = build_tutorial_post_payload(&draft).expect("valid revision payload");
    assert_eq!(payload.get(gel_fields::SOURCE_TIMESTAMP).map(|s| s.as_str()), Some("1781609897"));
    assert_eq!(payload.get(gel_fields::TEACHER_ID).map(|s| s.as_str()), Some("326743"));
    assert_eq!(payload.get(gel_fields::STUDENT_UID).map(|s| s.as_str()), Some("464954"));
    assert_eq!(payload.get(gel_fields::TUTORIAL_TYPE).map(|s| s.as_str()), Some("0"));
}

#[test]
fn unauthenticated_session_fails_closed_before_network_dispatch() {
    let session_res = gel_core::GelSession::new();
    if let Ok(mut session) = session_res {
        let draft = mock_new_draft();
        let res = gel_core::submission_transport::submit_tutorial_draft(&mut session, &draft, None);
        assert!(matches!(res, Err(gel_core::submission_transport::SubmissionError::Unauthenticated)));
    }
}
"""

p = ROOT / "gel-core" / "tests" / "submission_transport.rs"
p.write_text(test_content.rstrip() + "\n", encoding="utf-8")
print("[✓] gel-core/tests/submission_transport.rs updated successfully")