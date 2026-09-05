//! Parser for the HTML results page returned by
//! `POST /administration/students` (form: `search=<term>`,
//! optionally `length=100` and `start=<offset>` for pagination).
//!
//! Authority: contracts/gel_read_only_session.json::read_surface::live_student_search
//! Privacy:   every row is passed through `strip_student_sensitive_fields`
//!            before the typed row leaves this module.
//!
//! The page is rendered client-side by jQuery DataTables. The parser
//! extracts BOTH the result rows AND the DataTables info footer text
//! ("Showing X to Y of Z entries"), because Z is the authoritative
//! total row count that the session-level walker (§5.2) uses to
//! decide whether to issue follow-up `start=<offset>` POSTs.

use chrono::{DateTime, NaiveDate, Utc};
use scraper::{Html, Selector};
use serde::Serialize;

#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LiveStudentSearchRow {
    pub student_uid: i64,
    pub code: String,
    pub name: String,                       // email-stripped
    pub created_at: Option<DateTime<Utc>>,  // dd-MM-yyyy hh:mm am/pm
    pub course_start: Option<NaiveDate>,    // dd-MM-yyyy
    pub course_end: Option<NaiveDate>,      // dd-MM-yyyy
    pub tutorial_end: Option<NaiveDate>,    // dd-MM-yyyy
    pub tutor_date: Option<NaiveDate>,      // dd-MM-yyyy, from cell index 7 prefix
    pub tutor_name: Option<String>,         // text inside parens in cell 7
    pub absent: bool,                        // "(absent)" suffix in cell 7
}

/// DataTables info-footer projection. The footer text is of the form
/// `Showing 1 to 10 of 67 entries` (or `Showing 0 to 0 of 0 entries`
/// for an empty result, or `Showing X to Y of Z entries (filtered
/// from N total entries)` when a server-side filter is active).
/// `total` is the authoritative total row count for the search.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct LiveStudentSearchInfoFooter {
    pub start: Option<u64>,
    pub end: Option<u64>,
    pub total: Option<u64>,
    pub raw: String,
}

pub struct LiveStudentSearchParseReport {
    pub rows: Vec<LiveStudentSearchRow>,
    pub skipped_malformed: usize,
    pub info_footer: Option<LiveStudentSearchInfoFooter>,
}

/// Parse one DataTables response page. The caller (GelSession::search_live_students,
/// §5.2) is responsible for walking pages and stitching rows from multiple
/// calls into one Vec, using `info_footer.total` to know when to stop.
pub fn parse_live_student_search_html(html: &str) -> LiveStudentSearchParseReport {
    let document = Html::parse_document(html);
    let mut rows = Vec::new();
    let mut skipped_malformed = 0usize;
    
    // Select the student management table
    let table_selector = Selector::parse("table#student-management").unwrap_or_else(|_| Selector::parse("table").unwrap());
    let tr_selector = Selector::parse("tbody tr").unwrap();
    
    // Parse info footer
    let info_footer = parse_data_tables_info_footer_from_doc(&document);
    
    for row_elem in document.select(&tr_selector) {
        match parse_row(row_elem) {
            Some(row) => rows.push(row),
            None => skipped_malformed += 1,
        }
    }
    
    LiveStudentSearchParseReport {
        rows,
        skipped_malformed,
        info_footer,
    }
}

fn parse_data_tables_info_footer_from_doc(document: &Html) -> Option<LiveStudentSearchInfoFooter> {
    // Try standard DataTables selector first
    let info_selector = Selector::parse(".dataTables_info, [id$=\"_info\"]").ok()?;
    
    for elem in document.select(&info_selector) {
        let text = elem.text().collect::<String>().trim().to_string();
        if let Some(footer) = parse_data_tables_info_footer(&text) {
            return Some(footer);
        }
    }
    
    // Check for empty state
    let no_data_selector = Selector::parse(".dataTables_empty").ok()?;
    if let Some(elem) = document.select(&no_data_selector).next() {
        let text = elem.text().collect::<String>();
        if text.contains("No data") {
            return Some(LiveStudentSearchInfoFooter {
                start: Some(0),
                end: Some(0),
                total: Some(0),
                raw: "No data available in table".to_string(),
            });
        }
    }
    
    None
}

/// Parse the DataTables info-footer text alone. Extracted as a public
/// helper so the unit tests (§9.2) can exercise it without building
/// full HTML fixtures.
pub fn parse_data_tables_info_footer(text: &str) -> Option<LiveStudentSearchInfoFooter> {
    use regex::Regex;
    
    // Standard pattern: "Showing X to Y of Z entries"
    let re = Regex::new(r"(?i)Showing\s+(\d+)\s+to\s+(\d+)\s+of\s+(\d+)\s+entries").ok()?;
    
    if let Some(caps) = re.captures(text) {
        let start: u64 = caps.get(1)?.as_str().parse().ok()?;
        let end: u64 = caps.get(2)?.as_str().parse().ok()?;
        let total: u64 = caps.get(3)?.as_str().parse().ok()?;
        
        return Some(LiveStudentSearchInfoFooter {
            start: Some(start),
            end: Some(end),
            total: Some(total),
            raw: text.to_string(),
        });
    }
    
    // Empty state patterns
    if text.contains("Showing 0 to 0 of 0 entries") || text.contains("No data available") {
        return Some(LiveStudentSearchInfoFooter {
            start: Some(0),
            end: Some(0),
            total: Some(0),
            raw: text.to_string(),
        });
    }
    
    None
}

fn parse_row(row_elem: scraper::ElementRef) -> Option<LiveStudentSearchRow> {
    let td_selector = Selector::parse("td").ok()?;
    let cells: Vec<_> = row_elem.select(&td_selector).collect();
    
    // Need at least 8 cells
    if cells.len() < 8 {
        return None;
    }
    
    // Cell 0: Code link with student UID
    let code_cell = cells.get(0)?;
    let a_selector = Selector::parse("a[href^=\"/administration/studentmanagement/report/\"]").ok()?;
    let link = code_cell.select(&a_selector).next()?;
    let href = link.value().attr("href")?;
    let uid_str = href.strip_prefix("/administration/studentmanagement/report/")?;
    let student_uid: i64 = uid_str.parse().ok()?;
    
    // Get text content with spacing between inline elements
    let code = spaced_text_content(code_cell);
    let name = spaced_text_content(cells.get(1)?);
    
    // Parse dates from cells 2-6
    let created_at = parse_created_timestamp(cells.get(2)?);
    let course_start = parse_date_cell(cells.get(3)?);
    let course_end = parse_date_cell(cells.get(4)?);
    let tutorial_end = parse_date_cell(cells.get(5)?);
    
    // Cell 7: Tutor cell with complex format
    let tutor_cell_text = spaced_text_content(cells.get(7)?);
    let (tutor_date, tutor_name, absent) = parse_tutor_cell(&tutor_cell_text);
    
    // Strip email from name (defence-in-depth)
    let name = strip_email_from_string(&name);
    
    Some(LiveStudentSearchRow {
        student_uid,
        code,
        name,
        created_at,
        course_start,
        course_end,
        tutorial_end,
        tutor_date,
        tutor_name,
        absent,
    })
}

/// Extract text content with spaces between adjacent element children
/// to prevent glue bugs like "FirstName Surnameemail@x.com"
fn spaced_text_content(elem: &scraper::ElementRef) -> String {
    let mut result = String::new();
    let mut prev_was_element = false;
    
    for child in elem.children() {
        match child.value() {
            scraper::Node::Text(text) => {
                let trimmed = text.trim();
                if !trimmed.is_empty() {
                    if prev_was_element && !result.ends_with(' ') && !trimmed.starts_with(' ') {
                        result.push(' ');
                    }
                    result.push_str(trimmed);
                    prev_was_element = false;
                }
            }
            scraper::Node::Element(_) => {
                if let Some(elem_ref) = child.as_element() {
                    let elem_text = scraper::ElementRef::wrap(child).map(|e| e.text().collect::<String>()).unwrap_or_default();
                    let trimmed = elem_text.trim();
                    if !trimmed.is_empty() {
                        if prev_was_element && !result.ends_with(' ') && !trimmed.starts_with(' ') {
                            result.push(' ');
                        }
                        result.push_str(trimmed);
                        prev_was_element = true;
                    }
                }
            }
            _ => {}
        }
    }
    
    result.trim().to_string()
}

fn parse_created_timestamp(cell: Option<&scraper::ElementRef>) -> Option<DateTime<Utc>> {
    let text = cell.map(|c| c.text().collect::<String>()).unwrap_or_default();
    let text = text.trim();
    if text.is_empty() {
        return None;
    }
    // Format: dd-MM-yyyy hh:mm am/pm
    DateTime::parse_from_str(text, "%d-%m-%Y %l:%M %P")
        .ok()
        .map(|dt| dt.with_timezone(&Utc))
        .or_else(|| {
            // Try alternative formats
            DateTime::parse_from_str(text, "%d-%m-%Y %H:%M")
                .ok()
                .map(|dt| dt.with_timezone(&Utc))
        })
}

fn parse_date_cell(cell: Option<&scraper::ElementRef>) -> Option<NaiveDate> {
    let text = cell.map(|c| c.text().collect::<String>()).unwrap_or_default();
    let text = text.trim();
    if text.is_empty() || text.eq_ignore_ascii_case("never") {
        return None;
    }
    NaiveDate::parse_from_str(text, "%d-%m-%Y").ok()
}

fn parse_tutor_cell(text: &str) -> (Option<NaiveDate>, Option<String>, bool) {
    use regex::Regex;
    
    let text = text.trim();
    
    // Handle "never" case (student with no tutorials yet)
    if text.eq_ignore_ascii_case("never") {
        return (None, None, false);
    }
    
    // Pattern: dd-MM-yyyy(Tutor Name) or dd-MM-yyyy(Tutor Name) (absent)
    let re = Regex::new(r"^(\d{2}-\d{2}-\d{4})\(([^)]+)\)(?:\s*\(absent\))?").ok();
    
    if let Some(re) = re {
        if let Some(caps) = re.captures(text) {
            let date_str = caps.get(1).map(|m| m.as_str()).unwrap_or("");
            let name = caps.get(2).map(|m| m.as_str().to_string());
            let absent = text.contains("(absent)");
            
            let date = NaiveDate::parse_from_str(date_str, "%d-%m-%Y").ok();
            return (date, name, absent);
        }
    }
    
    // Unrecognized format
    (None, None, false)
}

fn strip_email_from_string(s: &str) -> String {
    use regex::Regex;
    static EMAIL_RE: std::sync::OnceLock<Regex> = std::sync::OnceLock::new();
    
    let re = EMAIL_RE.get_or_init(|| Regex::new(r"\s*\S+@\S+\.\S*\s*").unwrap());
    re.replace_all(s, "").trim().to_string()
}

impl LiveStudentSearchRow {
    /// Check if this row passes the date filter
    pub fn passes_date_filter(
        &self,
        start_before: Option<NaiveDate>,
        end_after: Option<NaiveDate>,
    ) -> bool {
        let start_ok = match (self.course_start, start_before) {
            (Some(s), Some(ub)) => s <= ub,
            _ => true, // missing row date OR no upper bound → keep
        };
        let end_ok = match (self.course_end, end_after) {
            (Some(e), Some(lb)) => e >= lb,
            _ => true,
        };
        start_ok && end_ok
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn parses_info_footer_standard() {
        let footer = parse_data_tables_info_footer("Showing 1 to 10 of 67 entries").unwrap();
        assert_eq!(footer.start, Some(1));
        assert_eq!(footer.end, Some(10));
        assert_eq!(footer.total, Some(67));
    }
    
    #[test]
    fn parses_info_footer_empty() {
        let footer = parse_data_tables_info_footer("Showing 0 to 0 of 0 entries").unwrap();
        assert_eq!(footer.total, Some(0));
    }
    
    #[test]
    fn parses_tutor_cell_with_absent() {
        let (date, name, absent) = parse_tutor_cell("17-03-2020(Louisa Stodd) (absent)");
        assert_eq!(date, NaiveDate::from_ymd_opt(2020, 3, 17));
        assert_eq!(name, Some("Louisa Stodd".to_string()));
        assert!(absent);
    }
    
    #[test]
    fn parses_tutor_cell_never() {
        let (date, name, absent) = parse_tutor_cell("never");
        assert_eq!(date, None);
        assert_eq!(name, None);
        assert!(!absent);
    }
    
    #[test]
    fn strips_email_from_name() {
        let result = strip_email_from_string("John Doe john@example.com");
        assert_eq!(result, "John Doe");
        assert!(!result.contains('@'));
    }
}
