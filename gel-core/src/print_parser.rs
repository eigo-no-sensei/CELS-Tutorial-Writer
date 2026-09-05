use crate::models::PrintRecord;
use anyhow::Result;
use regex::Regex;
use scraper::{ElementRef, Html, Selector};
use std::collections::BTreeMap;

const LABELS: &[&str] = &[
    "Tutorial Type",
    "absent",
    "Tutorial Overall Level",
    "Initial Speaking",
    "Initial Use of English",
    "Initial Writing",
    "Initial Listening",
    "Speaking",
    "Use of English",
    "Writing",
    "Listening",
    "Reading",
    "Assessment",
    "Aims",
    "Teacher's Comments",
    "Additional Comments/Accommodation (under 18s only)",
    "Do you want to take an English proficiency exam?",
    "If yes, which exam?",
    "If yes, when do you want to take the exam?",
];

fn normalize_ws(value: &str) -> String {
    value.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn element_text(element: &ElementRef<'_>) -> String {
    normalize_ws(&element.text().collect::<Vec<_>>().join(" "))
}

fn canonical_label(value: &str) -> Option<&'static str> {
    let normalized = normalize_ws(value).trim_end_matches(':').trim().to_string();
    LABELS
        .iter()
        .copied()
        .find(|label| label.eq_ignore_ascii_case(&normalized))
}

/// Parse a historical GEL print page with Python-v4.9-compatible semantics.
///
/// Labels are discovered only from the first direct cell of each table row.
/// Flattened page prose is used solely for the fixed tutorial header. This is
/// critical because teacher prose can legitimately contain label words such as
/// "Listening" or "Speaking" and must never be split into fake fields.
pub fn parse_print_page(html: &str) -> Result<PrintRecord> {
    let doc = Html::parse_document(html);
    let table_sel = Selector::parse("table").expect("static selector");
    let row_sel = Selector::parse("tr").expect("static selector");

    let mut best_fields = BTreeMap::new();
    let mut best_text: Option<String> = None;
    let mut best_score = 0usize;

    for table in doc.select(&table_sel) {
        let mut fields = BTreeMap::new();
        let mut score = 0usize;

        for row in table.select(&row_sel) {
            let cells: Vec<ElementRef<'_>> = row
                .children()
                .filter_map(ElementRef::wrap)
                .filter(|element| matches!(element.value().name(), "td" | "th"))
                .collect();
            if cells.len() < 2 {
                continue;
            }

            let Some(label) = canonical_label(&element_text(&cells[0])) else {
                continue;
            };

            let value = cells[1..]
                .iter()
                .map(element_text)
                .filter(|value| !value.is_empty())
                .collect::<Vec<_>>()
                .join(" ");
            fields.insert(label.to_string(), value);
            score += 1;
        }

        // Python v4.9 keeps the first table that establishes a strictly higher
        // score; equal-score later tables do not replace it.
        if score > best_score {
            best_score = score;
            best_fields = fields;
            let text = element_text(&table);
            best_text = (!text.is_empty()).then_some(text);
        }
    }

    let page_text = normalize_ws(&doc.root_element().text().collect::<Vec<_>>().join(" "));
    let header_re = Regex::new(
        r"Tutorial with (.+?) \(teacher\) and (.+?) \(student\) on (\d{2}-\d{2}-\d{4})",
    )?;
    let (teacher_name, student_name, custom_date) =
        if let Some(caps) = header_re.captures(&page_text) {
            (
                Some(normalize_ws(&caps[1])),
                Some(normalize_ws(&caps[2])),
                Some(caps[3].to_string()),
            )
        } else {
            (None, None, None)
        };

    let mut direct_fields = best_fields.clone();
    if let Some(value) = best_fields.get("Tutorial Type") {
        direct_fields
            .entry("Type".to_string())
            .or_insert_with(|| value.clone());
    }

    Ok(PrintRecord {
        teacher_name,
        student_name,
        custom_date,
        print_text: best_text,
        fields: best_fields,
        direct_fields,
    })
}
