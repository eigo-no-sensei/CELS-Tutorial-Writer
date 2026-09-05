use anyhow::{bail, Context, Result};
use gel_core::{parse_edit_form, parse_tutorial_summary, validate_edit_form, GelSession};
use std::env;
use std::io::{self, Write};
use std::time::Duration;

fn main() -> Result<()> {
    let mut student_uid: Option<i64> = None;
    let mut delay_ms = 300_u64;
    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--student-uid" => {
                student_uid = Some(
                    args.next()
                        .context("--student-uid requires a value")?
                        .parse()
                        .context("--student-uid must be an integer")?,
                );
            }
            "--delay-ms" => {
                delay_ms = args
                    .next()
                    .context("--delay-ms requires a value")?
                    .parse()
                    .context("--delay-ms must be an integer")?;
            }
            "-h" | "--help" => {
                println!("usage: check_gel_read_only_live --student-uid UID [--delay-ms 300]");
                return Ok(());
            }
            _ => bail!("unknown argument {arg:?}"),
        }
    }
    let student_uid = student_uid.context("--student-uid is required")?;
    if student_uid <= 0 {
        bail!("--student-uid must be positive");
    }

    let mut username = String::new();
    print!("GEL username: ");
    io::stdout().flush()?;
    io::stdin().read_line(&mut username)?;
    let username = username.trim();
    if username.is_empty() {
        bail!("GEL username is required");
    }
    let password = rpassword::prompt_password("GEL password: ")?;
    if password.is_empty() {
        bail!("GEL password is required");
    }

    let mut session = GelSession::with_delay(Duration::from_millis(delay_ms))?;
    session.login(username, &password)?;
    drop(password);

    let identities = session.get_tutorial_list(student_uid)?;
    let summary_html = session.get_tutorial_summary_html(student_uid)?;
    let summary_entries = parse_tutorial_summary(&summary_html)?;
    let entry = summary_entries
        .iter()
        .find(|entry| {
            entry.tutorial_ts > 0
                && !entry.ttype_raw.is_empty()
                && identities
                    .iter()
                    .any(|identity| identity.timestamp == entry.tutorial_ts)
        })
        .context("no parsed summary entry matched a tutorial-list timestamp")?;

    let print_html = session.get_tutorial_print_html(student_uid, entry.tutorial_ts)?;
    let edit_html =
        session.get_tutorial_edit_html(student_uid, entry.tutorial_ts, entry.ttype_raw.as_str())?;
    let raw_edit = parse_edit_form(&edit_html)?;
    validate_edit_form(&raw_edit).context("C1 validation of live historical edit form failed")?;

    println!("N1 live read-only parity PASS");
    println!("  tutorial identities: {}", identities.len());
    println!("  parsed summary entries: {}", summary_entries.len());
    println!("  matched timestamp: {}", entry.tutorial_ts);
    println!("  tutorial type: {}", entry.ttype_label);
    println!("  summary bytes: {}", summary_html.len());
    println!("  print bytes: {}", print_html.len());
    println!("  edit bytes: {}", edit_html.len());
    println!("  HTTP requests: {}", session.request_count());
    println!("  GEL tutorial writes: 0");
    Ok(())
}
