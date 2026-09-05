use anyhow::{bail, Context, Result};
use gel_core::models::{
    ApiTutorial, CollisionStateKind, HistoricalStateAuthorityStatus, RevisionBlockReason,
};
use gel_core::{pair_tutorials_with_summary, parse_tutorial_summary};
use serde_json::Value;
use std::collections::BTreeSet;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

fn main() -> Result<()> {
    let mut args = env::args().skip(1);
    let expected_dir = PathBuf::from(
        args.next()
            .context("usage: check_reconciliation_fixtures <expected-dir> <raw-dir>")?,
    );
    let raw_dir = PathBuf::from(
        args.next()
            .context("usage: check_reconciliation_fixtures <expected-dir> <raw-dir>")?,
    );
    if args.next().is_some() {
        bail!("usage: check_reconciliation_fixtures <expected-dir> <raw-dir>");
    }
    if !expected_dir.is_dir() {
        bail!(
            "expected reconciliation fixture directory does not exist: {}",
            expected_dir.display()
        );
    }
    if !raw_dir.is_dir() {
        bail!(
            "raw reconciliation fixture directory does not exist: {}",
            raw_dir.display()
        );
    }

    let mut expected_files = fs::read_dir(&expected_dir)?
        .filter_map(|entry| entry.ok().map(|entry| entry.path()))
        .filter(|path| path.extension().and_then(|x| x.to_str()) == Some("json"))
        .collect::<Vec<_>>();
    expected_files.sort();

    let mut labels = BTreeSet::new();
    for expected_path in &expected_files {
        labels.insert(check_fixture(expected_path, &raw_dir)?);
    }

    let required = BTreeSet::from([
        "duplicate_different_state".to_string(),
        "duplicate_identical_state".to_string(),
    ]);
    if labels != required {
        bail!("collision fixture labels {labels:?} != required {required:?}");
    }

    println!(
        "collision authority fixtures PASS — {} fixture(s)",
        expected_files.len()
    );
    Ok(())
}

fn check_fixture(expected_path: &Path, raw_root: &Path) -> Result<String> {
    let expected_text = fs::read_to_string(expected_path)
        .with_context(|| format!("read {}", expected_path.display()))?;
    let root: Value = serde_json::from_str(&expected_text)
        .with_context(|| format!("parse {}", expected_path.display()))?;
    let spec = root
        .get("spec")
        .and_then(Value::as_object)
        .context("collision fixture missing object .spec")?;

    let label = string_value(spec.get("label")).context("collision spec.label missing")?;
    let uid = i64_value(spec.get("uid")).context("collision spec.uid missing")?;
    let ts = i64_value(spec.get("timestamp")).context("collision spec.timestamp missing")?;
    let expected_distinct = i64_value(spec.get("expected_distinct_summary_states"))
        .context("collision spec.expected_distinct_summary_states missing")?;
    let expected_api_ids = spec
        .get("api_ids")
        .and_then(Value::as_array)
        .context("collision spec.api_ids missing")?
        .iter()
        .map(|value| i64_value(Some(value)).context("invalid collision API ID"))
        .collect::<Result<Vec<_>>>()?;

    let observed_distinct = root
        .get("observed_distinct_summary_states")
        .and_then(Value::as_i64)
        .context("collision expected JSON missing observed_distinct_summary_states")?;
    if observed_distinct != expected_distinct {
        bail!(
            "{label}: captured distinct-state count {observed_distinct} != expected {expected_distinct}"
        );
    }

    let fixture_raw = raw_root.join(&label);
    let api_text = fs::read_to_string(fixture_raw.join("api_rows.json"))
        .with_context(|| format!("{label}: read api_rows.json"))?;
    let api_json: Value =
        serde_json::from_str(&api_text).with_context(|| format!("{label}: parse api_rows.json"))?;
    let api = api_json
        .as_array()
        .context("api_rows.json must contain an array")?
        .iter()
        .map(api_tutorial_from_json)
        .collect::<Result<Vec<_>>>()?;

    let summary_html = fs::read_to_string(fixture_raw.join("summary.html"))
        .with_context(|| format!("{label}: read summary.html"))?;
    let summaries = parse_tutorial_summary(&summary_html)?
        .into_iter()
        .filter(|entry| entry.tutorial_ts == ts)
        .collect::<Vec<_>>();

    let result = pair_tutorials_with_summary(uid, &api, &summaries);
    if result.collisions.len() != 1 {
        bail!(
            "{label}: expected exactly one collision group, got {}",
            result.collisions.len()
        );
    }
    let collision = &result.collisions[0];
    let mut actual_ids = collision.api_tutorial_ids.clone();
    let mut expected_ids = expected_api_ids.clone();
    actual_ids.sort_unstable();
    expected_ids.sort_unstable();
    if actual_ids != expected_ids {
        bail!("{label}: API IDs {actual_ids:?} != expected {expected_ids:?}");
    }
    if collision.summary_entries.len() != summaries.len() {
        bail!(
            "{label}: collision owns {} summary entries but parser returned {}",
            collision.summary_entries.len(),
            summaries.len()
        );
    }
    if result.pairs.iter().any(|pair| pair.summary.is_some()) {
        bail!(
            "{label}: ambiguous collision candidate was positionally assigned to a canonical tutorial ID"
        );
    }

    match expected_distinct {
        1 => {
            if collision.collision_kind != CollisionStateKind::IdenticalState {
                bail!(
                    "{label}: expected identical-state collision, got {:?}",
                    collision.collision_kind
                );
            }
            for tutorial_id in expected_api_ids {
                let evidence = result.revision_state_for(tutorial_id)?;
                if evidence.authority.status
                    != HistoricalStateAuthorityStatus::SharedIdenticalCollision
                {
                    bail!(
                        "{label}: tutorial {tutorial_id} did not resolve through shared-identical authority"
                    );
                }
            }
        }
        value if value > 1 => {
            if collision.collision_kind != CollisionStateKind::DivergentState {
                bail!(
                    "{label}: expected divergent-state collision, got {:?}",
                    collision.collision_kind
                );
            }
            for tutorial_id in expected_api_ids {
                let error = result
                    .revision_state_for(tutorial_id)
                    .expect_err("divergent collision revision must be blocked");
                if error.reason != RevisionBlockReason::DivergentCollision {
                    bail!(
                        "{label}: tutorial {tutorial_id} blocked for {:?}, expected divergent collision",
                        error.reason
                    );
                }
            }
            if root.get("timestamp_route_state").is_none() {
                bail!(
                    "{label}: divergent fixture must retain timestamp_route_state as separate group evidence"
                );
            }
        }
        _ => bail!("{label}: invalid expected distinct-state count {expected_distinct}"),
    }

    Ok(label)
}

fn api_tutorial_from_json(value: &Value) -> Result<ApiTutorial> {
    let object = value
        .as_object()
        .context("API tutorial row must be an object")?;
    let id = i64_value(object.get("id").or_else(|| object.get("tutorial_id")))
        .context("API tutorial row missing id/tutorial_id")?;
    let timestamp =
        i64_value(object.get("timestamp")).context("API tutorial row missing timestamp")?;
    Ok(ApiTutorial { id, timestamp })
}

fn i64_value(value: Option<&Value>) -> Option<i64> {
    match value? {
        Value::Number(number) => number.as_i64(),
        Value::String(text) => text.parse().ok(),
        _ => None,
    }
}

fn string_value(value: Option<&Value>) -> Option<String> {
    match value? {
        Value::String(text) => Some(text.clone()),
        Value::Number(number) => Some(number.to_string()),
        _ => None,
    }
}
