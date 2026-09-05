#!/usr/bin/env python3
"""fix_w2_rust_and_ts.py — Fix compilation types in submission_transport and api.ts."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel: str, content: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"  [✓] updated: {rel}")

print("=== 1. Rewriting gel-core/src/submission_transport.rs with exact anyhow and ApiTutorial types ===")
submission_transport_rs = """//! Live GEL tutorial submission transport for Phase W2.
//!
//! Submits validated tutorial POST payloads to `/study/tutorials/process`, discovers
//! newly assigned canonical tutorial identities via post-submit GET readback, and
//! reconciles the server record into local archive v2 via targeted sync.

use std::collections::HashSet;
use std::fmt;
use std::path::Path;
use std::time::Duration;
use serde::{Deserialize, Serialize};

use crate::gel_session::GelSession;
use crate::post_mapper::build_tutorial_post_payload;
use crate::semantic::{DraftOrigin, TutorialFormState, TutorialType};
use crate::RustArchiver;

const TUTORIAL_PROCESS_PATH: &str = "/study/tutorials/process";
const LEARN2_BASE: &str = "https://learn2.guidedelearning.net";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SubmissionReceipt {
    pub tutorial_id: i64,
    pub tutorial_ts: i64,
    pub tutorial_type: TutorialType,
    pub student_uid: i64,
    pub is_new: bool,
    pub reconciled: bool,
}

#[derive(Debug)]
pub enum SubmissionError {
    Unauthenticated,
    Mapping(anyhow::Error),
    Network(String),
    ServerError(u16),
    ReadbackDiscoveryFailed,
    ArchiveSync(String),
    Session(anyhow::Error),
}

impl fmt::Display for SubmissionError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Unauthenticated => write!(f, "session is not authenticated"),
            Self::Mapping(e) => write!(f, "post mapping error: {e}"),
            Self::Network(e) => write!(f, "network transport error: {e}"),
            Self::ServerError(status) => write!(f, "GEL server error: HTTP {status}"),
            Self::ReadbackDiscoveryFailed => {
                write!(f, "post-submit readback failed to discover new tutorial identity")
            }
            Self::ArchiveSync(e) => write!(f, "archive sync error: {e}"),
            Self::Session(e) => write!(f, "session error: {e}"),
        }
    }
}

impl std::error::Error for SubmissionError {}

/// Submit an active tutorial draft to GEL, discover the assigned tutorial ID via readback,
/// and reconcile the record into the local SQLite archive.
pub fn submit_tutorial_draft(
    session: &mut GelSession,
    draft: &TutorialFormState,
    archive_path: Option<&Path>,
) -> Result<SubmissionReceipt, SubmissionError> {
    if !session.is_authenticated() {
        return Err(SubmissionError::Unauthenticated);
    }

    let student_uid = draft.student_uid;
    let is_new = matches!(draft.origin, DraftOrigin::New { .. });
    let expected_ts = match &draft.origin {
        DraftOrigin::Revision { source, .. } => Some(source.tutorial_ts),
        DraftOrigin::New { .. } => None,
    };

    // 1. Build POST payload using the canonical post_mapper
    let payload = build_tutorial_post_payload(draft)
        .map_err(SubmissionError::Mapping)?;

    // 2. Pre-submit readback: capture existing tutorial list IDs
    let pre_tutorials = session
        .get_tutorial_list(student_uid)
        .map_err(SubmissionError::Session)?;
    let pre_ids: HashSet<i64> = pre_tutorials.iter().map(|t| t.id).collect();

    // 3. Dispatch authenticated POST to /study/tutorials/process
    let url = format!("{LEARN2_BASE}{TUTORIAL_PROCESS_PATH}");
    let form_params: Vec<(&str, &str)> = payload.iter().map(|(k, v)| (k.as_str(), v.as_str())).collect();

    let response = session
        .client()
        .post(&url)
        .form(&form_params)
        .timeout(Duration::from_secs(30))
        .send()
        .map_err(|e| SubmissionError::Network(e.to_string()))?;

    let status = response.status().as_u16();
    if status >= 400 {
        return Err(SubmissionError::ServerError(status));
    }

    // 4. Post-submit server readback: discover canonical tutorial_id and timestamp
    let post_tutorials = session
        .get_tutorial_list(student_uid)
        .map_err(SubmissionError::Session)?;

    let (discovered_id, discovered_ts) = if is_new {
        let new_item = post_tutorials
            .iter()
            .find(|t| !pre_ids.contains(&t.id))
            .or_else(|| {
                post_tutorials
                    .iter()
                    .max_by_key(|t| t.timestamp)
            })
            .ok_or(SubmissionError::ReadbackDiscoveryFailed)?;

        (new_item.id, new_item.timestamp)
    } else {
        let expected = expected_ts.unwrap_or_default();
        let revised_item = post_tutorials
            .iter()
            .find(|t| t.timestamp == expected)
            .ok_or(SubmissionError::ReadbackDiscoveryFailed)?;

        (revised_item.id, revised_item.timestamp)
    };

    // 5. Local archive sync reconciliation (if archive path provided)
    let reconciled = if let Some(path) = archive_path {
        RustArchiver::sync_full(session, path)
            .map(|_| true)
            .map_err(|e| SubmissionError::ArchiveSync(e.to_string()))?
    } else {
        false
    };

    Ok(SubmissionReceipt {
        tutorial_id: discovered_id,
        tutorial_ts: discovered_ts,
        tutorial_type: draft.tutorial_type,
        student_uid,
        is_new,
        reconciled,
    })
}
"""
write("gel-core/src/submission_transport.rs", submission_transport_rs)

print("=== 2. Updating gel-core/tests/submission_transport.rs ===")
behavioral_test_rs = """use chrono::NaiveDate;
use gel_core::semantic::{
    BooleanFieldProvenance, DraftOrigin, FieldSource, LevelRegressionBaseline, TeacherRef,
    TutorialFormProvenance, TutorialFormState, TutorialIdentity, TutorialType,
};
use gel_core::post_mapper::build_tutorial_post_payload;
use gel_core::gel_fields;

fn mock_new_draft() -> TutorialFormState {
    TutorialFormState {
        origin: DraftOrigin::New {
            prepopulation_source: None,
            form_teacher: gel_core::semantic::ValidatedNewFormTeacher::from_validated_hidden_control(326743),
            level_regression_baseline: LevelRegressionBaseline::default(),
        },
        student_uid: 464954,
        tutorial_type: TutorialType::Standard,
        tutorial_date: NaiveDate::from_ymd_opt(2026, 9, 3).unwrap(),
        teacher: TeacherRef {
            teacher_id: Some(326743),
            teacher_name: Some("Authenticated Teacher".into()),
        },
        absent: false,
        overall_level: None,
        initial_scores: Default::default(),
        current_scores: Default::default(),
        reading: None,
        self_assessment: Default::default(),
        exam: Default::default(),
        aims: "Develop conversational fluency".into(),
        teacher_comments: "Good effort in class".into(),
        additional_comments: String::new(),
        provenance: TutorialFormProvenance {
            absent: BooleanFieldProvenance {
                authoritative_value: false,
                authoritative_source: FieldSource::NewForm,
                edit_form_value: None,
                discrepancy: None,
            },
            overall_level_source_raw: None,
            aims_source_html: None,
        },
    }
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
    assert_eq!(payload.get(gel_fields::STUDENT_UID).map(|s| s.as_str()), Some("464954"));
    assert_eq!(payload.get(gel_fields::TUTORIAL_TYPE).map(|s| s.as_str()), Some("0"));
    assert_eq!(payload.get(gel_fields::CUSTOM_DATE).map(|s| s.as_str()), Some("03-09-2026"));
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
write("gel-core/tests/submission_transport.rs", behavioral_test_rs)

print("=== 3. Updating writer-ui/src/api.ts with clean SubmissionReceiptView import ===")
api_clean = """import { invoke } from "@tauri-apps/api/core";
import type {
  ArchiveClassView,
  ArchiveStatus,
  ArchiveSyncReport,
  DraftView,
  SessionInfo,
  StudentView,
  TutorialDraftEdit,
  TutorialListView,
  TutorialType,
  HarperCheckDto,
  HarperDictionaryEntry,
  HarperDictionaryMutation,
  SubmissionReceiptView,
} from "./types";

export const sessionStatus = () => invoke<SessionInfo>("ui1_session_status");
export const login = (username: string, password: string) =>
  invoke<SessionInfo>("ui1_login", { username, password });
export const logout = () => invoke<void>("ui1_logout");
export const archiveStatus = () => invoke<ArchiveStatus>("ui1_archive_status");
export const syncArchive = () => invoke<ArchiveSyncReport>("ui1_sync_archive");
export const listClasses = () => invoke<ArchiveClassView[]>("ui1_list_classes");
export const listStudents = (classId: number) =>
  invoke<StudentView[]>("ui1_list_students", { classId });
export const listTutorials = (studentId: number) =>
  invoke<TutorialListView[]>("ui1_list_tutorials", { studentId });
export const openNewDraft = (studentId: number, tutorialType: TutorialType) =>
  invoke<DraftView>("ui1_open_new_draft", { studentId, tutorialType });
export const openRevisionDraft = (tutorialId: number) =>
  invoke<DraftView>("ui1_open_revision_draft", { tutorialId });
export const getDraft = () => invoke<DraftView | null>("ui1_get_draft");
export const applyDraftEdit = (edit: TutorialDraftEdit) =>
  invoke<DraftView>("ui1_apply_draft_edit", { edit });
export const discardDraft = () => invoke<void>("ui1_discard_draft");
export const submitDraft = () => invoke<SubmissionReceiptView>("ui1_submit_draft");

export const harperCheck = (
  field: HarperCheckDto["field"],
  text: string,
  disabledRules: string[] = [],
  suppressedKinds: string[] = [],
) =>
  invoke<HarperCheckDto>("ui1_harper_check", {
    field,
    text,
    disabledRules,
    suppressedKinds,
  });
export const harperDictionaryList = () =>
  invoke<HarperDictionaryEntry[]>("ui1_harper_dictionary_list");
export const harperDictionaryAdd = (word: string) =>
  invoke<HarperDictionaryMutation>("ui1_harper_dictionary_add", { word });
export const harperDictionaryRemove = (word: string) =>
  invoke<HarperDictionaryMutation>("ui1_harper_dictionary_remove", { word });
"""
write("writer-ui/src/api.ts", api_clean)

print("=== 4. Regenerating Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("=== Fix Complete! ===")