//! Live GEL tutorial submission transport for Phase W2.
//!
//! Submits validated tutorial POST payloads to `/study/tutorials/process`, discovers
//! newly assigned canonical tutorial identities via post-submit GET readback, and
//! reconciles the server record into local archive v2 via targeted sync.

use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::fmt;
use std::path::Path;
use std::time::Duration;

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
                write!(
                    f,
                    "post-submit readback failed to discover new tutorial identity"
                )
            }
            Self::ArchiveSync(e) => write!(f, "archive sync error: {e}"),
            Self::Session(e) => write!(f, "session error: {e}"),
        }
    }
}

impl std::error::Error for SubmissionError {}

/// Submit an active tutorial draft to GEL, discover the assigned tutorial ID via readback,
/// and reconcile the record into the local SQLite archive using targeted single-student sync.
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
    let payload = build_tutorial_post_payload(draft).map_err(SubmissionError::Mapping)?;

    // 2. Pre-submit readback: capture existing tutorial list IDs
    let pre_tutorials = session
        .get_tutorial_list(student_uid)
        .map_err(SubmissionError::Session)?;
    let pre_ids: HashSet<i64> = pre_tutorials.iter().map(|t| t.id).collect();

    // 3. Dispatch authenticated POST to /study/tutorials/process
    let url = format!("{LEARN2_BASE}{TUTORIAL_PROCESS_PATH}");
    let form_params: Vec<(&str, &str)> = payload
        .iter()
        .map(|(k, v)| (k.as_str(), v.as_str()))
        .collect();

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
            .or_else(|| post_tutorials.iter().max_by_key(|t| t.timestamp))
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

    // 5. Targeted local archive sync reconciliation for this specific student only
    let reconciled = if let Some(path) = archive_path {
        RustArchiver::sync_targeted_student(session, path, student_uid)
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
