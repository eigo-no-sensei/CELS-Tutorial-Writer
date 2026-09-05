use gel_core::fixture_support::archived_tutorial_from_expected_json;
use gel_core::models::HistoricalStateAuthorityStatus;
use gel_core::semantic::{CefrLevel, TutorialType};

#[test]
fn expected_fixture_adapter_accepts_scalar_json_values() {
    let fixture = r#"
    {
      "spec": {"ttype": 1},
      "normalized_db_reference": {
        "tutorial_id": 123,
        "student_uid": 456,
        "created_at": 1786000000,
        "custom_date": "06-08-2026",
        "teacher_id": 9,
        "teacher_name": "Teacher",
        "absent": 0,
        "overall_level": "B1: intermediate",
        "speaking_before": "A2",
        "uoe_before": "A2",
        "writing_before": "A2-",
        "listening_before": "A2",
        "speaking": "B1",
        "use_of_english": "B1-",
        "writing": "B1",
        "listening": "B1+",
        "reading": "B1",
        "teacher_comments": "Comment",
        "additional_comments": "",
        "reconciliation_status": "matched",
        "reconciliation_key": ""
      }
    }
    "#;

    let archived = archived_tutorial_from_expected_json(fixture).unwrap();
    assert_eq!(archived.identity.tutorial_type, TutorialType::Final);
    assert_eq!(archived.identity.tutorial_id, 123);
    assert_eq!(archived.identity.student_uid, 456);
    assert_eq!(archived.teacher.teacher_id, Some(9));
    assert_eq!(archived.reading, Some(CefrLevel::B1));
    assert!(!archived.absent);
    assert_eq!(
        archived.state_authority.status,
        HistoricalStateAuthorityStatus::ProvenPerTutorial
    );
}

#[test]
fn legacy_ambiguous_collision_fixture_is_fail_closed() {
    let fixture = r#"
    {
      "spec": {"ttype": 1},
      "normalized_db_reference": {
        "tutorial_id": 123,
        "student_uid": 456,
        "created_at": 1786000000,
        "custom_date": "06-08-2026",
        "teacher_id": 9,
        "teacher_name": "Teacher",
        "absent": 0,
        "overall_level": "B1: intermediate",
        "speaking_before": "A2",
        "uoe_before": "A2",
        "writing_before": "A2-",
        "listening_before": "A2",
        "speaking": "B1",
        "use_of_english": "B1-",
        "writing": "B1",
        "listening": "B1+",
        "reading": "B1",
        "teacher_comments": "Comment",
        "additional_comments": "",
        "reconciliation_status": "collision_ambiguous",
        "reconciliation_key": "456:1786000000"
      }
    }
    "#;

    let archived = archived_tutorial_from_expected_json(fixture).unwrap();
    assert_eq!(
        archived.state_authority.status,
        HistoricalStateAuthorityStatus::AmbiguousCollisionUnknown
    );
    assert!(!archived.state_authority.permits_revision_by_id());
}
