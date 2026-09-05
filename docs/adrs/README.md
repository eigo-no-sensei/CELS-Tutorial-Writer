# Architecture Decision Records — historical only

ADRs record historical decisions and rationale with explicit status. They are never current runtime authority; current behaviour is defined by higher-ranked executable contracts/tests and active specs. Superseded phase plans and acceptance narratives belong under docs/history/ or an external evidence store.

Every ADR file named `ADR-*.md` must declare one of these statuses near the top:

- `proposed`
- `accepted_historical`
- `superseded`
- `rejected`

An accepted historical ADR records why a decision was made. If current executable contracts/specs later change, the ADR is not edited into runtime authority; mark it `superseded` where appropriate and update the active authority instead.
