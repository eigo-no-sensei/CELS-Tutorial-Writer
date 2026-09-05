//! A2 production Rust archiver.
//!
//! Network acquisition is completed before the archive write transaction is
//! opened. The transaction therefore materializes an already-acquired snapshot
//! only, preserving the D2 rollback/invalidation contract while transferring
//! canonical local archive ownership from the Python v4.9 oracle to Rust.

use crate::archive_repository::{validate_archive_v2_connection, ARCHIVE_SCHEMA_VERSION};
use crate::archive_sync_repository::{
    ArchiveSyncRepository, ClassWrite, EvidenceSourceKind, FieldPresence, MembershipWrite,
    StateAssociationWrite, StoredCollisionKind, StudentWrite, SyncScope, TutorialIdentityWrite,
    TutorialSourceStateWrite,
};
use crate::models::{
    CollisionStateKind, HistoricalStateAuthorityStatus, PrintRecord, SummaryEntry,
};
use crate::semantic::TutorialType;
use crate::{
    pair_tutorials_with_summary, parse_edit_form, parse_print_page, parse_tutorial_summary,
    validate_edit_form, GelSession,
};
use anyhow::{bail, Context, Result};
use chrono::{DateTime, Utc};
use rusqlite::{Connection, OpenFlags, OptionalExtension};
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};

const FRESH_SCHEMA_SQL: &str = include_str!("../../schema/archive_v2.sql");

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct ArchiveSyncReport {
    pub classes: usize,
    pub students: usize,
    pub memberships: usize,
    pub tutorial_identities: usize,
    pub source_states: usize,
    pub proven_per_tutorial: usize,
    pub shared_identical_collisions: usize,
    pub blocked_collisions: usize,
    pub unmatched_without_state: usize,
    pub summary_failures: usize,
    pub print_failures: usize,
    pub profile_failures: usize,
    pub edit_failures: usize,
    pub preserved_prior_source_evidence: bool,
    pub http_requests: u64,
}

#[derive(Debug, Clone)]
struct AcquiredSnapshot {
    classes: Vec<ClassWrite>,
    students: Vec<StudentWrite>,
    memberships: Vec<MembershipWrite>,
    tutorials: Vec<AcquiredTutorial>,
    collisions: Vec<AcquiredCollision>,
    summary_failures: usize,
    print_failures: usize,
    profile_failures: usize,
    edit_failures: usize,
}

#[derive(Debug, Clone)]
struct AcquiredTutorial {
    identity: TutorialIdentityWrite,
    state: Option<AcquiredState>,
    authority_status: HistoricalStateAuthorityStatus,
    collision_key: Option<(i64, i64)>,
    proof_method: String,
}

#[derive(Debug, Clone)]
struct AcquiredCollision {
    student_uid: i64,
    tutorial_ts: i64,
    kind: CollisionStateKind,
    tutorial_ids: Vec<i64>,
    states: Vec<AcquiredState>,
}

#[derive(Debug, Clone)]
struct AcquiredState {
    value: TutorialSourceStateWrite,
    evidence: Vec<FieldEvidenceWrite>,
}

#[derive(Debug, Clone)]
struct FieldEvidenceWrite {
    field_name: String,
    source_kind: EvidenceSourceKind,
    presence: FieldPresence,
}

#[derive(Debug, Clone)]
struct CachedTeacher {
    teacher_id: i64,
    teacher_id_source: String,
    teacher_name: String,
}

/// Production A2 local-archive owner.
///
/// The Python v4.9 implementation remains a historical behavioural oracle, but
/// this type is the only supported runtime canonical-writer entry point after
/// A2. Writer/Viewer code still receives no raw SQLite connection.
pub struct RustArchiver;

impl RustArchiver {
    /// Ensure a canonical schema-v2 archive exists at `path`.
    ///
    /// Existing files are validated and never migrated or replaced in place.
    /// A missing file is created atomically via a sibling temporary database
    /// and renamed only after schema/FK validation succeeds.
    pub fn ensure_database(path: impl AsRef<Path>) -> Result<PathBuf> {
        let path = path.as_ref();
        if path.exists() {
            let connection = Connection::open_with_flags(
                path,
                OpenFlags::SQLITE_OPEN_READ_WRITE | OpenFlags::SQLITE_OPEN_NO_MUTEX,
            )?;
            validate_archive_v2_connection(&connection)?;
            return Ok(path.to_path_buf());
        }

        let parent = path
            .parent()
            .filter(|value| !value.as_os_str().is_empty())
            .unwrap_or_else(|| Path::new("."));
        fs::create_dir_all(parent)?;
        let file_name = path
            .file_name()
            .and_then(|value| value.to_str())
            .context("archive path must have a UTF-8 file name")?;
        let temp = parent.join(format!(".{file_name}.a2-incomplete-{}", std::process::id()));
        if temp.exists() {
            fs::remove_file(&temp)?;
        }

        let creation = (|| -> Result<()> {
            let connection = Connection::open_with_flags(
                &temp,
                OpenFlags::SQLITE_OPEN_READ_WRITE
                    | OpenFlags::SQLITE_OPEN_CREATE
                    | OpenFlags::SQLITE_OPEN_NO_MUTEX,
            )?;
            connection.execute_batch("PRAGMA foreign_keys=ON;")?;
            connection.execute_batch(FRESH_SCHEMA_SQL)?;
            connection.execute(
                "INSERT INTO archive_schema_migrations(version, name, source_version, applied_at) VALUES (?1, 'fresh_v2_a2_rust', 0, ?2)",
                               rusqlite::params![ARCHIVE_SCHEMA_VERSION, Utc::now().to_rfc3339()],
            )?;
            validate_archive_v2_connection(&connection)?;
            Ok(())
        })();
        if let Err(error) = creation {
            let _ = fs::remove_file(&temp);
            return Err(error);
        }

        if path.exists() {
            let _ = fs::remove_file(&temp);
            bail!(
                "archive destination appeared during atomic creation: {}",
                path.display()
            );
        }
        fs::rename(&temp, path).with_context(|| {
            format!(
                "atomically publish A2 archive {} -> {}",
                temp.display(),
                path.display()
            )
        })?;
        Ok(path.to_path_buf())
    }

    /// Acquire a complete GEL snapshot and transactionally materialize it into
    /// the canonical local archive.
    pub fn sync_full(
        session: &mut GelSession,
        path: impl AsRef<Path>,
    ) -> Result<ArchiveSyncReport> {
        if !session.is_authenticated() {
            bail!("A2 archive sync requires an authenticated GEL session");
        }
        let path = Self::ensure_database(path)?;
        let snapshot = acquire_full_snapshot(session)?;
        let request_count = session.request_count();
        let mut report = materialize_snapshot(&path, snapshot)?;
        report.http_requests = request_count;
        Ok(report)
    }

    /// Acquire a targeted snapshot for a single student and transactionally materialize it
    /// into the canonical local archive without class-wide absence invalidation.
    pub fn sync_targeted_student(
        session: &mut GelSession,
        path: impl AsRef<Path>,
        student_uid: i64,
    ) -> Result<ArchiveSyncReport> {
        if !session.is_authenticated() {
            bail!("A2 targeted archive sync requires an authenticated GEL session");
        }
        if student_uid <= 0 {
            bail!("targeted archive sync requires a positive student_uid");
        }
        let path = Self::ensure_database(path)?;
        let snapshot = acquire_targeted_snapshot(session, &path, student_uid)?;
        let request_count = session.request_count();
        let scope = SyncScope::Targeted(format!("student:{student_uid}"));
        let mut report = materialize_snapshot_with_scope(&path, snapshot, scope)?;
        report.http_requests = request_count;
        Ok(report)
    }
}

fn acquire_full_snapshot(session: &mut GelSession) -> Result<AcquiredSnapshot> {
    let classes_json = session.get_classes().context("A2 fetch open classes")?;
    let class_rows = classes_json
        .as_array()
        .context("GEL classes response must be a JSON array")?;

    let mut classes = Vec::new();
    let mut students_by_uid = BTreeMap::<i64, StudentWrite>::new();
    let mut memberships = Vec::new();
    let mut student_uids = BTreeSet::new();

    for class_row in class_rows {
        let class = class_from_json(class_row)?;
        let class_id = class.class_id;
        classes.push(class);
        let roster_json = session
            .get_students(class_id)
            .with_context(|| format!("A2 fetch students for class {class_id}"))?;
        let roster = roster_json
            .as_array()
            .context("GEL class students response must be a JSON array")?;
        for row in roster {
            let uid = student_uid_from_json(row)?;
            student_uids.insert(uid);
            let student = student_from_json(uid, row, None);
            students_by_uid
                .entry(uid)
                .and_modify(|current| merge_student(current, &student))
                .or_insert(student);
            memberships.push(membership_from_json(class_id, uid, row));
        }
    }

    let mut profile_failures = 0usize;
    for uid in &student_uids {
        match session.get_student_profile(*uid) {
            Ok(profile) => {
                if let Some(current) = students_by_uid.get_mut(uid) {
                    let candidate = student_from_json(*uid, &Value::Null, Some(&profile));
                    merge_student(current, &candidate);
                }
            }
            Err(_) => {
                profile_failures += 1;
            }
        }
    }

    let mut tutorials = Vec::new();
    let mut collisions = Vec::new();
    let mut summary_failures = 0usize;
    let mut print_failures = 0usize;
    let mut edit_failures = 0usize;
    let empty_known_teachers = BTreeMap::new();

    for uid in student_uids {
        acquire_student_tutorials(
            session,
            uid,
            &empty_known_teachers,
            &mut tutorials,
            &mut collisions,
            &mut summary_failures,
            &mut print_failures,
            &mut edit_failures,
        )?;
    }

    Ok(AcquiredSnapshot {
        classes,
        students: students_by_uid.into_values().collect(),
        memberships,
        tutorials,
        collisions,
        summary_failures,
        print_failures,
        profile_failures,
        edit_failures,
    })
}

fn acquire_targeted_snapshot(
    session: &mut GelSession,
    archive_path: &Path,
    student_uid: i64,
) -> Result<AcquiredSnapshot> {
    let mut profile_failures = 0usize;
    let fetched_profile = match session.get_student_profile(student_uid) {
        Ok(profile) => Some(student_from_json(student_uid, &Value::Null, Some(&profile))),
        Err(_) => {
            profile_failures += 1;
            None
        }
    };

    let mut student = StudentWrite {
        uid: student_uid,
        ..Default::default()
    };

    if archive_path.exists() {
        if let Ok(connection) = Connection::open_with_flags(
            archive_path,
            OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
        ) {
            let existing: Option<StudentWrite> = connection
            .query_row(
                "SELECT name, cefr_level, school_name, start_date, end_date FROM students WHERE uid=?1",
                [student_uid],
                |row| {
                    Ok(StudentWrite {
                        uid: student_uid,
                        name: row.get(0)?,
                       cefr_level: row.get(1)?,
                       school_name: row.get(2)?,
                       start_date: row.get(3)?,
                       end_date: row.get(4)?,
                    })
                },
            )
            .optional()
            .unwrap_or(None);
            if let Some(existing_data) = existing {
                student = existing_data;
            }
        }
    }

    if let Some(profile_data) = fetched_profile {
        merge_student_profile_overlay(&mut student, &profile_data);
    }

    let known_teachers = load_known_teachers(archive_path);

    let mut tutorials = Vec::new();
    let mut collisions = Vec::new();
    let mut summary_failures = 0usize;
    let mut print_failures = 0usize;
    let mut edit_failures = 0usize;

    acquire_student_tutorials(
        session,
        student_uid,
        &known_teachers,
        &mut tutorials,
        &mut collisions,
        &mut summary_failures,
        &mut print_failures,
        &mut edit_failures,
    )?;

    Ok(AcquiredSnapshot {
        classes: Vec::new(),
        students: vec![student],
        memberships: Vec::new(),
        tutorials,
        collisions,
        summary_failures,
        print_failures,
        profile_failures,
        edit_failures,
    })
}

fn load_known_teachers(archive_path: &Path) -> BTreeMap<(i64, i64), CachedTeacher> {
    let mut map = BTreeMap::new();
    if !archive_path.exists() {
        return map;
    }
    if let Ok(conn) = Connection::open_with_flags(
        archive_path,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    ) {
        if let Ok(mut stmt) = conn.prepare(
            "SELECT student_uid, tutorial_ts, teacher_id, teacher_id_source, teacher_name \
FROM tutorial_source_states \
WHERE teacher_id IS NOT NULL AND source_present = 1",
        ) {
            if let Ok(rows) = stmt.query_map([], |row| {
                let uid: i64 = row.get(0)?;
                let ts: i64 = row.get(1)?;
                let tid: i64 = row.get(2)?;
                let source: String = row.get(3).unwrap_or_default();
                let name: String = row.get(4).unwrap_or_default();
                Ok((
                    (uid, ts),
                    CachedTeacher {
                        teacher_id: tid,
                        teacher_id_source: source,
                        teacher_name: name,
                    },
                ))
            }) {
                for item in rows.flatten() {
                    map.insert(item.0, item.1);
                }
            }
        }
    }
    map
}

fn is_summary_complete_for_type(entry: &SummaryEntry, ttype: TutorialType) -> bool {
    if entry.datetime_label.split_whitespace().next().is_none() {
        return false;
    }
    // Must have a valid ttype_raw from the edit link to know the exact ttype
    if !matches!(entry.ttype_raw.trim(), "0" | "1" | "2") {
        return false;
    }
    if !entry.fields.contains_key("Teacher") || !entry.fields.contains_key("absent") {
        return false;
    }
    match ttype {
        TutorialType::Standard => [
            "Speaking",
            "Use of English",
            "Writing",
            "Listening",
            "Reading",
            "Assessment",
            "Aims",
            "Teacher's Comments",
            "Tutorial Overall Level",
        ]
        .iter()
        .all(|key| entry.fields.contains_key(*key)),

        TutorialType::Initial => [
            "Initial Speaking",
            "Initial Use of English",
            "Initial Writing",
            "Initial Listening",
            "Teacher's Comments",
            "Tutorial Overall Level",
        ]
        .iter()
        .all(|key| entry.fields.contains_key(*key)),

        TutorialType::Final => [
            "Initial Speaking",
            "Initial Use of English",
            "Initial Writing",
            "Initial Listening",
            "Speaking",
            "Use of English",
            "Writing",
            "Listening",
            "Reading",
            "Teacher's Comments",
            "Tutorial Overall Level",
        ]
        .iter()
        .all(|key| entry.fields.contains_key(*key)),
    }
}
#[allow(clippy::too_many_arguments)]
fn acquire_student_tutorials(
    session: &mut GelSession,
    uid: i64,
    known_teachers: &BTreeMap<(i64, i64), CachedTeacher>,
    tutorials: &mut Vec<AcquiredTutorial>,
    collisions: &mut Vec<AcquiredCollision>,
    summary_failures: &mut usize,
    print_failures: &mut usize,
    edit_failures: &mut usize,
) -> Result<()> {
    let api = session
        .get_tutorial_list(uid)
        .with_context(|| format!("A2 fetch tutorial list for student {uid}"))?;

    let summaries = match session.get_tutorial_summary_html(uid) {
        Ok(html) => match parse_tutorial_summary(&html) {
            Ok(values) => values,
            Err(_) => {
                *summary_failures += 1;
                Vec::new()
            }
        },
        Err(_) => {
            *summary_failures += 1;
            Vec::new()
        }
    };

    let reconciliation = pair_tutorials_with_summary(uid, &api, &summaries);

    let mut print_cache = BTreeMap::<i64, Option<PrintRecord>>::new();
    let mut edit_cache =
        BTreeMap::<(i64, String), Option<crate::models::ValidatedEditFormState>>::new();

    for group in &reconciliation.collisions {
        // Under ANOM-COLLISION-002, if the collision states diverge (e.g. absent vs present),
        // the print route /print/{uid}/{ts} resolves only to the absent state. We must not
        // let the print route contaminate divergent summary states.
        let group_needs_print = if group.collision_kind == CollisionStateKind::DivergentState {
            false
        } else {
            group.summary_entries.iter().any(|entry| {
                let ttype = tutorial_type_from_any(
                    &entry.ttype_raw,
                    entry.fields.get("Type").map(String::as_str),
                );
                !is_summary_complete_for_type(entry, ttype)
            })
        };

        let print = if group_needs_print {
            get_print_cached(
                session,
                uid,
                group.tutorial_ts,
                &mut print_cache,
                print_failures,
            )
        } else {
            None
        };

        let mut states = Vec::new();
        for entry in &group.summary_entries {
            let ttype = effective_ttype_raw(entry, print.as_ref());
            let cached_teacher = known_teachers.get(&(uid, group.tutorial_ts));
            let edit = if cached_teacher.is_none() {
                get_edit_cached(
                    session,
                    uid,
                    group.tutorial_ts,
                    &ttype,
                    &mut edit_cache,
                    edit_failures,
                )
            } else {
                None
            };

            states.push(build_state(
                uid,
                group.tutorial_ts,
                Some(entry),
                print.as_ref(),
                edit.as_ref(),
                cached_teacher,
                "collision_group",
            ));
        }
        collisions.push(AcquiredCollision {
            student_uid: uid,
            tutorial_ts: group.tutorial_ts,
            kind: group.collision_kind,
            tutorial_ids: group.api_tutorial_ids.clone(),
            states,
        });
    }

    for pair in &reconciliation.pairs {
        let identity = TutorialIdentityWrite {
            tutorial_id: pair.api.id,
            student_uid: uid,
            tutorial_ts: pair.api.timestamp,
        };
        if pair.state_authority.status != HistoricalStateAuthorityStatus::ProvenPerTutorial {
            tutorials.push(AcquiredTutorial {
                identity,
                state: None,
                authority_status: pair.state_authority.status,
                collision_key: pair
                    .state_authority
                    .reconciliation_key
                    .as_ref()
                    .map(|_| (uid, pair.api.timestamp)),
                proof_method: "summary_collision_authority".to_string(),
            });
            continue;
        }

        let cached_teacher = known_teachers.get(&(uid, pair.api.timestamp));

        // Skip print if summary is complete (ANOM-BLANK-001)
        let ttype_raw_candidate = pair
            .summary
            .as_ref()
            .map(|entry| entry.ttype_raw.trim().to_string())
            .unwrap_or_default();
        let tutorial_type = tutorial_type_from_any(
            &ttype_raw_candidate,
            pair.summary
                .as_ref()
                .and_then(|e| e.fields.get("Type").map(String::as_str)),
        );

        let needs_print = match &pair.summary {
            None => true,
            Some(entry) => !is_summary_complete_for_type(entry, tutorial_type),
        };

        let print = if needs_print {
            get_print_cached(
                session,
                uid,
                pair.api.timestamp,
                &mut print_cache,
                print_failures,
            )
        } else {
            None
        };

        let ttype = pair
            .summary
            .as_ref()
            .map(|entry| effective_ttype_raw(entry, print.as_ref()))
            .unwrap_or_else(|| ttype_from_print(print.as_ref()));

        let edit = if cached_teacher.is_none() {
            get_edit_cached(
                session,
                uid,
                pair.api.timestamp,
                &ttype,
                &mut edit_cache,
                edit_failures,
            )
        } else {
            None
        };

        let state = build_state(
            uid,
            pair.api.timestamp,
            pair.summary.as_ref(),
            print.as_ref(),
            edit.as_ref(),
            cached_teacher,
            match pair.match_method {
                crate::models::MatchMethod::ExactTimestamp => "exact_timestamp",
                crate::models::MatchMethod::SameDateFallback => "same_date_fallback",
                crate::models::MatchMethod::CollisionGroup => "collision_group",
                crate::models::MatchMethod::Unmatched => "unmatched",
            },
        );
        tutorials.push(AcquiredTutorial {
            identity,
            state: Some(state),
            authority_status: HistoricalStateAuthorityStatus::ProvenPerTutorial,
            collision_key: None,
            proof_method: "api_identity+summary_or_print".to_string(),
        });
    }

    // Unique API identities with no summary entry remain eligible for print fallback.
    for tutorial in tutorials.iter_mut().filter(|value| {
        value.identity.student_uid == uid
            && value.authority_status == HistoricalStateAuthorityStatus::UnmatchedSourceState
            && value.collision_key.is_none()
    }) {
        let print = get_print_cached(
            session,
            uid,
            tutorial.identity.tutorial_ts,
            &mut print_cache,
            print_failures,
        );
        let Some(print_record) = print.as_ref().filter(|value| !value.fields.is_empty()) else {
            continue;
        };
        let ttype = ttype_from_print(Some(print_record));
        let cached_teacher = known_teachers.get(&(uid, tutorial.identity.tutorial_ts));
        let edit = if cached_teacher.is_none() {
            get_edit_cached(
                session,
                uid,
                tutorial.identity.tutorial_ts,
                &ttype,
                &mut edit_cache,
                edit_failures,
            )
        } else {
            None
        };
        tutorial.state = Some(build_state(
            uid,
            tutorial.identity.tutorial_ts,
            None,
            Some(print_record),
            edit.as_ref(),
            cached_teacher,
            "print_only_unique_timestamp",
        ));
        tutorial.authority_status = HistoricalStateAuthorityStatus::ProvenPerTutorial;
        tutorial.proof_method = "api_unique_timestamp+print".to_string();
    }

    Ok(())
}

fn materialize_snapshot(path: &Path, snapshot: AcquiredSnapshot) -> Result<ArchiveSyncReport> {
    let auxiliary_evidence_partial =
        snapshot.summary_failures > 0 || snapshot.print_failures > 0 || snapshot.edit_failures > 0;
    let scope = if auxiliary_evidence_partial {
        SyncScope::FullPreserveSourceEvidence
    } else {
        SyncScope::Full
    };
    materialize_snapshot_with_scope(path, snapshot, scope)
}

fn materialize_snapshot_with_scope(
    path: &Path,
    snapshot: AcquiredSnapshot,
    scope: SyncScope,
) -> Result<ArchiveSyncReport> {
    let mut repository = ArchiveSyncRepository::open_existing(path)?;
    let mut report = ArchiveSyncReport {
        classes: snapshot.classes.len(),
        students: snapshot.students.len(),
        memberships: snapshot.memberships.len(),
        tutorial_identities: snapshot.tutorials.len(),
        source_states: 0,
        proven_per_tutorial: 0,
        shared_identical_collisions: 0,
        blocked_collisions: 0,
        unmatched_without_state: 0,
        summary_failures: snapshot.summary_failures,
        print_failures: snapshot.print_failures,
        profile_failures: snapshot.profile_failures,
        edit_failures: snapshot.edit_failures,
        preserved_prior_source_evidence: matches!(scope, SyncScope::FullPreserveSourceEvidence),
        http_requests: 0,
    };

    repository.run_sync("gel-rust-a2", scope, |sync| {
        for value in &snapshot.classes {
            sync.upsert_class(value)?;
        }
        for value in &snapshot.students {
            sync.upsert_student(value)?;
        }
        for value in &snapshot.memberships {
            sync.upsert_membership(value)?;
        }
        for value in &snapshot.tutorials {
            sync.upsert_tutorial_identity(&value.identity)?;
        }

        let mut collision_ids = BTreeMap::<(i64, i64), i64>::new();
        let mut collision_shared_state = BTreeMap::<(i64, i64), i64>::new();
        for group in &snapshot.collisions {
            let kind = match group.kind {
                CollisionStateKind::IdenticalState => StoredCollisionKind::IdenticalState,
                CollisionStateKind::DivergentState => StoredCollisionKind::DivergentState,
                CollisionStateKind::IncompleteEvidence => StoredCollisionKind::IncompleteEvidence,
            };
            let group_id =
                sync.upsert_collision_group(group.student_uid, group.tutorial_ts, kind)?;
            collision_ids.insert((group.student_uid, group.tutorial_ts), group_id);
            for tutorial_id in &group.tutorial_ids {
                sync.link_collision_identity(group_id, *tutorial_id)?;
            }
            let mut state_ids = Vec::new();
            for state in &group.states {
                let state_id = persist_state(sync, state)?;
                report.source_states += 1;
                sync.link_collision_state(group_id, state_id)?;
                state_ids.push(state_id);
            }
            state_ids.sort_unstable();
            state_ids.dedup();
            if group.kind == CollisionStateKind::IdenticalState {
                if state_ids.len() != 1 {
                    bail!(
                        "identical collision {}:{} materialized {} distinct source states",
                        group.student_uid,
                        group.tutorial_ts,
                        state_ids.len()
                    );
                }
                collision_shared_state.insert((group.student_uid, group.tutorial_ts), state_ids[0]);
            }
        }

        for tutorial in &snapshot.tutorials {
            match tutorial.authority_status {
                HistoricalStateAuthorityStatus::ProvenPerTutorial => {
                    let state = tutorial
                        .state
                        .as_ref()
                        .context("proven A2 tutorial missing acquired state")?;
                    let state_id = persist_state(sync, state)?;
                    report.source_states += 1;
                    report.proven_per_tutorial += 1;
                    sync.set_state_association(&StateAssociationWrite {
                        tutorial_id: tutorial.identity.tutorial_id,
                        authority_status: HistoricalStateAuthorityStatus::ProvenPerTutorial,
                        source_state_id: Some(state_id),
                        collision_group_id: None,
                        proof_method: tutorial.proof_method.clone(),
                    })?;
                }
                HistoricalStateAuthorityStatus::SharedIdenticalCollision => {
                    let key = tutorial
                        .collision_key
                        .context("shared collision tutorial missing collision key")?;
                    let group_id = *collision_ids
                        .get(&key)
                        .context("shared collision group was not materialized")?;
                    let state_id = *collision_shared_state
                        .get(&key)
                        .context("shared collision has no unique source state")?;
                    report.shared_identical_collisions += 1;
                    sync.set_state_association(&StateAssociationWrite {
                        tutorial_id: tutorial.identity.tutorial_id,
                        authority_status: HistoricalStateAuthorityStatus::SharedIdenticalCollision,
                        source_state_id: Some(state_id),
                        collision_group_id: Some(group_id),
                        proof_method: tutorial.proof_method.clone(),
                    })?;
                }
                HistoricalStateAuthorityStatus::AmbiguousDivergentCollision
                | HistoricalStateAuthorityStatus::IncompleteCollisionEvidence
                | HistoricalStateAuthorityStatus::AmbiguousCollisionUnknown => {
                    let key = tutorial
                        .collision_key
                        .context("blocked collision tutorial missing collision key")?;
                    let group_id = *collision_ids
                        .get(&key)
                        .context("blocked collision group was not materialized")?;
                    report.blocked_collisions += 1;
                    sync.set_state_association(&StateAssociationWrite {
                        tutorial_id: tutorial.identity.tutorial_id,
                        authority_status: tutorial.authority_status,
                        source_state_id: None,
                        collision_group_id: Some(group_id),
                        proof_method: tutorial.proof_method.clone(),
                    })?;
                }
                HistoricalStateAuthorityStatus::UnmatchedSourceState => {
                    report.unmatched_without_state += 1;
                    sync.set_state_association(&StateAssociationWrite {
                        tutorial_id: tutorial.identity.tutorial_id,
                        authority_status: HistoricalStateAuthorityStatus::UnmatchedSourceState,
                        source_state_id: None,
                        collision_group_id: None,
                        proof_method: tutorial.proof_method.clone(),
                    })?;
                }
            }
        }
        Ok(())
    })?;
    Ok(report)
}

fn persist_state(
    sync: &crate::archive_sync_repository::ArchiveSyncSession<'_>,
    state: &AcquiredState,
) -> Result<i64> {
    let state_id = sync.upsert_source_state(&state.value)?;
    for evidence in &state.evidence {
        sync.upsert_field_evidence(
            state_id,
            &evidence.field_name,
            evidence.source_kind,
            evidence.presence,
        )?;
    }
    Ok(state_id)
}

fn get_print_cached(
    session: &mut GelSession,
    uid: i64,
    tutorial_ts: i64,
    cache: &mut BTreeMap<i64, Option<PrintRecord>>,
    failures: &mut usize,
) -> Option<PrintRecord> {
    if let Some(value) = cache.get(&tutorial_ts) {
        return value.clone();
    }
    let parsed = match session.get_tutorial_print_html(uid, tutorial_ts) {
        Ok(html) => match parse_print_page(&html) {
            Ok(value) => Some(value),
            Err(_) => {
                *failures += 1;
                None
            }
        },
        Err(_) => {
            *failures += 1;
            None
        }
    };
    cache.insert(tutorial_ts, parsed.clone());
    parsed
}

fn get_edit_cached(
    session: &mut GelSession,
    uid: i64,
    tutorial_ts: i64,
    ttype_raw: &str,
    cache: &mut BTreeMap<(i64, String), Option<crate::models::ValidatedEditFormState>>,
    failures: &mut usize,
) -> Option<crate::models::ValidatedEditFormState> {
    if tutorial_ts <= 0 || !matches!(ttype_raw, "0" | "1" | "2") {
        return None;
    }
    let key = (tutorial_ts, ttype_raw.to_string());
    if let Some(value) = cache.get(&key) {
        return value.clone();
    }
    let parsed = match session.get_tutorial_edit_html(uid, tutorial_ts, ttype_raw) {
        Ok(html) => match parse_edit_form(&html) {
            Ok(raw) => match validate_edit_form(&raw) {
                Ok(value) => Some(value),
                Err(_) => {
                    *failures += 1;
                    None
                }
            },
            Err(_) => {
                *failures += 1;
                None
            }
        },
        Err(_) => {
            *failures += 1;
            None
        }
    };
    cache.insert(key, parsed.clone());
    parsed
}

fn build_state(
    student_uid: i64,
    tutorial_ts: i64,
    summary: Option<&SummaryEntry>,
    print: Option<&PrintRecord>,
    edit: Option<&crate::models::ValidatedEditFormState>,
    cached_teacher: Option<&CachedTeacher>,
    match_method: &str,
) -> AcquiredState {
    let mut fields = summary
        .map(|entry| entry.fields.clone())
        .unwrap_or_default();
    if let Some(print) = print {
        for (key, value) in &print.fields {
            fields.entry(key.clone()).or_insert_with(|| value.clone());
        }
        for key in [
            "Tutorial Overall Level",
            "Aims",
            "Teacher's Comments",
            "Additional Comments/Accommodation (under 18s only)",
            "Do you want to take an English proficiency exam?",
            "If yes, which exam?",
            "If yes, when do you want to take the exam?",
            "Initial Speaking",
            "Initial Use of English",
            "Initial Writing",
            "Initial Listening",
            "Speaking",
            "Use of English",
            "Writing",
            "Listening",
            "Reading",
            "Assessment",
            "Type",
            "absent",
        ] {
            if !fields.contains_key(key) {
                if let Some(value) = print.direct_fields.get(key) {
                    fields.insert(key.to_string(), value.clone());
                }
            }
        }
    }

    let stored_ttype_raw = summary
        .map(|entry| entry.ttype_raw.trim().to_string())
        .unwrap_or_default();
    let effective_ttype_raw = if matches!(stored_ttype_raw.as_str(), "0" | "1" | "2") {
        stored_ttype_raw.clone()
    } else {
        ttype_from_fields(&fields)
    };
    let tutorial_type =
        tutorial_type_from_any(&effective_ttype_raw, fields.get("Type").map(String::as_str));
    let assessment = parse_assessment(fields.get("Assessment").map(String::as_str).unwrap_or(""));
    let date = summary
        .and_then(|entry| entry.datetime_label.split_whitespace().next())
        .filter(|value| !value.is_empty())
        .map(str::to_string)
        .or_else(|| print.and_then(|value| value.custom_date.clone()))
        .unwrap_or_default();

    let teacher = edit.map(|value| value.teacher());
    let teacher_id = teacher
        .as_ref()
        .and_then(|value| value.teacher_id)
        .or_else(|| cached_teacher.map(|c| c.teacher_id));
    let teacher_id_source = teacher
        .as_ref()
        .and_then(|value| value.source.clone())
        .or_else(|| cached_teacher.map(|c| c.teacher_id_source.clone()))
        .unwrap_or_default();
    let teacher_name = nonblank(fields.get("Teacher").cloned())
        .or_else(|| print.and_then(|value| nonblank(value.teacher_name.clone())))
        .or_else(|| {
            teacher
                .as_ref()
                .and_then(|value| value.teacher_name.clone())
        })
        .or_else(|| cached_teacher.and_then(|c| nonblank(Some(c.teacher_name.clone()))))
        .unwrap_or_default();

    let (
        speaking,
        use_of_english,
        writing,
        listening,
        reading,
        speaking_before,
        uoe_before,
        writing_before,
        listening_before,
    ) = match tutorial_type {
        TutorialType::Initial => (
            field(&fields, "Initial Speaking"),
            field(&fields, "Initial Use of English"),
            field(&fields, "Initial Writing"),
            field(&fields, "Initial Listening"),
            String::new(),
            String::new(),
            String::new(),
            String::new(),
            String::new(),
        ),
        TutorialType::Standard => (
            field(&fields, "Speaking"),
            field(&fields, "Use of English"),
            field(&fields, "Writing"),
            field(&fields, "Listening"),
            field(&fields, "Reading"),
            String::new(),
            String::new(),
            String::new(),
            String::new(),
        ),
        TutorialType::Final => (
            field(&fields, "Speaking"),
            field(&fields, "Use of English"),
            field(&fields, "Writing"),
            field(&fields, "Listening"),
            field(&fields, "Reading"),
            field(&fields, "Initial Speaking"),
            field(&fields, "Initial Use of English"),
            field(&fields, "Initial Writing"),
            field(&fields, "Initial Listening"),
        ),
    };

    let mut evidence = Vec::new();
    if let Some(summary) = summary {
        for (label, value) in &summary.fields {
            if let Some(field_name) = summary_evidence_name(label) {
                evidence.push(FieldEvidenceWrite {
                    field_name: field_name.to_string(),
                    source_kind: EvidenceSourceKind::Summary,
                    presence: if value.trim().is_empty() {
                        FieldPresence::PresentBlank
                    } else {
                        FieldPresence::Present
                    },
                });
            }
        }
    }
    if teacher_id.is_some() {
        evidence.push(FieldEvidenceWrite {
            field_name: "teacher_id".to_string(),
            source_kind: EvidenceSourceKind::Edit,
            presence: FieldPresence::Present,
        });
    }

    AcquiredState {
        value: TutorialSourceStateWrite {
            student_uid,
            tutorial_ts,
            tutorial_type: Some(tutorial_type),
            ttype_raw: Some(stored_ttype_raw),
            teacher_id,
            teacher_id_source: Some(teacher_id_source),
            teacher_name: Some(teacher_name),
            custom_date: Some(date),
            absent: Some(is_truthy(&field(&fields, "absent"))),
            overall_level: Some(field(&fields, "Tutorial Overall Level")),
            speaking: Some(speaking),
            use_of_english: Some(use_of_english),
            writing: Some(writing),
            listening: Some(listening),
            reading: Some(reading),
            speaking_before: Some(speaking_before),
            uoe_before: Some(uoe_before),
            writing_before: Some(writing_before),
            listening_before: Some(listening_before),
            exam_want: Some(field(
                &fields,
                "Do you want to take an English proficiency exam?",
            )),
            exam_which: Some(field(&fields, "If yes, which exam?")),
            exam_when: Some(field(&fields, "If yes, when do you want to take the exam?")),
            self_listening: Some(assessment.get("listening").cloned().unwrap_or_default()),
            self_reading: Some(assessment.get("reading").cloned().unwrap_or_default()),
            self_writing: Some(assessment.get("writing").cloned().unwrap_or_default()),
            self_speaking: Some(assessment.get("speaking").cloned().unwrap_or_default()),
            self_vocabulary: Some(assessment.get("vocabulary").cloned().unwrap_or_default()),
            self_grammar: Some(assessment.get("grammar").cloned().unwrap_or_default()),
            self_pronunciation: Some(assessment.get("pronunciation").cloned().unwrap_or_default()),
            aims: Some(field(&fields, "Aims")),
            teacher_comments: Some(field(&fields, "Teacher's Comments")),
            additional_comments: Some(field(
                &fields,
                "Additional Comments/Accommodation (under 18s only)",
            )),
            source_method: Some(if summary.is_some_and(|entry| !entry.fields.is_empty()) {
                "summary+print".to_string()
            } else {
                "print_only".to_string()
            }),
            summary_url: Some(format!("/study/tutorials/summary/{student_uid}")),
            print_url: Some(
                summary
                    .map(|entry| entry.print_url.clone())
                    .filter(|value| !value.is_empty())
                    .unwrap_or_else(|| {
                        format!("/study/tutorials/print/{student_uid}/{tutorial_ts}")
                    }),
            ),
            edit_url: Some(
                summary
                    .map(|entry| entry.edit_url.clone())
                    .filter(|value| !value.is_empty())
                    .unwrap_or_else(|| {
                        format!(
                            "/study/tutorials/add/{student_uid}/{tutorial_ts}/{}",
                            tutorial_type.ttype()
                        )
                    }),
            ),
            summary_match_method: Some(match_method.to_string()),
        },
        evidence,
    }
}

fn class_from_json(value: &Value) -> Result<ClassWrite> {
    let object = value
        .as_object()
        .context("GEL class row must be an object")?;
    let class_id = flexible_i64(object, &["id", "class_id"]).context("class id missing")?;
    if class_id <= 0 {
        bail!("class id must be positive");
    }
    Ok(ClassWrite {
        class_id,
        name: flexible_string(object, &["name", "class_name"]),
        course_code: flexible_string(object, &["courseCode"]).filter(|value| value != "Array"),
        start_date: flexible_string(object, &["start_date"])
            .or_else(|| flexible_i64(object, &["from"]).and_then(timestamp_date)),
        end_date: flexible_string(object, &["end_date"])
            .or_else(|| flexible_i64(object, &["to"]).and_then(timestamp_date)),
        is_active: true,
    })
}

fn student_uid_from_json(value: &Value) -> Result<i64> {
    let object = value
        .as_object()
        .context("GEL student row must be an object")?;
    let uid = flexible_i64(object, &["uid", "id", "user_id"]).context("student uid missing")?;
    if uid <= 0 {
        bail!("student uid must be positive");
    }
    Ok(uid)
}

fn student_from_json(uid: i64, roster: &Value, profile: Option<&Value>) -> StudentWrite {
    let empty = Map::new();
    let roster = roster.as_object().unwrap_or(&empty);
    let profile_object = profile.and_then(Value::as_object);
    let school_name = profile_object
        .and_then(|value| value.get("school"))
        .and_then(Value::as_object)
        .and_then(|value| value.get("name"))
        .and_then(value_string);
    StudentWrite {
        uid,
        name: flexible_string(roster, &["name"]).or_else(|| {
            profile_object.and_then(|value| flexible_string(value, &["name", "full_name"]))
        }),
        cefr_level: profile_object.and_then(|value| flexible_i64(value, &["level"])),
        school_name,
        start_date: profile_object
            .and_then(|value| flexible_i64(value, &["startDate"]))
            .or_else(|| flexible_i64(roster, &["start"]))
            .and_then(timestamp_date),
        end_date: profile_object
            .and_then(|value| flexible_i64(value, &["endDate"]))
            .or_else(|| flexible_i64(roster, &["end"]))
            .and_then(timestamp_date),
    }
}

fn merge_student(current: &mut StudentWrite, candidate: &StudentWrite) {
    if current.name.is_none() {
        current.name = candidate.name.clone();
    }
    if current.cefr_level.is_none() {
        current.cefr_level = candidate.cefr_level;
    }
    if current.school_name.is_none() {
        current.school_name = candidate.school_name.clone();
    }
    if current.start_date.is_none() {
        current.start_date = candidate.start_date.clone();
    }
    if current.end_date.is_none() {
        current.end_date = candidate.end_date.clone();
    }
}

fn merge_student_profile_overlay(current: &mut StudentWrite, profile: &StudentWrite) {
    if profile.name.is_some() {
        current.name = profile.name.clone();
    }
    if profile.cefr_level.is_some() {
        current.cefr_level = profile.cefr_level;
    }
    if profile.school_name.is_some() {
        current.school_name = profile.school_name.clone();
    }
    if profile.start_date.is_some() {
        current.start_date = profile.start_date.clone();
    }
    if profile.end_date.is_some() {
        current.end_date = profile.end_date.clone();
    }
}

fn membership_from_json(class_id: i64, uid: i64, value: &Value) -> MembershipWrite {
    let empty = Map::new();
    let object = value.as_object().unwrap_or(&empty);
    let tutorial = object.get("tutorial").and_then(Value::as_object);
    let test = object.get("test").and_then(Value::as_object);
    MembershipWrite {
        class_id,
        student_uid: uid,
        attendance: flexible_i64(object, &["attendance"]),
        tutorial_late: tutorial.and_then(|value| flexible_bool(value, &["late"])),
        last_tutorial_ts: tutorial.and_then(|value| flexible_i64(value, &["timestamp"])),
        test_type: test.and_then(|value| flexible_string(value, &["type"])),
        last_test_ts: test.and_then(|value| flexible_i64(value, &["timestamp"])),
        unmarked_exit_test: flexible_bool(object, &["unmarkedExitTest"]),
    }
}

fn flexible_i64(object: &Map<String, Value>, keys: &[&str]) -> Option<i64> {
    keys.iter().find_map(|key| {
        object.get(*key).and_then(|value| {
            value
                .as_i64()
                .or_else(|| value.as_u64().and_then(|number| i64::try_from(number).ok()))
                .or_else(|| value.as_str().and_then(|text| text.trim().parse().ok()))
        })
    })
}

fn flexible_string(object: &Map<String, Value>, keys: &[&str]) -> Option<String> {
    keys.iter()
        .find_map(|key| object.get(*key).and_then(value_string))
}

fn value_string(value: &Value) -> Option<String> {
    match value {
        Value::String(text) => Some(text.clone()),
        Value::Number(number) => Some(number.to_string()),
        _ => None,
    }
}

fn flexible_bool(object: &Map<String, Value>, keys: &[&str]) -> Option<bool> {
    keys.iter().find_map(|key| {
        object.get(*key).and_then(|value| match value {
            Value::Bool(value) => Some(*value),
            Value::Number(value) => value.as_i64().map(|value| value != 0),
            Value::String(value) => match value.trim().to_ascii_lowercase().as_str() {
                "1" | "true" | "yes" | "on" => Some(true),
                "0" | "false" | "no" | "off" | "" => Some(false),
                _ => None,
            },
            _ => None,
        })
    })
}

fn timestamp_date(timestamp: i64) -> Option<String> {
    DateTime::<Utc>::from_timestamp(timestamp, 0).map(|value| value.date_naive().to_string())
}

fn ttype_from_print(print: Option<&PrintRecord>) -> String {
    print
        .and_then(|value| value.direct_fields.get("Type"))
        .map(|value| ttype_from_label(value))
        .unwrap_or_else(|| "0".to_string())
}

fn ttype_from_fields(fields: &BTreeMap<String, String>) -> String {
    fields
        .get("Type")
        .or_else(|| fields.get("Tutorial Type"))
        .map(|value| ttype_from_label(value))
        .unwrap_or_else(|| "0".to_string())
}

fn effective_ttype_raw(entry: &SummaryEntry, print: Option<&PrintRecord>) -> String {
    if matches!(entry.ttype_raw.trim(), "0" | "1" | "2") {
        entry.ttype_raw.trim().to_string()
    } else {
        ttype_from_print(print)
    }
}

fn ttype_from_label(value: &str) -> String {
    let value = value.trim();
    if matches!(value, "0" | "1" | "2") {
        return value.to_string();
    }
    let value = value.to_ascii_lowercase();
    if value.contains("initial") {
        "2".to_string()
    } else if value.contains("final") {
        "1".to_string()
    } else {
        "0".to_string()
    }
}

fn tutorial_type_from_any(ttype_raw: &str, type_label: Option<&str>) -> TutorialType {
    match ttype_raw.trim() {
        "2" => TutorialType::Initial,
        "1" => TutorialType::Final,
        "0" => TutorialType::Standard,
        _ => match type_label.unwrap_or("").to_ascii_lowercase() {
            value if value.contains("initial") => TutorialType::Initial,
            value if value.contains("final") => TutorialType::Final,
            _ => TutorialType::Standard,
        },
    }
}

fn field(fields: &BTreeMap<String, String>, label: &str) -> String {
    fields.get(label).cloned().unwrap_or_default()
}

fn nonblank(value: Option<String>) -> Option<String> {
    value.filter(|value| !value.trim().is_empty())
}

fn is_truthy(value: &str) -> bool {
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "yes" | "true" | "1" | "on"
    )
}

fn parse_assessment(value: &str) -> BTreeMap<String, String> {
    let mut result = BTreeMap::new();
    for name in [
        "listening",
        "reading",
        "writing",
        "speaking",
        "vocabulary",
        "grammar",
        "pronunciation",
    ] {
        result.insert(name.to_string(), String::new());
    }
    let regex = regex::Regex::new(
        r"(?i)\b(listening|reading|writing|speaking|vocabulary|grammar|pronunciation)\s*:\s*",
    )
    .expect("static assessment regex");
    let matches = regex.captures_iter(value).collect::<Vec<_>>();
    for (index, captures) in matches.iter().enumerate() {
        let whole = captures.get(0).expect("whole assessment match");
        let label = captures
            .get(1)
            .expect("assessment label")
            .as_str()
            .to_ascii_lowercase();
        let end = matches
            .get(index + 1)
            .and_then(|next| next.get(0))
            .map(|next| next.start())
            .unwrap_or(value.len());
        result.insert(
            label,
            value[whole.end()..end]
                .trim_matches(|character: char| " ;,.-".contains(character))
                .to_string(),
        );
    }
    result
}

fn summary_evidence_name(label: &str) -> Option<&'static str> {
    match label {
        "Teacher" => Some("teacher_name"),
        "Tutorial Overall Level" => Some("overall_level"),
        "Initial Speaking" => Some("initial_speaking"),
        "Speaking" => Some("speaking"),
        "Initial Use of English" => Some("initial_use_of_english"),
        "Use of English" => Some("use_of_english"),
        "Initial Writing" => Some("initial_writing"),
        "Writing" => Some("writing"),
        "Initial Listening" => Some("initial_listening"),
        "Listening" => Some("listening"),
        "Reading" => Some("reading"),
        "Assessment" => Some("self_assessment"),
        "Aims" => Some("aims"),
        "Teacher's Comments" => Some("teacher_comments"),
        "Additional Comments/Accommodation (under 18s only)" => Some("additional_comments"),
        "Do you want to take an English proficiency exam?" => Some("exam_intent"),
        "If yes, which exam?" => Some("exam_type"),
        "If yes, when do you want to take the exam?" => Some("exam_when"),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::archive_sync_repository::SyncScope;
    use crate::{ArchiveRepository, ArchiveRevisionAvailability};
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_db(label: &str) -> PathBuf {
        let nonce = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("gel-a2-{label}-{}-{nonce}.db", std::process::id()))
    }

    #[test]
    fn a2_creates_schema_v2_atomically_and_read_repository_accepts_it() -> Result<()> {
        let path = temp_db("fresh");
        RustArchiver::ensure_database(&path)?;
        let repository = ArchiveRepository::open_read_only(&path)?;
        assert!(repository.list_classes(false)?.is_empty());
        fs::remove_file(path)?;
        Ok(())
    }

    #[test]
    fn python_v49_summary_blank_beats_print_fallback() {
        let summary = SummaryEntry {
            datetime_label: "19-02-2026 10:00".to_string(),
            tutorial_ts: 1_771_495_200,
            ttype_raw: "0".to_string(),
            ttype_label: "Standard".to_string(),
            print_url: String::new(),
            edit_url: String::new(),
            fields: BTreeMap::from([
                ("Tutorial Type".to_string(), "Standard".to_string()),
                ("Aims".to_string(), String::new()),
                ("Speaking".to_string(), "B1".to_string()),
            ]),
        };
        let print = PrintRecord {
            fields: BTreeMap::from([
                ("Aims".to_string(), "must not replace blank".to_string()),
                ("Listening".to_string(), "B1+".to_string()),
            ]),
            direct_fields: BTreeMap::from([
                ("Aims".to_string(), "must not replace blank".to_string()),
                ("Listening".to_string(), "B1+".to_string()),
            ]),
            ..PrintRecord::default()
        };
        let state = build_state(
            42,
            summary.tutorial_ts,
            Some(&summary),
            Some(&print),
            None,
            None,
            "exact_timestamp",
        );
        assert_eq!(state.value.aims.as_deref(), Some(""));
        assert_eq!(state.value.listening.as_deref(), Some("B1+"));
    }

    #[test]
    fn in_absentia_tutorial_retains_full_academic_scores_and_absent_flag() {
        let summary = SummaryEntry {
            datetime_label: "05-08-2026 12:00 pm (absent)".to_string(),
            tutorial_ts: 1_785_928_657,
            ttype_raw: "1".to_string(),
            ttype_label: "Final".to_string(),
            print_url: "/print/42".to_string(),
            edit_url: "/edit/42".to_string(),
            fields: BTreeMap::from([
                ("Type".to_string(), "final".to_string()),
                ("absent".to_string(), "yes".to_string()),
                (
                    "Tutorial Overall Level".to_string(),
                    "A2-: pre-intermediate".to_string(),
                ),
                ("Initial Speaking".to_string(), "A1".to_string()),
                ("Speaking".to_string(), "A2".to_string()),
                ("Initial Use of English".to_string(), "A1".to_string()),
                ("Use of English".to_string(), "A2-".to_string()),
                ("Initial Writing".to_string(), "A1+".to_string()),
                ("Writing".to_string(), "A1+".to_string()),
                ("Initial Listening".to_string(), "A1".to_string()),
                ("Listening".to_string(), "A2".to_string()),
                ("Reading".to_string(), "A2".to_string()),
                (
                    "Teacher's Comments".to_string(),
                    "Student completed work before the session.".to_string(),
                ),
            ]),
        };

        let state = build_state(
            42,
            summary.tutorial_ts,
            Some(&summary),
            None,
            None,
            None,
            "exact_timestamp",
        );

        assert_eq!(state.value.absent, Some(true));
        assert_eq!(state.value.speaking.as_deref(), Some("A2"));
        assert_eq!(state.value.listening.as_deref(), Some("A2"));
        assert_eq!(state.value.reading.as_deref(), Some("A2"));
        assert_eq!(state.value.speaking_before.as_deref(), Some("A1"));
        assert_eq!(
            state.value.teacher_comments.as_deref(),
            Some("Student completed work before the session.")
        );
    }

    #[test]
    fn anom_absent_001_summary_presence_beats_edit_form_checkbox() {
        let summary = SummaryEntry {
            datetime_label: "20-07-2026 3:18 pm".to_string(),
            tutorial_ts: 1_781_609_897,
            ttype_raw: "0".to_string(),
            ttype_label: "Standard".to_string(),
            print_url: String::new(),
            edit_url: String::new(),
            fields: BTreeMap::from([
                ("Tutorial Type".to_string(), "Standard".to_string()),
                ("absent".to_string(), "no".to_string()),
                ("Speaking".to_string(), "B1".to_string()),
            ]),
        };

        let state = build_state(
            42,
            summary.tutorial_ts,
            Some(&summary),
            None,
            None,
            None,
            "exact_timestamp",
        );

        assert_eq!(state.value.absent, Some(false));
    }

    #[test]
    fn summary_completeness_requires_valid_ttype_raw() {
        let mut fields = BTreeMap::new();
        fields.insert("Teacher".to_string(), "Teacher A".to_string());
        fields.insert("absent".to_string(), "no".to_string());
        fields.insert("Tutorial Overall Level".to_string(), "B1".to_string());
        fields.insert("Speaking".to_string(), "B1".to_string());
        fields.insert("Use of English".to_string(), "B1".to_string());
        fields.insert("Writing".to_string(), "B1".to_string());
        fields.insert("Listening".to_string(), "B1".to_string());
        fields.insert("Reading".to_string(), "B1".to_string());
        fields.insert("Assessment".to_string(), "OK".to_string());
        fields.insert("Aims".to_string(), "Aims".to_string());
        fields.insert("Teacher's Comments".to_string(), "Good".to_string());

        let mut entry = SummaryEntry {
            datetime_label: "19-02-2026 10:00".to_string(),
            tutorial_ts: 1_771_495_200,
            ttype_raw: "0".to_string(),
            ttype_label: "Standard".to_string(),
            print_url: String::new(),
            edit_url: String::new(),
            fields,
        };

        assert!(is_summary_complete_for_type(&entry, TutorialType::Standard));

        entry.ttype_raw = "".to_string();
        assert!(!is_summary_complete_for_type(
            &entry,
            TutorialType::Standard
        ));
    }

    #[test]
    fn cached_teacher_preserves_exact_source_and_fingerprint() {
        let summary = SummaryEntry {
            datetime_label: "19-02-2026 10:00".to_string(),
            tutorial_ts: 1_771_495_200,
            ttype_raw: "0".to_string(),
            ttype_label: "Standard".to_string(),
            print_url: String::new(),
            edit_url: String::new(),
            fields: BTreeMap::from([
                ("Tutorial Type".to_string(), "Standard".to_string()),
                ("Teacher".to_string(), "Teacher Name".to_string()),
            ]),
        };

        let cached = CachedTeacher {
            teacher_id: 326743,
            teacher_id_source: "edit_form_inline_js".to_string(),
            teacher_name: "Teacher Name".to_string(),
        };

        let state = build_state(
            42,
            summary.tutorial_ts,
            Some(&summary),
            None,
            None,
            Some(&cached),
            "exact_timestamp",
        );

        assert_eq!(state.value.teacher_id, Some(326743));
        assert_eq!(
            state.value.teacher_id_source.as_deref(),
            Some("edit_form_inline_js")
        );
        assert_eq!(state.value.teacher_name.as_deref(), Some("Teacher Name"));
    }

    #[test]
    fn a2_materialization_makes_proven_state_revision_readable() -> Result<()> {
        let path = temp_db("materialize");
        RustArchiver::ensure_database(&path)?;
        let state = AcquiredState {
            value: TutorialSourceStateWrite {
                student_uid: 42,
                tutorial_ts: 1_771_495_200,
                tutorial_type: Some(TutorialType::Standard),
                ttype_raw: Some("0".into()),
                teacher_id: Some(7),
                teacher_id_source: Some("inline_js_tid".into()),
                teacher_name: Some("Teacher".into()),
                custom_date: Some("19-02-2026".into()),
                absent: Some(false),
                overall_level: Some("B1: intermediate".into()),
                speaking: Some("B1".into()),
                use_of_english: Some("B1".into()),
                writing: Some("B1".into()),
                listening: Some("B1".into()),
                reading: Some("B1".into()),
                speaking_before: Some(String::new()),
                uoe_before: Some(String::new()),
                writing_before: Some(String::new()),
                listening_before: Some(String::new()),
                exam_want: Some(String::new()),
                exam_which: Some(String::new()),
                exam_when: Some(String::new()),
                self_listening: Some(String::new()),
                self_reading: Some(String::new()),
                self_writing: Some(String::new()),
                self_speaking: Some(String::new()),
                self_vocabulary: Some(String::new()),
                self_grammar: Some(String::new()),
                self_pronunciation: Some(String::new()),
                aims: Some("Aim".into()),
                teacher_comments: Some("Comment".into()),
                additional_comments: Some(String::new()),
                source_method: Some("summary+print".into()),
                summary_url: Some("/summary/42".into()),
                print_url: Some("/print/42".into()),
                edit_url: Some("/edit/42".into()),
                summary_match_method: Some("exact_timestamp".into()),
            },
            evidence: Vec::new(),
        };
        materialize_snapshot(
            &path,
            AcquiredSnapshot {
                classes: vec![ClassWrite {
                    class_id: 1,
                    name: Some("Class".into()),
                    is_active: true,
                    ..ClassWrite::default()
                }],
                students: vec![StudentWrite {
                    uid: 42,
                    name: Some("Student".into()),
                    ..StudentWrite::default()
                }],
                memberships: vec![MembershipWrite {
                    class_id: 1,
                    student_uid: 42,
                    ..MembershipWrite::default()
                }],
                tutorials: vec![AcquiredTutorial {
                    identity: TutorialIdentityWrite {
                        tutorial_id: 1001,
                        student_uid: 42,
                        tutorial_ts: 1_771_495_200,
                    },
                    state: Some(state),
                    authority_status: HistoricalStateAuthorityStatus::ProvenPerTutorial,
                    collision_key: None,
                    proof_method: "test".into(),
                }],
                collisions: Vec::new(),
                summary_failures: 0,
                print_failures: 0,
                profile_failures: 0,
                edit_failures: 0,
            },
        )?;
        let repository = ArchiveRepository::open_read_only(&path)?;
        assert!(matches!(
            repository.revision_source(1001)?,
            ArchiveRevisionAvailability::Available { .. }
        ));
        fs::remove_file(path)?;
        Ok(())
    }

    #[test]
    fn targeted_sync_materializes_student_and_tutorials_without_classes() -> Result<()> {
        let path = temp_db("targeted");
        RustArchiver::ensure_database(&path)?;
        let state = AcquiredState {
            value: TutorialSourceStateWrite {
                student_uid: 42,
                tutorial_ts: 1_771_495_200,
                tutorial_type: Some(TutorialType::Standard),
                ttype_raw: Some("0".into()),
                teacher_id: Some(7),
                teacher_id_source: Some("inline_js_tid".into()),
                teacher_name: Some("Teacher".into()),
                custom_date: Some("19-02-2026".into()),
                absent: Some(false),
                overall_level: Some("B1: intermediate".into()),
                speaking: Some("B1".into()),
                use_of_english: Some("B1".into()),
                writing: Some("B1".into()),
                listening: Some("B1".into()),
                reading: Some("B1".into()),
                speaking_before: Some(String::new()),
                uoe_before: Some(String::new()),
                writing_before: Some(String::new()),
                listening_before: Some(String::new()),
                exam_want: Some(String::new()),
                exam_which: Some(String::new()),
                exam_when: Some(String::new()),
                self_listening: Some(String::new()),
                self_reading: Some(String::new()),
                self_writing: Some(String::new()),
                self_speaking: Some(String::new()),
                self_vocabulary: Some(String::new()),
                self_grammar: Some(String::new()),
                self_pronunciation: Some(String::new()),
                aims: Some("Aim".into()),
                teacher_comments: Some("Comment".into()),
                additional_comments: Some(String::new()),
                source_method: Some("summary+print".into()),
                summary_url: Some("/summary/42".into()),
                print_url: Some("/print/42".into()),
                edit_url: Some("/edit/42".into()),
                summary_match_method: Some("exact_timestamp".into()),
            },
            evidence: Vec::new(),
        };
        let snapshot = AcquiredSnapshot {
            classes: Vec::new(),
            students: vec![StudentWrite {
                uid: 42,
                name: Some("Targeted Student".into()),
                ..StudentWrite::default()
            }],
            memberships: Vec::new(),
            tutorials: vec![AcquiredTutorial {
                identity: TutorialIdentityWrite {
                    tutorial_id: 2002,
                    student_uid: 42,
                    tutorial_ts: 1_771_495_200,
                },
                state: Some(state),
                authority_status: HistoricalStateAuthorityStatus::ProvenPerTutorial,
                collision_key: None,
                proof_method: "targeted_test".into(),
            }],
            collisions: Vec::new(),
            summary_failures: 0,
            print_failures: 0,
            profile_failures: 0,
            edit_failures: 0,
        };
        let report = materialize_snapshot_with_scope(
            &path,
            snapshot,
            SyncScope::Targeted("student:42".into()),
        )?;
        assert_eq!(report.students, 1);
        assert_eq!(report.tutorial_identities, 1);
        assert_eq!(report.proven_per_tutorial, 1);

        let repository = ArchiveRepository::open_read_only(&path)?;
        assert!(matches!(
            repository.revision_source(2002)?,
            ArchiveRevisionAvailability::Available { .. }
        ));
        fs::remove_file(path)?;
        Ok(())
    }
}
