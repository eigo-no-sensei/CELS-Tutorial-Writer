//! Public read-only repository for archive schema v2.
//!
//! This module is intentionally read-only. Canonical-history mutation is owned
//! by the crate-private archive-sync repository capability in
//! `archive_sync_repository`; Writer/Viewer callers can depend on this module
//! without receiving a SQLite write handle.

use crate::models::{
    HistoricalStateAuthority, HistoricalStateAuthorityStatus, RevisionBlockReason,
};
use crate::semantic::{
    ArchivedTutorial, AssessmentValue, CefrLevel, ExamIntent, RichTextValue, SelfAssessment,
    SkillScores, TeacherRef, TutorialIdentity, TutorialType,
};
use anyhow::{bail, Context, Result};
use chrono::NaiveDate;
use rusqlite::{Connection, OpenFlags, OptionalExtension, Row};
use serde::{Deserialize, Serialize};
use std::path::Path;

pub const ARCHIVE_SCHEMA_VERSION: i64 = 2;

pub struct ArchiveRepository {
    connection: Connection,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArchiveClass {
    pub class_id: i64,
    pub name: Option<String>,
    pub course_code: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
    pub is_active: bool,
    pub source_present: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArchiveStudent {
    pub uid: i64,
    pub name: Option<String>,
    pub cefr_level: Option<i64>,
    pub school_name: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
    pub source_present: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArchiveClassStudent {
    pub class_id: i64,
    pub student: ArchiveStudent,
    pub attendance: Option<i64>,
    pub tutorial_late: Option<bool>,
    pub last_tutorial_ts: Option<i64>,
    pub test_type: Option<String>,
    pub last_test_ts: Option<i64>,
    pub unmarked_exit_test: Option<bool>,
    pub membership_source_present: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ArchiveTutorialListItem {
    pub tutorial_id: i64,
    pub student_uid: i64,
    pub tutorial_ts: i64,
    pub source_present: bool,
    pub authority_status: Option<HistoricalStateAuthorityStatus>,
    pub collision_group_id: Option<i64>,
    pub tutorial_type: Option<TutorialType>,
    pub custom_date: Option<String>,
    pub teacher_name: Option<String>,
    pub absent: Option<bool>,
    pub overall_level: Option<String>,
    pub revision_available: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ArchiveRevisionBlockReason {
    Authority(RevisionBlockReason),
    IdentityNotPresent,
    SourceStateNotPresent,
    MissingAssociation,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum ArchiveRevisionAvailability {
    Available { tutorial: Box<ArchivedTutorial> },
    Blocked { reason: ArchiveRevisionBlockReason },
    NotFound,
}

impl ArchiveRepository {
    /// Open an existing archive-v2 database in SQLite read-only + query-only mode.
    /// This constructor never creates a database and never exposes its connection.
    pub fn open_read_only(path: impl AsRef<Path>) -> Result<Self> {
        let connection = Connection::open_with_flags(
            path,
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )?;
        validate_archive_v2_connection(&connection)?;
        connection.execute_batch("PRAGMA query_only=ON;")?;
        Ok(Self { connection })
    }

    pub fn list_classes(&self, include_not_present: bool) -> Result<Vec<ArchiveClass>> {
        let mut statement = self.connection.prepare(
            "SELECT class_id, name, course_code, start_date, end_date, is_active, source_present\n             FROM classes\n             WHERE ?1 = 1 OR source_present = 1\n             ORDER BY COALESCE(name, ''), class_id",
        )?;
        let rows = statement.query_map([bool_int(include_not_present)], |row| {
            Ok(ArchiveClass {
                class_id: row.get(0)?,
                name: row.get(1)?,
                course_code: row.get(2)?,
                start_date: row.get(3)?,
                end_date: row.get(4)?,
                is_active: int_bool(row.get(5)?),
                source_present: int_bool(row.get(6)?),
            })
        })?;
        let values = rows.collect::<rusqlite::Result<Vec<_>>>()?;
        Ok(values)
    }

    pub fn list_students_for_class(
        &self,
        class_id: i64,
        include_not_present: bool,
    ) -> Result<Vec<ArchiveClassStudent>> {
        let mut statement = self.connection.prepare(
            "SELECT m.class_id, s.uid, s.name, s.cefr_level, s.school_name, s.start_date, s.end_date,\n                    s.source_present, m.attendance, m.tutorial_late, m.last_tutorial_ts,\n                    m.test_type, m.last_test_ts, m.unmarked_exit_test, m.source_present\n             FROM class_memberships AS m\n             JOIN students AS s ON s.uid = m.student_uid\n             WHERE m.class_id = ?1\n               AND (?2 = 1 OR (m.source_present = 1 AND s.source_present = 1))\n             ORDER BY COALESCE(s.name, ''), s.uid",
        )?;
        let rows = statement.query_map(
            rusqlite::params![class_id, bool_int(include_not_present)],
            |row| {
                Ok(ArchiveClassStudent {
                    class_id: row.get(0)?,
                    student: ArchiveStudent {
                        uid: row.get(1)?,
                        name: row.get(2)?,
                        cefr_level: row.get(3)?,
                        school_name: row.get(4)?,
                        start_date: row.get(5)?,
                        end_date: row.get(6)?,
                        source_present: int_bool(row.get(7)?),
                    },
                    attendance: row.get(8)?,
                    tutorial_late: optional_int_bool(row.get(9)?),
                    last_tutorial_ts: row.get(10)?,
                    test_type: row.get(11)?,
                    last_test_ts: row.get(12)?,
                    unmarked_exit_test: optional_int_bool(row.get(13)?),
                    membership_source_present: int_bool(row.get(14)?),
                })
            },
        )?;
        let values = rows.collect::<rusqlite::Result<Vec<_>>>()?;
        Ok(values)
    }

    pub fn list_tutorials_for_student(
        &self,
        student_uid: i64,
        include_not_present: bool,
    ) -> Result<Vec<ArchiveTutorialListItem>> {
        let mut statement = self.connection.prepare(
            "SELECT i.tutorial_id, i.student_uid, i.tutorial_ts, i.source_present,\n                    a.authority_status, a.collision_group_id,\n                    s.source_present, s.tutorial_type, s.custom_date, s.teacher_name,\n                    s.absent, s.overall_level\n             FROM tutorial_identities AS i\n             LEFT JOIN tutorial_state_associations AS a ON a.tutorial_id = i.tutorial_id\n             LEFT JOIN tutorial_source_states AS s ON s.source_state_id = a.source_state_id\n             WHERE i.student_uid = ?1 AND (?2 = 1 OR i.source_present = 1)\n             ORDER BY i.tutorial_ts DESC, i.tutorial_id DESC",
        )?;
        let rows = statement.query_map(
            rusqlite::params![student_uid, bool_int(include_not_present)],
            read_tutorial_list_item,
        )?;
        let values = rows.collect::<rusqlite::Result<Vec<_>>>()?;
        Ok(values)
    }

    /// Load a revision-ready historical tutorial. Ambiguous authority or stale
    /// source-presence is returned as an explicit blocked result rather than a
    /// partially populated semantic value.
    pub fn revision_source(&self, tutorial_id: i64) -> Result<ArchiveRevisionAvailability> {
        let row = self
            .connection
            .query_row(
                "SELECT i.tutorial_id, i.student_uid, i.tutorial_ts, i.source_present,\n                        a.authority_status, a.collision_group_id, a.source_state_id,\n                        s.source_present, s.tutorial_type, s.ttype_raw, s.teacher_id,\n                        s.teacher_name, s.custom_date, s.absent, s.overall_level,\n                        s.speaking, s.use_of_english, s.writing, s.listening, s.reading,\n                        s.speaking_before, s.uoe_before, s.writing_before, s.listening_before,\n                        s.exam_want, s.exam_which, s.exam_when,\n                        s.self_listening, s.self_reading, s.self_writing, s.self_speaking,\n                        s.self_vocabulary, s.self_grammar, s.self_pronunciation,\n                        s.aims, s.teacher_comments, s.additional_comments\n                 FROM tutorial_identities AS i\n                 LEFT JOIN tutorial_state_associations AS a ON a.tutorial_id = i.tutorial_id\n                 LEFT JOIN tutorial_source_states AS s ON s.source_state_id = a.source_state_id\n                 WHERE i.tutorial_id = ?1",
                [tutorial_id],
                read_stored_revision_row,
            )
            .optional()?;

        let Some(row) = row else {
            return Ok(ArchiveRevisionAvailability::NotFound);
        };
        if !row.identity_source_present {
            return Ok(ArchiveRevisionAvailability::Blocked {
                reason: ArchiveRevisionBlockReason::IdentityNotPresent,
            });
        }
        let Some(authority_status) = row.authority_status else {
            return Ok(ArchiveRevisionAvailability::Blocked {
                reason: ArchiveRevisionBlockReason::MissingAssociation,
            });
        };
        let authority = historical_authority(authority_status, row.student_uid, row.tutorial_ts);
        if !authority.permits_revision_by_id() {
            return Ok(ArchiveRevisionAvailability::Blocked {
                reason: ArchiveRevisionBlockReason::Authority(revision_block_reason(
                    authority_status,
                )),
            });
        }
        if row.source_state_present != Some(true) {
            return Ok(ArchiveRevisionAvailability::Blocked {
                reason: ArchiveRevisionBlockReason::SourceStateNotPresent,
            });
        }

        let tutorial_type = row
            .tutorial_type
            .as_deref()
            .and_then(parse_tutorial_type_label)
            .with_context(|| format!("tutorial {tutorial_id} has no valid stored tutorial_type"))?;
        let tutorial_date = row
            .custom_date
            .as_deref()
            .and_then(parse_archive_date)
            .with_context(|| format!("tutorial {tutorial_id} has no valid custom_date"))?;
        let absent = row
            .absent
            .with_context(|| format!("tutorial {tutorial_id} has no authoritative absent value"))?;

        let primary = SkillScores {
            speaking: parse_level(row.speaking.as_deref()),
            use_of_english: parse_level(row.use_of_english.as_deref()),
            writing: parse_level(row.writing.as_deref()),
            listening: parse_level(row.listening.as_deref()),
        };
        let before = SkillScores {
            speaking: parse_level(row.speaking_before.as_deref()),
            use_of_english: parse_level(row.uoe_before.as_deref()),
            writing: parse_level(row.writing_before.as_deref()),
            listening: parse_level(row.listening_before.as_deref()),
        };
        let (initial_scores, current_scores) = match tutorial_type {
            TutorialType::Initial => (primary, SkillScores::default()),
            TutorialType::Standard => (SkillScores::default(), primary),
            TutorialType::Final => (before, primary),
        };

        let tutorial = ArchivedTutorial {
            identity: TutorialIdentity {
                tutorial_id: row.tutorial_id,
                student_uid: row.student_uid,
                tutorial_ts: row.tutorial_ts,
                tutorial_type,
            },
            state_authority: authority,
            tutorial_date,
            teacher: TeacherRef {
                teacher_id: row.teacher_id,
                teacher_name: row.teacher_name,
            },
            absent,
            overall_level_raw: row.overall_level.unwrap_or_default(),
            initial_scores,
            current_scores,
            reading: parse_level(row.reading.as_deref()),
            self_assessment: SelfAssessment {
                listening: parse_assessment(row.self_listening.as_deref()),
                reading: parse_assessment(row.self_reading.as_deref()),
                writing: parse_assessment(row.self_writing.as_deref()),
                speaking: parse_assessment(row.self_speaking.as_deref()),
                vocabulary: parse_assessment(row.self_vocabulary.as_deref()),
                grammar: parse_assessment(row.self_grammar.as_deref()),
                pronunciation: parse_assessment(row.self_pronunciation.as_deref()),
            },
            exam: ExamIntent {
                intent: clean_optional(row.exam_want),
                exam_type: clean_optional(row.exam_which),
                when: clean_optional(row.exam_when),
            },
            aims: RichTextValue {
                html: String::new(),
                text: row.aims.unwrap_or_default(),
            },
            teacher_comments: row.teacher_comments.unwrap_or_default(),
            additional_comments: row.additional_comments.unwrap_or_default(),
        };
        Ok(ArchiveRevisionAvailability::Available {
            tutorial: Box::new(tutorial),
        })
    }
}

pub(crate) fn validate_archive_v2_connection(connection: &Connection) -> Result<()> {
    connection.execute_batch("PRAGMA foreign_keys=ON;")?;
    let foreign_keys: i64 =
        connection.pragma_query_value(None, "foreign_keys", |row| row.get(0))?;
    if foreign_keys != 1 {
        bail!("archive repository could not enable SQLite foreign_keys");
    }
    let user_version: i64 =
        connection.pragma_query_value(None, "user_version", |row| row.get(0))?;
    if user_version != ARCHIVE_SCHEMA_VERSION {
        bail!(
            "archive repository requires schema v{ARCHIVE_SCHEMA_VERSION}, found user_version={user_version}"
        );
    }
    let migration_present: bool = connection.query_row(
        "SELECT EXISTS(SELECT 1 FROM archive_schema_migrations WHERE version=?1)",
        [ARCHIVE_SCHEMA_VERSION],
        |row| row.get(0),
    )?;
    if !migration_present {
        bail!("archive schema v2 migration metadata is missing");
    }
    let view_present: bool = connection.query_row(
        "SELECT EXISTS(SELECT 1 FROM sqlite_master WHERE type='view' AND name='tutorial_revision_state')",
        [],
        |row| row.get(0),
    )?;
    if !view_present {
        bail!("archive schema v2 tutorial_revision_state view is missing");
    }
    let mut foreign_key_check = connection.prepare("PRAGMA foreign_key_check")?;
    if foreign_key_check.exists([])? {
        bail!("archive repository refused database with foreign-key violations");
    }
    Ok(())
}

fn read_tutorial_list_item(row: &Row<'_>) -> rusqlite::Result<ArchiveTutorialListItem> {
    let identity_present = int_bool(row.get(3)?);
    let authority_raw: Option<String> = row.get(4)?;
    let authority_status = authority_raw.as_deref().and_then(parse_authority_status);
    let state_present: Option<i64> = row.get(6)?;
    let revision_available = identity_present
        && state_present.map(int_bool).unwrap_or(false)
        && authority_status
            .map(|status| {
                matches!(
                    status,
                    HistoricalStateAuthorityStatus::ProvenPerTutorial
                        | HistoricalStateAuthorityStatus::SharedIdenticalCollision
                )
            })
            .unwrap_or(false);
    Ok(ArchiveTutorialListItem {
        tutorial_id: row.get(0)?,
        student_uid: row.get(1)?,
        tutorial_ts: row.get(2)?,
        source_present: identity_present,
        authority_status,
        collision_group_id: row.get(5)?,
        tutorial_type: row
            .get::<_, Option<String>>(7)?
            .as_deref()
            .and_then(parse_tutorial_type_label),
        custom_date: row.get(8)?,
        teacher_name: row.get(9)?,
        absent: optional_int_bool(row.get(10)?),
        overall_level: row.get(11)?,
        revision_available,
    })
}

#[derive(Debug)]
struct StoredRevisionRow {
    tutorial_id: i64,
    student_uid: i64,
    tutorial_ts: i64,
    identity_source_present: bool,
    authority_status: Option<HistoricalStateAuthorityStatus>,
    source_state_present: Option<bool>,
    tutorial_type: Option<String>,
    teacher_id: Option<i64>,
    teacher_name: Option<String>,
    custom_date: Option<String>,
    absent: Option<bool>,
    overall_level: Option<String>,
    speaking: Option<String>,
    use_of_english: Option<String>,
    writing: Option<String>,
    listening: Option<String>,
    reading: Option<String>,
    speaking_before: Option<String>,
    uoe_before: Option<String>,
    writing_before: Option<String>,
    listening_before: Option<String>,
    exam_want: Option<String>,
    exam_which: Option<String>,
    exam_when: Option<String>,
    self_listening: Option<String>,
    self_reading: Option<String>,
    self_writing: Option<String>,
    self_speaking: Option<String>,
    self_vocabulary: Option<String>,
    self_grammar: Option<String>,
    self_pronunciation: Option<String>,
    aims: Option<String>,
    teacher_comments: Option<String>,
    additional_comments: Option<String>,
}

fn read_stored_revision_row(row: &Row<'_>) -> rusqlite::Result<StoredRevisionRow> {
    Ok(StoredRevisionRow {
        tutorial_id: row.get(0)?,
        student_uid: row.get(1)?,
        tutorial_ts: row.get(2)?,
        identity_source_present: int_bool(row.get(3)?),
        authority_status: row
            .get::<_, Option<String>>(4)?
            .as_deref()
            .and_then(parse_authority_status),
        source_state_present: optional_int_bool(row.get(7)?),
        tutorial_type: row.get(8)?,
        teacher_id: row.get(10)?,
        teacher_name: row.get(11)?,
        custom_date: row.get(12)?,
        absent: optional_int_bool(row.get(13)?),
        overall_level: row.get(14)?,
        speaking: row.get(15)?,
        use_of_english: row.get(16)?,
        writing: row.get(17)?,
        listening: row.get(18)?,
        reading: row.get(19)?,
        speaking_before: row.get(20)?,
        uoe_before: row.get(21)?,
        writing_before: row.get(22)?,
        listening_before: row.get(23)?,
        exam_want: row.get(24)?,
        exam_which: row.get(25)?,
        exam_when: row.get(26)?,
        self_listening: row.get(27)?,
        self_reading: row.get(28)?,
        self_writing: row.get(29)?,
        self_speaking: row.get(30)?,
        self_vocabulary: row.get(31)?,
        self_grammar: row.get(32)?,
        self_pronunciation: row.get(33)?,
        aims: row.get(34)?,
        teacher_comments: row.get(35)?,
        additional_comments: row.get(36)?,
    })
}

pub(crate) fn parse_authority_status(value: &str) -> Option<HistoricalStateAuthorityStatus> {
    match value {
        "proven_per_tutorial" => Some(HistoricalStateAuthorityStatus::ProvenPerTutorial),
        "shared_identical_collision" => {
            Some(HistoricalStateAuthorityStatus::SharedIdenticalCollision)
        }
        "ambiguous_divergent_collision" => {
            Some(HistoricalStateAuthorityStatus::AmbiguousDivergentCollision)
        }
        "incomplete_collision_evidence" => {
            Some(HistoricalStateAuthorityStatus::IncompleteCollisionEvidence)
        }
        "ambiguous_collision_unknown" => {
            Some(HistoricalStateAuthorityStatus::AmbiguousCollisionUnknown)
        }
        "unmatched_source_state" => Some(HistoricalStateAuthorityStatus::UnmatchedSourceState),
        _ => None,
    }
}

pub(crate) fn authority_status_db_value(status: HistoricalStateAuthorityStatus) -> &'static str {
    match status {
        HistoricalStateAuthorityStatus::ProvenPerTutorial => "proven_per_tutorial",
        HistoricalStateAuthorityStatus::SharedIdenticalCollision => "shared_identical_collision",
        HistoricalStateAuthorityStatus::AmbiguousDivergentCollision => {
            "ambiguous_divergent_collision"
        }
        HistoricalStateAuthorityStatus::IncompleteCollisionEvidence => {
            "incomplete_collision_evidence"
        }
        HistoricalStateAuthorityStatus::AmbiguousCollisionUnknown => "ambiguous_collision_unknown",
        HistoricalStateAuthorityStatus::UnmatchedSourceState => "unmatched_source_state",
    }
}

fn historical_authority(
    status: HistoricalStateAuthorityStatus,
    student_uid: i64,
    tutorial_ts: i64,
) -> HistoricalStateAuthority {
    match status {
        HistoricalStateAuthorityStatus::ProvenPerTutorial => HistoricalStateAuthority::proven(),
        HistoricalStateAuthorityStatus::UnmatchedSourceState => {
            HistoricalStateAuthority::unmatched()
        }
        collision => HistoricalStateAuthority::for_collision(collision, student_uid, tutorial_ts),
    }
}

fn revision_block_reason(status: HistoricalStateAuthorityStatus) -> RevisionBlockReason {
    match status {
        HistoricalStateAuthorityStatus::AmbiguousDivergentCollision => {
            RevisionBlockReason::DivergentCollision
        }
        HistoricalStateAuthorityStatus::IncompleteCollisionEvidence => {
            RevisionBlockReason::IncompleteCollisionEvidence
        }
        HistoricalStateAuthorityStatus::AmbiguousCollisionUnknown => {
            RevisionBlockReason::AmbiguousCollisionUnknown
        }
        HistoricalStateAuthorityStatus::UnmatchedSourceState => {
            RevisionBlockReason::UnmatchedSourceState
        }
        HistoricalStateAuthorityStatus::ProvenPerTutorial
        | HistoricalStateAuthorityStatus::SharedIdenticalCollision => {
            RevisionBlockReason::UnmatchedSourceState
        }
    }
}

fn parse_tutorial_type_label(value: &str) -> Option<TutorialType> {
    match value.trim() {
        "Initial" => Some(TutorialType::Initial),
        "Standard" => Some(TutorialType::Standard),
        "Final" => Some(TutorialType::Final),
        _ => None,
    }
}

fn parse_archive_date(value: &str) -> Option<NaiveDate> {
    NaiveDate::parse_from_str(value.trim(), "%d-%m-%Y")
        .or_else(|_| NaiveDate::parse_from_str(value.trim(), "%Y-%m-%d"))
        .ok()
}

fn parse_level(value: Option<&str>) -> Option<CefrLevel> {
    value.and_then(CefrLevel::parse)
}

fn parse_assessment(value: Option<&str>) -> Option<AssessmentValue> {
    value.and_then(AssessmentValue::parse)
}

fn clean_optional(value: Option<String>) -> Option<String> {
    value.and_then(|value| {
        let trimmed = value.trim();
        if trimmed.is_empty() || trimmed.eq_ignore_ascii_case("none") {
            None
        } else {
            Some(trimmed.to_string())
        }
    })
}

fn int_bool(value: i64) -> bool {
    value != 0
}

fn optional_int_bool(value: Option<i64>) -> Option<bool> {
    value.map(int_bool)
}

fn bool_int(value: bool) -> i64 {
    if value {
        1
    } else {
        0
    }
}
