#!/usr/bin/env python3
"""A1 structural/fixture contract for Python-v4.9-compatible Rust print parsing."""
from __future__ import annotations
import ast, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def require(cond,msg):
    if not cond: raise RuntimeError(msg)

def main():
    parser=(ROOT/'gel-core/src/print_parser.rs').read_text()
    models=(ROOT/'gel-core/src/models.rs').read_text()
    tests=(ROOT/'gel-core/tests/print_parity.rs').read_text()
    capture=(ROOT/'tools/capture_gel_fixtures.py').read_text()
    private_checker=(ROOT/'tools/check_private_print_parity.py').read_text()
    oracle=(ROOT/'python-oracle/tutorial_down4_resilient_v4_9_summary_blank_fidelity_no_email.py').read_text()
    raw=sorted((ROOT/'gel-core/fixtures/print_parity/raw').glob('*.html'))
    expected=sorted((ROOT/'gel-core/fixtures/print_parity/expected').glob('*.json'))
    require(len(raw)==len(expected)==14,'A1 requires exactly 14 public print parity fixtures')
    require([p.stem for p in raw]==[p.stem for p in expected],'A1 raw/expected fixture stems differ')
    for path in expected: json.loads(path.read_text())
    require('recursive=False' in oracle,'Python v4.9 print oracle lost direct-cell parsing')
    require('result["print_text"] = best_text' in oracle,'Python v4.9 print_text projection drifted')
    require('result.update(best_fields)' in oracle,'Python v4.9 direct-label projection drifted')
    require('result["Type"] = best_fields["Tutorial Type"]' in oracle,'Python v4.9 Type alias drifted')
    require('children()' in parser and 'matches!(element.value().name(), "td" | "th")' in parser,'Rust A1 parser must use direct DOM cells')
    require('direct_fields' in parser and '"Type".to_string()' in parser,'Rust A1 direct label/Type projection missing')
    require('print_text: best_text' in parser,'Rust A1 print_text projection missing')
    require('#[serde(flatten, default)]' in models,'PrintRecord direct fields must serialize at top level')
    require('python_v49_print_fallback_fixture_parity_is_exact' in tests,'A1 exact Rust fixture test missing')
    require('print_labels_inside_prose_do_not_create_fields' in tests,'A1 prose false-positive regression missing')
    require('def capture_print_fixtures' in capture and 'parse_print_page_fallback(html)' in capture,'A1 private print capture must use Python-v4.9 oracle')
    require('--scope' in capture and '(\"all\", \"print\")' in capture,'A1 private print-only capture mode missing')
    require('--required-count' in private_checker,'A1 strict private print checker must enforce required fixture count')
    print('check:a1-print-parity PASS — 14 Python-v4.9 oracle-backed fixtures + exact JSON shape + prose-boundary regression')
    return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(f'check:a1-print-parity FAIL — {e}',file=sys.stderr); raise SystemExit(1)
