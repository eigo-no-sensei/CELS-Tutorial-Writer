use anyhow::{bail, Context, Result};
use gel_core::fixture_compare::{compare_edit_fixture_dirs, ComparisonStatus, FieldComparison};
use std::env;
use std::fs;
use std::path::PathBuf;

#[derive(Debug)]
struct Args {
    expected_dir: PathBuf,
    raw_dir: PathBuf,
    show_all: bool,
    json_path: Option<PathBuf>,
    fail_on_mismatch: bool,
}

fn usage() -> &'static str {
    "usage: compare_edit_fixtures <expected-dir> <raw-dir> [--all] [--json <path>] [--fail-on-mismatch]"
}

fn parse_args() -> Result<Args> {
    let mut iter = env::args().skip(1);
    let expected_dir = PathBuf::from(iter.next().context(usage())?);
    let raw_dir = PathBuf::from(iter.next().context(usage())?);
    let mut show_all = false;
    let mut json_path = None;
    let mut fail_on_mismatch = false;

    while let Some(arg) = iter.next() {
        match arg.as_str() {
            "--all" => show_all = true,
            "--json" => {
                json_path = Some(PathBuf::from(
                    iter.next().context("--json requires a path")?,
                ));
            }
            "--fail-on-mismatch" => fail_on_mismatch = true,
            "-h" | "--help" => bail!(usage()),
            other => bail!("unknown argument {other:?}\n{}", usage()),
        }
    }

    Ok(Args {
        expected_dir,
        raw_dir,
        show_all,
        json_path,
        fail_on_mismatch,
    })
}

fn main() -> Result<()> {
    let args = parse_args()?;
    let report = compare_edit_fixture_dirs(&args.expected_dir, &args.raw_dir)?;

    println!(
        "Compared {} fixtures / {} fields: {} OK, {} mismatch, {} unavailable",
        report.fixture_count,
        report.field_count,
        report.ok_count,
        report.mismatch_count,
        report.unavailable_count
    );

    println!("\nFixture summary");
    println!(
        "{:<32} {:<9} {:>6} {:>6} {:>9} {:>11}",
        "fixture", "type", "fields", "ok", "mismatch", "unavailable"
    );
    println!("{}", "-".repeat(80));
    for fixture in &report.fixtures {
        println!(
            "{:<32} {:<9} {:>6} {:>6} {:>9} {:>11}",
            truncate(&fixture.fixture, 32),
            fixture.tutorial_type,
            fixture.total,
            fixture.ok,
            fixture.mismatch,
            fixture.unavailable
        );
    }

    let selected: Vec<&FieldComparison> = report
        .comparisons
        .iter()
        .filter(|row| args.show_all || row.status != ComparisonStatus::Ok)
        .collect();

    if selected.is_empty() {
        println!("\nNo non-OK field comparisons.");
    } else {
        println!(
            "\n{} field comparisons",
            if args.show_all { "All" } else { "Non-OK" }
        );
        println!(
            "{:<32} {:<23} {:<12} {:<28} {:<28}",
            "fixture", "field", "status", "archive", "edit"
        );
        println!("{}", "-".repeat(130));
        for row in selected {
            println!(
                "{:<32} {:<23} {:<12} {:<28} {:<28}",
                truncate(&row.fixture, 32),
                truncate(&row.field, 23),
                status_label(row.status),
                truncate(&display_value(Some(&row.archive_value)), 28),
                truncate(&display_value(row.edit_value.as_ref()), 28),
            );
        }
    }

    if let Some(path) = args.json_path {
        let json = serde_json::to_string_pretty(&report)?;
        fs::write(&path, json).with_context(|| format!("write {}", path.display()))?;
        println!("\nFull JSON report: {}", path.display());
    }

    if args.fail_on_mismatch && (report.mismatch_count > 0 || report.unavailable_count > 0) {
        std::process::exit(2);
    }

    Ok(())
}

fn status_label(status: ComparisonStatus) -> &'static str {
    match status {
        ComparisonStatus::Ok => "OK",
        ComparisonStatus::Mismatch => "MISMATCH",
        ComparisonStatus::Unavailable => "UNAVAILABLE",
    }
}

fn display_value(value: Option<&String>) -> String {
    match value {
        None => "<missing control>".to_string(),
        Some(value) if value.is_empty() => "<blank>".to_string(),
        Some(value) => value.split_whitespace().collect::<Vec<_>>().join(" "),
    }
}

fn truncate(value: &str, width: usize) -> String {
    let chars: Vec<char> = value.chars().collect();
    if chars.len() <= width {
        return value.to_string();
    }
    if width <= 1 {
        return "…".to_string();
    }
    chars[..width - 1].iter().collect::<String>() + "…"
}
