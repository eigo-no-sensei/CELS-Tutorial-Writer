import {
  AllCommunityModule,
  ModuleRegistry,
  themeQuartz,
  type ColDef,
  type RowClickedEvent,
} from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useMemo } from "react";
import type { StudentView } from "../types";
import { formatAttendance, formatCourseRange, formatLastTutorial } from "../viewFormat";

ModuleRegistry.registerModules([AllCommunityModule]);

interface Props {
  students: StudentView[];
  studentId: number | null;
  studentSearch: string;
  busy: boolean;
  onStudentChange: (student: StudentView | null) => void;
}

export function StudentListPane({ students, studentId, studentSearch, busy, onStudentChange }: Props) {
  const columns = useMemo<ColDef<StudentView>[]>(() => [
    { field: "name", headerName: "Student", flex: 1.7, minWidth: 150 },
    {
      colId: "course",
      headerName: "Course",
      flex: 1.35,
      minWidth: 145,
      valueGetter: ({ data }) => data ? formatCourseRange(data.courseStartDate, data.courseEndDate) : "—",
    },
    {
      field: "attendance",
      headerName: "Attendance",
      width: 112,
      valueFormatter: ({ value }) => formatAttendance(value ?? null),
    },
    {
      colId: "lastTutorial",
      headerName: "Last tutorial",
      flex: 1.25,
      minWidth: 145,
      valueGetter: ({ data }) => data ? formatLastTutorial(data.lastTutorialDate, data.lastTutorialType) : "—",
    },
  ], []);

  const defaultColDef = useMemo<ColDef>(() => ({
    sortable: true,
    filter: true,
    resizable: true,
    editable: false,
    suppressMovable: true,
  }), []);

  return (
    <section className="student-list-pane" aria-label="Students">
      <div className="pane-heading">
        <div>
          <h2>Students</h2>
          <p className="subtle">{students.length} in current class</p>
        </div>
      </div>
      <div className="ag-theme-quartz student-grid">
        <AgGridReact<StudentView>
          theme={themeQuartz}
          rowData={students}
          quickFilterText={studentSearch}
          columnDefs={columns}
          defaultColDef={defaultColDef}
          getRowId={({ data }) => String(data.studentId)}
          rowSelection={{ mode: "singleRow", enableClickSelection: true, checkboxes: false }}
          onRowClicked={(event: RowClickedEvent<StudentView>) => {
            if (!busy) onStudentChange(event.data ?? null);
          }}
          rowClassRules={{ "row-focused": ({ data }) => data?.studentId === studentId }}
        />
      </div>
    </section>
  );
}
