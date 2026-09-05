use anyhow::{Context, Result};
use gel_core::parse_print_page;
use serde_json::Value;
use std::fs;
use std::path::{Path, PathBuf};

fn fixture_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("fixtures/print_parity")
}

#[test]
fn python_v49_print_fallback_fixture_parity_is_exact() -> Result<()> {
    let root = fixture_root();
    let mut expected_files = fs::read_dir(root.join("expected"))?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.extension().and_then(|value| value.to_str()) == Some("json"))
        .collect::<Vec<_>>();
    expected_files.sort();
    assert_eq!(
        expected_files.len(),
        14,
        "A1 requires fourteen parity fixtures"
    );

    for expected_path in expected_files {
        let stem = expected_path
            .file_stem()
            .and_then(|value| value.to_str())
            .context("fixture name must be UTF-8")?;
        let raw_path = root.join("raw").join(format!("{stem}.html"));
        let html = fs::read_to_string(&raw_path)
            .with_context(|| format!("read {}", raw_path.display()))?;
        let expected: Value = serde_json::from_str(&fs::read_to_string(&expected_path)?)?;
        let actual = serde_json::to_value(parse_print_page(&html)?)?;
        assert_eq!(actual, expected, "A1 print parity mismatch in {stem}");
    }
    Ok(())
}

#[test]
fn print_labels_inside_prose_do_not_create_fields() -> Result<()> {
    let html = fs::read_to_string(fixture_root().join("raw/04_prose_labels.html"))?;
    let parsed = parse_print_page(&html)?;
    assert_eq!(
        parsed.fields.get("Listening").map(String::as_str),
        Some("B1+")
    );
    assert_eq!(
        parsed.fields.get("Speaking").map(String::as_str),
        Some("A2-")
    );
    assert_eq!(parsed.fields.len(), 4);
    assert!(parsed
        .fields
        .get("Teacher's Comments")
        .is_some_and(|value| value.contains("Reading is improving")));
    Ok(())
}
