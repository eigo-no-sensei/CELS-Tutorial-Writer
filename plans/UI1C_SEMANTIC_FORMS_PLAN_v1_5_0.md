# UI1c semantic forms plan v1.5.0

**Status:** UI1c5 implemented pending strict acceptance  
**Date:** 2026-08-31

UI1c5 is the integrated validation/release closure for the already implemented Standard, Initial and Final semantic forms. Strict GRI acceptance was recorded at **PASS=39 / SKIP=0 / FAIL=0** and authorizes this implementation, but the changed source identity must pass a new strict `ui1c5` scope.

## UI1c5 implementation

- Adds `gel-core/tests/ui1c5_integrated.rs` covering New Standard/Initial/Final reconstruction together.
- Proves all seven Standard assessment mutations remain typed semantic edits.
- Proves Initial hidden exam state and unrecognized course-type storage survive unrelated edits.
- Proves Final Initial/current roles remain independent with Reading/current-only semantics.
- Proves rejected New same-role regression returns structured `LEVEL_REGRESSION` and leaves prior state unchanged.
- Proves Revision source identity and teacher authority remain immutable and Revision has no New regression floor.
- Adds `tools/check_ui1c5_integrated.py` and a two-check extension over the accepted 39-check GRI baseline.
- Adds no GEL tutorial write, teacher reassignment, persistent tutorial draft, frontend semantic authority, or archive-writer capability.

## Strict exit

Run the `ui1c5` strict release scope. The target is **PASS=41 / SKIP=0 / FAIL=0**, `TARGET STATUS: STRICT_ACCEPTED`, with immutable evidence written outside the source tree. UI1d begins only after that result is recorded.
