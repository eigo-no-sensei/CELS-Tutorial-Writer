use gel_core::{check_harper_text, HarperDictionaryRepository, HARPER_DICTIONARY_FILE_NAME};
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

fn temp_dir() -> PathBuf {
    let suffix = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock before unix epoch")
        .as_nanos();
    std::env::temp_dir().join(format!("gel-ui1d-harper-test-{suffix}"))
}

fn repo() -> (PathBuf, HarperDictionaryRepository) {
    let dir = temp_dir();
    let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
    (dir, repo)
}

#[test]
fn british_engine_returns_complete_field_replacement_for_color() {
    let (dir, repo) = repo();
    let result = check_harper_text(&repo, "aims", "We use color here.", &[], &[]).unwrap();
    assert_eq!(result.field, "aims");
    assert_eq!(result.source_text, "We use color here.");
    assert_eq!(result.engine_version, "2.8.0");
    assert!(result
        .findings
        .iter()
        .flat_map(|finding| finding.suggestions.iter())
        .any(|suggestion| suggestion.replacement_text == "We use colour here."));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn findings_carry_span_coordinates_for_inline_highlight() {
    let (dir, repo) = repo();
    let result = check_harper_text(&repo, "aims", "We use color here.", &[], &[]).unwrap();
    let finding = result
        .findings
        .iter()
        .find(|finding| finding.original_text.eq_ignore_ascii_case("color"))
        .expect("color finding should be reported");
    assert_eq!(finding.span_start, 7);
    assert_eq!(finding.span_end, 12);
    let reconstructed: String = result
        .source_text
        .chars()
        .skip(finding.span_start)
        .take(finding.span_end - finding.span_start)
        .collect();
    assert_eq!(reconstructed, "color");
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn suggestions_carry_human_readable_labels() {
    let (dir, repo) = repo();
    let result = check_harper_text(&repo, "aims", "We use color here.", &[], &[]).unwrap();
    let finding = result
        .findings
        .iter()
        .find(|finding| finding.original_text.eq_ignore_ascii_case("color"))
        .expect("color finding should be reported");
    assert!(finding
        .suggestions
        .iter()
        .all(|suggestion| !suggestion.label.is_empty()));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn findings_carry_stable_rule_names_for_disable_action() {
    let (dir, repo) = repo();
    let result = check_harper_text(&repo, "aims", "We use color here.", &[], &[]).unwrap();
    assert!(result
        .findings
        .iter()
        .all(|finding| !finding.rule.is_empty()));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn user_dictionary_word_is_used_by_document_and_linter() {
    let (dir, repo) = repo();
    repo.add("gelwriterqz").unwrap();
    let result = check_harper_text(
        &repo,
        "teacher_comments",
        "gelwriterqz is a local term.",
        &[],
        &[],
    )
    .unwrap();
    assert!(!result
        .findings
        .iter()
        .any(|finding| finding.original_text.eq_ignore_ascii_case("gelwriterqz")));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn user_dictionary_covers_subspan_for_mixed_alphanumeric_term() {
    let (dir, repo) = repo();
    repo.add("CHI365").unwrap();
    let result = check_harper_text(
        &repo,
        "teacher_comments",
        "Student I also has access to Chi365 for a further three months.",
        &[],
        &[],
    )
    .unwrap();
    assert!(!result
        .findings
        .iter()
        .any(|finding| finding.original_text.eq_ignore_ascii_case("Chi")));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn dictionary_mutations_are_case_insensitive_and_persistent() {
    let (dir, repo) = repo();
    assert!(repo.add("Zebra").unwrap().changed);
    assert!(!repo.add(" zebra ").unwrap().changed);
    assert_eq!(repo.list().unwrap(), vec!["Zebra"]);
    assert!(repo.remove("zEbRa").unwrap().changed);
    assert!(repo.list().unwrap().is_empty());
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn legacy_dictionary_is_migrated_to_schema_v1() {
    let (dir, repo) = repo();
    let path = dir.join(HARPER_DICTIONARY_FILE_NAME);
    fs::create_dir_all(&dir).unwrap();
    fs::write(&path, b"[\"Beta\",\"alpha\",\"beta\"]").unwrap();
    assert_eq!(repo.list().unwrap(), vec!["alpha", "Beta"]);
    let migrated = fs::read_to_string(&path).unwrap();
    assert!(migrated.contains("\"schema_version\": 1"));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn future_dictionary_schema_fails_closed_and_does_not_downgrade() {
    let (dir, repo) = repo();
    let path = dir.join(HARPER_DICTIONARY_FILE_NAME);
    fs::create_dir_all(&dir).unwrap();
    let bytes = br#"{"schema_version":999,"words":["future"]}"#;
    fs::write(&path, bytes).unwrap();
    assert!(repo.list().is_err());
    assert_eq!(fs::read(&path).unwrap(), bytes);
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn unsupported_field_fails_closed() {
    let (dir, repo) = repo();
    let result = check_harper_text(&repo, "overall_level", "B2", &[], &[]);
    match result {
        Ok(_) => panic!("unsupported field unexpectedly accepted"),
        Err(error) => assert!(error.to_string().contains("not permitted")),
    }
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn empty_text_short_circuits_to_no_findings() {
    let (dir, repo) = repo();
    let result = check_harper_text(&repo, "aims", "   ", &[], &[]).unwrap();
    assert!(result.findings.is_empty());
    assert_eq!(result.source_text, "   ");
    assert_eq!(result.engine_version, "2.8.0");
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn disabled_rules_are_suppressed_for_session() {
    let (dir, repo) = repo();
    let enabled = check_harper_text(&repo, "aims", "CELSX is useful.", &[], &[]).unwrap();
    let spell_rule = enabled
        .findings
        .iter()
        .find(|finding| finding.original_text.eq_ignore_ascii_case("CELSX"))
        .map(|finding| finding.rule.clone())
        .expect("spelling finding should be reported for an unknown term");
    let disabled = check_harper_text(
        &repo,
        "aims",
        "CELSX is useful.",
        std::slice::from_ref(&spell_rule),
        &[],
    )
    .unwrap();
    assert!(!disabled
        .findings
        .iter()
        .any(|finding| finding.rule == spell_rule));
    let _ = fs::remove_dir_all(dir);
}

#[test]
fn suppressed_kinds_are_filtered() {
    let (dir, repo) = repo();
    let text = "This is a sentence that contains a large number of words and continues for quite some time because it is deliberately verbose and is intended to give Harper a chance to produce a readability finding for the test.";
    let unsuppressed = check_harper_text(&repo, "aims", text, &[], &[]).unwrap();
    let suppressed =
        check_harper_text(&repo, "aims", text, &[], &["Readability".to_string()]).unwrap();
    assert!(suppressed
        .findings
        .iter()
        .all(|finding| finding.lint_kind != "Readability"));
    assert!(suppressed.findings.len() <= unsuppressed.findings.len());
    let _ = fs::remove_dir_all(dir);
}
