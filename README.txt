UI1d migration repair overlay

Fixes legacy Harper dictionary migration so a legacy array/object schema 0 is persisted as schema_version 1 when first loaded. Future schema versions remain fail-closed and are never downgraded.

Overlay:
  gel-core/src/harper.rs

Verify:
  cargo test -p gel-core --test ui1d_harper -- --nocapture
  python -S tools/check_ui1d_harper.py
  python -S tools/check_contracts.py
  python -S tools/check_governance.py
  python -S tools/check_intake.py --mode source
