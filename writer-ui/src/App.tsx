import { useEffect, useMemo, useRef, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import {
  applyDraftEdit,
  submitDraft,
  archiveStatus,
  discardDraft,
  getDraft,
  listClasses,
  listStudents,
  listTutorials,
  login,
  logout,
  openNewDraft,
  openRevisionDraft,
  sessionStatus,
  syncArchive,
  harperDictionaryAdd,
} from "./api";
import { DiscardDraftDialog } from "./components/DiscardDraftDialog";
import { ConfirmSubmitDialog } from "./components/ConfirmSubmitDialog";
import { DraftFoundationPanel } from "./components/DraftFoundationPanel";
import { LoginPanel } from "./components/LoginPanel";
import { StudentListPane } from "./components/StudentListPane";
import { StudentOverview } from "./components/StudentOverview";
import { WriteContextPane } from "./components/WriteContextPane";
import { StudentSearchPane } from "./components/StudentSearchPane";
import type {
  ArchiveClassView,
  ArchiveStatus,
  DraftView,
  StudentView,
  TutorialDraftEdit,
  TutorialListView,
  TutorialType,
  DraftValidationIssue,
  StudentSearchResult,
} from "./types";

function errorText(error: unknown): string {
  if (typeof error === "string") return error;
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null && "message" in error) {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string") return message;
  }
  return "Unexpected error";
}

function asDraftValidationIssue(error: unknown): DraftValidationIssue | null {
  if (typeof error !== "object" || error === null) return null;
  const value = error as Partial<DraftValidationIssue>;
  if (typeof value.code !== "string" || typeof value.message !== "string") return null;
  if (value.severity !== "error" && value.severity !== "warning") return null;
  if (!("field" in value)) return null;
  return value as DraftValidationIssue;
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [archive, setArchive] = useState<ArchiveStatus | null>(null);
  const [classes, setClasses] = useState<ArchiveClassView[]>([]);
  const [classId, setClassId] = useState<number | null>(null);
  const [students, setStudents] = useState<StudentView[]>([]);
  const [studentSearch, setStudentSearch] = useState("");
  const [studentId, setStudentId] = useState<number | null>(null);
  const [tutorials, setTutorials] = useState<TutorialListView[]>([]);
  const [draft, setDraft] = useState<DraftView | null>(null);
  const [contextCollapsed, setContextCollapsed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [syncingArchive, setSyncingArchive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draftIssue, setDraftIssue] = useState<DraftValidationIssue | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [pendingNavigation, setPendingNavigation] = useState<null | (() => Promise<void> | void)>(null);
  const [pendingAction, setPendingAction] = useState("continuing");
  const [disabledHarperRules, setDisabledHarperRules] = useState<string[]>([]);
  const [ignoredHarperFindings, setIgnoredHarperFindings] = useState<Set<string>>(new Set());
  const [harperDictionaryRevision, setHarperDictionaryRevision] = useState(0);
  const [showStudentSearch, setShowStudentSearch] = useState(false);
  const [selectedSearchStudents, setSelectedSearchStudents] = useState<Set<number>>(new Set());
  const [searchStudentsToAdd, setSearchStudentsToAdd] = useState<StudentSearchResult[]>([]);

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
  }, []);

  function handleDisableHarperRule(rule: string) {
    setDisabledHarperRules((current) => (current.includes(rule) ? current : [...current, rule]));
  }

  function handleIgnoreHarperFinding(key: string) {
    setIgnoredHarperFindings((current) => {
      if (current.has(key)) return current;
      const next = new Set(current);
      next.add(key);
      return next;
    });
  }

  async function handleAddHarperDictionaryTerm(word: string) {
    await harperDictionaryAdd(word);
    setHarperDictionaryRevision((revision) => revision + 1);
  }

  function bumpHarperDictionaryRevision() {
    setHarperDictionaryRevision((revision) => revision + 1);
  }

  const selectedStudent = useMemo(
    () => students.find((student) => student.studentId === studentId) ?? null,
                                  [students, studentId],
  );

  useEffect(() => {
    Promise.allSettled([sessionStatus(), archiveStatus(), getDraft()]).then(([session, archiveResult, draftResult]) => {
      if (session.status === "fulfilled") setAuthenticated(session.value.authenticated);
      if (archiveResult.status === "fulfilled") setArchive(archiveResult.value);
      if (draftResult.status === "fulfilled") setDraft(draftResult.value);
    });
  }, []);

  useEffect(() => {
    if (!archive?.readable) return;
    listClasses().then(setClasses).catch((value) => setError(errorText(value)));
  }, [archive?.readable]);

  function guardDraft(action: string, next: () => Promise<void> | void) {
    if (draft?.status === "dirty") {
      setPendingAction(action);
      setPendingNavigation(() => next);
      return;
    }
    void next();
  }

  async function chooseClass(nextClassId: number | null) {
    guardDraft("changing class", async () => {
      setClassId(nextClassId);
      setStudentId(null);
      setStudentSearch("");
      setTutorials([]);
      if (nextClassId == null) {
        setStudents([]);
        return;
      }
      try {
        setStudents(await listStudents(nextClassId));
      } catch (value) {
        setError(errorText(value));
      }
    });
  }

  async function chooseStudent(student: StudentView | null) {
    guardDraft("changing student", async () => {
      setStudentId(student?.studentId ?? null);
      if (!student) {
        setTutorials([]);
        return;
      }
      try {
        setTutorials(await listTutorials(student.studentId));
      } catch (value) {
        setError(errorText(value));
      }
    });
  }

  async function doLogin(username: string, password: string) {
    setBusy(true);
    setLoginError(null);
    try {
      const status = await login(username, password);
      setAuthenticated(status.authenticated);
    } catch (value) {
      setLoginError(errorText(value));
      setAuthenticated(false);
    } finally {
      setBusy(false);
    }
  }

  async function doSyncArchive() {
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
  }

  async function doLogout() {
    guardDraft("logging out", async () => {
      await logout();
      setAuthenticated(false);
      setDraft(null);
      setDraftIssue(null);
      setDisabledHarperRules([]);
      setIgnoredHarperFindings(new Set());
      setShowStudentSearch(false);
      setSelectedSearchStudents(new Set());
      setSearchStudentsToAdd([]);
    });
  }

  async function doOpenNew(tutorialType: TutorialType) {
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
  }

  async function doOpenRevision(tutorial: TutorialListView) {
    if (!authenticated) {
      setError("Log in to GEL before opening a Revision tutorial.");
      return;
    }
    if (!tutorial.revisionAvailable) {
      const detail = tutorial.authorityStatus ? ` (${tutorial.authorityStatus})` : "";
      setError(`Revision unavailable because archive authority is blocked${detail}.`);
      return;
    }
    guardDraft("opening another tutorial", async () => {
      setBusy(true);
      setError(null);
      try {
        setDraftIssue(null);
        setDraft(await openRevisionDraft(tutorial.tutorialId));
        setContextCollapsed(false);
      } catch (value) {
        setError(errorText(value));
      } finally {
        setBusy(false);
      }
    });
  }

  async function doEdit(edit: TutorialDraftEdit) {
    setError(null);
    setDraftIssue(null);
    try {
      setDraft(await applyDraftEdit(edit));
    } catch (value) {
      const issue = asDraftValidationIssue(value);
      if (issue) {
        setDraftIssue(issue);
      } else {
        setError(errorText(value));
      }
    }
  }

  async function doDiscard() {
    await discardDraft();
    setDraft(null);
    setContextCollapsed(false);
  }

  function leaveEditor() {
    guardDraft("returning to the student", doDiscard);
  }

  function handleSearchStudentSelect(student: StudentSearchResult) {
    setSelectedSearchStudents((prev) => {
      const next = new Set(prev);
      next.add(student.uid);
      return next;
    });
    setSearchStudentsToAdd((prev) => {
      if (prev.find((s) => s.uid === student.uid)) return prev;
      return [...prev, student];
    });
  }

  function handleSearchStudentDeselect(uid: number) {
    setSelectedSearchStudents((prev) => {
      const next = new Set(prev);
      next.delete(uid);
      return next;
    });
    setSearchStudentsToAdd((prev) => prev.filter((s) => s.uid !== uid));
  }

  async function handleAddSelectedStudents() {
    if (searchStudentsToAdd.length === 0 || classId == null) return;
    setBusy(true);
    setError(null);
    try {
      const updatedStudents = await listStudents(classId);
      setStudents(updatedStudents);
      setShowStudentSearch(false);
      setSelectedSearchStudents(new Set());
      setSearchStudentsToAdd([]);
    } catch (value) {
      setError(errorText(value));
    } finally {
      setBusy(false);
    }
  }

  async function confirmPendingDiscard() {
    const next = pendingNavigation;
    setPendingNavigation(null);
    await doDiscard();
    if (next) await next();
  }

  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function doSubmit() {
    setConfirmSubmitOpen(false);
    setSubmitting(true);
    setError(null);
    try {
      await submitDraft();
      setDraft(null);
      setDraftIssue(null);
      setContextCollapsed(false);
      if (studentId != null) {
        setTutorials(await listTutorials(studentId));
      }
    } catch (value) {
      setError(errorText(value));
    } finally {
      setSubmitting(false);
    }
  }

  const writing = draft != null;

  return (
    <main className={`app-shell ${writing ? "mode-write" : "mode-browse"}`}>
    <header className="app-header">
    <div>
    <h1>GEL Tutorial Writer</h1>
    <p>{writing ? "Write mode · editor focused" : "Browse mode · find student, review history, start tutorial"}</p>
    </div>
    <div className="header-status">
    {syncingArchive ? (
      <span className="syncing-badge">⏳ Synchronizing archive from GEL…</span>
    ) : (
      <span className={archive?.readable ? "ok" : "warning"}>{archive?.message ?? "Checking archive…"}</span>
    )}
    {authenticated ? (
      <>
      <button
      type="button"
      className={`secondary ${syncingArchive ? "syncing" : ""}`}
      disabled={busy || writing || syncingArchive}
      onClick={() => void doSyncArchive()}
      >
      {syncingArchive ? "Syncing archive…" : "Sync archive"}
      </button>
      <button type="button" className="secondary" onClick={doLogout}>Log out</button>
      </>
    ) : <span className="warning">GEL read session not authenticated</span>}
    </div>
    </header>

    {!authenticated && !writing && <LoginPanel busy={busy} error={loginError} onLogin={doLogin} />}
    {error && <div className="error-banner global-error">{error}</div>}

    {showStudentSearch && (
      <div className="student-search-modal-overlay">
        <div className="student-search-modal">
          <div className="modal-header">
            <h2>Add Students to Class</h2>
            <button
              type="button"
              className="close-btn"
              onClick={() => {
                setShowStudentSearch(false);
                setSelectedSearchStudents(new Set());
                setSearchStudentsToAdd([]);
              }}
              aria-label="Close search"
            >
              ✕
            </button>
          </div>
          <StudentSearchPane
            onStudentSelect={handleSearchStudentSelect}
            onStudentDeselect={handleSearchStudentDeselect}
            selectedStudents={selectedSearchStudents}
          />
          <div className="modal-footer">
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setShowStudentSearch(false);
                setSelectedSearchStudents(new Set());
                setSearchStudentsToAdd([]);
              }}
              disabled={busy}
            >
              Cancel
            </button>
            <button
              type="button"
              className="primary"
              onClick={() => void handleAddSelectedStudents()}
              disabled={busy || searchStudentsToAdd.length === 0}
            >
              Add {searchStudentsToAdd.length} Student{searchStudentsToAdd.length !== 1 ? 's' : ''} to Class
            </button>
          </div>
        </div>
      </div>
    )}

    {!writing ? (
      <>
      <section className="workspace-toolbar" aria-label="Browse controls">
      <label>
      Class
      <select value={classId ?? ""} disabled={busy} onChange={(event) => void chooseClass(event.target.value ? Number(event.target.value) : null)}>
      <option value="">Choose class…</option>
      {classes.map((item) => <option key={item.classId} value={item.classId}>{item.name}{item.courseCode ? ` · ${item.courseCode}` : ""}</option>)}
      </select>
      </label>
      <button
        type="button"
        className="primary"
        onClick={() => setShowStudentSearch(true)}
        disabled={busy || !classId}
        title={classId ? "Search and add students to this class" : "Select a class first"}
      >
        Add Students
      </button>
      <label className="student-search-control">
      Search students
      <input type="search" value={studentSearch} placeholder="Find student…" onChange={(event) => setStudentSearch(event.target.value)} />
      </label>
      </section>
      <div className="browse-workspace">
      <StudentListPane
      students={students}
      studentId={studentId}
      studentSearch={studentSearch}
      busy={busy}
      onStudentChange={chooseStudent}
      />
      <StudentOverview
      student={selectedStudent}
      tutorials={tutorials}
      authenticated={authenticated}
      busy={busy}
      onOpenNew={doOpenNew}
      onOpenRevision={doOpenRevision}
      />
      </div>
      </>
    ) : (
      <div className={`write-workspace ${contextCollapsed ? "context-collapsed" : ""}`}>
      <WriteContextPane
      student={selectedStudent}
      draft={draft}
      collapsed={contextCollapsed}
      onToggle={() => setContextCollapsed((value) => !value)}
      onBack={leaveEditor}
      />
      <DraftFoundationPanel
      draft={draft}
      onEdit={doEdit}
      onDiscard={doDiscard}
      onSubmit={() => setConfirmSubmitOpen(true)}
      isSubmitting={submitting}
      validationIssue={draftIssue}
      disabledHarperRules={disabledHarperRules}
      ignoredHarperFindings={ignoredHarperFindings}
      onDisableHarperRule={handleDisableHarperRule}
      onIgnoreHarperFinding={handleIgnoreHarperFinding}
      onAddHarperDictionaryTerm={handleAddHarperDictionaryTerm}
      harperDictionaryRevision={harperDictionaryRevision}
      onHarperDictionaryMutation={bumpHarperDictionaryRevision}
      />
      </div>
    )}

    <ConfirmSubmitDialog
    open={confirmSubmitOpen}
    studentName={selectedStudent?.name ?? "Student"}
    tutorialType={draft?.tutorialType ?? "Standard"}
    tutorialDate={draft?.tutorialDate ?? ""}
    isNew={draft?.origin === "new"}
    onConfirm={() => void doSubmit()}
    onCancel={() => setConfirmSubmitOpen(false)}
    />

    <DiscardDraftDialog
    open={pendingNavigation != null}
    action={pendingAction}
    onDiscard={() => void confirmPendingDiscard()}
    onStay={() => setPendingNavigation(null)}
    />
    </main>
  );
}
