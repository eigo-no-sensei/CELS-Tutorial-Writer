use crate::models::{FormControl, SelectOption};
use anyhow::Result;
use regex::Regex;
use scraper::{ElementRef, Html, Selector};
use std::collections::BTreeMap;

fn selector(value: &str) -> Result<Selector> {
    Selector::parse(value).map_err(|_| anyhow::anyhow!("invalid selector: {value}"))
}

fn text_of(element: &ElementRef<'_>) -> String {
    element
        .text()
        .collect::<Vec<_>>()
        .join("")
        .trim()
        .to_string()
}

fn rich_text_of(element: &ElementRef<'_>) -> Result<String> {
    let mut html = element.inner_html();
    let br = Regex::new(r"(?is)<br\s*/?>")?;
    let blocks = Regex::new(r"(?is)</?(?:div|p|li|section|article|h[1-6])(?:\s[^>]*)?>")?;
    html = br.replace_all(&html, "\n").into_owned();
    html = blocks.replace_all(&html, "\n").into_owned();

    let fragment = Html::parse_fragment(&html);
    let raw = fragment.root_element().text().collect::<Vec<_>>().join("");
    let mut lines = Vec::new();
    for line in raw.replace('\r', "").lines() {
        let normalized = line.split_whitespace().collect::<Vec<_>>().join(" ");
        if !normalized.is_empty() {
            lines.push(normalized);
        }
    }
    Ok(lines.join("\n"))
}

fn parse_js_values(html: &str) -> Result<BTreeMap<String, String>> {
    let re = Regex::new(
        r#"(?is)(?:\$\s*|jQuery\s*)\(\s*[\"']#(?P<id>[^\"']+)[\"']\s*\)\s*\.val\s*\(\s*[\"'](?P<value>.*?)[\"']\s*\)"#,
    )?;
    let mut values = BTreeMap::new();
    for caps in re.captures_iter(html) {
        values.insert(caps["id"].to_string(), caps["value"].to_string());
    }
    Ok(values)
}

/// Lexically parse browser form controls without assigning New-vs-Revision
/// authority. Source-specific validators own semantic interpretation.
pub(crate) fn parse_form_controls(
    html: &str,
) -> Result<(Vec<FormControl>, BTreeMap<String, String>)> {
    let document = Html::parse_document(html);
    let js_values_by_id = parse_js_values(html)?;

    let input_sel = selector("input[name]")?;
    let select_sel = selector("select[name]")?;
    let textarea_sel = selector("textarea[name]")?;
    let contenteditable_sel = selector("[contenteditable][name]")?;
    let option_sel = selector("option")?;

    let mut controls = Vec::new();

    for input in document.select(&input_sel) {
        let v = input.value();
        controls.push(FormControl::Input {
            name: v.attr("name").unwrap_or_default().to_string(),
            id: v.attr("id").map(ToString::to_string),
            input_type: v.attr("type").unwrap_or("text").to_ascii_lowercase(),
            value: v.attr("value").unwrap_or_default().to_string(),
            checked: v.attr("checked").is_some(),
        });
    }

    for select in document.select(&select_sel) {
        let v = select.value();
        let id = v.attr("id").map(ToString::to_string);
        let mut options = Vec::new();
        let mut html_selected_value = None;

        for option in select.select(&option_sel) {
            let ov = option.value();
            let selected = ov.attr("selected").is_some();
            let value = ov.attr("value").unwrap_or_default().to_string();
            if selected && html_selected_value.is_none() {
                html_selected_value = Some(value.clone());
            }
            options.push(SelectOption {
                value,
                text: text_of(&option),
                selected_in_html: selected,
            });
        }

        let js_value = id.as_ref().and_then(|id| js_values_by_id.get(id)).cloned();
        let (effective_value, value_source) = if let Some(value) = js_value {
            (Some(value), Some("inline_js".to_string()))
        } else if let Some(value) = html_selected_value.clone() {
            (Some(value), Some("selected_option".to_string()))
        } else if let Some(first) = options.first() {
            (
                Some(first.value.clone()),
                Some("browser_default_first_option".to_string()),
            )
        } else {
            (None, None)
        };

        controls.push(FormControl::Select {
            name: v.attr("name").unwrap_or_default().to_string(),
            id,
            options,
            html_selected_value,
            effective_value,
            value_source,
        });
    }

    for textarea in document.select(&textarea_sel) {
        let v = textarea.value();
        controls.push(FormControl::Textarea {
            name: v.attr("name").unwrap_or_default().to_string(),
            id: v.attr("id").map(ToString::to_string),
            value: textarea.text().collect::<Vec<_>>().join(""),
        });
    }

    for editor in document.select(&contenteditable_sel) {
        let v = editor.value();
        if matches!(v.attr("contenteditable"), Some(value) if value.eq_ignore_ascii_case("false")) {
            continue;
        }
        controls.push(FormControl::ContentEditable {
            name: v.attr("name").unwrap_or_default().to_string(),
            id: v.attr("id").map(ToString::to_string),
            value: rich_text_of(&editor)?,
            html: editor.inner_html(),
        });
    }

    Ok((controls, js_values_by_id))
}
