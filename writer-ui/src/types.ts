export type TutorialType = "standard" | "initial" | "final";
export type DraftStatus = "clean" | "dirty" | "stale_source" | "invalid";

export interface SessionInfo {
  authenticated: boolean;
}

export interface ArchiveStatus {
  configured: boolean;
  readable: boolean;
  message: string;
}

export interface ArchiveSyncReport {
  classes: number;
  students: number;
  memberships: number;
  tutorialIdentities: number;
  sourceStates: number;
  provenPerTutorial: number;
  sharedIdenticalCollisions: number;
  blockedCollisions: number;
  unmatchedWithoutState: number;
  summaryFailures: number;
  printFailures: number;
  profileFailures: number;
  editFailures: number;
  preservedPriorSourceEvidence: boolean;
  httpRequests: number;
}

export interface ArchiveClassView {
  classId: number;
  name: string;
  courseCode: string | null;
  active: boolean;
}

export interface StudentView {
  studentId: number;
  name: string;
  courseStartDate: string | null;
  courseEndDate: string | null;
  attendance: number | null;
  lastTutorialDate: string | null;
  lastTutorialType: TutorialType | null;
}

export interface TutorialListView {
  tutorialId: number;
  type: TutorialType | null;
  date: string | null;
  teacherName: string | null;
  absent: boolean | null;
  overallLevel: string | null;
  revisionAvailable: boolean;
  authorityStatus: string | null;
}

export interface SkillLevelView {
  speaking: string | null;
  useOfEnglish: string | null;
  writing: string | null;
  listening: string | null;
}

export interface AssessmentView {
  listening: string | null;
  reading: string | null;
  writing: string | null;
  speaking: string | null;
  vocabulary: string | null;
  grammar: string | null;
  pronunciation: string | null;
}

export interface ExamView {
  intent: string | null;
  examType: string | null;
  when: string | null;
}

export type TutorialSemanticField = "tutorial_date" | "overall_level" | "teacher_read_only" | "absent" | "initial_speaking" | "initial_use_of_english" | "initial_writing" | "initial_listening" | "current_speaking" | "current_use_of_english" | "current_writing" | "current_listening" | "reading" | "assessment_listening" | "assessment_reading" | "assessment_writing" | "assessment_speaking" | "assessment_vocabulary" | "assessment_grammar" | "assessment_pronunciation" | "aims" | "teacher_comments" | "additional_comments" | "initial_course_type" | "exam_intent" | "exam_type" | "exam_when";

export interface DraftFieldRuleView { field: TutorialSemanticField; disposition: "editable" | "read_only" | "hidden_preserved" | "inapplicable";
}

export interface DraftOptionView {
  value: string;
  label: string;
}

export interface AimsAssistanceView {
  available: boolean;
  version: string | null;
  items: string[];
}

export interface DraftFormContractView {
  fields: DraftFieldRuleView[];
  levelOptions: DraftOptionView[];
  assessmentOptions: DraftOptionView[];
  initialCourseTypeOptions: DraftOptionView[];
  teacherCommentsMaxChars: number;
  additionalCommentsMaxChars: number;
  aimsAssistance: AimsAssistanceView;
}

export interface InitialCourseTypeView {
  status: "unset" | "recognized" | "unrecognized_preserved";
  value: string | null;
  preservedText: string | null;
}

export interface DraftValidationIssue {
  code: string;
  field: string | null;
  severity: "error" | "warning";
  message: string;
  priorValue: string | null;
  candidateValue: string | null;
}

export interface DraftView {
  draftId: number;
  status: DraftStatus;
  origin: "new" | "revision";
  tutorialType: TutorialType;
  tutorialDate: string;
  teacherDisplay: string | null;
  teacherAuthority: "authenticated_new_form" | "historical_revision";
  absent: boolean;
  overallLevel: string | null;
  formContract: DraftFormContractView;
  initialCourseType: InitialCourseTypeView | null;
  initial: SkillLevelView;
  current: SkillLevelView;
  reading: string | null;
  assessment: AssessmentView;
  exam: ExamView;
  aims: string;
  teacherComments: string;
  additionalComments: string;
}

export type FourSkill = "speaking" | "use_of_english" | "writing" | "listening";
export type AssessmentSkill = FourSkill | "reading" | "vocabulary" | "grammar" | "pronunciation";
export type TutorialDraftEdit =
  | { kind: "set_tutorial_date"; value: string }
  | { kind: "set_absent"; value: boolean }
  | { kind: "set_overall_level"; value: string | null }
  | { kind: "set_initial_level"; skill: FourSkill; value: string | null }
  | { kind: "set_current_level"; skill: FourSkill; value: string | null }
  | { kind: "set_reading"; value: string | null }
  | { kind: "set_assessment"; skill: AssessmentSkill; value: string | null }
  | { kind: "set_aims"; value: string }
  | { kind: "set_teacher_comments"; value: string }
  | { kind: "set_additional_comments"; value: string }
  | { kind: "set_initial_course_type"; value: string };

export interface HarperSuggestionDto {
  /**
   * Short human-readable label previewing the suggested fix (e.g.
   * `Replace with "colour"`). Mirrors the label CELS-Report-Generator shows
   * on its suggestion buttons. Used for display only; never parsed for
   * semantic authority.
   */
  label: string;
  /**
   * The complete field text after applying this suggestion. React applies
   * the suggestion by emitting this value as the next typed-edit value — it
   * never interprets Harper spans or constructs replacements itself.
   */
  replacementText: string;
}

export interface HarperFindingDto {
  /** Debug form of harper-core's `LintKind` (e.g. "Spelling", "Formatting"). React uses this only to pick a highlight color variant. */
  lintKind: string;
  /** Stable Harper rule name (e.g. "SpellCheck"). React uses this only for the "Disable rule" action. */
  rule: string;
  message: string;
  /** Matched substring from the source snapshot. Displayed verbatim in the side panel. */
  originalText: string;
  /** Character (Unicode code-point) offset, inclusive, of the matched span within sourceText. Used for inline highlight rendering only. */
  spanStart: number;
  /** Character (Unicode code-point) offset, exclusive, of the matched span within sourceText. Used for inline highlight rendering only. */
  spanEnd: number;
  suggestions: HarperSuggestionDto[];
}

export interface HarperCheckDto {
  field: "aims" | "teacher_comments" | "additional_comments";
  sourceText: string;
  engineVersion: string;
  findings: HarperFindingDto[];
}

export interface HarperDictionaryEntry {
  word: string;
}

export interface HarperDictionaryMutation {
  changed: boolean;
  words: HarperDictionaryEntry[];
}

export interface StudentSearchResult {
  uid: number;
  name: string;
  courseStart: string | null;
  courseEnd: string | null;
  tutorialEnd: string | null;
  inArchive: boolean;
}

export interface StudentSearchParams {
  searchTerm: string;
  page?: number;
  pageSize?: number;
}

export interface StudentSearchResponse {
  results: StudentSearchResult[];
  totalRecords: number;
  page: number;
  pageSize: number;
}

export interface SubmissionReceiptView {
  tutorialId: number;
  tutorialTs: number;
  tutorialType: TutorialType;
  studentUid: number;
  isNew: boolean;
  reconciled: boolean;
}
