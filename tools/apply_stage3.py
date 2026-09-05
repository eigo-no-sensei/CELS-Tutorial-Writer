#!/usr/bin/env python3
"""apply_stage3.py — Apply UI1e Stage 3 frontend window close and staleness guards."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel: str, content: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"  [✓] updated: {rel}")

print("=== 1. Updating writer-ui/src/App.tsx ===")
app_tsx = read("writer-ui/src/App.tsx")

# Add getCurrentWindow import
if 'getCurrentWindow' not in app_tsx:
    app_tsx = app_tsx.replace(
        'import { useEffect, useMemo, useState } from "react";',
        'import { useEffect, useMemo, useRef, useState } from "react";\nimport { getCurrentWindow } from "@tauri-apps/api/window";'
    )

# Add window close listener and ref inside App
window_listener_code = """  const [harperDictionaryRevision, setHarperDictionaryRevision] = useState(0);

  const draftRef = useRef(draft);
  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  // Native window close interception: intercept OS close when draft is dirty
  useEffect(() => {
    let unlisten: (() => void) | undefined;
    let mounted = true;

    try {
      getCurrentWindow()
        .onCloseRequested(async (event) => {
          if (draftRef.current?.status === "dirty") {
            event.preventDefault();
            setPendingAction("closing the application");
            setPendingNavigation(() => async () => {
              try {
                await getCurrentWindow().destroy();
              } catch {
                // Ignore if destroy fails or outside Tauri runtime
              }
            });
          }
        })
        .then((fn) => {
          if (mounted) {
            unlisten = fn;
          } else {
            fn();
          }
        })
        .catch(() => {
          // Ignore outside Tauri runtime
        });
    } catch {
      // Ignore outside Tauri runtime
    }

    return () => {
      mounted = false;
      if (unlisten) unlisten();
    };
  }, []);"""

app_tsx = app_tsx.replace(
    "  const [harperDictionaryRevision, setHarperDictionaryRevision] = useState(0);",
    window_listener_code
)

# Guard doOpenNew if not yet guarded
old_open_new = """  async function doOpenNew(tutorialType: TutorialType) {
    if (studentId == null) return;
    setBusy(true)
    setError(null);
    try {
      setDraft(await openNewDraft(studentId, tutorialType));
      setContextCollapsed(false);
    } catch (value) {
      setError(errorText(value));
    } finally {
      setBusy(false);
    }
  }"""
new_open_new = """  async function doOpenNew(tutorialType: TutorialType) {
    if (studentId == null) return;
    guardDraft("opening a new tutorial", async () => {
      setBusy(true);
      setError(null);
      try {
        setDraftIssue(null);
        setDraft(await openNewDraft(studentId, tutorialType));
        setContextCollapsed(false);
      } catch (value) {
        setError(errorText(value));
      } finally {
        setBusy(false);
      }
    });
  }"""
if old_open_new in app_tsx:
    app_tsx = app_tsx.replace(old_open_new, new_open_new)
elif 'guardDraft("opening a new tutorial"' not in app_tsx:
    app_tsx = app_tsx.replace(
        "async function doOpenNew(tutorialType: TutorialType) {\n    if (studentId == null) return;",
        "async function doOpenNew(tutorialType: TutorialType) {\n    if (studentId == null) return;\n    guardDraft(\"opening a new tutorial\", async () => {"
    )

# Flush Harper suppression state on logout
logout_target = """  async function doLogout() {
    guardDraft("logging out", async () => {
      await logout();
      setAuthenticated(false);
      setDraft(null);
      setDraftIssue(null);
    });
  }"""
logout_replacement = """  async function doLogout() {
    guardDraft("logging out", async () => {
      await logout();
      setAuthenticated(false);
      setDraft(null);
      setDraftIssue(null);
      setDisabledHarperRules([]);
      setIgnoredHarperFindings(new Set());
    });
  }"""
app_tsx = app_tsx.replace(logout_target, logout_replacement)
write("writer-ui/src/App.tsx", app_tsx)

print("=== 2. Updating writer-ui/src/components/DraftFoundationPanel.tsx ===")
panel = read("writer-ui/src/components/DraftFoundationPanel.tsx")

# Make ruleFor and isEditable convert editable to read_only when stale or invalid
rule_for_target = """function ruleFor(draft: DraftView, field: TutorialSemanticField): DraftFieldRuleView | undefined {
  return draft.formContract.fields.find((rule) => rule.field === field);
}

export function isEditable(draft: DraftView, field: TutorialSemanticField): boolean {
  return ruleFor(draft, field)?.disposition === "editable";
}"""

rule_for_replacement = """function ruleFor(draft: DraftView, field: TutorialSemanticField): DraftFieldRuleView | undefined {
  const rule = draft.formContract.fields.find((r) => r.field === field);
  if (!rule) return undefined;
  if (draft.status === "stale_source" || draft.status === "invalid") {
    return {
      ...rule,
      disposition: rule.disposition === "editable" ? "read_only" : rule.disposition,
    };
  }
  return rule;
}

export function isEditable(draft: DraftView, field: TutorialSemanticField): boolean {
  if (draft.status === "stale_source" || draft.status === "invalid") {
    return false;
  }
  return ruleFor(draft, field)?.disposition === "editable";
}"""

panel = panel.replace(rule_for_target, rule_for_replacement)

# Add actionable stale_source banner
stale_banner = """          <DraftValidationIssueSummary issue={validationIssue} />

          {draft.status === "stale_source" && (
            <div className="error-banner draft-stale-banner" role="alert">
              <div>
                <strong>Draft source authority invalidated.</strong>
                <p style={{ margin: "4px 0 0" }}>
                  {draft.origin === "new"
                    ? "The authenticated GEL session has expired or the student's latest tutorial has drifted. Direct editing is locked."
                    : "The historical tutorial source in the archive is no longer available or has drifted. Direct editing is locked."}
                </p>
              </div>
              <button type="button" className="secondary" onClick={onDiscard}>
                Discard draft
              </button>
            </div>
          )}"""

panel = panel.replace("          <DraftValidationIssueSummary issue={validationIssue} />", stale_banner)
write("writer-ui/src/components/DraftFoundationPanel.tsx", panel)

print("=== 3. Adding CSS styling to writer-ui/src/styles/app.css ===")
css = read("writer-ui/src/styles/app.css")
if ".draft-stale-banner" not in css:
    css += """

.draft-stale-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 6px 0 10px;
  border-left: 4px solid #b84b4b;
}
"""
    write("writer-ui/src/styles/app.css", css)

print("=== 4. Updating tools/check_ui1e_safety.py with Stage 3 checks ===")
safety = read("tools/check_ui1e_safety.py")
stage3_assertions = """        # Stage 3 Frontend Native Dirty-Close & Navigation Guards verification
        app_tsx = read("writer-ui/src/App.tsx")
        require("onCloseRequested" in app_tsx, "App.tsx must listen for onCloseRequested event")
        require("closing the application" in app_tsx, "App.tsx must trigger discard dialog for window close")
        require("guardDraft(\\"opening a new tutorial\\"" in app_tsx, "doOpenNew must guard active dirty drafts")
        require("setDisabledHarperRules([])" in app_tsx, "doLogout must flush session-only Harper rules")

        foundation = read("writer-ui/src/components/DraftFoundationPanel.tsx")
        require("draft-stale-banner" in foundation, "DraftFoundationPanel must render stale source banner")
        require('draft.status === "stale_source"' in foundation, "DraftFoundationPanel must evaluate stale_source status")
"""

if "Stage 3 Frontend Native" not in safety:
    safety = safety.replace(
        'print("check:ui1e-safety PASS — window close interception + discard guards + backend staleness guards verified")',
        stage3_assertions + '\n    print("check:ui1e-safety PASS — window close interception + discard guards + backend staleness guards verified")'
    )
    write("tools/check_ui1e_safety.py", safety)

print("=== Stage 3 Complete! ===")