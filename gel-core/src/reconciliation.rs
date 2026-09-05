use crate::models::{
    ApiTutorial, CollisionGroup, CollisionStateKind, HistoricalStateAuthority,
    HistoricalStateAuthorityStatus, MatchMethod, PairedTutorial, ReconciliationResult,
    ReconciliationStatus, SummaryEntry,
};
use chrono::{Local, TimeZone};
use std::collections::{BTreeMap, BTreeSet};

fn date_key(ts: i64) -> Option<String> {
    Local
        .timestamp_opt(ts, 0)
        .single()
        .map(|dt| dt.format("%Y-%m-%d").to_string())
}

/// Governed historical-state equality for a same-timestamp collision.
///
/// URLs and rendering labels are source-entry metadata. The tutorial type and
/// normalized summary fields are the state used to decide whether multiple
/// candidate summary entries are semantically equivalent.
fn same_governed_summary_state(left: &SummaryEntry, right: &SummaryEntry) -> bool {
    left.ttype_raw == right.ttype_raw && left.fields == right.fields
}

fn classify_collision(api_count: usize, summaries: &[SummaryEntry]) -> CollisionStateKind {
    if api_count == 0 || summaries.is_empty() || api_count != summaries.len() {
        return CollisionStateKind::IncompleteEvidence;
    }

    let Some(first) = summaries.first() else {
        return CollisionStateKind::IncompleteEvidence;
    };
    if summaries
        .iter()
        .skip(1)
        .all(|entry| same_governed_summary_state(first, entry))
    {
        CollisionStateKind::IdenticalState
    } else {
        CollisionStateKind::DivergentState
    }
}

fn collision_authority(
    kind: CollisionStateKind,
    student_uid: i64,
    tutorial_ts: i64,
) -> HistoricalStateAuthority {
    let status = match kind {
        CollisionStateKind::IdenticalState => {
            HistoricalStateAuthorityStatus::SharedIdenticalCollision
        }
        CollisionStateKind::DivergentState => {
            HistoricalStateAuthorityStatus::AmbiguousDivergentCollision
        }
        CollisionStateKind::IncompleteEvidence => {
            HistoricalStateAuthorityStatus::IncompleteCollisionEvidence
        }
    };
    HistoricalStateAuthority::for_collision(status, student_uid, tutorial_ts)
}

fn collision_status(kind: CollisionStateKind) -> ReconciliationStatus {
    match kind {
        CollisionStateKind::IdenticalState => ReconciliationStatus::CollisionIdenticalState,
        CollisionStateKind::DivergentState => ReconciliationStatus::CollisionDivergentState,
        CollisionStateKind::IncompleteEvidence => ReconciliationStatus::CollisionIncompleteEvidence,
    }
}

pub fn pair_tutorials_with_summary(
    student_uid: i64,
    api: &[ApiTutorial],
    summaries: &[SummaryEntry],
) -> ReconciliationResult {
    let mut by_ts: BTreeMap<i64, Vec<usize>> = BTreeMap::new();
    let mut by_date: BTreeMap<String, Vec<usize>> = BTreeMap::new();
    for (idx, entry) in summaries.iter().enumerate() {
        if entry.tutorial_ts != 0 {
            by_ts.entry(entry.tutorial_ts).or_default().push(idx);
            if let Some(day) = date_key(entry.tutorial_ts) {
                by_date.entry(day).or_default().push(idx);
            }
        }
    }

    let mut api_by_ts: BTreeMap<i64, Vec<&ApiTutorial>> = BTreeMap::new();
    for tutorial in api {
        if tutorial.timestamp != 0 {
            api_by_ts
                .entry(tutorial.timestamp)
                .or_default()
                .push(tutorial);
        }
    }

    let mut timestamps = BTreeSet::new();
    timestamps.extend(by_ts.keys().copied());
    timestamps.extend(api_by_ts.keys().copied());

    let mut collision_ts = BTreeSet::new();
    let mut collisions = Vec::new();
    for ts in timestamps {
        let api_group = api_by_ts.get(&ts).cloned().unwrap_or_default();
        let summary_indices = by_ts.get(&ts).cloned().unwrap_or_default();
        if api_group.len() > 1 || summary_indices.len() > 1 {
            collision_ts.insert(ts);
            let summary_entries = summary_indices
                .iter()
                .map(|idx| summaries[*idx].clone())
                .collect::<Vec<_>>();
            let collision_kind = classify_collision(api_group.len(), &summary_entries);
            collisions.push(CollisionGroup {
                student_uid,
                tutorial_ts: ts,
                reconciliation_key: format!("{student_uid}:{ts}"),
                api_tutorial_ids: api_group.iter().map(|tutorial| tutorial.id).collect(),
                summary_entries,
                collision_kind,
            });
        }
    }

    // Collision-owned source states are reserved at group level immediately.
    // They must never later be consumed by positional per-ID matching or by a
    // same-date fallback belonging to another API tutorial.
    let collision_summary_indices = collision_ts
        .iter()
        .flat_map(|ts| by_ts.get(ts).into_iter().flatten().copied())
        .collect::<BTreeSet<_>>();
    let mut unconsumed = (0..summaries.len())
        .filter(|idx| !collision_summary_indices.contains(idx))
        .collect::<BTreeSet<_>>();

    let collision_by_ts = collisions
        .iter()
        .map(|group| (group.tutorial_ts, group))
        .collect::<BTreeMap<_, _>>();

    let mut pairs = Vec::new();
    let mut unmatched = 0usize;

    for tutorial in api {
        let ts = tutorial.timestamp;

        if let Some(group) = collision_by_ts.get(&ts) {
            pairs.push(PairedTutorial {
                api: tutorial.clone(),
                summary: None,
                match_method: MatchMethod::CollisionGroup,
                reconciliation_status: collision_status(group.collision_kind),
                state_authority: collision_authority(group.collision_kind, student_uid, ts),
            });
            continue;
        }

        let exact = by_ts
            .get(&ts)
            .and_then(|indices| indices.iter().copied().find(|idx| unconsumed.contains(idx)));

        let (summary_idx, method) = if let Some(idx) = exact {
            (Some(idx), MatchMethod::ExactTimestamp)
        } else {
            let candidate = date_key(ts).and_then(|day| {
                by_date.get(&day).and_then(|indices| {
                    indices
                        .iter()
                        .copied()
                        .filter(|idx| unconsumed.contains(idx))
                        .filter(|idx| !collision_ts.contains(&summaries[*idx].tutorial_ts))
                        .min_by_key(|idx| (summaries[*idx].tutorial_ts - ts).abs())
                })
            });
            match candidate {
                Some(idx) => (Some(idx), MatchMethod::SameDateFallback),
                None => (None, MatchMethod::Unmatched),
            }
        };

        let summary = summary_idx.map(|idx| {
            unconsumed.remove(&idx);
            summaries[idx].clone()
        });

        let (status, state_authority) = if summary.is_some() {
            (
                ReconciliationStatus::Matched,
                HistoricalStateAuthority::proven(),
            )
        } else {
            unmatched += 1;
            (
                ReconciliationStatus::UnmatchedSummary,
                HistoricalStateAuthority::unmatched(),
            )
        };

        pairs.push(PairedTutorial {
            api: tutorial.clone(),
            summary,
            match_method: method,
            reconciliation_status: status,
            state_authority,
        });
    }

    ReconciliationResult {
        pairs,
        unmatched_summary_count: unmatched,
        collisions,
    }
}
