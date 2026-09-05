#!/usr/bin/env python3
"""fix_sync_progress_ui.py — Add responsive progress feedback to archive sync."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Enforce no bytecode generation
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")

def write(rel: str, content: str) -> None:
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.rstrip() + "\n", encoding="utf-8")
    print(f"  [✓] updated: {rel}")

print("=== 1. Updating writer-ui/src/App.tsx ===")
app = read("writer-ui/src/App.tsx")

# Add syncingArchive state
if "const [syncingArchive, setSyncingArchive] = useState(false);" not in app:
    app = app.replace(
        "  const [busy, setBusy] = useState(false);",
        "  const [busy, setBusy] = useState(false);\n  const [syncingArchive, setSyncingArchive] = useState(false);"
    )

# Update doSyncArchive with immediate status message and syncing state
old_do_sync = """  async function doSyncArchive() {
    if (!authenticated) return;
    setBusy(true);
    setError(null);
    try {
      const report = await syncArchive();
      const nextArchive = await archiveStatus();
      setArchive({
        ...nextArchive,
        message: `Archive synchronized: ${report.classes} classes, ${report.students} students, ${report.tutorialIdentities} tutorials${report.preservedPriorSourceEvidence ? " (prior source evidence preserved for partial auxiliary reads)" : ""}.`,
      });
      setClasses(nextArchive.readable ? await listClasses() : []);
      setClassId(null);
      setStudents([]);
      setStudentId(null);
      setTutorials([]);
    } catch (value) {
      setError(errorText(value));
    } finally {
      setBusy(false);
    }
  }"""

new_do_sync = """  async function doSyncArchive() {
    if (!authenticated || syncingArchive) return;
    setSyncingArchive(true);
    setBusy(true);
    setError(null);
    const prevMessage = archive?.message;
    setArchive((prev) => prev ? { ...prev, message: "Synchronizing archive from GEL (fetching classes, students & tutorials)…" } : null);
    try {
      const report = await syncArchive();
      const nextArchive = await archiveStatus();
      setArchive({
        ...nextArchive,
        message: `Archive synchronized: ${report.classes} classes, ${report.students} students, ${report.tutorialIdentities} tutorials${report.preservedPriorSourceEvidence ? " (prior source evidence preserved)" : ""}.`,
      });
      setClasses(nextArchive.readable ? await listClasses() : []);
      setClassId(null);
      setStudents([]);
      setStudentId(null);
      setTutorials([]);
    } catch (value) {
      setError(errorText(value));
      if (prevMessage) {
        setArchive((prev) => prev ? { ...prev, message: prevMessage } : null);
      }
    } finally {
      setSyncingArchive(false);
      setBusy(false);
    }
  }"""

if old_do_sync in app:
    app = app.replace(old_do_sync, new_do_sync)
else:
    # Generic replacement if spacing differs
    app = re.sub(r'async function doSyncArchive\(\)\s*\{.*?finally\s*\{\s*setBusy\(false\);\s*\}\s*\}', new_do_sync, app, flags=re.S)

# Update Sync button label and header status display
app = app.replace(
    '<button type="button" className="secondary" disabled={busy || writing} onClick={() => void doSyncArchive()}>Sync archive</button>',
    '<button type="button" className={`secondary ${syncingArchive ? "syncing" : ""}`} disabled={busy || writing || syncingArchive} onClick={() => void doSyncArchive()}>{syncingArchive ? "Syncing archive…" : "Sync archive"}</button>'
)

old_header_status = """        <div className="header-status">
          <span className={archive?.readable ? "ok" : "warning"}>{archive?.message ?? "Checking archive…"}</span>"""

new_header_status = """        <div className="header-status">
          {syncingArchive ? (
            <span className="syncing-badge">⏳ Synchronizing archive from GEL…</span>
          ) : (
            <span className={archive?.readable ? "ok" : "warning"}>{archive?.message ?? "Checking archive…"}</span>
          )}"""

app = app.replace(old_header_status, new_header_status)
write("writer-ui/src/App.tsx", app)

print("=== 2. Adding Syncing Badge CSS to writer-ui/src/styles/app.css ===")
css = read("writer-ui/src/styles/app.css")
if ".syncing-badge" not in css:
    css += """

/* Archive sync progress indicator */
.syncing-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  background: #e0f2fe;
  color: #0369a1;
  border: 1px solid #bae6fd;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  animation: pulse-sync 1.6s infinite ease-in-out;
}

@keyframes pulse-sync {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.65; transform: scale(0.98); }
}

button.syncing {
  cursor: wait;
}
"""
    write("writer-ui/src/styles/app.css", css)

# Cleanup bytecode
for p in list(ROOT.rglob("__pycache__")):
    shutil.rmtree(p, ignore_errors=True)
for p in list(ROOT.rglob("*.pyc")):
    p.unlink(missing_ok=True)

print("=== Fix Complete! ===")