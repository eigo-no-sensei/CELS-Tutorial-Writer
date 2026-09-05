#!/usr/bin/env sh
set -eu
grep -q '^pub mod fixture_compare;' src/lib.rs
grep -q 'gel_core::fixture_compare' src/bin/compare_edit_fixtures.rs
printf '%s\n' 'Comparator module wiring: OK'
