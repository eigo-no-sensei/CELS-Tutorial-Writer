# Fixtures

`synthetic/` contains non-sensitive fixtures that are safe to keep in source
control.

The live fixture bundle created by `../tools/capture_gel_fixtures.py` should
remain outside the repository (for example `../fixtures-private`). Raw files can
contain student, teacher, tutorial and comment data.

The edit parser now retains both forms of Standard Aims state:

- raw hidden `input[name="trecs-79"]` submission backing value;
- visible `#tcinput[contenteditable][name="trecs-79"]` historical editor value.

Example private-fixture inspection:

```fish
cargo run --bin inspect_fixture -- edit ../fixtures-private/raw/edit_forms/standard_full_mixed.html
cargo run --bin inspect_fixture -- summary ../fixtures-private/raw/reconciliation/duplicate_different_state/summary.html
cargo run --bin inspect_fixture -- print ../fixtures-private/raw/reconciliation/duplicate_different_state/print_route.html
```
