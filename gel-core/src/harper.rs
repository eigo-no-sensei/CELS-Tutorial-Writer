//! UI1d Rust-owned Harper checking and persistent local user dictionary.
//!
//! The dictionary is local Writer preference/source state, not tutorial state.
//! React never persists or mutates this file directly; Tauri commands call this
//! repository under the Writer operation lock for mutations.

use anyhow::{anyhow, Context, Result};
use harper_core::linting::{LintGroup, Suggestion};
use harper_core::spell::{FstDictionary, MergedDictionary, MutableDictionary};
use harper_core::{Dialect, DictWordMetadata, Document};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::Arc;

pub const HARPER_VERSION: &str = "2.8.0";
pub const HARPER_DICTIONARY_SCHEMA_VERSION: u32 = 1;
pub const HARPER_DICTIONARY_ENV: &str = "GEL_HARPER_DICTIONARY";
pub const HARPER_DICTIONARY_FILE_NAME: &str = "harper-dictionary.json";

const ALLOWED_FIELDS: &[&str] = &["aims", "teacher_comments", "additional_comments"];

/// Canonical persisted UI1d dictionary state.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct HarperDictionaryFile {
    pub schema_version: u32,
    pub words: Vec<String>,
}

impl HarperDictionaryFile {
    fn new(words: Vec<String>) -> Self {
        Self {
            schema_version: HARPER_DICTIONARY_SCHEMA_VERSION,
            words,
        }
    }
}

/// Canonical local writer owned state class for the user dictionary.
#[derive(Debug, Clone)]
pub struct HarperDictionaryRepository {
    path: PathBuf,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HarperDictionaryEntry {
    pub word: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HarperDictionaryMutation {
    pub changed: bool,
    pub words: Vec<HarperDictionaryEntry>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HarperSuggestionDto {
    pub label: String,
    pub replacement_text: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HarperFindingDto {
    pub lint_kind: String,
    pub rule: String,
    pub message: String,
    pub original_text: String,
    pub span_start: usize,
    pub span_end: usize,
    pub suggestions: Vec<HarperSuggestionDto>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HarperCheckDto {
    pub field: String,
    pub source_text: String,
    pub engine_version: &'static str,
    pub findings: Vec<HarperFindingDto>,
}

impl HarperDictionaryRepository {
    pub fn new(path: PathBuf) -> Self {
        Self { path }
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn list(&self) -> Result<Vec<String>> {
        Ok(self.load_file()?.words)
    }

    pub fn add(&self, word: &str) -> Result<HarperDictionaryMutation> {
        let word = normalize_word(word)?;
        let mut words = self.load_file()?.words;
        let key = word.to_lowercase();
        if words.iter().any(|existing| existing.to_lowercase() == key) {
            return Ok(HarperDictionaryMutation {
                changed: false,
                words: dictionary_entries(words),
            });
        }
        words.push(word);
        words = normalize_words(words)?;
        self.save_words(&words)?;
        Ok(HarperDictionaryMutation {
            changed: true,
            words: dictionary_entries(words),
        })
    }

    pub fn remove(&self, word: &str) -> Result<HarperDictionaryMutation> {
        let word = normalize_word(word)?;
        let key = word.to_lowercase();
        let mut words = self.load_file()?.words;
        let before = words.len();
        words.retain(|existing| existing.to_lowercase() != key);
        let changed = words.len() != before;
        if changed {
            words = normalize_words(words)?;
            self.save_words(&words)?;
        }
        Ok(HarperDictionaryMutation {
            changed,
            words: dictionary_entries(words),
        })
    }

    pub fn dictionary(&self) -> Result<Arc<MergedDictionary>> {
        let words = self.load_file()?.words;
        let mut user_dictionary = MutableDictionary::new();
        for word in words {
            user_dictionary.append_word_str(&word, DictWordMetadata::default());
        }

        let mut merged = MergedDictionary::new();
        merged.add_dictionary(FstDictionary::curated());
        merged.add_dictionary(Arc::new(user_dictionary));
        Ok(Arc::new(merged))
    }

    fn load_file(&self) -> Result<HarperDictionaryFile> {
        if !self.path.exists() {
            let backup = backup_path(&self.path);
            if backup.exists() {
                let file = parse_dictionary_file(&backup)?;
                self.repair_from_backup(&file)?;
                return Ok(file);
            }
            return Ok(HarperDictionaryFile::new(Vec::new()));
        }

        match parse_dictionary_file(&self.path) {
            Ok(file) => {
                if is_legacy_dictionary_file(&self.path)? {
                    self.save_words(&file.words)
                        .context("migrate legacy dictionary to schema v1")?;
                }
                Ok(file)
            }
            Err(primary_error) if is_future_schema_error(&primary_error) => Err(primary_error),
            Err(primary_error) => {
                let backup = backup_path(&self.path);
                if !backup.exists() {
                    return Err(primary_error);
                }
                let backup_file = parse_dictionary_file(&backup).with_context(|| {
                    format!(
                        "dictionary is unreadable and its recovery backup is also invalid: {}",
                        self.path.display()
                    )
                })?;
                self.repair_from_backup(&backup_file)?;
                Ok(backup_file)
            }
        }
    }

    fn repair_from_backup(&self, _file: &HarperDictionaryFile) -> Result<()> {
        Ok(())
    }

    fn save_words(&self, words: &[String]) -> Result<()> {
        let parent = self
            .path
            .parent()
            .ok_or_else(|| anyhow!("dictionary path has no parent: {}", self.path.display()))?;
        fs::create_dir_all(parent)
            .with_context(|| format!("create dictionary directory {}", parent.display()))?;

        let temp = temp_path(&self.path);
        let backup = backup_path(&self.path);
        let payload = serde_json::to_vec_pretty(&HarperDictionaryFile::new(words.to_vec()))?;

        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temp)
            .with_context(|| format!("create dictionary temporary file {}", temp.display()))?;
        if let Err(error) = write_and_sync(&mut file, &payload) {
            let _ = fs::remove_file(&temp);
            return Err(error).context("write and sync dictionary temporary file");
        }
        drop(file);

        if backup.exists() {
            fs::remove_file(&backup)
                .with_context(|| format!("remove stale dictionary backup {}", backup.display()))?;
        }

        let had_canonical = self.path.exists();
        if had_canonical {
            if let Err(error) = fs::rename(&self.path, &backup) {
                let _ = fs::remove_file(&temp);
                return Err(error).context("move current dictionary to recovery backup");
            }
        }

        if let Err(error) = fs::rename(&temp, &self.path) {
            if had_canonical {
                let _ = fs::rename(&backup, &self.path);
            }
            let _ = fs::remove_file(&temp);
            return Err(error).context("promote dictionary temporary file");
        }

        if had_canonical {
            let _ = fs::remove_file(&backup);
        }
        Ok(())
    }
}

pub fn check_text(
    repository: &HarperDictionaryRepository,
    field: &str,
    source_text: &str,
    disabled_rules: &[String],
    suppressed_kinds: &[String],
) -> Result<HarperCheckDto> {
    if !ALLOWED_FIELDS.contains(&field) {
        return Err(anyhow!(
            "Harper checking is not permitted for field {field:?}"
        ));
    }

    if source_text.trim().is_empty() {
        return Ok(HarperCheckDto {
            field: field.to_string(),
            source_text: source_text.to_string(),
            engine_version: HARPER_VERSION,
            findings: Vec::new(),
        });
    }

    let dictionary = repository.dictionary()?;
    let document = Document::new_markdown_default(source_text, dictionary.as_ref());
    let mut linter = LintGroup::new_curated(Arc::clone(&dictionary), Dialect::British);

    for rule in disabled_rules {
        if linter.contains_key(rule) {
            linter.config.set_rule_enabled(rule, false);
        }
    }

    let source_chars: Vec<char> = source_text.chars().collect();
    let user_words = repository.list().unwrap_or_default();
    let findings = linter
        .organized_lints(&document)
        .into_iter()
        .flat_map(|(rule, lints)| {
            let source_chars = &source_chars;
            let user_words = &user_words;
            lints.into_iter().filter_map(move |lint| {
                let span = lint.span;
                let lint_kind = format!("{:?}", lint.lint_kind);

                if suppressed_kinds
                    .iter()
                    .any(|suppressed| suppressed.eq_ignore_ascii_case(&lint_kind))
                {
                    return None;
                }

                let original_text = lint.get_str(source_chars);

                if lint_kind == "Spelling"
                    && (user_dictionary_matches(user_words, &original_text)
                        || user_dictionary_covers_span(
                            user_words,
                            source_chars,
                            span.start,
                            span.end,
                        ))
                {
                    return None;
                }

                let message = lint.message.clone();
                let suggestions = lint
                    .suggestions
                    .iter()
                    .map(|suggestion| HarperSuggestionDto {
                        label: suggestion.to_string(),
                        replacement_text: apply_suggestion(source_text, lint.span, suggestion),
                    })
                    .collect();
                Some(HarperFindingDto {
                    lint_kind,
                    rule: rule.clone(),
                    message,
                    original_text,
                    span_start: span.start,
                    span_end: span.end,
                    suggestions,
                })
            })
        })
        .collect();

    Ok(HarperCheckDto {
        field: field.to_string(),
        source_text: source_text.to_string(),
        engine_version: HARPER_VERSION,
        findings,
    })
}

fn apply_suggestion(
    source_text: &str,
    span: harper_core::Span<char>,
    suggestion: &Suggestion,
) -> String {
    let mut chars: Vec<char> = source_text.chars().collect();
    suggestion.apply(span, &mut chars);
    chars.into_iter().collect()
}

fn user_dictionary_matches(user_terms: &[String], excerpt: &str) -> bool {
    user_terms
        .iter()
        .any(|term| term.eq_ignore_ascii_case(excerpt.trim()))
}

fn user_dictionary_covers_span(
    user_terms: &[String],
    source: &[char],
    span_start: usize,
    span_end: usize,
) -> bool {
    user_terms.iter().any(|term| {
        let term_chars = term.chars().collect::<Vec<_>>();
        let term_len = term_chars.len();
        if term_len == 0 || term_len > source.len() || span_start >= span_end {
            return false;
        }

        let first_candidate = span_end.saturating_sub(term_len);
        let last_candidate = span_start.min(source.len().saturating_sub(term_len));
        (first_candidate..=last_candidate).any(|candidate_start| {
            let candidate_end = candidate_start + term_len;
            if candidate_start > span_start || candidate_end < span_end {
                return false;
            }
            let candidate = source[candidate_start..candidate_end]
                .iter()
                .collect::<String>();
            candidate.eq_ignore_ascii_case(term)
        })
    })
}

fn normalize_word(word: &str) -> Result<String> {
    let trimmed = word.trim();
    if trimmed.is_empty() {
        return Err(anyhow!("dictionary word must not be empty"));
    }
    if trimmed
        .chars()
        .any(|ch| ch.is_whitespace() || ch.is_control())
    {
        return Err(anyhow!(
            "dictionary entries must contain one word and no whitespace/control characters"
        ));
    }
    Ok(trimmed.to_string())
}

fn normalize_words(words: Vec<String>) -> Result<Vec<String>> {
    let mut unique = BTreeMap::<String, String>::new();
    for word in words {
        let normalized = normalize_word(&word)?;
        unique
            .entry(normalized.to_lowercase())
            .or_insert(normalized);
    }
    Ok(unique.into_values().collect())
}

fn dictionary_entries(words: Vec<String>) -> Vec<HarperDictionaryEntry> {
    words
        .into_iter()
        .map(|word| HarperDictionaryEntry { word })
        .collect()
}

fn parse_dictionary_file(path: &Path) -> Result<HarperDictionaryFile> {
    let bytes = fs::read(path).with_context(|| format!("read dictionary {}", path.display()))?;
    let value: serde_json::Value = serde_json::from_slice(&bytes)
        .with_context(|| format!("parse dictionary JSON {}", path.display()))?;

    let file = match value {
        serde_json::Value::Array(items) => {
            let words = items
                .into_iter()
                .map(|item| {
                    item.as_str().map(str::to_owned).ok_or_else(|| {
                        anyhow!("legacy dictionary array contains a non-string entry")
                    })
                })
                .collect::<Result<Vec<_>>>()?;
            HarperDictionaryFile::new(normalize_words(words)?)
        }
        serde_json::Value::Object(mut object) => {
            let schema = object.remove("schema_version");
            let words = object
                .remove("words")
                .ok_or_else(|| anyhow!("dictionary object is missing words"))?;
            let words = words
                .as_array()
                .ok_or_else(|| anyhow!("dictionary words must be an array"))?
                .iter()
                .map(|item| {
                    item.as_str()
                        .map(str::to_owned)
                        .ok_or_else(|| anyhow!("dictionary contains a non-string word"))
                })
                .collect::<Result<Vec<_>>>()?;

            match schema {
                None => HarperDictionaryFile::new(normalize_words(words)?),
                Some(value) => {
                    let version = value.as_u64().ok_or_else(|| {
                        anyhow!("dictionary schema_version must be an unsigned integer")
                    })?;
                    let version = u32::try_from(version)
                        .map_err(|_| anyhow!("dictionary schema_version is out of range"))?;
                    if version > HARPER_DICTIONARY_SCHEMA_VERSION {
                        return Err(anyhow!(
                            "dictionary schema_version {version} is newer than supported version {HARPER_DICTIONARY_SCHEMA_VERSION} (future schema)"
                        ));
                    }
                    if version == 0 {
                        HarperDictionaryFile::new(normalize_words(words)?)
                    } else {
                        HarperDictionaryFile {
                            schema_version: version,
                            words: normalize_words(words)?,
                        }
                    }
                }
            }
        }
        _ => return Err(anyhow!("dictionary root must be an array or object")),
    };

    if file.schema_version != HARPER_DICTIONARY_SCHEMA_VERSION {
        return Err(anyhow!(
            "dictionary schema_version {} is not the supported version {}",
            file.schema_version,
            HARPER_DICTIONARY_SCHEMA_VERSION
        ));
    }
    Ok(file)
}

fn is_legacy_dictionary_file(path: &Path) -> Result<bool> {
    let bytes = fs::read(path).with_context(|| format!("read dictionary {}", path.display()))?;
    let value: serde_json::Value = serde_json::from_slice(&bytes)
        .with_context(|| format!("parse dictionary JSON {}", path.display()))?;
    Ok(match value {
        serde_json::Value::Array(_) => true,
        serde_json::Value::Object(object) => match object.get("schema_version") {
            None => true,
            Some(value) => value.as_u64() == Some(0),
        },
        _ => false,
    })
}

fn is_future_schema_error(error: &anyhow::Error) -> bool {
    error
        .chain()
        .any(|cause| cause.to_string().contains("future schema"))
}

fn temp_path(path: &Path) -> PathBuf {
    PathBuf::from(format!("{}.tmp", path.display()))
}

fn backup_path(path: &Path) -> PathBuf {
    PathBuf::from(format!("{}.bak", path.display()))
}

fn write_and_sync(file: &mut File, payload: &[u8]) -> Result<()> {
    file.write_all(payload)?;
    file.sync_all()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn temp_dir() -> PathBuf {
        let suffix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("gel-ui1d-harper-{suffix}"))
    }

    #[test]
    fn british_dictionary_suggests_colour_for_color() {
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        let result = check_text(&repo, "aims", "We use color here.", &[], &[]).unwrap();
        assert_eq!(result.engine_version, "2.8.0");
        assert!(result
            .findings
            .iter()
            .flat_map(|finding| finding.suggestions.iter())
            .any(|suggestion| suggestion.replacement_text == "We use colour here."));
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn findings_carry_span_coordinates_in_char_offsets() {
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        let result = check_text(&repo, "aims", "We use color here.", &[], &[]).unwrap();
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
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        let result = check_text(&repo, "aims", "We use color here.", &[], &[]).unwrap();
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
    fn findings_carry_stable_rule_names() {
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        let result = check_text(&repo, "aims", "We use color here.", &[], &[]).unwrap();
        assert!(result
            .findings
            .iter()
            .all(|finding| !finding.rule.is_empty()));
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn dictionary_word_suppresses_spelling_lint() {
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        repo.add("gelwriterqz").unwrap();
        let result = check_text(&repo, "aims", "gelwriterqz is a local term.", &[], &[]).unwrap();
        assert!(!result
            .findings
            .iter()
            .any(|finding| finding.original_text == "gelwriterqz"));
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn user_dictionary_covers_subspan_for_mixed_alphanumeric_term() {
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        repo.add("CHI365").unwrap();
        let result = check_text(
            &repo,
            "aims",
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
    fn add_remove_and_list_are_deterministic_and_case_insensitive() {
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        assert!(repo.add("Zebra").unwrap().changed);
        assert!(!repo.add(" zebra ").unwrap().changed);
        assert_eq!(repo.list().unwrap(), vec!["Zebra"]);
        assert!(repo.remove("zEbRa").unwrap().changed);
        assert!(repo.list().unwrap().is_empty());
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn legacy_array_is_migrated_to_schema_v1() {
        let dir = temp_dir();
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join(HARPER_DICTIONARY_FILE_NAME);
        fs::write(&path, b"[\"Beta\", \"alpha\", \"beta\"]").unwrap();
        let repo = HarperDictionaryRepository::new(path.clone());
        assert_eq!(repo.list().unwrap(), vec!["alpha", "Beta"]);
        let parsed: HarperDictionaryFile =
            serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
        assert_eq!(parsed.schema_version, HARPER_DICTIONARY_SCHEMA_VERSION);
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn future_schema_fails_closed() {
        let dir = temp_dir();
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join(HARPER_DICTIONARY_FILE_NAME);
        fs::write(&path, br#"{"schema_version":999,"words":["future"]}"#).unwrap();
        let repo = HarperDictionaryRepository::new(path.clone());
        assert!(repo.list().is_err());
        assert_eq!(
            fs::read_to_string(path).unwrap(),
            r#"{"schema_version":999,"words":["future"]}"#
        );
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn empty_text_short_circuits_to_no_findings() {
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        let result = check_text(&repo, "aims", "   ", &[], &[]).unwrap();
        assert!(result.findings.is_empty());
        assert_eq!(result.source_text, "   ");
        let _ = fs::remove_dir_all(dir);
    }

    #[test]
    fn disabled_rules_are_suppressed_for_session() {
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        let enabled = check_text(&repo, "aims", "CELSX is useful.", &[], &[]).unwrap();
        let spell_rule = enabled
            .findings
            .iter()
            .find(|finding| finding.original_text.eq_ignore_ascii_case("CELSX"))
            .map(|finding| finding.rule.clone())
            .expect("spelling finding should be reported for an unknown term");
        let disabled = check_text(
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
        let dir = temp_dir();
        let repo = HarperDictionaryRepository::new(dir.join(HARPER_DICTIONARY_FILE_NAME));
        let text = "This is a sentence that contains a large number of words and continues for quite some time because it is deliberately verbose and is intended to give Harper a chance to produce a readability finding for the test.";
        let unsuppressed = check_text(&repo, "aims", text, &[], &[]).unwrap();
        let suppressed =
            check_text(&repo, "aims", text, &[], &["Readability".to_string()]).unwrap();
        assert!(suppressed
            .findings
            .iter()
            .all(|finding| finding.lint_kind != "Readability"));
        assert!(suppressed.findings.len() <= unsuppressed.findings.len());
        let _ = fs::remove_dir_all(dir);
    }
}
