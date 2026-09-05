import {
  AllCommunityModule,
  ModuleRegistry,
  themeQuartz,
  type ColDef,
} from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useMemo } from "react";
import type { StudentView, TutorialListView, TutorialType } from "../types";
import { formatAttendance, formatCourseRange, formatLastTutorial, formatTutorialType } from "../viewFormat";

ModuleRegistry.registerModules([AllCommunityModule]);

interface Props {
  student: StudentView | null;
  tutorials: TutorialListView[];
  authenticated: boolean;
  busy: boolean;
  onOpenNew: (tutorialType: TutorialType) => void;
  onOpenRevision: (tutorial: TutorialListView) => void;
}

export function StudentOverview({ student, tutorials, authenticated, busy, onOpenNew, onOpenRevision }: Props) {
  const columns = useMemo<ColDef<TutorialListView>[]>(() => [
    { field: "date", headerName: "Date", width: 118 },
    {
      field: "type",
      headerName: "Type",
      width: 112,
      valueFormatter: ({ value }) => formatTutorialType(value ?? null),
    },
    { field: "overallLevel", headerName: "Level", width: 92 },
    { field: "teacherName", headerName: "Teacher", flex: 1, minWidth: 145 },
  ], []);

  const defaultColDef = useMemo<ColDef>(() => ({
    sortable: true,
    filter: true,
    resizable: true,
    editable: false,
    suppressMovable: true,
  }), []);

  if (!student) {
    return (
      <section className="student-overview empty-overview">
        <div className="empty-state compact-empty">
          Select a student to see course context, tutorial history, and New Tutorial actions.
        </div>
      </section>
    );
  }

  return (
    <section className="student-overview" aria-label="Selected student">
      <header className="student-summary-header">
        <div>
          <p className="eyebrow">Selected student</p>
          <h2>{student.name}</h2>
        </div>
        <div className="student-facts" aria-label="Student course facts">
          <span><strong>Course</strong>{formatCourseRange(student.courseStartDate, student.courseEndDate)}</span>
          <span><strong>Attendance</strong>{formatAttendance(student.attendance)}</span>
          <span><strong>Last tutorial</strong>{formatLastTutorial(student.lastTutorialDate, student.lastTutorialType)}</span>
        </div>
      </header>

      <div className="new-tutorial-actions">
        <button type="button" className="primary" disabled={!authenticated || busy} onClick={() => onOpenNew("standard")}>New Standard</button>
        <button type="button" disabled={!authenticated || busy} onClick={() => onOpenNew("initial")}>New Initial</button>
        <button type="button" disabled={!authenticated || busy} onClick={() => onOpenNew("final")}>New Final</button>
        {!authenticated && <span className="subtle">Log in to open authoritative GEL forms.</span>}
      </div>

      <div className="history-heading">
        <div>
          <h3>Recent tutorials</h3>
          <p className="subtle">Newest first · double-click a tutorial to revise</p>
        </div>
      </div>
      <div className="ag-theme-quartz overview-history-grid">
        <AgGridReact<TutorialListView>
          theme={themeQuartz}
          rowData={tutorials}
          columnDefs={columns}
          defaultColDef={defaultColDef}
          getRowId={({ data }) => String(data.tutorialId)}
          onRowDoubleClicked={(event) => {
            if (event.data) onOpenRevision(event.data);
          }}
        />
      </div>
    </section>
  );
}
