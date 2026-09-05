//! Private-fixture adapter used by offline diagnostics.
//!
//! The capture JSON mirrors the current Python archive column names. Keeping
//! this translation here prevents those SQL names from leaking into the core
//! semantic model.

use crate::models::{HistoricalStateAuthority, HistoricalStateAuthorityStatus};
use crate::semantic::{
    ArchivedTutorial, AssessmentValue, CefrLevel, ExamIntent, RichTextValue, SelfAssessment,
    SkillScores, TeacherRef, TutorialIdentity, TutorialType,
};
use anyhow::{Context, Result};
use chrono::NaiveDate;
use serde_json::{Map, Value};

pub fn archived_tutorial_from_expected_json(text: &str) -> Result<ArchivedTutorial> {
    let root: Value = serde_json::from_str(text).context("parse expected fixture JSON")?;
    let spec = root
        .get("spec")
        .and_then(Value::as_object)
        .context("expected fixture is missing object .spec")?;
    let db = root
        .get("normalized_db_reference")
        .and_then(Value::as_object)
        .context("expected fixture is missing object .normalized_db_reference")?;

    let ttype = value_string(spec.get("ttype")).context("fixture .spec.ttype is missing")?;
    let tutorial_type = TutorialType::from_ttype(&ttype)?;
    let tutorial_id = db_i64(db, "tutorial_id").context("tutorial_id is missing")?;
    let student_uid = db_i64(db, "student_uid").context("student_uid is missing")?;
    let tutorial_ts = db_i64(db, "created_at").context("created_at is missing")?;
    let tutorial_date =
        parse_date(&db_string(db, "custom_date")).context("custom_date is not a supported date")?;

    let primary_scores = SkillScores {
        speaking: CefrLevel::parse(&db_string(db, "speaking")),
        use_of_english: CefrLevel::parse(&db_string(db, "use_of_english")),
        writing: CefrLevel::parse(&db_string(db, "writing")),
        listening: CefrLevel::parse(&db_string(db, "listening")),
    };
    let before_scores = SkillScores {
        speaking: CefrLevel::parse(&db_string(db, "speaking_before")),
        use_of_english: CefrLevel::parse(&db_string(db, "uoe_before")),
        writing: CefrLevel::parse(&db_string(db, "writing_before")),
        listening: CefrLevel::parse(&db_string(db, "listening_before")),
    };

    let (initial_scores, current_scores) = match tutorial_type {
        TutorialType::Initial => (primary_scores, SkillScores::default()),
        TutorialType::Standard => (SkillScores::default(), primary_scores),
        TutorialType::Final => (before_scores, primary_scores),
    };

    let self_assessment = if tutorial_type == TutorialType::Standard {
        SelfAssessment {
            listening: AssessmentValue::parse(&db_string(db, "self_listening")),
            reading: AssessmentValue::parse(&db_string(db, "self_reading")),
            writing: AssessmentValue::parse(&db_string(db, "self_writing")),
            speaking: AssessmentValue::parse(&db_string(db, "self_speaking")),
            vocabulary: AssessmentValue::parse(&db_string(db, "self_vocabulary")),
            grammar: AssessmentValue::parse(&db_string(db, "self_grammar")),
            pronunciation: AssessmentValue::parse(&db_string(db, "self_pronunciation")),
        }
    } else {
        SelfAssessment::default()
    };

    let exam = if tutorial_type == TutorialType::Initial {
        ExamIntent {
            intent: optional_text(&db_string(db, "exam_want"), "Please choose:"),
            exam_type: optional_text(&db_string(db, "exam_which"), "Please choose:"),
            when: optional_text(&db_string(db, "exam_when"), "Please choose:"),
        }
    } else {
        ExamIntent::default()
    };

    let state_authority = archive_state_authority(db)?;

    Ok(ArchivedTutorial {
        identity: TutorialIdentity {
            tutorial_id,
            student_uid,
            tutorial_ts,
            tutorial_type,
        },
        state_authority,
        tutorial_date,
        teacher: TeacherRef {
            teacher_id: db_i64(db, "teacher_id"),
            teacher_name: optional_nonempty(&db_string(db, "teacher_name")),
        },
        absent: db_bool(db, "absent"),
        overall_level_raw: db_string(db, "overall_level"),
        initial_scores,
        current_scores,
        reading: if matches!(tutorial_type, TutorialType::Standard | TutorialType::Final) {
            CefrLevel::parse(&db_string(db, "reading"))
        } else {
            None
        },
        self_assessment,
        exam,
        aims: RichTextValue {
            html: String::new(),
            text: db_string(db, "aims"),
        },
        teacher_comments: db_string(db, "teacher_comments"),
        additional_comments: db_string(db, "additional_comments"),
    })
}

fn archive_state_authority(db: &Map<String, Value>) -> Result<HistoricalStateAuthority> {
    let status = db_string(db, "reconciliation_status");
    let key = optional_nonempty(&db_string(db, "reconciliation_key"));
    match status.trim() {
        "matched" => Ok(HistoricalStateAuthority::proven()),
        "collision_ambiguous" => Ok(HistoricalStateAuthority {
            status: HistoricalStateAuthorityStatus::AmbiguousCollisionUnknown,
            reconciliation_key: key,
        }),
        "unmatched_summary" | "summary_unavailable" => Ok(HistoricalStateAuthority {
            status: HistoricalStateAuthorityStatus::UnmatchedSourceState,
            reconciliation_key: key,
        }),
        "" => anyhow::bail!(
            "expected fixture is missing reconciliation_status; C3 requires explicit historical state authority"
        ),
        other => anyhow::bail!("unknown archive reconciliation_status {other:?}"),
    }
}

fn db_string(db: &Map<String, Value>, key: &str) -> String {
    value_string(db.get(key)).unwrap_or_default()
}

fn db_i64(db: &Map<String, Value>, key: &str) -> Option<i64> {
    match db.get(key) {
        Some(Value::Number(value)) => value.as_i64(),
        Some(Value::String(value)) => value.parse().ok(),
        _ => None,
    }
}

fn db_bool(db: &Map<String, Value>, key: &str) -> bool {
    match db.get(key) {
        Some(Value::Bool(value)) => *value,
        Some(Value::Number(value)) => value.as_i64().unwrap_or_default() != 0,
        Some(Value::String(value)) => matches!(
            value.trim().to_ascii_lowercase().as_str(),
            "1" | "true" | "yes" | "on"
        ),
        _ => false,
    }
}

fn value_string(value: Option<&Value>) -> Option<String> {
    match value? {
        Value::Null => Some(String::new()),
        Value::String(value) => Some(value.clone()),
        Value::Number(value) => Some(value.to_string()),
        Value::Bool(value) => Some(value.to_string()),
        _ => None,
    }
}

fn optional_nonempty(value: &str) -> Option<String> {
    let trimmed = value.trim();
    (!trimmed.is_empty()).then(|| trimmed.to_string())
}

fn optional_text(value: &str, placeholder: &str) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() || trimmed.eq_ignore_ascii_case(placeholder) {
        None
    } else {
        Some(trimmed.to_string())
    }
}

fn parse_date(value: &str) -> Option<NaiveDate> {
    for pattern in ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"] {
        if let Ok(date) = NaiveDate::parse_from_str(value.trim(), pattern) {
            return Some(date);
        }
    }
    None
}
