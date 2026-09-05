use anyhow::{bail, Context, Result};
use gel_core::fixture_support::archived_tutorial_from_expected_json;
use gel_core::{
    build_revision_form_state, parse_edit_form, validate_edit_form, validate_semantic_form_state,
    DraftOrigin,
};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

fn main() -> Result<()> {
    let mut args = env::args().skip(1);
    let expected_dir = args
        .next()
        .map(PathBuf::from)
        .context("usage: check_semantic_fixtures <expected-dir> <raw-dir>")?;
    let raw_dir = args
        .next()
        .map(PathBuf::from)
        .context("usage: check_semantic_fixtures <expected-dir> <raw-dir>")?;

    if args.next().is_some() {
        bail!("usage: check_semantic_fixtures <expected-dir> <raw-dir>");
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

    let checked = expected_files.len();
    for expected_path in expected_files {
        check_fixture(&expected_path, &raw_dir)?;
    }

    println!("semantic revision fixtures PASS — {checked} fixture(s)");
    Ok(())
}

fn check_fixture(expected_path: &Path, raw_dir: &Path) -> Result<()> {
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
    validate_semantic_form_state(&state)
        .with_context(|| format!("validate semantic revision fixture {stem}"))?;

    match &state.origin {
        DraftOrigin::Revision {
            source,
            source_teacher_id,
        } => {
            if source != &archive.identity
                || *source_teacher_id != archive.teacher.teacher_id.unwrap_or_default()
            {
                bail!(
                    "fixture {stem} revision authority {:?}/{} != archive identity {:?}/{}",
                    source,
                    source_teacher_id,
                    archive.identity,
                    archive.teacher.teacher_id.unwrap_or_default()
                );
            }
            Ok(())
        }
        DraftOrigin::New { .. } => bail!("fixture {stem} unexpectedly constructed New origin"),
    }
}
