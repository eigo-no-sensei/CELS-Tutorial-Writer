//! Crate-private archive-schema-v2 write capability.
//!
//! D2 keeps this module private to `gel-core`. After A2, external Writer and
//! Viewer crates still cannot construct a canonical-history writer: the public
//! production entry point is `RustArchiver`, which delegates transactional
//! SQLite mutation to this capability without exposing it outside the crate.
#![allow(dead_code)]

use crate::archive_repository::{authority_status_db_value, validate_archive_v2_connection};
use crate::models::HistoricalStateAuthorityStatus;
use crate::semantic::TutorialType;
use anyhow::{bail, Context, Result};
use chrono::Utc;
use rusqlite::{params, Connection, OpenFlags, OptionalExtension};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fmt::Write as _;
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) enum SyncScope {
    /// Fully authoritative acquisition: unseen identities and source evidence
    /// may be marked source-absent after a successful run.
    Full,
    /// Authoritative identity acquisition with incomplete auxiliary
    /// summary/print/edit evidence. Unseen source states/collision groups are
    /// retained for still-present API tutorial keys, while truly disappeared
    /// identities and their evidence are still invalidated.
    FullPreserveSourceEvidence,
    Targeted(String),
}

impl SyncScope {
    fn db_value(&self) -> String {
        match self {
            Self::Full => "full".to_string(),
            Self::FullPreserveSourceEvidence => "full:preserve_source_evidence".to_string(),
            Self::Targeted(label) => format!("targeted:{label}"),
        }
    }

    fn invalidates_unseen(&self) -> bool {
        matches!(self, Self::Full | Self::FullPreserveSourceEvidence)
    }

    fn preserves_unseen_source_evidence(&self) -> bool {
        matches!(self, Self::FullPreserveSourceEvidence)
    }
}

#[derive(Debug)]
pub(crate) struct ArchiveSyncRepository {
    connection: Connection,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct ClassWrite {
    pub class_id: i64,
    pub name: Option<String>,
    pub course_code: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
    pub is_active: bool,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct StudentWrite {
    pub uid: i64,
    pub name: Option<String>,
    pub cefr_level: Option<i64>,
    pub school_name: Option<String>,
    pub start_date: Option<String>,
    pub end_date: Option<String>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct MembershipWrite {
    pub class_id: i64,
    pub student_uid: i64,
    pub attendance: Option<i64>,
    pub tutorial_late: Option<bool>,
    pub last_tutorial_ts: Option<i64>,
    pub test_type: Option<String>,
    pub last_test_ts: Option<i64>,
    pub unmarked_exit_test: Option<bool>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct TutorialIdentityWrite {
    pub tutorial_id: i64,
    pub student_uid: i64,
    pub tutorial_ts: i64,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct TutorialSourceStateWrite {
    pub student_uid: i64,
    pub tutorial_ts: i64,
    pub tutorial_type: Option<TutorialType>,
    pub ttype_raw: Option<String>,
    pub teacher_id: Option<i64>,
    pub teacher_id_source: Option<String>,
    pub teacher_name: Option<String>,
    pub custom_date: Option<String>,
    pub absent: Option<bool>,
    pub overall_level: Option<String>,
    pub speaking: Option<String>,
    pub use_of_english: Option<String>,
    pub writing: Option<String>,
    pub listening: Option<String>,
    pub reading: Option<String>,
    pub speaking_before: Option<String>,
    pub uoe_before: Option<String>,
    pub writing_before: Option<String>,
    pub listening_before: Option<String>,
    pub exam_want: Option<String>,
    pub exam_which: Option<String>,
    pub exam_when: Option<String>,
    pub self_listening: Option<String>,
    pub self_reading: Option<String>,
    pub self_writing: Option<String>,
    pub self_speaking: Option<String>,
    pub self_vocabulary: Option<String>,
    pub self_grammar: Option<String>,
    pub self_pronunciation: Option<String>,
    pub aims: Option<String>,
    pub teacher_comments: Option<String>,
    pub additional_comments: Option<String>,
    pub source_method: Option<String>,
    pub summary_url: Option<String>,
    pub print_url: Option<String>,
    pub edit_url: Option<String>,
    pub summary_match_method: Option<String>,
}

impl TutorialSourceStateWrite {
    pub(crate) fn state_fingerprint(&self) -> Result<String> {
        let mut payload = BTreeMap::<String, Value>::new();
        payload.insert("student_uid".into(), json!(self.student_uid));
        payload.insert("tutorial_ts".into(), json!(self.tutorial_ts));
        payload.insert(
            "tutorial_type".into(),
            self.tutorial_type
                .map(tutorial_type_label)
                .map(Value::from)
                .unwrap_or(Value::Null),
        );
        insert_text(&mut payload, "ttype_raw", &self.ttype_raw);
        payload.insert(
            "teacher_id".into(),
            self.teacher_id.map(Value::from).unwrap_or(Value::Null),
        );
        insert_text(&mut payload, "teacher_id_source", &self.teacher_id_source);
        insert_text(&mut payload, "teacher_name", &self.teacher_name);
        insert_text(&mut payload, "custom_date", &self.custom_date);
        payload.insert(
            "absent".into(),
            self.absent
                .map(|value| Value::from(bool_int(value)))
                .unwrap_or(Value::Null),
        );
        insert_text(&mut payload, "overall_level", &self.overall_level);
        insert_text(&mut payload, "speaking", &self.speaking);
        insert_text(&mut payload, "use_of_english", &self.use_of_english);
        insert_text(&mut payload, "writing", &self.writing);
        insert_text(&mut payload, "listening", &self.listening);
        insert_text(&mut payload, "reading", &self.reading);
        insert_text(&mut payload, "speaking_before", &self.speaking_before);
        insert_text(&mut payload, "uoe_before", &self.uoe_before);
        insert_text(&mut payload, "writing_before", &self.writing_before);
        insert_text(&mut payload, "listening_before", &self.listening_before);
        insert_text(&mut payload, "exam_want", &self.exam_want);
        insert_text(&mut payload, "exam_which", &self.exam_which);
        insert_text(&mut payload, "exam_when", &self.exam_when);
        insert_text(&mut payload, "self_listening", &self.self_listening);
        insert_text(&mut payload, "self_reading", &self.self_reading);
        insert_text(&mut payload, "self_writing", &self.self_writing);
        insert_text(&mut payload, "self_speaking", &self.self_speaking);
        insert_text(&mut payload, "self_vocabulary", &self.self_vocabulary);
        insert_text(&mut payload, "self_grammar", &self.self_grammar);
        insert_text(&mut payload, "self_pronunciation", &self.self_pronunciation);
        insert_text(&mut payload, "aims", &self.aims);
        insert_text(&mut payload, "teacher_comments", &self.teacher_comments);
        insert_text(
            &mut payload,
            "additional_comments",
            &self.additional_comments,
        );

        // D1 migration intentionally excludes acquisition-route/provenance URLs
        // from semantic source-state identity. Keep Rust parity exact.
        let encoded = serde_json::to_vec(&payload)?;
        let digest = Sha256::digest(encoded);
        let mut out = String::with_capacity(64);
        for byte in digest {
            write!(&mut out, "{byte:02x}").expect("writing to String cannot fail");
        }
        Ok(out)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum EvidenceSourceKind {
    Api,
    Summary,
    Edit,
    Print,
    Legacy,
}

impl EvidenceSourceKind {
    fn db_value(self) -> &'static str {
        match self {
            Self::Api => "api",
            Self::Summary => "summary",
            Self::Edit => "edit",
            Self::Print => "print",
            Self::Legacy => "legacy",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum FieldPresence {
    Present,
    PresentBlank,
    Missing,
}

impl FieldPresence {
    fn db_value(self) -> &'static str {
        match self {
            Self::Present => "present",
            Self::PresentBlank => "present_blank",
            Self::Missing => "missing",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum StoredCollisionKind {
    IdenticalState,
    DivergentState,
    IncompleteEvidence,
    AmbiguousUnknown,
}

impl StoredCollisionKind {
    fn db_value(self) -> &'static str {
        match self {
            Self::IdenticalState => "identical_state",
            Self::DivergentState => "divergent_state",
            Self::IncompleteEvidence => "incomplete_evidence",
            Self::AmbiguousUnknown => "ambiguous_unknown",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct StateAssociationWrite {
    pub tutorial_id: i64,
    pub authority_status: HistoricalStateAuthorityStatus,
    pub source_state_id: Option<i64>,
    pub collision_group_id: Option<i64>,
    pub proof_method: String,
}

pub(crate) struct ArchiveSyncSession<'a> {
    connection: &'a Connection,
    run_id: i64,
    seen_at: String,
}

impl ArchiveSyncRepository {
    pub(crate) fn open_existing(path: impl AsRef<Path>) -> Result<Self> {
        let connection = Connection::open_with_flags(
            path,
            OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        )?;
        validate_archive_v2_connection(&connection)?;
        Ok(Self { connection })
    }

    pub(crate) fn run_sync<T>(
        &mut self,
        source: &str,
        scope: SyncScope,
        operation: impl FnOnce(&ArchiveSyncSession<'_>) -> Result<T>,
    ) -> Result<T> {
        if source.trim().is_empty() {
            bail!("archive sync source must not be blank");
        }
        if let SyncScope::Targeted(label) = &scope {
            if label.trim().is_empty() {
                bail!("targeted archive sync scope label must not be blank");
            }
        }

        let started_at = Utc::now().to_rfc3339();
        self.connection.execute(
            "INSERT INTO archive_sync_runs(source, scope, status, started_at)\n             VALUES (?1, ?2, 'running', ?3)",
            params![source.trim(), scope.db_value(), started_at],
        )?;
        let run_id = self.connection.last_insert_rowid();

        let transaction = self.connection.transaction()?;
        let session = ArchiveSyncSession {
            connection: &transaction,
            run_id,
            seen_at: started_at,
        };
        let operation_result = operation(&session);

        match operation_result {
            Ok(value) => {
                let completed_at = Utc::now().to_rfc3339();
                match finalize_success(&transaction, &scope, run_id, &completed_at) {
                    Ok(()) => match transaction.commit() {
                        Ok(()) => Ok(value),
                        Err(error) => {
                            let message = format!("archive sync commit failed: {error}");
                            mark_run_failed(&self.connection, run_id, &message)?;
                            bail!(message)
                        }
                    },
                    Err(error) => {
                        transaction.rollback()?;
                        let message =
                            format!("archive sync validation/finalization failed: {error:#}");
                        mark_run_failed(&self.connection, run_id, &message)?;
                        bail!(message)
                    }
                }
            }
            Err(error) => {
                transaction.rollback()?;
                let message = format!("archive sync operation failed: {error:#}");
                mark_run_failed(&self.connection, run_id, &message)?;
                bail!(message)
            }
        }
    }
}

impl ArchiveSyncSession<'_> {
    pub(crate) fn run_id(&self) -> i64 {
        self.run_id
    }

    pub(crate) fn upsert_class(&self, value: &ClassWrite) -> Result<()> {
        require_positive(value.class_id, "class_id")?;
        self.connection.execute(
            "INSERT INTO classes(\n                class_id, name, course_code, start_date, end_date, is_active,\n                source_present, first_seen, last_seen, last_seen_run_id, presence_checked_run_id\n             ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 1, ?7, ?7, ?8, NULL)\n             ON CONFLICT(class_id) DO UPDATE SET\n                name=excluded.name, course_code=excluded.course_code, start_date=excluded.start_date,\n                end_date=excluded.end_date, is_active=excluded.is_active, source_present=1,\n                last_seen=excluded.last_seen, last_seen_run_id=excluded.last_seen_run_id,\n                presence_checked_run_id=NULL",
            params![
                value.class_id,
                value.name,
                value.course_code,
                value.start_date,
                value.end_date,
                bool_int(value.is_active),
                self.seen_at,
                self.run_id,
            ],
        )?;
        Ok(())
    }

    pub(crate) fn upsert_student(&self, value: &StudentWrite) -> Result<()> {
        require_positive(value.uid, "student uid")?;
        self.connection.execute(
            "INSERT INTO students(\n                uid, name, cefr_level, school_name, start_date, end_date,\n                source_present, first_seen, last_seen, last_seen_run_id, presence_checked_run_id\n             ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 1, ?7, ?7, ?8, NULL)\n             ON CONFLICT(uid) DO UPDATE SET\n                name=excluded.name, cefr_level=excluded.cefr_level, school_name=excluded.school_name,\n                start_date=excluded.start_date, end_date=excluded.end_date, source_present=1,\n                last_seen=excluded.last_seen, last_seen_run_id=excluded.last_seen_run_id,\n                presence_checked_run_id=NULL",
            params![
                value.uid,
                value.name,
                value.cefr_level,
                value.school_name,
                value.start_date,
                value.end_date,
                self.seen_at,
                self.run_id,
            ],
        )?;
        Ok(())
    }

    pub(crate) fn upsert_membership(&self, value: &MembershipWrite) -> Result<()> {
        require_positive(value.class_id, "membership class_id")?;
        require_positive(value.student_uid, "membership student_uid")?;
        self.connection.execute(
            "INSERT INTO class_memberships(\n                class_id, student_uid, attendance, tutorial_late, last_tutorial_ts, test_type,\n                last_test_ts, unmarked_exit_test, source_present, first_seen, last_seen,\n                last_seen_run_id, presence_checked_run_id\n             ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, 1, ?9, ?9, ?10, NULL)\n             ON CONFLICT(class_id, student_uid) DO UPDATE SET\n                attendance=excluded.attendance, tutorial_late=excluded.tutorial_late,\n                last_tutorial_ts=excluded.last_tutorial_ts, test_type=excluded.test_type,\n                last_test_ts=excluded.last_test_ts, unmarked_exit_test=excluded.unmarked_exit_test,\n                source_present=1, last_seen=excluded.last_seen,\n                last_seen_run_id=excluded.last_seen_run_id, presence_checked_run_id=NULL",
            params![
                value.class_id,
                value.student_uid,
                value.attendance,
                optional_bool_int(value.tutorial_late),
                value.last_tutorial_ts,
                value.test_type,
                value.last_test_ts,
                optional_bool_int(value.unmarked_exit_test),
                self.seen_at,
                self.run_id,
            ],
        )?;
        Ok(())
    }

    pub(crate) fn upsert_tutorial_identity(&self, value: &TutorialIdentityWrite) -> Result<()> {
        require_positive(value.tutorial_id, "tutorial_id")?;
        require_positive(value.student_uid, "tutorial identity student_uid")?;
        if value.tutorial_ts < 0 {
            bail!("tutorial identity timestamp must be non-negative");
        }
        let existing: Option<(i64, i64)> = self
            .connection
            .query_row(
                "SELECT student_uid, tutorial_ts FROM tutorial_identities WHERE tutorial_id=?1",
                [value.tutorial_id],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .optional()?;
        if let Some((student_uid, tutorial_ts)) = existing {
            if student_uid != value.student_uid || tutorial_ts != value.tutorial_ts {
                bail!(
                    "canonical tutorial_id {} cannot be re-keyed from ({student_uid},{tutorial_ts}) to ({},{})",
                    value.tutorial_id,
                    value.student_uid,
                    value.tutorial_ts
                );
            }
        }
        self.connection.execute(
            "INSERT INTO tutorial_identities(\n                tutorial_id, student_uid, tutorial_ts, source_present, first_seen, last_seen,\n                last_seen_run_id, presence_checked_run_id\n             ) VALUES (?1, ?2, ?3, 1, ?4, ?4, ?5, NULL)\n             ON CONFLICT(tutorial_id) DO UPDATE SET\n                source_present=1, last_seen=excluded.last_seen,\n                last_seen_run_id=excluded.last_seen_run_id, presence_checked_run_id=NULL",
            params![
                value.tutorial_id,
                value.student_uid,
                value.tutorial_ts,
                self.seen_at,
                self.run_id,
            ],
        )?;
        Ok(())
    }

    pub(crate) fn upsert_source_state(&self, value: &TutorialSourceStateWrite) -> Result<i64> {
        require_positive(value.student_uid, "source-state student_uid")?;
        if value.tutorial_ts < 0 {
            bail!("source-state tutorial_ts must be non-negative");
        }
        let fingerprint = value.state_fingerprint()?;
        self.connection.execute(
            "INSERT INTO tutorial_source_states(\n                student_uid, tutorial_ts, state_fingerprint, tutorial_type, ttype_raw, teacher_id,\n                teacher_id_source, teacher_name, custom_date, absent, overall_level, speaking,\n                use_of_english, writing, listening, reading, speaking_before, uoe_before,\n                writing_before, listening_before, exam_want, exam_which, exam_when, self_listening,\n                self_reading, self_writing, self_speaking, self_vocabulary, self_grammar,\n                self_pronunciation, aims, teacher_comments, additional_comments, source_method,\n                summary_url, print_url, edit_url, summary_match_method, source_present, first_seen,\n                last_seen, last_seen_run_id, presence_checked_run_id\n             ) VALUES (\n                ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16,\n                ?17, ?18, ?19, ?20, ?21, ?22, ?23, ?24, ?25, ?26, ?27, ?28, ?29, ?30,\n                ?31, ?32, ?33, ?34, ?35, ?36, ?37, ?38, 1, ?39, ?39, ?40, NULL\n             )\n             ON CONFLICT(student_uid, tutorial_ts, state_fingerprint) DO UPDATE SET\n                tutorial_type=excluded.tutorial_type, ttype_raw=excluded.ttype_raw,\n                teacher_id=excluded.teacher_id, teacher_id_source=excluded.teacher_id_source,\n                teacher_name=excluded.teacher_name, custom_date=excluded.custom_date,\n                absent=excluded.absent, overall_level=excluded.overall_level, speaking=excluded.speaking,\n                use_of_english=excluded.use_of_english, writing=excluded.writing, listening=excluded.listening,\n                reading=excluded.reading, speaking_before=excluded.speaking_before,\n                uoe_before=excluded.uoe_before, writing_before=excluded.writing_before,\n                listening_before=excluded.listening_before, exam_want=excluded.exam_want,\n                exam_which=excluded.exam_which, exam_when=excluded.exam_when,\n                self_listening=excluded.self_listening, self_reading=excluded.self_reading,\n                self_writing=excluded.self_writing, self_speaking=excluded.self_speaking,\n                self_vocabulary=excluded.self_vocabulary, self_grammar=excluded.self_grammar,\n                self_pronunciation=excluded.self_pronunciation, aims=excluded.aims,\n                teacher_comments=excluded.teacher_comments, additional_comments=excluded.additional_comments,\n                source_method=excluded.source_method, summary_url=excluded.summary_url, print_url=excluded.print_url,\n                edit_url=excluded.edit_url, summary_match_method=excluded.summary_match_method,\n                source_present=1, last_seen=excluded.last_seen,\n                last_seen_run_id=excluded.last_seen_run_id, presence_checked_run_id=NULL",
            params![
                value.student_uid,
                value.tutorial_ts,
                fingerprint,
                value.tutorial_type.map(tutorial_type_label),
                value.ttype_raw,
                value.teacher_id,
                value.teacher_id_source,
                value.teacher_name,
                value.custom_date,
                optional_bool_int(value.absent),
                value.overall_level,
                value.speaking,
                value.use_of_english,
                value.writing,
                value.listening,
                value.reading,
                value.speaking_before,
                value.uoe_before,
                value.writing_before,
                value.listening_before,
                value.exam_want,
                value.exam_which,
                value.exam_when,
                value.self_listening,
                value.self_reading,
                value.self_writing,
                value.self_speaking,
                value.self_vocabulary,
                value.self_grammar,
                value.self_pronunciation,
                value.aims,
                value.teacher_comments,
                value.additional_comments,
                value.source_method,
                value.summary_url,
                value.print_url,
                value.edit_url,
                value.summary_match_method,
                self.seen_at,
                self.run_id,
            ],
        )?;
        self.connection
            .query_row(
                "SELECT source_state_id FROM tutorial_source_states\n                 WHERE student_uid=?1 AND tutorial_ts=?2 AND state_fingerprint=?3",
                params![value.student_uid, value.tutorial_ts, fingerprint],
                |row| row.get(0),
            )
            .map_err(Into::into)
    }

    pub(crate) fn upsert_field_evidence(
        &self,
        source_state_id: i64,
        field_name: &str,
        source_kind: EvidenceSourceKind,
        presence: FieldPresence,
    ) -> Result<()> {
        require_positive(source_state_id, "source_state_id")?;
        if field_name.trim().is_empty() {
            bail!("field evidence field_name must not be blank");
        }
        self.connection.execute(
            "INSERT INTO tutorial_source_field_evidence(\n                source_state_id, field_name, source_kind, presence\n             ) VALUES (?1, ?2, ?3, ?4)\n             ON CONFLICT(source_state_id, field_name, source_kind)\n             DO UPDATE SET presence=excluded.presence",
            params![
                source_state_id,
                field_name.trim(),
                source_kind.db_value(),
                presence.db_value(),
            ],
        )?;
        Ok(())
    }

    pub(crate) fn upsert_collision_group(
        &self,
        student_uid: i64,
        tutorial_ts: i64,
        kind: StoredCollisionKind,
    ) -> Result<i64> {
        require_positive(student_uid, "collision student_uid")?;
        if tutorial_ts < 0 {
            bail!("collision tutorial_ts must be non-negative");
        }
        self.connection.execute(
            "INSERT INTO tutorial_collision_groups(\n                student_uid, tutorial_ts, collision_kind, source_present, first_seen, last_seen,\n                last_seen_run_id, presence_checked_run_id\n             ) VALUES (?1, ?2, ?3, 1, ?4, ?4, ?5, NULL)\n             ON CONFLICT(student_uid, tutorial_ts) DO UPDATE SET\n                collision_kind=excluded.collision_kind, source_present=1, last_seen=excluded.last_seen,\n                last_seen_run_id=excluded.last_seen_run_id, presence_checked_run_id=NULL",
            params![
                student_uid,
                tutorial_ts,
                kind.db_value(),
                self.seen_at,
                self.run_id,
            ],
        )?;
        self.connection
            .query_row(
                "SELECT collision_group_id FROM tutorial_collision_groups\n                 WHERE student_uid=?1 AND tutorial_ts=?2",
                params![student_uid, tutorial_ts],
                |row| row.get(0),
            )
            .map_err(Into::into)
    }

    pub(crate) fn link_collision_identity(
        &self,
        collision_group_id: i64,
        tutorial_id: i64,
    ) -> Result<()> {
        self.connection.execute(
            "INSERT INTO tutorial_collision_identities(collision_group_id, tutorial_id)\n             VALUES (?1, ?2) ON CONFLICT(collision_group_id, tutorial_id) DO NOTHING",
            params![collision_group_id, tutorial_id],
        )?;
        Ok(())
    }

    pub(crate) fn link_collision_state(
        &self,
        collision_group_id: i64,
        source_state_id: i64,
    ) -> Result<()> {
        self.connection.execute(
            "INSERT INTO tutorial_collision_states(collision_group_id, source_state_id)\n             VALUES (?1, ?2) ON CONFLICT(collision_group_id, source_state_id) DO NOTHING",
            params![collision_group_id, source_state_id],
        )?;
        Ok(())
    }

    pub(crate) fn set_state_association(&self, value: &StateAssociationWrite) -> Result<()> {
        require_positive(value.tutorial_id, "association tutorial_id")?;
        if value.proof_method.trim().is_empty() {
            bail!("association proof_method must not be blank");
        }
        validate_association_shape(self.connection, value)?;
        self.connection.execute(
            "INSERT INTO tutorial_state_associations(\n                tutorial_id, authority_status, source_state_id, collision_group_id, proof_method,\n                first_seen, last_seen\n             ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?6)\n             ON CONFLICT(tutorial_id) DO UPDATE SET\n                authority_status=excluded.authority_status, source_state_id=excluded.source_state_id,\n                collision_group_id=excluded.collision_group_id, proof_method=excluded.proof_method,\n                last_seen=excluded.last_seen",
            params![
                value.tutorial_id,
                authority_status_db_value(value.authority_status),
                value.source_state_id,
                value.collision_group_id,
                value.proof_method.trim(),
                self.seen_at,
            ],
        )?;
        Ok(())
    }
}

fn validate_association_shape(
    connection: &Connection,
    value: &StateAssociationWrite,
) -> Result<()> {
    use HistoricalStateAuthorityStatus as Status;
    match value.authority_status {
        Status::ProvenPerTutorial => {
            let state_id = value
                .source_state_id
                .context("proven_per_tutorial association requires source_state_id")?;
            if value.collision_group_id.is_some() {
                bail!("proven_per_tutorial association must not carry collision_group_id");
            }
            require_state_matches_identity(connection, value.tutorial_id, state_id)?;
        }
        Status::SharedIdenticalCollision => {
            let state_id = value
                .source_state_id
                .context("shared_identical_collision requires source_state_id")?;
            let group_id = value
                .collision_group_id
                .context("shared_identical_collision requires collision_group_id")?;
            require_collision_membership(
                connection,
                value.tutorial_id,
                group_id,
                Some(state_id),
                "identical_state",
            )?;
        }
        Status::AmbiguousDivergentCollision => {
            require_blocked_collision_shape(
                connection,
                value,
                "divergent_state",
                "ambiguous_divergent_collision",
            )?;
        }
        Status::IncompleteCollisionEvidence => {
            require_blocked_collision_shape(
                connection,
                value,
                "incomplete_evidence",
                "incomplete_collision_evidence",
            )?;
        }
        Status::AmbiguousCollisionUnknown => {
            require_blocked_collision_shape(
                connection,
                value,
                "ambiguous_unknown",
                "ambiguous_collision_unknown",
            )?;
        }
        Status::UnmatchedSourceState => {
            if value.source_state_id.is_some() || value.collision_group_id.is_some() {
                bail!("unmatched_source_state association must carry neither state nor collision group");
            }
        }
    }
    Ok(())
}

fn require_blocked_collision_shape(
    connection: &Connection,
    value: &StateAssociationWrite,
    expected_kind: &str,
    label: &str,
) -> Result<()> {
    if value.source_state_id.is_some() {
        bail!("{label} must not carry source_state_id");
    }
    let group_id = value
        .collision_group_id
        .with_context(|| format!("{label} requires collision_group_id"))?;
    require_collision_membership(connection, value.tutorial_id, group_id, None, expected_kind)
}

fn require_state_matches_identity(
    connection: &Connection,
    tutorial_id: i64,
    source_state_id: i64,
) -> Result<()> {
    let matches: bool = connection.query_row(
        "SELECT EXISTS(\n            SELECT 1 FROM tutorial_identities AS i\n            JOIN tutorial_source_states AS s\n              ON s.student_uid=i.student_uid AND s.tutorial_ts=i.tutorial_ts\n            WHERE i.tutorial_id=?1 AND s.source_state_id=?2\n         )",
        params![tutorial_id, source_state_id],
        |row| row.get(0),
    )?;
    if !matches {
        bail!("source state does not match canonical tutorial identity reconciliation key");
    }
    Ok(())
}

fn require_collision_membership(
    connection: &Connection,
    tutorial_id: i64,
    collision_group_id: i64,
    source_state_id: Option<i64>,
    expected_kind: &str,
) -> Result<()> {
    let identity_linked: bool = connection.query_row(
        "SELECT EXISTS(\n            SELECT 1 FROM tutorial_collision_groups AS g\n            JOIN tutorial_collision_identities AS ci ON ci.collision_group_id=g.collision_group_id\n            WHERE g.collision_group_id=?1 AND g.collision_kind=?2 AND ci.tutorial_id=?3\n         )",
        params![collision_group_id, expected_kind, tutorial_id],
        |row| row.get(0),
    )?;
    if !identity_linked {
        bail!("tutorial identity is not a member of the required collision group/kind");
    }
    if let Some(source_state_id) = source_state_id {
        let state_linked: bool = connection.query_row(
            "SELECT EXISTS(\n                SELECT 1 FROM tutorial_collision_states\n                WHERE collision_group_id=?1 AND source_state_id=?2\n             )",
            params![collision_group_id, source_state_id],
            |row| row.get(0),
        )?;
        if !state_linked {
            bail!("source state is not group-owned by the required collision group");
        }
    }
    Ok(())
}

fn invalidate_unseen(
    connection: &Connection,
    run_id: i64,
    preserve_source_evidence: bool,
) -> Result<()> {
    // Class/student/API identity acquisition is mandatory for an A2 full run,
    // so absence there is authoritative even when an auxiliary summary/print/
    // edit source failed.
    for table in [
        "class_memberships",
        "tutorial_identities",
        "classes",
        "students",
    ] {
        let sql = format!(
            "UPDATE {table}\n             SET source_present=0, presence_checked_run_id=?1\n             WHERE source_present=1 AND COALESCE(last_seen_run_id, -1) <> ?1"
        );
        connection.execute(&sql, [run_id])?;
    }

    for table in ["tutorial_source_states", "tutorial_collision_groups"] {
        let extra = if preserve_source_evidence {
            // Preserve prior semantic evidence only when this full run still
            // observed an API identity at the same student/timestamp key.
            // Evidence for actually disappeared tutorial keys is invalidated.
            " AND NOT EXISTS (SELECT 1 FROM tutorial_identities AS i \
                 WHERE i.student_uid={table}.student_uid \
                   AND i.tutorial_ts={table}.tutorial_ts \
                   AND i.last_seen_run_id=?1)"
                .replace("{table}", table)
        } else {
            String::new()
        };
        let sql = format!(
            "UPDATE {table}\n             SET source_present=0, presence_checked_run_id=?1\n             WHERE source_present=1 AND COALESCE(last_seen_run_id, -1) <> ?1{extra}"
        );
        connection.execute(&sql, [run_id])?;
    }
    Ok(())
}

fn validate_repository_semantics(connection: &Connection) -> Result<()> {
    let checks = [
        (
            "present class membership requires present class and student",
            "SELECT COUNT(*) FROM class_memberships AS m\n             JOIN classes AS c ON c.class_id=m.class_id\n             JOIN students AS s ON s.uid=m.student_uid\n             WHERE m.source_present=1 AND (c.source_present<>1 OR s.source_present<>1)",
        ),
        (
            "present tutorial identity requires present student",
            "SELECT COUNT(*) FROM tutorial_identities AS i\n             JOIN students AS s ON s.uid=i.student_uid\n             WHERE i.source_present=1 AND s.source_present<>1",
        ),
        (
            "present source state requires present student",
            "SELECT COUNT(*) FROM tutorial_source_states AS st\n             JOIN students AS s ON s.uid=st.student_uid\n             WHERE st.source_present=1 AND s.source_present<>1",
        ),
        (
            "present collision group requires present student",
            "SELECT COUNT(*) FROM tutorial_collision_groups AS g\n             JOIN students AS s ON s.uid=g.student_uid\n             WHERE g.source_present=1 AND s.source_present<>1",
        ),
        (
            "present tutorial identity requires governed association",
            "SELECT COUNT(*) FROM tutorial_identities AS i\n             LEFT JOIN tutorial_state_associations AS a ON a.tutorial_id=i.tutorial_id\n             WHERE i.source_present=1 AND a.tutorial_id IS NULL",
        ),
        (
            "shared-identical association must point to identical group-owned identity/state",
            "SELECT COUNT(*) FROM tutorial_state_associations AS a\n             JOIN tutorial_collision_groups AS g ON g.collision_group_id=a.collision_group_id\n             WHERE a.authority_status='shared_identical_collision' AND (\n                g.collision_kind<>'identical_state' OR\n                NOT EXISTS (SELECT 1 FROM tutorial_collision_identities ci\n                            WHERE ci.collision_group_id=a.collision_group_id AND ci.tutorial_id=a.tutorial_id) OR\n                NOT EXISTS (SELECT 1 FROM tutorial_collision_states cs\n                            WHERE cs.collision_group_id=a.collision_group_id AND cs.source_state_id=a.source_state_id)\n             )",
        ),
        (
            "divergent association must point to divergent group-owned identity",
            "SELECT COUNT(*) FROM tutorial_state_associations AS a\n             JOIN tutorial_collision_groups AS g ON g.collision_group_id=a.collision_group_id\n             WHERE a.authority_status='ambiguous_divergent_collision' AND (\n                g.collision_kind<>'divergent_state' OR a.source_state_id IS NOT NULL OR\n                NOT EXISTS (SELECT 1 FROM tutorial_collision_identities ci\n                            WHERE ci.collision_group_id=a.collision_group_id AND ci.tutorial_id=a.tutorial_id)\n             )",
        ),
        (
            "incomplete association must point to incomplete group-owned identity",
            "SELECT COUNT(*) FROM tutorial_state_associations AS a\n             JOIN tutorial_collision_groups AS g ON g.collision_group_id=a.collision_group_id\n             WHERE a.authority_status='incomplete_collision_evidence' AND (\n                g.collision_kind<>'incomplete_evidence' OR a.source_state_id IS NOT NULL OR\n                NOT EXISTS (SELECT 1 FROM tutorial_collision_identities ci\n                            WHERE ci.collision_group_id=a.collision_group_id AND ci.tutorial_id=a.tutorial_id)\n             )",
        ),
        (
            "unknown collision association must point to unknown group-owned identity",
            "SELECT COUNT(*) FROM tutorial_state_associations AS a\n             JOIN tutorial_collision_groups AS g ON g.collision_group_id=a.collision_group_id\n             WHERE a.authority_status='ambiguous_collision_unknown' AND (\n                g.collision_kind<>'ambiguous_unknown' OR a.source_state_id IS NOT NULL OR\n                NOT EXISTS (SELECT 1 FROM tutorial_collision_identities ci\n                            WHERE ci.collision_group_id=a.collision_group_id AND ci.tutorial_id=a.tutorial_id)\n             )",
        ),
        (
            "present identical collision requires at least two identities and exactly one source state",
            "SELECT COUNT(*) FROM tutorial_collision_groups AS g\n             WHERE g.source_present=1 AND g.collision_kind='identical_state' AND (\n                (SELECT COUNT(*) FROM tutorial_collision_identities ci WHERE ci.collision_group_id=g.collision_group_id) < 2 OR\n                (SELECT COUNT(*) FROM tutorial_collision_states cs WHERE cs.collision_group_id=g.collision_group_id) <> 1\n             )",
        ),
        (
            "present divergent collision requires at least two identities and two source states",
            "SELECT COUNT(*) FROM tutorial_collision_groups AS g\n             WHERE g.source_present=1 AND g.collision_kind='divergent_state' AND (\n                (SELECT COUNT(*) FROM tutorial_collision_identities ci WHERE ci.collision_group_id=g.collision_group_id) < 2 OR\n                (SELECT COUNT(*) FROM tutorial_collision_states cs WHERE cs.collision_group_id=g.collision_group_id) < 2\n             )",
        ),
    ];
    for (label, sql) in checks {
        let count: i64 = connection.query_row(sql, [], |row| row.get(0))?;
        if count != 0 {
            bail!("archive repository invariant failed: {label} ({count} violation(s))");
        }
    }
    let mut foreign_key_check = connection.prepare("PRAGMA foreign_key_check")?;
    if foreign_key_check.exists([])? {
        bail!("archive repository invariant failed: foreign-key violations present");
    }
    Ok(())
}

fn finalize_success(
    connection: &Connection,
    scope: &SyncScope,
    run_id: i64,
    completed_at: &str,
) -> Result<()> {
    connection.execute(
        "UPDATE archive_sync_runs\n         SET status='complete', completed_at=?1\n         WHERE run_id=?2 AND status='running'",
        params![completed_at, run_id],
    )?;
    if scope.invalidates_unseen() {
        invalidate_unseen(connection, run_id, scope.preserves_unseen_source_evidence())?;
    }
    validate_repository_semantics(connection)?;
    Ok(())
}

fn mark_run_failed(connection: &Connection, run_id: i64, message: &str) -> Result<()> {
    let completed_at = Utc::now().to_rfc3339();
    connection.execute(
        "UPDATE archive_sync_runs SET status='failed', completed_at=?1\n         WHERE run_id=?2 AND status='running'",
        params![completed_at, run_id],
    )?;
    connection.execute(
        "INSERT INTO scrape_log(action, target, status, message, timestamp)\n         VALUES ('archive_sync', ?1, 'failed', ?2, ?3)",
        params![run_id.to_string(), message, completed_at],
    )?;
    Ok(())
}

fn require_positive(value: i64, label: &str) -> Result<()> {
    if value <= 0 {
        bail!("{label} must be positive");
    }
    Ok(())
}

fn bool_int(value: bool) -> i64 {
    if value {
        1
    } else {
        0
    }
}

fn optional_bool_int(value: Option<bool>) -> Option<i64> {
    value.map(bool_int)
}

fn tutorial_type_label(value: TutorialType) -> &'static str {
    match value {
        TutorialType::Initial => "Initial",
        TutorialType::Standard => "Standard",
        TutorialType::Final => "Final",
    }
}

fn insert_text(payload: &mut BTreeMap<String, Value>, key: &str, value: &Option<String>) {
    payload.insert(
        key.to_string(),
        value
            .as_ref()
            .map(|value| Value::from(value.trim().to_string()))
            .unwrap_or(Value::Null),
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::archive_repository::ARCHIVE_SCHEMA_VERSION;
    use crate::archive_repository::{ArchiveRepository, ArchiveRevisionAvailability};
    use std::fs;
    use std::path::PathBuf;
    use std::time::{SystemTime, UNIX_EPOCH};

    const SCHEMA_SQL: &str = include_str!("../../schema/archive_v2.sql");

    fn temp_path(label: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!(
            "gel-d2-{label}-{}-{nonce}.sqlite",
            std::process::id()
        ))
    }

    fn make_database(label: &str) -> PathBuf {
        let path = temp_path(label);
        let connection = Connection::open(&path).unwrap();
        connection.execute_batch("PRAGMA foreign_keys=ON;").unwrap();
        connection.execute_batch(SCHEMA_SQL).unwrap();
        connection
            .execute(
                "INSERT INTO archive_schema_migrations(version,name,source_version,applied_at)\n                 VALUES (?1,'d2_test',0,'2026-08-26T00:00:00Z')",
                [ARCHIVE_SCHEMA_VERSION],
            )
            .unwrap();
        drop(connection);
        path
    }

    fn student(uid: i64, name: &str) -> StudentWrite {
        StudentWrite {
            uid,
            name: Some(name.into()),
            ..StudentWrite::default()
        }
    }

    fn standard_state(uid: i64, ts: i64) -> TutorialSourceStateWrite {
        TutorialSourceStateWrite {
            student_uid: uid,
            tutorial_ts: ts,
            tutorial_type: Some(TutorialType::Standard),
            ttype_raw: Some("0".into()),
            teacher_id: Some(9),
            teacher_id_source: Some("edit_form_inline_js".into()),
            teacher_name: Some("Teacher".into()),
            custom_date: Some("01-08-2026".into()),
            absent: Some(false),
            overall_level: Some("B1: intermediate".into()),
            speaking: Some("B1".into()),
            use_of_english: Some("B1-".into()),
            writing: Some("A2+".into()),
            listening: Some("B1".into()),
            reading: Some("B1-".into()),
            aims: Some("Read more".into()),
            teacher_comments: Some("Good".into()),
            additional_comments: Some(String::new()),
            source_method: Some("summary+edit".into()),
            summary_url: Some("/summary".into()),
            print_url: Some("/print".into()),
            edit_url: Some("/edit".into()),
            summary_match_method: Some("exact".into()),
            ..TutorialSourceStateWrite::default()
        }
    }

    #[test]
    fn source_state_fingerprint_matches_d1_python_migration_algorithm() {
        let mut state = standard_state(42, 123456);
        state.teacher_name = Some(" Teacher ".into());
        state.aims = Some(" Read more ".into());
        state.teacher_comments = Some(" Good ".into());
        state.summary_url = Some("/different-route-does-not-affect-fingerprint".into());
        assert_eq!(
            state.state_fingerprint().unwrap(),
            "80837a0539106a7d770938d86845b175ffdadcbc5934332525650f4f7b3c6211"
        );
    }

    #[test]
    fn failed_full_sync_rolls_back_writes_and_never_invalidates_prior_history() {
        let path = make_database("rollback");
        let mut repository = ArchiveSyncRepository::open_existing(&path).unwrap();
        repository
            .run_sync("gel", SyncScope::Full, |sync| {
                sync.upsert_student(&student(10, "Student"))?;
                sync.upsert_tutorial_identity(&TutorialIdentityWrite {
                    tutorial_id: 100,
                    student_uid: 10,
                    tutorial_ts: 111,
                })?;
                let state_id = sync.upsert_source_state(&standard_state(10, 111))?;
                sync.set_state_association(&StateAssociationWrite {
                    tutorial_id: 100,
                    authority_status: HistoricalStateAuthorityStatus::ProvenPerTutorial,
                    source_state_id: Some(state_id),
                    collision_group_id: None,
                    proof_method: "exact_timestamp".into(),
                })?;
                Ok(())
            })
            .unwrap();

        let failure = repository.run_sync("gel", SyncScope::Full, |sync| -> Result<()> {
            sync.upsert_student(&student(20, "Partial"))?;
            bail!("synthetic acquisition/materialization failure")
        });
        assert!(failure.is_err());

        let old_present: i64 = repository
            .connection
            .query_row(
                "SELECT source_present FROM tutorial_identities WHERE tutorial_id=100",
                [],
                |row| row.get(0),
            )
            .unwrap();
        let partial_count: i64 = repository
            .connection
            .query_row("SELECT COUNT(*) FROM students WHERE uid=20", [], |row| {
                row.get(0)
            })
            .unwrap();
        let failed_runs: i64 = repository
            .connection
            .query_row(
                "SELECT COUNT(*) FROM archive_sync_runs WHERE status='failed'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(old_present, 1);
        assert_eq!(partial_count, 0);
        assert_eq!(failed_runs, 1);
        drop(repository);
        fs::remove_file(path).ok();
    }

    #[test]
    fn completed_full_sync_invalidates_unseen_without_deleting_history() {
        let path = make_database("invalidation");
        let mut repository = ArchiveSyncRepository::open_existing(&path).unwrap();
        repository
            .run_sync("gel", SyncScope::Full, |sync| {
                sync.upsert_student(&student(10, "One"))?;
                sync.upsert_tutorial_identity(&TutorialIdentityWrite {
                    tutorial_id: 100,
                    student_uid: 10,
                    tutorial_ts: 111,
                })?;
                let state_id = sync.upsert_source_state(&standard_state(10, 111))?;
                sync.set_state_association(&StateAssociationWrite {
                    tutorial_id: 100,
                    authority_status: HistoricalStateAuthorityStatus::ProvenPerTutorial,
                    source_state_id: Some(state_id),
                    collision_group_id: None,
                    proof_method: "exact_timestamp".into(),
                })?;
                Ok(())
            })
            .unwrap();
        repository
            .run_sync("gel", SyncScope::Full, |_sync| Ok(()))
            .unwrap();

        let row: (i64, i64) = repository
            .connection
            .query_row(
                "SELECT source_present, presence_checked_run_id IS NOT NULL\n                 FROM tutorial_identities WHERE tutorial_id=100",
                [],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .unwrap();
        assert_eq!(row, (0, 1));
        let still_exists: i64 = repository
            .connection
            .query_row(
                "SELECT COUNT(*) FROM tutorial_identities WHERE tutorial_id=100",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(still_exists, 1);
        drop(repository);
        fs::remove_file(path).ok();
    }

    #[test]
    fn canonical_tutorial_id_cannot_be_rekeyed() {
        let path = make_database("identity");
        let mut repository = ArchiveSyncRepository::open_existing(&path).unwrap();
        repository
            .run_sync("gel", SyncScope::Targeted("first".into()), |sync| {
                sync.upsert_student(&student(10, "One"))?;
                sync.upsert_tutorial_identity(&TutorialIdentityWrite {
                    tutorial_id: 100,
                    student_uid: 10,
                    tutorial_ts: 111,
                })?;
                sync.set_state_association(&StateAssociationWrite {
                    tutorial_id: 100,
                    authority_status: HistoricalStateAuthorityStatus::UnmatchedSourceState,
                    source_state_id: None,
                    collision_group_id: None,
                    proof_method: "unmatched".into(),
                })?;
                Ok(())
            })
            .unwrap();

        let changed = repository.run_sync("gel", SyncScope::Targeted("second".into()), |sync| {
            sync.upsert_student(&student(11, "Other"))?;
            sync.upsert_tutorial_identity(&TutorialIdentityWrite {
                tutorial_id: 100,
                student_uid: 11,
                tutorial_ts: 222,
            })
        });
        assert!(changed.is_err());
        drop(repository);
        fs::remove_file(path).ok();
    }

    #[test]
    fn divergent_collision_is_persisted_group_owned_and_read_side_blocks_revision() {
        let path = make_database("divergent");
        let mut repository = ArchiveSyncRepository::open_existing(&path).unwrap();
        repository
            .run_sync("gel", SyncScope::Targeted("collision".into()), |sync| {
                sync.upsert_student(&student(10, "Student"))?;
                for tutorial_id in [100, 101] {
                    sync.upsert_tutorial_identity(&TutorialIdentityWrite {
                        tutorial_id,
                        student_uid: 10,
                        tutorial_ts: 111,
                    })?;
                }
                let state_a = sync.upsert_source_state(&standard_state(10, 111))?;
                let mut second = standard_state(10, 111);
                second.speaking = Some("B1+".into());
                let state_b = sync.upsert_source_state(&second)?;
                let group =
                    sync.upsert_collision_group(10, 111, StoredCollisionKind::DivergentState)?;
                for tutorial_id in [100, 101] {
                    sync.link_collision_identity(group, tutorial_id)?;
                    sync.set_state_association(&StateAssociationWrite {
                        tutorial_id,
                        authority_status:
                            HistoricalStateAuthorityStatus::AmbiguousDivergentCollision,
                        source_state_id: None,
                        collision_group_id: Some(group),
                        proof_method: "collision_group".into(),
                    })?;
                }
                sync.link_collision_state(group, state_a)?;
                sync.link_collision_state(group, state_b)?;
                Ok(())
            })
            .unwrap();
        drop(repository);

        let reader = ArchiveRepository::open_read_only(&path).unwrap();
        let result = reader.revision_source(100).unwrap();
        assert!(matches!(
            result,
            ArchiveRevisionAvailability::Blocked { .. }
        ));
        drop(reader);
        fs::remove_file(path).ok();
    }

    #[test]
    fn proven_state_is_read_back_as_semantic_archived_tutorial() {
        let path = make_database("readback");
        let mut repository = ArchiveSyncRepository::open_existing(&path).unwrap();
        repository
            .run_sync("gel", SyncScope::Targeted("tutorial".into()), |sync| {
                sync.upsert_student(&student(10, "Student"))?;
                sync.upsert_tutorial_identity(&TutorialIdentityWrite {
                    tutorial_id: 100,
                    student_uid: 10,
                    tutorial_ts: 111,
                })?;
                let state_id = sync.upsert_source_state(&standard_state(10, 111))?;
                sync.set_state_association(&StateAssociationWrite {
                    tutorial_id: 100,
                    authority_status: HistoricalStateAuthorityStatus::ProvenPerTutorial,
                    source_state_id: Some(state_id),
                    collision_group_id: None,
                    proof_method: "exact_timestamp".into(),
                })?;
                Ok(())
            })
            .unwrap();
        drop(repository);

        let reader = ArchiveRepository::open_read_only(&path).unwrap();
        let result = reader.revision_source(100).unwrap();
        match result {
            ArchiveRevisionAvailability::Available { tutorial } => {
                assert_eq!(tutorial.identity.tutorial_id, 100);
                assert_eq!(tutorial.identity.student_uid, 10);
                assert_eq!(tutorial.teacher.teacher_id, Some(9));
                assert_eq!(tutorial.current_scores.speaking.unwrap().form_value(), "B1");
                assert!(!tutorial.absent);
            }
            other => panic!("expected available revision source, got {other:?}"),
        }
        drop(reader);
        fs::remove_file(path).ok();
    }
}
