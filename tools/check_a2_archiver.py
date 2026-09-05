#!/usr/bin/env python3
"""A2 structural ownership/cutover check; Rust behavior is covered by cargo tests."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def req(c,m):
    if not c: raise RuntimeError(m)
def main():
    arch=(ROOT/'gel-core/src/archiver.rs').read_text()
    sync=(ROOT/'gel-core/src/archive_sync_repository.rs').read_text()
    lib=(ROOT/'gel-core/src/lib.rs').read_text()
    tauri=(ROOT/'writer-ui/src-tauri/src/lib.rs').read_text()
    api=(ROOT/'writer-ui/src/api.ts').read_text()
    contract=json.loads((ROOT/'contracts/archive_repository.json').read_text())
    own=json.loads((ROOT/'contracts/state_ownership.json').read_text())
    components=json.loads((ROOT/'contracts/component_boundaries.json').read_text())
    req('pub struct RustArchiver' in arch and 'pub fn sync_full' in arch,'A2 RustArchiver production entry point missing')
    req('acquire_full_snapshot(session)?' in arch and 'materialize_snapshot(&path, snapshot)?' in arch,'A2 must acquire before transactional materialization')
    req('ArchiveSyncRepository::open_existing' in arch and 'SyncScope::Full' in arch,'A2 must use governed D2 transactional repository')
    req('SyncScope::FullPreserveSourceEvidence' in arch and 'preserved_prior_source_evidence' in arch,'A2 partial auxiliary evidence must preserve prior source evidence')
    req('get_student_profile' in arch and 'profile_failures' in arch,'A2 must retain Python-v4.9-compatible optional profile enrichment')
    req('ttype_raw: Some(stored_ttype_raw)' in arch,'A2 print-only state must preserve Python-v4.9 blank source ttype_raw semantics')
    req('fresh_v2_a2_rust' in arch and '.a2-incomplete-' in arch and 'fs::rename(&temp, path)' in arch,'A2 atomic fresh database creation missing')
    req('api_unique_timestamp+print' in arch,'A2 print-only per-ID proof rule missing')
    req('SharedIdenticalCollision' in arch and 'AmbiguousDivergentCollision' in arch and 'IncompleteCollisionEvidence' in arch,'A2 collision authority handling incomplete')
    req('pub mod archiver;' in lib and 'RustArchiver' in lib,'A2 public orchestration API not exported')
    req('mod archive_sync_repository;' in lib and 'pub mod archive_sync_repository' not in lib,'low-level SQLite writer must remain crate-private')
    req('ui1_sync_archive' in tauri and 'RustArchiver::sync_full' in tauri and 'syncArchive' in api,'Writer has no explicit governed A2 sync action')
    req('post_tutorial' not in tauri,'A2 must not grant GEL tutorial mutation authority')
    req(contract.get('phase')=='A2' and contract.get('ownership',{}).get('a2_cutover') is True,'archive repository contract has not cut over to A2')
    states={s['id']:s for s in own['state_classes']}
    req(states['normalized_local_archive']['permitted_writers']==['rust_archive_sync_repository'],'normalized local archive writer ownership not transferred to Rust')
    comps={c['id']:c for c in components['components']}
    req(comps['python_archiver_oracle']['status']=='historical_reference','Python archiver oracle must be historical/reference after A2')
    req(comps['rust_archive_sync_repository']['status']=='active_a2_canonical','Rust archive component must be active A2 canonical writer')
    req('candidate/offline until A2' not in sync,'stale D2 candidate-only source comment remains')
    print('check:a2-archiver PASS — Rust canonical writer + atomic v2 creation + acquire-before-transaction + collision-safe materialization + explicit UI sync')
    return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e: print(f'check:a2-archiver FAIL — {e}',file=sys.stderr); raise SystemExit(1)
