use anyhow::{bail, Context, Result};
use gel_core::parse_print_page;
use serde_json::Value;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

fn main() -> Result<()> {
    let mut args = env::args().skip(1);
    let expected_dir = PathBuf::from(
        args.next()
            .context("usage: check_print_fixtures <expected-dir> <raw-dir>")?,
    );
    let raw_dir = PathBuf::from(
        args.next()
            .context("usage: check_print_fixtures <expected-dir> <raw-dir>")?,
    );
    if args.next().is_some() {
        bail!("usage: check_print_fixtures <expected-dir> <raw-dir>");
    }

    let mut expected_files = fs::read_dir(&expected_dir)
        .with_context(|| format!("read {}", expected_dir.display()))?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.extension().and_then(|value| value.to_str()) == Some("json"))
        .collect::<Vec<_>>();
    expected_files.sort();
    if expected_files.is_empty() {
        bail!("no expected print fixtures found");
    }

    for expected_path in &expected_files {
        check_fixture(expected_path, &raw_dir)?;
    }
    println!(
        "A1 print parity PASS — {} exact Python-v4.9-compatible fixture(s)",
        expected_files.len()
    );
    Ok(())
}

fn check_fixture(expected_path: &Path, raw_dir: &Path) -> Result<()> {
    let stem = expected_path
        .file_stem()
        .and_then(|value| value.to_str())
        .context("fixture stem must be UTF-8")?;
    let raw_path = raw_dir.join(format!("{stem}.html"));
    let html =
        fs::read_to_string(&raw_path).with_context(|| format!("read {}", raw_path.display()))?;
    let expected: Value = serde_json::from_str(&fs::read_to_string(expected_path)?)
        .with_context(|| format!("parse {}", expected_path.display()))?;
    let actual = serde_json::to_value(parse_print_page(&html)?)?;
    if actual != expected {
        bail!(
            "print fixture {stem} mismatch\nexpected={}\nactual={}",
            serde_json::to_string_pretty(&expected)?,
            serde_json::to_string_pretty(&actual)?
        );
    }
    Ok(())
}
