use crate::gel_fields;
use crate::models::SummaryEntry;
use anyhow::{anyhow, Result};
use regex::Regex;
use scraper::{ElementRef, Html, Selector};
use std::collections::BTreeMap;

fn sel(value: &str) -> Result<Selector> {
    Selector::parse(value).map_err(|_| anyhow!("invalid selector: {value}"))
}

fn normalize_ws(value: &str) -> String {
    value.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn direct_cells<'a>(row: &ElementRef<'a>, names: &[&str]) -> Vec<ElementRef<'a>> {
    row.children()
        .filter_map(ElementRef::wrap)
        .filter(|e| names.iter().any(|name| e.value().name() == *name))
        .collect()
}

fn cell_text(cell: &ElementRef<'_>) -> Result<String> {
    let hidden_sel = sel("span.hidden-text")?;
    if let Some(hidden) = cell.select(&hidden_sel).next() {
        return Ok(normalize_ws(&hidden.text().collect::<Vec<_>>().join(" ")));
    }
    Ok(normalize_ws(&cell.text().collect::<Vec<_>>().join(" "))
        .replace(" read more", "")
        .trim()
        .to_string())
}

fn first_href(cell: &ElementRef<'_>, needle: &str) -> Result<String> {
    let link_sel = sel("a[href]")?;
    Ok(cell
        .select(&link_sel)
        .filter_map(|a| a.value().attr("href"))
        .find(|href| href.contains(needle))
        .unwrap_or_default()
        .to_string())
}

fn parse_ts(url: &str) -> i64 {
    let re = Regex::new(r"/study/tutorials/(?:print|add)/\d+/(\d+)").unwrap();
    re.captures(url)
        .and_then(|c| c.get(1))
        .and_then(|m| m.as_str().parse().ok())
        .unwrap_or(0)
}

fn parse_ttype(edit_url: &str) -> String {
    let re = Regex::new(r"/study/tutorials/add/\d+/\d+/(\d+)").unwrap();
    re.captures(edit_url)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .unwrap_or_default()
}

fn normalize_type(raw: &str) -> String {
    match raw {
        gel_fields::TTYPE_INITIAL => "Initial",
        gel_fields::TTYPE_FINAL => "Final",
        _ => "Standard",
    }
    .to_string()
}

pub fn parse_tutorial_summary(html: &str) -> Result<Vec<SummaryEntry>> {
    let document = Html::parse_document(html);
    let table_sel = sel("#Open_Text_General.FixedTables, #Open_Text_General, table.FixedTables")?;
    let table = document
        .select(&table_sel)
        .next()
        .ok_or_else(|| anyhow!("summary page missing direct FixedTables table"))?;

    let header_sel = sel("thead tr")?;
    let body_sel = sel("tbody > tr")?;
    let header = table
        .select(&header_sel)
        .next()
        .ok_or_else(|| anyhow!("summary table missing header"))?;
    let header_cells = direct_cells(&header, &["th", "td"]);
    if header_cells.len() < 2 {
        return Err(anyhow!("summary header has no tutorial columns"));
    }

    let datetime_labels = header_cells[1..]
        .iter()
        .map(cell_text)
        .collect::<Result<Vec<_>>>()?;

    let column_count = datetime_labels.len();
    let mut fields: Vec<BTreeMap<String, String>> =
        (0..column_count).map(|_| BTreeMap::new()).collect();
    let mut print_urls = vec![String::new(); column_count];
    let mut edit_urls = vec![String::new(); column_count];

    for row in table.select(&body_sel) {
        let cells = direct_cells(&row, &["td"]);
        if cells.len() < 2 {
            continue;
        }
        let label = cell_text(&cells[0])?;
        for (col, cell) in cells[1..].iter().enumerate().take(column_count) {
            fields[col].insert(label.clone(), cell_text(cell)?);
            if label == gel_fields::SUMMARY_ACTIONS {
                print_urls[col] = first_href(cell, "/study/tutorials/print/")?;
                edit_urls[col] = first_href(cell, "/study/tutorials/add/")?;
            }
        }
    }

    if !fields
        .iter()
        .any(|f| f.contains_key(gel_fields::SUMMARY_ACTIONS))
    {
        return Err(anyhow!("summary table missing Actions row"));
    }

    let mut result = Vec::new();
    for col in 0..column_count {
        if print_urls[col].is_empty() && edit_urls[col].is_empty() {
            continue;
        }
        let ts = parse_ts(if !print_urls[col].is_empty() {
            &print_urls[col]
        } else {
            &edit_urls[col]
        });
        let ttype_raw = parse_ttype(&edit_urls[col]);
        result.push(SummaryEntry {
            datetime_label: datetime_labels[col].clone(),
            tutorial_ts: ts,
            ttype_label: normalize_type(&ttype_raw),
            ttype_raw,
            print_url: print_urls[col].clone(),
            edit_url: edit_urls[col].clone(),
            fields: fields[col].clone(),
        });
    }
    Ok(result)
}
