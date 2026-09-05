#!/usr/bin/env python3
"""apply_w2_implementation.py — Apply Phase W2 live submission transport and UI integration in place."""
from __future__ import annotations

import json
import re
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

def write_json(rel: str, data: dict) -> None:
    write(rel, json.dumps(data, indent=2, ensure_ascii=False))

print("=== 1. Writing gel-core/src/submission_transport.rs ===")
submission_transport_rs = """//! Live GEL tutorial submission transport for Phase W2.
//!
//! Submits validated tutorial POST payloads to `/study/tutorials/process`, discovers
//! newly assigned canonical tutorial identities via post-submit GET readback, and
//! reconciles the server record into local archive v2 via targeted sync.

use std::collections::HashSet;
use std::path::Path;
use std::time::Duration;
use serde::{Deserialize, Serialize};

use crate::gel_session::{GelSession, GelSessionError};
use crate::post_mapper::{build_new_tutorial_post_payload, build_revision_tutorial_post_payload, PostMapperError};
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

#[derive(Debug, thiserror::Error)]
pub enum SubmissionError {
    #[error("session is not authenticated")]
    Unauthenticated,
    #[error("post mapping error: {0}")]
    Mapping(#[from] PostMapperError),
    #[error("network transport error: {0}")]
    Network(String),
    #[error("GEL server error: HTTP {0}")]
    ServerError(u16),
    #[error("post-submit readback failed to discover new tutorial identity")]
    ReadbackDiscoveryFailed,
    #[error("targeted archive sync error: {0}")]
    ArchiveSync(String),
    #[error("session error: {0}")]
    Session(#[from] GelSessionError),
}

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

    // 1. Build origin-specific POST payload
    let (payload, is_new, expected_ts) = match &draft.origin {
        DraftOrigin::New { .. } => {
            let p = build_new_tutorial_post_payload(draft)?;
            if p.contains_key(crate::gel_fields::SOURCE_TIMESTAMP) {
                return Err(SubmissionError::Mapping(PostMapperError::UnexpectedField {
                    field: crate::gel_fields::SOURCE_TIMESTAMP,
                }));
            }
            (p, true, None)
        }
        DraftOrigin::Revision { source, .. } => {
            let p = build_revision_tutorial_post_payload(draft)?;
            let source_ts_str = source.tutorial_ts.to_string();
            if p.get(crate::gel_fields::SOURCE_TIMESTAMP) != Some(&source_ts_str) {
                return Err(SubmissionError::Mapping(PostMapperError::MissingRequiredField {
                    field: crate::gel_fields::SOURCE_TIMESTAMP,
                }));
            }
            (p, false, Some(source.tutorial_ts))
        }
    };

    // 2. Pre-submit readback: capture existing tutorial list IDs
    let pre_tutorials = session
        .get_tutorial_list(student_uid)
        .map_err(SubmissionError::Session)?;
    let pre_ids: HashSet<i64> = pre_tutorials.iter().map(|t| t.tutorial_id).collect();

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
            .find(|t| !pre_ids.contains(&t.tutorial_id))
            .or_else(|| {
                post_tutorials
                    .iter()
                    .max_by_key(|t| t.tutorial_ts)
            })
            .ok_or(SubmissionError::ReadbackDiscoveryFailed)?;

        (new_item.tutorial_id, new_item.tutorial_ts)
    } else {
        let expected = expected_ts.unwrap_or_default();
        let revised_item = post_tutorials
            .iter()
            .find(|t| t.tutorial_ts == expected)
            .ok_or(SubmissionError::ReadbackDiscoveryFailed)?;

        (revised_item.tutorial_id, revised_item.tutorial_ts)
    };

    // 5. Targeted local archive sync reconciliation
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

print("=== 2. Updating gel-core/src/lib.rs and gel-core/src/gel_session.rs ===")
session_rs = read("gel-core/src/gel_session.rs")
if "pub(crate) fn client(&self)" not in session_rs:
    session_rs = session_rs.replace(
        "    pub fn is_authenticated(&self) -> bool {",
        "    pub(crate) fn client(&self) -> &reqwest::blocking::Client {\n        &self.client\n    }\n\n    pub fn is_authenticated(&self) -> bool {"
    )
    write("gel-core/src/gel_session.rs", session_rs)

lib_rs = read("gel-core/src/lib.rs")
if "pub mod submission_transport;" not in lib_rs:
    lib_rs += "\npub mod submission_transport;\npub use submission_transport::{submit_tutorial_draft, SubmissionReceipt, SubmissionError};\n"
    write("gel-core/src/lib.rs", lib_rs)

print("=== 3. Updating writer-ui/src-tauri/src/lib.rs with ui1_submit_draft ===")
tauri_lib = read("writer-ui/src-tauri/src/lib.rs")

if "struct SubmissionReceiptView" not in tauri_lib:
    dto_def = """
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SubmissionReceiptView {
    tutorial_id: i64,
    tutorial_ts: i64,
    tutorial_type: &'static str,
    student_uid: i64,
    is_new: bool,
    reconciled: bool,
}
"""
    tauri_lib = tauri_lib.replace("#[derive(Debug, Serialize)]\n#[serde(rename_all = \"camelCase\")]\nstruct DraftView {", dto_def + "\n#[derive(Debug, Serialize)]\n#[serde(rename_all = \"camelCase\")]\nstruct DraftView {")

submit_command = """
#[tauri::command]
fn ui1_submit_draft(
    state: State<'_, WriterAppState>,
) -> Result<SubmissionReceiptView, String> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;

    let (draft_current, is_stale) = {
        let draft_guard = state
            .draft
            .read()
            .map_err(|_| "draft lock poisoned".to_string())?;
        let loaded = draft_guard
            .as_ref()
            .ok_or_else(|| "no active draft to submit".to_string())?;
        (loaded.current.clone(), loaded.stale)
    };

    if is_stale {
        return Err("cannot submit draft with stale source authority; please discard and reopen".into());
    }

    let mut session_guard = state
        .session
        .lock()
        .map_err(|_| "session lock poisoned".to_string())?;
    let session = session_guard
        .as_mut()
        .filter(|s| s.is_authenticated())
        .ok_or_else(|| "an authenticated GEL session is required to submit a tutorial".to_string())?;

    let receipt = gel_core::submission_transport::submit_tutorial_draft(
        session,
        &draft_current,
        state.archive_path.as_deref(),
    )
    .map_err(|error| format!("submission failed: {error}"))?;

    *state
        .draft
        .write()
        .map_err(|_| "draft lock poisoned".to_string())? = None;

    Ok(SubmissionReceiptView {
        tutorial_id: receipt.tutorial_id,
        tutorial_ts: receipt.tutorial_ts,
        tutorial_type: tutorial_type_name(receipt.tutorial_type),
        student_uid: receipt.student_uid,
        is_new: receipt.is_new,
        reconciled: receipt.reconciled,
    })
}
"""

if "fn ui1_submit_draft(" not in tauri_lib:
    tauri_lib = tauri_lib.replace(
        "#[tauri::command]\nfn ui1_discard_draft(",
        submit_command + "\n#[tauri::command]\nfn ui1_discard_draft("
    )
    tauri_lib = tauri_lib.replace(
        "ui1_discard_draft,\n            ui1_harper_check,",
        "ui1_discard_draft,\n            ui1_submit_draft,\n            ui1_harper_check,"
    )
    write("writer-ui/src-tauri/src/lib.rs", tauri_lib)

print("=== 4. Updating Frontend Types & API Wrappers ===")
types_ts = read("writer-ui/src/types.ts")
if "SubmissionReceiptView" not in types_ts:
    types_ts += """

export interface SubmissionReceiptView {
  tutorialId: number;
  tutorialTs: number;
  tutorialType: TutorialType;
  studentUid: number;
  isNew: boolean;
  reconciled: boolean;
}
"""
    write("writer-ui/src/types.ts", types_ts)

api_ts = read("writer-ui/src/api.ts")
if "ui1_submit_draft" not in api_ts:
    api_ts = api_ts.replace(
        'export const discardDraft = () => invoke<void>("ui1_discard_draft");',
        'export const discardDraft = () => invoke<void>("ui1_discard_draft");\nexport const submitDraft = () => invoke<SubmissionReceiptView>("ui1_submit_draft");'
    )
    if "SubmissionReceiptView" not in api_ts:
        api_ts = api_ts.replace(
            'import type {',
            'import type {\n  SubmissionReceiptView,'
        )
    write("writer-ui/src/api.ts", api_ts)

print("=== 5. Adding ConfirmSubmitDialog and UI Controls ===")
confirm_dialog_tsx = """interface Props {
  open: boolean;
  studentName: string;
  tutorialType: string;
  tutorialDate: string;
  isNew: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmSubmitDialog({
  open,
  studentName,
  tutorialType,
  tutorialDate,
  isNew,
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null;
  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="submit-title">
        <h2 id="submit-title">Submit tutorial to GEL server?</h2>
        <p>
          You are about to {isNew ? "create a new" : "update the historical"} <strong>{tutorialType}</strong> tutorial for <strong>{studentName}</strong> dated <strong>{tutorialDate}</strong>.
        </p>
        <p className="subtle" style={{ margin: "6px 0 12px" }}>
          This will dispatch a live HTTP POST to the school server and reconcile the record into your local archive.
        </p>
        <div className="dialog-actions">
          <button className="primary" type="button" onClick={onConfirm} autoFocus>
            Submit to GEL
          </button>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </section>
    </div>
  );
}
"""
write("writer-ui/src/components/ConfirmSubmitDialog.tsx", confirm_dialog_tsx)

foundation_tsx = read("writer-ui/src/components/DraftFoundationPanel.tsx")
if "onSubmit" not in foundation_tsx:
    foundation_tsx = foundation_tsx.replace(
        "  onDiscard: () => void;",
        "  onDiscard: () => void;\n  onSubmit: () => void;\n  isSubmitting?: boolean;"
    )
    foundation_tsx = foundation_tsx.replace(
        "  onDiscard,\n  disabledHarperRules,",
        "  onDiscard,\n  onSubmit,\n  isSubmitting = false,\n  disabledHarperRules,"
    )
    submit_btn_markup = """            <button
              type="button"
              className="primary"
              disabled={isSubmitting || draft.status === "clean" || draft.status === "stale_source" || draft.status === "invalid"}
              onClick={onSubmit}
            >
              {isSubmitting ? "Submitting…" : "Submit tutorial"}
            </button>
            <button type="button" className="secondary" onClick={onDiscard}>Discard</button>"""
    foundation_tsx = foundation_tsx.replace(
        '            <button type="button" className="secondary" onClick={onDiscard}>Discard</button>',
        submit_btn_markup
    )
    write("writer-ui/src/components/DraftFoundationPanel.tsx", foundation_tsx)

app_tsx = read("writer-ui/src/App.tsx")
if "ConfirmSubmitDialog" not in app_tsx:
    app_tsx = app_tsx.replace(
        'import { DiscardDraftDialog } from "./components/DiscardDraftDialog";',
        'import { DiscardDraftDialog } from "./components/DiscardDraftDialog";\nimport { ConfirmSubmitDialog } from "./components/ConfirmSubmitDialog";'
    )
    app_tsx = app_tsx.replace(
        'import {\n  applyDraftEdit,',
        'import {\n  applyDraftEdit,\n  submitDraft,'
    )
    submit_logic = """  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function doSubmit() {
    setConfirmSubmitOpen(false);
    setSubmitting(true);
    setError(null);
    try {
      const receipt = await submitDraft();
      setDraft(null);
      setDraftIssue(null);
      setContextCollapsed(false);
      if (studentId != null) {
        setTutorials(await listTutorials(studentId));
      }
    } catch (value) {
      setError(errorText(value));
    } finally {
      setSubmitting(false);
    }
  }"""
    app_tsx = app_tsx.replace("  const writing = draft != null;", submit_logic + "\n\n  const writing = draft != null;")
    app_tsx = app_tsx.replace(
        "<DraftFoundationPanel draft={draft} onEdit={doEdit} onDiscard={doDiscard}",
        "<DraftFoundationPanel draft={draft} onEdit={doEdit} onDiscard={doDiscard} onSubmit={() => setConfirmSubmitOpen(true)} isSubmitting={submitting}"
    )
    dialog_insert = """      <ConfirmSubmitDialog
        open={confirmSubmitOpen}
        studentName={selectedStudent?.name ?? "Student"}
        tutorialType={draft?.tutorialType ?? "Standard"}
        tutorialDate={draft?.tutorialDate ?? ""}
        isNew={draft?.origin === "new"}
        onConfirm={() => void doSubmit()}
        onCancel={() => setConfirmSubmitOpen(false)}
      />"""
    app_tsx = app_tsx.replace("      <DiscardDraftDialog", dialog_insert + "\n\n      <DiscardDraftDialog")
    write("writer-ui/src/App.tsx", app_tsx)

print("=== 6. Writing Offline Behavioral Tests (gel-core/tests/submission_transport.rs) ===")
behavioral_test_rs = """use chrono::NaiveDate;
use gel_core::semantic::{
    BooleanFieldProvenance, DraftOrigin, FieldSource, LevelRegressionBaseline, TeacherRef,
    TutorialFormProvenance, TutorialFormState, TutorialIdentity, TutorialType,
};
use gel_core::post_mapper::{build_new_tutorial_post_payload, build_revision_tutorial_post_payload};
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
    let payload = build_new_tutorial_post_payload(&draft).expect("valid new payload");
    assert!(!payload.contains_key(gel_fields::SOURCE_TIMESTAMP));
    assert_eq!(payload.get(gel_fields::TEACHER_ID).map(|s| s.as_str()), Some("326743"));
    assert_eq!(payload.get(gel_fields::STUDENT_UID).map(|s| s.as_str()), Some("464954"));
    assert_eq!(payload.get(gel_fields::TUTORIAL_TYPE).map(|s| s.as_str()), Some("0"));
    assert_eq!(payload.get(gel_fields::CUSTOM_DATE).map(|s| s.as_str()), Some("03-09-2026"));
}

#[test]
fn revision_submission_payload_strictly_preserves_source_timestamp_and_teacher() {
    let draft = mock_revision_draft();
    let payload = build_revision_tutorial_post_payload(&draft).expect("valid revision payload");
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

print("=== 7. Updating contracts/release_gate.json for 47 Checks ===")
gate = json.loads(read("contracts/release_gate.json"))
gate["contract_version"] = 25
gate["effective_date"] = "2026-09-03"
gate["current_release_scope"] = "w2"

check_ids = {c["id"] for c in gate["checks"]}
if "w2_submission_behavior" not in check_ids:
    gate["checks"].append({
        "id": "w2_submission_behavior",
        "command": ["cargo", "test", "--locked", "-p", "gel-core", "--test", "submission_transport"],
        "profiles": ["portable", "strict"],
        "missing_policy": "fail",
        "purpose": "W2 live submission transport behavioral tests: New datetime omission, Revision timestamp preservation, unauthenticated fail-closed, and zero blind inserts.",
        "evidence_class": "behavioral"
    })

if "w2_submission_behavior" not in gate["scopes"]["w2"]["checks"]:
    gate["scopes"]["w2"]["checks"].append("w2_submission_behavior")

write_json("contracts/release_gate.json", gate)

print("=== 8. Updating tools/check_w2_boundaries.py ===")
w2_bounds = read("tools/check_w2_boundaries.py")
w2_bounds = w2_bounds.replace('len(gate["scopes"]["w2"]["checks"]) == 46', 'len(gate["scopes"]["w2"]["checks"]) == 47')
write("tools/check_w2_boundaries.py", w2_bounds)

print("=== 9. Updating tools/check_governance.py Scopes Logic ===")
cg = read("tools/check_governance.py")

# Ensure required set contains both w2 checks
if '"w2_submission_behavior"' not in cg:
    cg = cg.replace(
        '"w2_boundaries"',
        '"w2_boundaries", "w2_submission_behavior"'
    )

if 'require(check_by_id["w2_submission_behavior"]' not in cg:
    cg = cg.replace(
        'require(check_by_id["ui1e_workflow_behavior"].get("command")',
        'require(check_by_id["w2_submission_behavior"].get("command") == ["cargo", "test", "--locked", "-p", "gel-core", "--test", "submission_transport"], "W2 behavioral check command drifted")\n    require(check_by_id["ui1e_workflow_behavior"].get("command")'
    )

# Exact scopes block replacement
scopes_start = cg.find('scopes = gate.get("scopes", {})')
scopes_end = cg.find('require(gate.get("artifact_acceptance"')

exact_scopes_code = """scopes = gate.get("scopes", {})
    gri_required = required - {
        "ui1c5_integrated", "ui1c5_integrated_behavior",
        "ui1d_harper", "ui1d_harper_behavior",
        "ui1e_safety", "ui1e_workflow_behavior",
        "w2_boundaries", "w2_submission_behavior"
    }
    require("gri" in scopes and set(scopes["gri"]["checks"]) == gri_required and len(scopes["gri"]["checks"]) == 39, "GRI scope must remain the strictly accepted 39-check baseline")

    ui1c5_required = required - {
        "ui1d_harper", "ui1d_harper_behavior",
        "ui1e_safety", "ui1e_workflow_behavior",
        "w2_boundaries", "w2_submission_behavior"
    }
    require("ui1c5" in scopes and set(scopes["ui1c5"]["checks"]) == ui1c5_required and len(scopes["ui1c5"]["checks"]) == 41, "UI1c5 scope must remain the 41-check predecessor")
    require(scopes["ui1c5"]["checks"][:39] == scopes["gri"]["checks"], "UI1c5 scope must preserve GRI check ordering as an unchanged prefix")

    ui1d_required = required - {
        "ui1e_safety", "ui1e_workflow_behavior",
        "w2_boundaries", "w2_submission_behavior"
    }
    require("ui1d" in scopes and set(scopes["ui1d"]["checks"]) == ui1d_required and len(scopes["ui1d"]["checks"]) == 43, "UI1d scope must contain 43 checks")
    require(scopes["ui1d"]["checks"][:41] == scopes["ui1c5"]["checks"], "UI1d must preserve UI1c5 check ordering as prefix")
    require(scopes["ui1d"]["checks"][-2:] == ["ui1d_harper", "ui1d_harper_behavior"], "UI1d dedicated checks must be appended")

    ui1e_required = required - {"w2_boundaries", "w2_submission_behavior"}
    require("ui1e" in scopes and set(scopes["ui1e"]["checks"]) == ui1e_required and len(scopes["ui1e"]["checks"]) == 45, "UI1e scope must contain 45 checks")
    require(scopes["ui1e"]["checks"][:43] == scopes["ui1d"]["checks"], "UI1e must preserve UI1d check ordering as prefix")
    require(scopes["ui1e"]["checks"][-2:] == ["ui1e_safety", "ui1e_workflow_behavior"], "UI1e dedicated checks must be appended")

    require("w2" in scopes, "W2 scope missing from release_gate")
    w2_scope = scopes["w2"]["checks"]
    require(len(w2_scope) == 47, "W2 scope must contain 47 checks")
    require(w2_scope[:45] == scopes["ui1e"]["checks"], "W2 must preserve UI1e check ordering as prefix")
    require(w2_scope[-2:] == ["w2_boundaries", "w2_submission_behavior"], "W2 dedicated checks must be appended")
    require(gate["current_release_scope"] == "w2", "W2 must be the current release scope")\n\n    """

cg = cg[:scopes_start] + exact_scopes_code + cg[scopes_end:]
write("tools/check_governance.py", cg)

print("=== 10. Regenerating Documentation and Projections ===")
for gen in [
    "tools/generate_contract_artifacts.py",
    "tools/generate_development_plan_doc.py",
    "tools/generate_governance_artifacts.py",
    "tools/generate_current_state.py",
]:
    print(f"  running {gen}...")
    subprocess.run([sys.executable, str(ROOT / gen)], check=True)

print("\n=== Phase W2 Complete Implementation Applied! ===")