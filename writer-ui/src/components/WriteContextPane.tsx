import type { DraftView, StudentView } from "../types";
import { formatAttendance, formatCourseRange, formatLastTutorial } from "../viewFormat";

interface Props {
  student: StudentView | null;
  draft: DraftView;
  collapsed: boolean;
  onToggle: () => void;
  onBack: () => void;
}

export function WriteContextPane({ student, draft, collapsed, onToggle, onBack }: Props) {
  if (collapsed) {
    return (
      <aside className="write-context-pane collapsed" aria-label="Student context collapsed">
        <button type="button" className="rail-toggle" onClick={onToggle} title="Show student context" aria-label="Show student context">›</button>
      </aside>
    );
  }

  return (
    <aside className="write-context-pane" aria-label="Student context">
      <div className="write-context-topline">
        <button type="button" className="text-button" onClick={onBack}>← Back to student</button>
        <button type="button" className="rail-toggle" onClick={onToggle} title="Collapse student context" aria-label="Collapse student context">‹</button>
      </div>
      <p className="eyebrow">Writing</p>
      <h2>{student?.name ?? "Active tutorial"}</h2>
      <span className="tutorial-type-badge">{draft.tutorialType}</span>
      {student && (
        <dl className="context-facts">
          <div><dt>Course</dt><dd>{formatCourseRange(student.courseStartDate, student.courseEndDate)}</dd></div>
          <div><dt>Attendance</dt><dd>{formatAttendance(student.attendance)}</dd></div>
          <div><dt>Last tutorial</dt><dd>{formatLastTutorial(student.lastTutorialDate, student.lastTutorialType)}</dd></div>
        </dl>
      )}
      <div className="context-note">
        This draft is held only in Rust process memory. UI1 has no GEL submission command.
      </div>
    </aside>
  );
}
