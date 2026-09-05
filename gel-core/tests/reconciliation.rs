use gel_core::models::{
    ApiTutorial, CollisionStateKind, HistoricalStateAuthorityStatus, MatchMethod,
    ReconciliationStatus, RevisionBlockReason, SummaryEntry,
};
use gel_core::pair_tutorials_with_summary;
use std::collections::BTreeMap;

fn summary(ts: i64, absent: &str) -> SummaryEntry {
    let mut fields = BTreeMap::new();
    fields.insert("absent".to_string(), absent.to_string());
    SummaryEntry {
        datetime_label: "fixture".to_string(),
        tutorial_ts: ts,
        ttype_raw: "1".to_string(),
        ttype_label: "Final".to_string(),
        print_url: format!("/study/tutorials/print/900001/{ts}"),
        edit_url: format!("/study/tutorials/add/900001/{ts}/1"),
        fields,
    }
}

#[test]
fn identical_state_collision_preserves_ids_without_positional_state_assignment() {
    let ts = 1_786_523_673;
    let api = vec![
        ApiTutorial {
            id: 157269,
            timestamp: ts,
        },
        ApiTutorial {
            id: 157270,
            timestamp: ts,
        },
        ApiTutorial {
            id: 157271,
            timestamp: ts,
        },
    ];
    let summaries = vec![summary(ts, "yes"), summary(ts, "yes"), summary(ts, "yes")];
    let result = pair_tutorials_with_summary(464982, &api, &summaries);

    assert_eq!(result.pairs.len(), 3);
    assert_eq!(result.collisions.len(), 1);
    let collision = &result.collisions[0];
    assert_eq!(collision.collision_kind, CollisionStateKind::IdenticalState);
    assert_eq!(collision.api_tutorial_ids, vec![157269, 157270, 157271]);
    assert_eq!(collision.summary_entries.len(), 3);

    for pair in &result.pairs {
        assert_eq!(pair.match_method, MatchMethod::CollisionGroup);
        assert_eq!(
            pair.reconciliation_status,
            ReconciliationStatus::CollisionIdenticalState
        );
        assert_eq!(
            pair.state_authority.status,
            HistoricalStateAuthorityStatus::SharedIdenticalCollision
        );
        assert!(
            pair.summary.is_none(),
            "collision candidates must remain group-owned, not positionally assigned"
        );
    }

    for tutorial_id in [157269, 157270, 157271] {
        let evidence = result.revision_state_for(tutorial_id).unwrap();
        assert_eq!(
            evidence.authority.status,
            HistoricalStateAuthorityStatus::SharedIdenticalCollision
        );
        assert_eq!(evidence.summary.fields["absent"], "yes");
    }
}

#[test]
fn divergent_state_collision_blocks_revision_by_id_and_assigns_no_candidate_state() {
    let ts = 1_771_504_395;
    let api = vec![
        ApiTutorial {
            id: 151774,
            timestamp: ts,
        },
        ApiTutorial {
            id: 156932,
            timestamp: ts,
        },
    ];
    let summaries = vec![summary(ts, "no"), summary(ts, "yes")];
    let result = pair_tutorials_with_summary(464951, &api, &summaries);

    assert_eq!(result.pairs.len(), 2);
    assert_eq!(result.collisions.len(), 1);
    let collision = &result.collisions[0];
    assert_eq!(collision.collision_kind, CollisionStateKind::DivergentState);
    assert_eq!(collision.summary_entries[0].fields["absent"], "no");
    assert_eq!(collision.summary_entries[1].fields["absent"], "yes");

    for pair in &result.pairs {
        assert_eq!(pair.match_method, MatchMethod::CollisionGroup);
        assert_eq!(
            pair.reconciliation_status,
            ReconciliationStatus::CollisionDivergentState
        );
        assert_eq!(
            pair.state_authority.status,
            HistoricalStateAuthorityStatus::AmbiguousDivergentCollision
        );
        assert!(
            pair.summary.is_none(),
            "divergent collision must never claim a per-ID summary state"
        );
        let error = result.revision_state_for(pair.api.id).unwrap_err();
        assert_eq!(error.reason, RevisionBlockReason::DivergentCollision);
        assert_eq!(
            error.reconciliation_key.as_deref(),
            Some("464951:1771504395")
        );
    }
}

#[test]
fn incomplete_collision_evidence_blocks_revision() {
    let ts = 1_700_000_000;
    let api = vec![
        ApiTutorial {
            id: 1,
            timestamp: ts,
        },
        ApiTutorial {
            id: 2,
            timestamp: ts,
        },
    ];
    let summaries = vec![summary(ts, "no")];
    let result = pair_tutorials_with_summary(9, &api, &summaries);

    assert_eq!(result.collisions.len(), 1);
    assert_eq!(
        result.collisions[0].collision_kind,
        CollisionStateKind::IncompleteEvidence
    );
    for pair in &result.pairs {
        assert!(pair.summary.is_none());
        assert_eq!(
            pair.state_authority.status,
            HistoricalStateAuthorityStatus::IncompleteCollisionEvidence
        );
        let error = result.revision_state_for(pair.api.id).unwrap_err();
        assert_eq!(
            error.reason,
            RevisionBlockReason::IncompleteCollisionEvidence
        );
    }
}

#[test]
fn consumed_exact_summary_cannot_be_reused_by_same_date_fallback() {
    let exact_ts = 1_785_000_000;
    let other_ts = exact_ts + 60;
    let api = vec![
        ApiTutorial {
            id: 1,
            timestamp: exact_ts,
        },
        ApiTutorial {
            id: 2,
            timestamp: other_ts,
        },
    ];
    let summaries = vec![summary(exact_ts, "no")];
    let result = pair_tutorials_with_summary(900001, &api, &summaries);
    assert!(result.pairs[0].summary.is_some());
    assert!(result.pairs[1].summary.is_none());
    assert_eq!(
        result.pairs[0].state_authority.status,
        HistoricalStateAuthorityStatus::ProvenPerTutorial
    );
    assert_eq!(
        result.pairs[1].state_authority.status,
        HistoricalStateAuthorityStatus::UnmatchedSourceState
    );
}

#[test]
fn source_entry_urls_do_not_create_false_state_divergence() {
    let ts = 1_786_523_673;
    let api = vec![
        ApiTutorial {
            id: 10,
            timestamp: ts,
        },
        ApiTutorial {
            id: 11,
            timestamp: ts,
        },
    ];
    let first = summary(ts, "yes");
    let mut second = summary(ts, "yes");
    second.print_url = "/different/source/locator".to_string();
    second.edit_url = "/another/source/locator".to_string();
    second.datetime_label = "different rendering label".to_string();

    let result = pair_tutorials_with_summary(464982, &api, &[first, second]);
    assert_eq!(
        result.collisions[0].collision_kind,
        CollisionStateKind::IdenticalState
    );
}
