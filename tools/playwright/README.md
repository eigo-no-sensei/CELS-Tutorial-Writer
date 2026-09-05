# N2-PW1 Playwright evidence tooling

This directory contains temporary evidence tooling. It is **not** part of the production Tutorial Writer runtime.

`n2_zero_write_evidence.py` launches a fresh headed Chromium session and opens GEL at the real interactive `/corelogin/` page and requires manual login there. It does not accept or read credentials. A context-wide mutation firewall is installed before login and blocks service workers.

The harness distinguishes the interactive login page from the login handshake endpoint: it GETs `/corelogin/`, while the only mutation that may reach GEL is the canonical POST to `/user/login` while the firewall is in `AUTHENTICATION`. If the interactive login flow attempts any other mutation, the request is still aborted, but the terminal immediately prints only `phase`, HTTP `method`, `origin`, and a `redacted_path`. Query parameters, body, headers, cookies and credential values are not printed or persisted. This diagnostic exists only to identify the real login route before any allowlist change. Once the operator confirms login, every tutorial mutation is blocked. An explicitly armed `/study/tutorials/process` POST may be transiently reduced to allowlisted structural evidence, but it is always aborted.

Run:

```fish
python tools/playwright/n2_zero_write_evidence.py --student-uid 123456
```

Evidence is privacy-safe and defaults to `evidence-private/n2-playwright/`, which is gitignored. Never move raw browser captures, cookies, HAR/trace output or screenshots into this directory; those artefacts are outside the PW1 contract.


## v13.6 authentication flow

PW1 keeps the mutation firewall armed throughout authentication. The operator first submits `/corelogin/` manually. PW1 then performs a GET-only `/administration/students` session verification without inspecting response bodies, headers, cookies, username or password values. If Learn2 is not yet authenticated but the canonical login POST was observed, PW1 opens `/user/login` in the same ephemeral context and asks the operator to complete that GEL form manually, then repeats the GET-only verification. PW1 enters EVIDENCE only after verification succeeds.

## v13.9 persisted-evidence privacy metadata

The live evidence document is initialized through `initial_evidence_document()`, which immediately runs the same strict privacy validator used before file write. Safety-policy metadata deliberately avoids forbidden raw-data field names: page-source, submission-payload, network-header and staff-display-label capture are represented as disabled boolean capabilities. The forbidden-key guard itself is unchanged.
