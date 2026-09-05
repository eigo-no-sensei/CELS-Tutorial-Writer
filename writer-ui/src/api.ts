import { invoke } from "@tauri-apps/api/core";
import type {
  ArchiveClassView,
  ArchiveStatus,
  ArchiveSyncReport,
  DraftView,
  SessionInfo,
  StudentView,
  TutorialDraftEdit,
  TutorialListView,
  TutorialType,
  HarperCheckDto,
  HarperDictionaryEntry,
  HarperDictionaryMutation,
  SubmissionReceiptView,
} from "./types";

export const sessionStatus = () => invoke<SessionInfo>("ui1_session_status");
export const login = (username: string, password: string) =>
  invoke<SessionInfo>("ui1_login", { username, password });
export const logout = () => invoke<void>("ui1_logout");
export const archiveStatus = () => invoke<ArchiveStatus>("ui1_archive_status");
export const syncArchive = () => invoke<ArchiveSyncReport>("ui1_sync_archive");
export const listClasses = () => invoke<ArchiveClassView[]>("ui1_list_classes");
export const listStudents = (classId: number) =>
  invoke<StudentView[]>("ui1_list_students", { classId });
export const listTutorials = (studentId: number) =>
  invoke<TutorialListView[]>("ui1_list_tutorials", { studentId });
export const openNewDraft = (studentId: number, tutorialType: TutorialType) =>
  invoke<DraftView>("ui1_open_new_draft", { studentId, tutorialType });
export const openRevisionDraft = (tutorialId: number) =>
  invoke<DraftView>("ui1_open_revision_draft", { tutorialId });
export const getDraft = () => invoke<DraftView | null>("ui1_get_draft");
export const applyDraftEdit = (edit: TutorialDraftEdit) =>
  invoke<DraftView>("ui1_apply_draft_edit", { edit });
export const discardDraft = () => invoke<void>("ui1_discard_draft");
export const submitDraft = () => invoke<SubmissionReceiptView>("ui1_submit_draft");

export const harperCheck = (
  field: HarperCheckDto["field"],
  text: string,
  disabledRules: string[] = [],
  suppressedKinds: string[] = [],
) =>
  invoke<HarperCheckDto>("ui1_harper_check", {
    field,
    text,
    disabledRules,
    suppressedKinds,
  });
export const harperDictionaryList = () =>
  invoke<HarperDictionaryEntry[]>("ui1_harper_dictionary_list");
export const harperDictionaryAdd = (word: string) =>
  invoke<HarperDictionaryMutation>("ui1_harper_dictionary_add", { word });
export const harperDictionaryRemove = (word: string) =>
  invoke<HarperDictionaryMutation>("ui1_harper_dictionary_remove", { word });
