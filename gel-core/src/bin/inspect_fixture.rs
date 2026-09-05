use anyhow::{bail, Context, Result};
use gel_core::{parse_edit_form, parse_print_page, parse_tutorial_summary, validate_edit_form};
use std::{env, fs};

fn main() -> Result<()> {
    let mut args = env::args().skip(1);
    let kind = args
        .next()
        .context("usage: inspect_fixture <summary|edit|edit-validated|print> <path>")?;
    let path = args
        .next()
        .context("usage: inspect_fixture <summary|edit|edit-validated|print> <path>")?;
    let html = fs::read_to_string(&path).with_context(|| format!("read {path}"))?;

    match kind.as_str() {
        "summary" => println!(
            "{}",
            serde_json::to_string_pretty(&parse_tutorial_summary(&html)?)?
        ),
        "edit" => println!(
            "{}",
            serde_json::to_string_pretty(&parse_edit_form(&html)?)?
        ),
        "edit-validated" => {
            let raw = parse_edit_form(&html)?;
            println!(
                "{}",
                serde_json::to_string_pretty(&validate_edit_form(&raw)?)?
            )
        }
        "print" => println!(
            "{}",
            serde_json::to_string_pretty(&parse_print_page(&html)?)?
        ),
        _ => {
            bail!("unknown fixture type {kind:?}; expected summary, edit, edit-validated or print")
        }
    }
    Ok(())
}
