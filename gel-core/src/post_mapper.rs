//! Offline GEL POST serialization.
//!
//! This module has no HTTP client and cannot submit anything. It translates a
//! semantic `TutorialFormState` into the tutorial-content fields expected by
//! `/study/tutorials/process` so that round-trip tests can be completed before
//! any network write path is enabled.

use crate::gel_fields;
use crate::semantic::{
    validate_semantic_form_state, AssessmentValue, CefrLevel, DraftOrigin, TutorialFormState,
    TutorialType,
};
use anyhow::{bail, Context, Result};
use std::collections::BTreeMap;

pub type TutorialPostPayload = BTreeMap<String, String>;

/// Type-safe offline New submission view. There is deliberately no datetime
/// member: New tutorial identity is assigned by GEL and learned only by a
/// future fresh readback.
pub struct NewTutorialSubmission<'a> {
    state: &'a TutorialFormState,
}

impl<'a> NewTutorialSubmission<'a> {
    pub fn try_from_state(state: &'a TutorialFormState) -> Result<Self> {
        validate_submission_state(state)?;
        if !matches!(&state.origin, DraftOrigin::New { .. }) {
            bail!("NewTutorialSubmission requires DraftOrigin::New");
        }
        Ok(Self { state })
    }
}

/// Type-safe offline Revision submission view. Revision datetime is not an
/// optional caller-supplied value: it comes only from the bound source identity.
pub struct RevisionTutorialSubmission<'a> {
    state: &'a TutorialFormState,
}

impl<'a> RevisionTutorialSubmission<'a> {
    pub fn try_from_state(state: &'a TutorialFormState) -> Result<Self> {
        validate_submission_state(state)?;
        if !matches!(&state.origin, DraftOrigin::Revision { .. }) {
            bail!("RevisionTutorialSubmission requires DraftOrigin::Revision");
        }
        Ok(Self { state })
    }
}

pub fn build_new_tutorial_post_payload(
    submission: NewTutorialSubmission<'_>,
) -> Result<TutorialPostPayload> {
    let mut payload = serialize_common(submission.state)?;
    serialize_type_specific(&mut payload, submission.state);
    Ok(payload)
}

pub fn build_revision_tutorial_post_payload(
    submission: RevisionTutorialSubmission<'_>,
) -> Result<TutorialPostPayload> {
    let mut payload = serialize_common(submission.state)?;
    let source_timestamp = match &submission.state.origin {
        DraftOrigin::Revision { source, .. } => source.tutorial_ts,
        DraftOrigin::New { .. } => unreachable!("constructor proved Revision origin"),
    };
    put(
        &mut payload,
        gel_fields::SOURCE_TIMESTAMP,
        source_timestamp.to_string(),
    );
    serialize_type_specific(&mut payload, submission.state);
    Ok(payload)
}

/// Compatibility entry point for callers that already hold semantic state.
/// Dispatch is origin-specific so New can never acquire a datetime through a
/// shared Option/default path.
pub fn build_tutorial_post_payload(state: &TutorialFormState) -> Result<TutorialPostPayload> {
    match &state.origin {
        DraftOrigin::New { .. } => {
            build_new_tutorial_post_payload(NewTutorialSubmission::try_from_state(state)?)
        }
        DraftOrigin::Revision { .. } => {
            build_revision_tutorial_post_payload(RevisionTutorialSubmission::try_from_state(state)?)
        }
    }
}

fn validate_submission_state(state: &TutorialFormState) -> Result<()> {
    validate_semantic_form_state(state)?;
    validate_lengths(state)?;
    Ok(())
}

fn serialize_common(state: &TutorialFormState) -> Result<TutorialPostPayload> {
    let teacher_id = state
        .teacher
        .teacher_id
        .context("tutorial form state has no teacher_id")?;

    let mut payload = BTreeMap::new();
    put(&mut payload, gel_fields::TEACHER_ID, teacher_id.to_string());
    put(
        &mut payload,
        gel_fields::STUDENT_UID,
        state.student_uid.to_string(),
    );
    put(
        &mut payload,
        gel_fields::TUTORIAL_TYPE,
        state.tutorial_type.ttype(),
    );
    put(&mut payload, gel_fields::LANGUAGE, "en");

    // Browser checkbox semantics: checked => `absent=on`; unchecked => the
    // successful-control set contains no `absent` key at all.
    if state.absent {
        put(&mut payload, gel_fields::ABSENT, "on");
    }

    put(
        &mut payload,
        gel_fields::CUSTOM_DATE,
        state.tutorial_date.format("%d-%m-%Y").to_string(),
    );
    put(
        &mut payload,
        gel_fields::OVERALL_LEVEL,
        overall_post_value(state),
    );
    put(
        &mut payload,
        gel_fields::TEACHER_COMMENTS,
        state.teacher_comments.clone(),
    );
    Ok(payload)
}

fn serialize_type_specific(payload: &mut TutorialPostPayload, state: &TutorialFormState) {
    match state.tutorial_type {
        TutorialType::Initial => serialize_initial(payload, state),
        TutorialType::Standard => serialize_standard(payload, state),
        TutorialType::Final => serialize_final(payload, state),
    }
}

fn serialize_initial(payload: &mut TutorialPostPayload, state: &TutorialFormState) {
    put_level(
        payload,
        gel_fields::INITIAL_SPEAKING,
        state.initial_scores.speaking,
    );
    put_level(
        payload,
        gel_fields::INITIAL_USE_OF_ENGLISH,
        state.initial_scores.use_of_english,
    );
    put_level(
        payload,
        gel_fields::INITIAL_WRITING,
        state.initial_scores.writing,
    );
    put_level(
        payload,
        gel_fields::INITIAL_LISTENING,
        state.initial_scores.listening,
    );
    put(
        payload,
        gel_fields::EXAM_INTENT,
        state
            .exam
            .intent
            .clone()
            .unwrap_or_else(|| gel_fields::EXAM_PLACEHOLDER.to_string()),
    );
    put(
        payload,
        gel_fields::EXAM_TYPE,
        state
            .exam
            .exam_type
            .clone()
            .unwrap_or_else(|| gel_fields::EXAM_PLACEHOLDER.to_string()),
    );
    put(
        payload,
        gel_fields::EXAM_WHEN,
        state
            .exam
            .when
            .clone()
            .unwrap_or_else(|| gel_fields::EXAM_PLACEHOLDER.to_string()),
    );
}

fn serialize_standard(payload: &mut TutorialPostPayload, state: &TutorialFormState) {
    put_level(payload, gel_fields::SPEAKING, state.current_scores.speaking);
    put_level(
        payload,
        gel_fields::USE_OF_ENGLISH,
        state.current_scores.use_of_english,
    );
    put_level(payload, gel_fields::WRITING, state.current_scores.writing);
    put_level(
        payload,
        gel_fields::LISTENING,
        state.current_scores.listening,
    );
    put_level(payload, gel_fields::READING, state.reading);

    put_assessment(
        payload,
        gel_fields::ASSESSMENT_LISTENING,
        state.self_assessment.listening,
    );
    put_assessment(
        payload,
        gel_fields::ASSESSMENT_READING,
        state.self_assessment.reading,
    );
    put_assessment(
        payload,
        gel_fields::ASSESSMENT_WRITING,
        state.self_assessment.writing,
    );
    put_assessment(
        payload,
        gel_fields::ASSESSMENT_SPEAKING,
        state.self_assessment.speaking,
    );
    put_assessment(
        payload,
        gel_fields::ASSESSMENT_VOCABULARY,
        state.self_assessment.vocabulary,
    );
    put_assessment(
        payload,
        gel_fields::ASSESSMENT_GRAMMAR,
        state.self_assessment.grammar,
    );
    put_assessment(
        payload,
        gel_fields::ASSESSMENT_PRONUNCIATION,
        state.self_assessment.pronunciation,
    );

    // GEL displays historical aims in #tcinput but ultimately receives the
    // value under the GEL Aims field. The semantic text is the editable value; always
    // serialize that current value so a UI edit cannot be masked by stale
    // source HTML retained only for provenance/fidelity inspection.
    put(
        payload,
        gel_fields::AIMS,
        plain_text_to_br_html(&state.aims),
    );
}

fn serialize_final(payload: &mut TutorialPostPayload, state: &TutorialFormState) {
    put_level(
        payload,
        gel_fields::INITIAL_SPEAKING,
        state.initial_scores.speaking,
    );
    put_level(
        payload,
        gel_fields::INITIAL_USE_OF_ENGLISH,
        state.initial_scores.use_of_english,
    );
    put_level(
        payload,
        gel_fields::INITIAL_WRITING,
        state.initial_scores.writing,
    );
    put_level(
        payload,
        gel_fields::INITIAL_LISTENING,
        state.initial_scores.listening,
    );
    put_level(payload, gel_fields::SPEAKING, state.current_scores.speaking);
    put_level(
        payload,
        gel_fields::USE_OF_ENGLISH,
        state.current_scores.use_of_english,
    );
    put_level(payload, gel_fields::WRITING, state.current_scores.writing);
    put_level(
        payload,
        gel_fields::LISTENING,
        state.current_scores.listening,
    );

    // Proven by the captured Final edit forms: the Reading field is a normal,
    // enabled select inside the submitted form. Final Reading must be sent.
    put_level(payload, gel_fields::READING, state.reading);
    put(
        payload,
        gel_fields::ADDITIONAL_COMMENTS,
        state.additional_comments.clone(),
    );
}

fn overall_post_value(state: &TutorialFormState) -> String {
    state
        .overall_level
        .map(|level| level.overall_form_value().to_string())
        .unwrap_or_else(|| gel_fields::OVERALL_PLACEHOLDER.to_string())
}

fn put_level(payload: &mut TutorialPostPayload, field: &str, value: Option<CefrLevel>) {
    put(
        payload,
        field,
        value
            .map(|level| level.form_value().to_string())
            .unwrap_or_else(|| gel_fields::SKILL_PLACEHOLDER.to_string()),
    );
}

fn put_assessment(payload: &mut TutorialPostPayload, field: &str, value: Option<AssessmentValue>) {
    if let Some(value) = value {
        put(payload, field, value.form_value());
    }
}

fn put(payload: &mut TutorialPostPayload, key: &str, value: impl Into<String>) {
    payload.insert(key.to_string(), value.into());
}

fn plain_text_to_br_html(value: &str) -> String {
    let normalized = value.replace("\r\n", "\n").replace('\r', "\n");
    let mut escaped = String::with_capacity(normalized.len());
    for ch in normalized.chars() {
        match ch {
            '&' => escaped.push_str("&amp;"),
            '<' => escaped.push_str("&lt;"),
            '>' => escaped.push_str("&gt;"),
            '"' => escaped.push_str("&quot;"),
            '\'' => escaped.push_str("&#39;"),
            '\n' => escaped.push_str("<br>"),
            _ => escaped.push(ch),
        }
    }
    escaped
}

fn validate_lengths(state: &TutorialFormState) -> Result<()> {
    if state.teacher_comments.chars().count() > gel_fields::TEACHER_COMMENTS_MAX_CHARS {
        bail!(
            "teacher comments exceed GEL limit of {} characters",
            gel_fields::TEACHER_COMMENTS_MAX_CHARS
        );
    }
    if state.additional_comments.chars().count() > gel_fields::ADDITIONAL_COMMENTS_MAX_CHARS {
        bail!(
            "additional comments exceed GEL limit of {} characters",
            gel_fields::ADDITIONAL_COMMENTS_MAX_CHARS
        );
    }
    Ok(())
}
