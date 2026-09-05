use anyhow::{Context, Result};
use gel_core::fixture_support::archived_tutorial_from_expected_json;
use gel_core::{
    build_revision_form_state, build_tutorial_post_payload, parse_edit_form, validate_edit_form,
};
use serde_json::json;
use std::env;
use std::fs;
use std::path::PathBuf;

fn main() -> Result<()> {
    let mut args = env::args().skip(1);
    let expected_path = args
        .next()
        .map(PathBuf::from)
        .context("usage: inspect_revision_fixture <expected.json> <raw-edit.html>")?;
    let raw_path = args
        .next()
        .map(PathBuf::from)
        .context("usage: inspect_revision_fixture <expected.json> <raw-edit.html>")?;

    let expected_text = fs::read_to_string(&expected_path)
        .with_context(|| format!("read {}", expected_path.display()))?;
    let html =
        fs::read_to_string(&raw_path).with_context(|| format!("read {}", raw_path.display()))?;

    let archive = archived_tutorial_from_expected_json(&expected_text)?;
    let raw_edit = parse_edit_form(&html)?;
    let edit = validate_edit_form(&raw_edit)?;
    let semantic = build_revision_form_state(&archive, &edit)?;
    let payload = build_tutorial_post_payload(&semantic)?;

    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "archive": archive,
            "semantic_form": semantic,
            "post_payload": payload,
        }))?
    );
    Ok(())
}
