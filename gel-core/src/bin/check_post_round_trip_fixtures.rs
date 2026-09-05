use anyhow::{bail, Context, Result};
use gel_core::fixture_support::archived_tutorial_from_expected_json;
use gel_core::gel_fields;
use gel_core::models::ValidatedEditFormState;
use gel_core::semantic::{ArchivedTutorial, TutorialType};
use gel_core::{
    build_revision_form_state, build_tutorial_post_payload, parse_edit_form, validate_edit_form,
};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

fn main() -> Result<()> {
    let mut args = env::args().skip(1);
    let expected_dir = args
        .next()
        .map(PathBuf::from)
        .context("usage: check_post_round_trip_fixtures <expected-dir> <raw-dir>")?;
    let raw_dir = args
        .next()
        .map(PathBuf::from)
        .context("usage: check_post_round_trip_fixtures <expected-dir> <raw-dir>")?;
    if args.next().is_some() {
        bail!("usage: check_post_round_trip_fixtures <expected-dir> <raw-dir>");
    }
    if !expected_dir.is_dir() {
        bail!(
            "expected fixture directory does not exist: {}",
            expected_dir.display()
        );
    }
    if !raw_dir.is_dir() {
        bail!(
            "raw fixture directory does not exist: {}",
            raw_dir.display()
        );
    }

    let mut expected_files: Vec<PathBuf> = fs::read_dir(&expected_dir)?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.extension().and_then(|x| x.to_str()) == Some("json"))
        .collect();
    expected_files.sort();

    let mut final_count = 0usize;
    let mut absent_discrepancy_count = 0usize;
    for expected_path in &expected_files {
        let result = check_fixture(expected_path, &raw_dir)?;
        if result.is_final {
            final_count += 1;
        }
        if result.absent_source_discrepancy {
            absent_discrepancy_count += 1;
        }
    }

    println!(
        concat!(
            "offline POST round-trip fixtures PASS — {} fixture(s) / {} Final / ",
            "{} governed absent source discrepancies"
        ),
        expected_files.len(),
        final_count,
        absent_discrepancy_count
    );
    Ok(())
}

struct FixtureResult {
    is_final: bool,
    absent_source_discrepancy: bool,
}

fn check_fixture(expected_path: &Path, raw_dir: &Path) -> Result<FixtureResult> {
    let stem = expected_path
        .file_stem()
        .and_then(|x| x.to_str())
        .context("expected fixture has no UTF-8 stem")?;
    let raw_path = raw_dir.join(format!("{stem}.html"));
    if !raw_path.is_file() {
        bail!("missing raw fixture for {stem}: {}", raw_path.display());
    }

    let expected_text = fs::read_to_string(expected_path)
        .with_context(|| format!("read {}", expected_path.display()))?;
    let html =
        fs::read_to_string(&raw_path).with_context(|| format!("read {}", raw_path.display()))?;

    let archive = archived_tutorial_from_expected_json(&expected_text)
        .with_context(|| format!("adapt archive fixture {stem}"))?;
    let raw = parse_edit_form(&html).with_context(|| format!("parse edit fixture {stem}"))?;
    let validated =
        validate_edit_form(&raw).with_context(|| format!("validate edit fixture {stem}"))?;
    let state = build_revision_form_state(&archive, &validated)
        .with_context(|| format!("construct semantic revision fixture {stem}"))?;
    let actual = build_tutorial_post_payload(&state)
        .with_context(|| format!("build offline POST payload for fixture {stem}"))?;
    let expected = expected_payload(&archive, &validated)
        .with_context(|| format!("build independent expected payload for fixture {stem}"))?;

    if actual != expected {
        bail!(
            "fixture {stem} POST payload differs from independent expectation: {}",
            payload_diff(&expected, &actual)
        );
    }

    let is_final = archive.identity.tutorial_type == TutorialType::Final;
    if is_final && !actual.contains_key(gel_fields::READING) {
        bail!("fixture {stem} Final POST payload is missing Reading");
    }

    let edit_absent = validated
        .checkbox_checked(gel_fields::ABSENT)
        .context("validated historical edit form is missing absent checkbox state")?;
    Ok(FixtureResult {
        is_final,
        absent_source_discrepancy: edit_absent != archive.absent,
    })
}

fn expected_payload(
    archive: &ArchivedTutorial,
    edit: &ValidatedEditFormState,
) -> Result<BTreeMap<String, String>> {
    let mut payload = BTreeMap::new();

    let teacher_id = edit
        .teacher()
        .teacher_id
        .context("validated historical edit form has no teacher ID")?;
    put(&mut payload, gel_fields::TEACHER_ID, teacher_id.to_string());

    let edit_uid = required_raw(edit, gel_fields::STUDENT_UID)?
        .parse::<i64>()
        .context("validated edit UID is not an integer")?;
    if edit_uid != archive.identity.student_uid {
        bail!(
            "edit UID {} != archive UID {}",
            edit_uid,
            archive.identity.student_uid
        );
    }
    put(
        &mut payload,
        gel_fields::STUDENT_UID,
        archive.identity.student_uid.to_string(),
    );

    let edit_timestamp = required_raw(edit, gel_fields::SOURCE_TIMESTAMP)?
        .parse::<i64>()
        .context("validated edit source timestamp is not an integer")?;
    if edit_timestamp != archive.identity.tutorial_ts {
        bail!(
            "edit source timestamp {} != archive tutorial timestamp {}",
            edit_timestamp,
            archive.identity.tutorial_ts
        );
    }
    put(
        &mut payload,
        gel_fields::SOURCE_TIMESTAMP,
        archive.identity.tutorial_ts.to_string(),
    );

    let ttype = required_raw(edit, gel_fields::TUTORIAL_TYPE)?;
    if ttype != archive.identity.tutorial_type.ttype() {
        bail!(
            "edit tutorial type {:?} != archive tutorial type {:?}",
            ttype,
            archive.identity.tutorial_type.ttype()
        );
    }
    put(&mut payload, gel_fields::TUTORIAL_TYPE, ttype);
    put(&mut payload, gel_fields::LANGUAGE, "en");

    if archive.absent {
        put(&mut payload, gel_fields::ABSENT, "on");
    }

    put(
        &mut payload,
        gel_fields::CUSTOM_DATE,
        required_raw(edit, gel_fields::CUSTOM_DATE)?,
    );
    put(
        &mut payload,
        gel_fields::OVERALL_LEVEL,
        required_raw(edit, gel_fields::OVERALL_LEVEL)?,
    );
    put(
        &mut payload,
        gel_fields::TEACHER_COMMENTS,
        required_raw(edit, gel_fields::TEACHER_COMMENTS)?,
    );

    match archive.identity.tutorial_type {
        TutorialType::Initial => expected_initial(&mut payload, edit)?,
        TutorialType::Standard => expected_standard(&mut payload, edit)?,
        TutorialType::Final => expected_final(&mut payload, edit)?,
    }

    Ok(payload)
}

fn expected_initial(
    payload: &mut BTreeMap<String, String>,
    edit: &ValidatedEditFormState,
) -> Result<()> {
    for field in [
        gel_fields::INITIAL_SPEAKING,
        gel_fields::INITIAL_USE_OF_ENGLISH,
        gel_fields::INITIAL_WRITING,
        gel_fields::INITIAL_LISTENING,
        gel_fields::EXAM_INTENT,
        gel_fields::EXAM_TYPE,
        gel_fields::EXAM_WHEN,
    ] {
        put(payload, field, required_raw(edit, field)?);
    }
    Ok(())
}

fn expected_standard(
    payload: &mut BTreeMap<String, String>,
    edit: &ValidatedEditFormState,
) -> Result<()> {
    for field in [
        gel_fields::SPEAKING,
        gel_fields::USE_OF_ENGLISH,
        gel_fields::WRITING,
        gel_fields::LISTENING,
        gel_fields::READING,
    ] {
        put(payload, field, required_raw(edit, field)?);
    }

    for field in [
        gel_fields::ASSESSMENT_LISTENING,
        gel_fields::ASSESSMENT_READING,
        gel_fields::ASSESSMENT_WRITING,
        gel_fields::ASSESSMENT_SPEAKING,
        gel_fields::ASSESSMENT_VOCABULARY,
        gel_fields::ASSESSMENT_GRAMMAR,
        gel_fields::ASSESSMENT_PRONUNCIATION,
    ] {
        if let Some(value) = edit.value_for_name(field) {
            put(payload, field, value);
        }
    }

    let aims = edit
        .contenteditable_value_for_id(gel_fields::AIMS_EDITOR_ID)
        .context("validated Standard edit form is missing Aims editor")?;
    put(payload, gel_fields::AIMS, encode_aims(&aims));
    Ok(())
}

fn expected_final(
    payload: &mut BTreeMap<String, String>,
    edit: &ValidatedEditFormState,
) -> Result<()> {
    for field in [
        gel_fields::INITIAL_SPEAKING,
        gel_fields::INITIAL_USE_OF_ENGLISH,
        gel_fields::INITIAL_WRITING,
        gel_fields::INITIAL_LISTENING,
        gel_fields::SPEAKING,
        gel_fields::USE_OF_ENGLISH,
        gel_fields::WRITING,
        gel_fields::LISTENING,
        gel_fields::READING,
        gel_fields::ADDITIONAL_COMMENTS,
    ] {
        put(payload, field, required_raw(edit, field)?);
    }
    Ok(())
}

fn required_raw<'a>(edit: &'a ValidatedEditFormState, field: &str) -> Result<&'a str> {
    edit.raw_value_for_name(field)
        .with_context(|| format!("validated edit form has no raw value for {field}"))
}

fn put(payload: &mut BTreeMap<String, String>, key: &str, value: impl Into<String>) {
    payload.insert(key.to_string(), value.into());
}

fn encode_aims(value: &str) -> String {
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

fn payload_diff(expected: &BTreeMap<String, String>, actual: &BTreeMap<String, String>) -> String {
    let keys: BTreeSet<&str> = expected
        .keys()
        .map(String::as_str)
        .chain(actual.keys().map(String::as_str))
        .collect();
    keys.into_iter()
        .filter_map(|key| {
            let left = expected.get(key);
            let right = actual.get(key);
            (left != right).then(|| format!("{key}: expected={left:?} actual={right:?}"))
        })
        .collect::<Vec<_>>()
        .join("; ")
}
