use gel_core::semantic::{
    apply_tutorial_draft_edit, build_new_form_state, build_revision_form_state,
    initial_course_type_state, tutorial_field_rules, AssessmentValue, CefrLevel, InitialCourseType,
    InitialCourseTypeState, SkillScores, TutorialFormState, TutorialType,
};
use gel_core::{
    check_harper_text, parse_edit_form, parse_new_tutorial_form, validate_edit_form,
    ArchiveRepository, ArchiveRevisionAvailability, ArchiveSyncReport, DraftValidationIssue,
    GelSession, HarperCheckDto, HarperDictionaryEntry, HarperDictionaryMutation,
    HarperDictionaryRepository, LiveStudentSearchRow, RustArchiver, TutorialDraftEdit,
    HARPER_DICTIONARY_ENV, HARPER_DICTIONARY_FILE_NAME,
};
use serde::Serialize;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, RwLock};
use tauri::{AppHandle, Manager, State};

pub struct WriterAppState {
    session: Mutex<Option<GelSession>>,
    draft: RwLock<Option<LoadedTutorialDraft>>,
    writer_operation: Mutex<()>,
    archive_path: Option<PathBuf>,
    harper_dictionary: HarperDictionaryRepository,
    next_draft_id: AtomicU64,
}

impl WriterAppState {
    fn new(archive_path: Option<PathBuf>, harper_dictionary_path: PathBuf) -> Self {
        Self {
            session: Mutex::new(None),
            draft: RwLock::new(None),
            writer_operation: Mutex::new(()),
            archive_path,
            harper_dictionary: HarperDictionaryRepository::new(harper_dictionary_path),
            next_draft_id: AtomicU64::new(1),
        }
    }

    fn open_archive(&self) -> Result<ArchiveRepository, String> {
        let path = self.archive_path.as_ref().ok_or_else(|| {
            format!(
                "No archive-v2 database resolved: set GEL_ARCHIVE_DB or place {DEFAULT_ARCHIVE_DB_NAME} beside the application executable on Windows (project root on non-Windows); Tutorial Writer will not create an archive database"
            )
        })?;
        ArchiveRepository::open_read_only(path)
            .map_err(|error| format!("open archive read-only: {error}"))
    }

    fn next_draft_id(&self) -> u64 {
        self.next_draft_id.fetch_add(1, Ordering::Relaxed)
    }
}

#[derive(Clone)]
struct LoadedTutorialDraft {
    id: u64,
    base: TutorialFormState,
    current: TutorialFormState,
    stale: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SessionInfo {
    authenticated: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ArchiveStatus {
    configured: bool,
    readable: bool,
    message: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ArchiveClassView {
    class_id: i64,
    name: String,
    course_code: Option<String>,
    active: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct StudentView {
    student_id: i64,
    name: String,
    course_start_date: Option<String>,
    course_end_date: Option<String>,
    attendance: Option<i64>,
    last_tutorial_date: Option<String>,
    last_tutorial_type: Option<&'static str>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct StudentSearchResultView {
    student_uid: i64,
    code: String,
    name: String,
    created_at: Option<String>,
    course_start: Option<String>,
    course_end: Option<String>,
    tutorial_end: Option<String>,
    tutor_date: Option<String>,
    tutor_name: Option<String>,
    absent: bool,
    in_archive: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct TutorialListView {
    tutorial_id: i64,
    #[serde(rename = "type")]
    tutorial_type: Option<&'static str>,
    date: Option<String>,
    teacher_name: Option<String>,
    absent: Option<bool>,
    overall_level: Option<String>,
    revision_available: bool,
    authority_status: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SkillLevelView {
    speaking: Option<String>,
    use_of_english: Option<String>,
    writing: Option<String>,
    listening: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct AssessmentView {
    listening: Option<&'static str>,
    reading: Option<&'static str>,
    writing: Option<&'static str>,
    speaking: Option<&'static str>,
    vocabulary: Option<&'static str>,
    grammar: Option<&'static str>,
    pronunciation: Option<&'static str>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ExamView {
    intent: Option<String>,
    exam_type: Option<String>,
    when: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DraftFieldRuleView {
    field: gel_core::TutorialSemanticField,
    disposition: gel_core::FieldDisposition,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DraftOptionView {
    value: String,
    label: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct AimsAssistanceView {
    available: bool,
    version: Option<&'static str>,
    items: Vec<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DraftFormContractView {
    fields: Vec<DraftFieldRuleView>,
    level_options: Vec<DraftOptionView>,
    assessment_options: Vec<DraftOptionView>,
    initial_course_type_options: Vec<DraftOptionView>,
    teacher_comments_max_chars: usize,
    additional_comments_max_chars: usize,
    aims_assistance: AimsAssistanceView,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct InitialCourseTypeView {
    status: &'static str,
    value: Option<String>,
    preserved_text: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct SubmissionReceiptView {
    tutorial_id: i64,
    tutorial_ts: i64,
    tutorial_type: &'static str,
    student_uid: i64,
    is_new: bool,
    reconciled: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct DraftView {
    draft_id: u64,
    status: &'static str,
    origin: &'static str,
    tutorial_type: &'static str,
    tutorial_date: String,
    teacher_display: Option<String>,
    teacher_authority: &'static str,
    absent: bool,
    overall_level: Option<String>,
    form_contract: DraftFormContractView,
    initial_course_type: Option<InitialCourseTypeView>,
    initial: SkillLevelView,
    current: SkillLevelView,
    reading: Option<String>,
    assessment: AssessmentView,
    exam: ExamView,
    aims: String,
    teacher_comments: String,
    additional_comments: String,
}

#[tauri::command]
fn ui1_session_status(state: State<'_, WriterAppState>) -> Result<SessionInfo, String> {
    let session = state
        .session
        .lock()
        .map_err(|_| "session lock poisoned".to_string())?;
    Ok(SessionInfo {
        authenticated: session.as_ref().is_some_and(GelSession::is_authenticated),
    })
}

#[tauri::command]
fn ui1_login(
    state: State<'_, WriterAppState>,
    username: String,
    password: String,
) -> Result<SessionInfo, String> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;
    let mut session =
        GelSession::new().map_err(|error| format!("create GEL read session: {error}"))?;
    let result = session.login(&username, &password);
    drop(username);
    drop(password);
    match result {
        Ok(()) => {
            *state
                .session
                .lock()
                .map_err(|_| "session lock poisoned".to_string())? = Some(session);
            Ok(SessionInfo {
                authenticated: true,
            })
        }
        Err(error) => {
            *state
                .session
                .lock()
                .map_err(|_| "session lock poisoned".to_string())? = None;
            Err(format!("GEL login failed: {error}"))
        }
    }
}

#[tauri::command]
fn ui1_logout(state: State<'_, WriterAppState>) -> Result<(), String> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;
    *state
        .session
        .lock()
        .map_err(|_| "session lock poisoned".to_string())? = None;
    *state
        .draft
        .write()
        .map_err(|_| "draft lock poisoned".to_string())? = None;
    Ok(())
}

#[tauri::command]
async fn ui1_sync_archive(app: AppHandle) -> Result<ArchiveSyncReport, String> {
    let report = tauri::async_runtime::spawn_blocking(move || -> Result<ArchiveSyncReport, String> {
        let state = app.state::<WriterAppState>();
        let archive_path = state.archive_path.as_ref().cloned().ok_or_else(|| {
            format!(
                "No archive path resolved: set GEL_ARCHIVE_DB or use the platform default {DEFAULT_ARCHIVE_DB_NAME}"
            )
        })?;

        let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;
        let mut session = state
        .session
        .lock()
        .map_err(|_| "session lock poisoned".to_string())?;
        let session = session
        .as_mut()
        .filter(|session| session.is_authenticated())
        .ok_or_else(|| {
            "an authenticated GEL session is required to synchronize the archive".to_string()
        })?;
        let report = RustArchiver::sync_full(session, &archive_path)
        .map_err(|error| format!("synchronize canonical Rust archive: {error:#}"))?;

        if let Ok(mut draft_guard) = state.draft.write() {
            if let Some(loaded) = draft_guard.as_mut() {
                if let Ok(repository) = ArchiveRepository::open_read_only(&archive_path) {
                    match &loaded.current.origin {
                        gel_core::semantic::DraftOrigin::New {
                            prepopulation_source,
                            ..
                        } => {
                            let latest_id = repository
                            .list_tutorials_for_student(loaded.current.student_uid, false)
                            .ok()
                            .and_then(|list| list.into_iter().next())
                            .map(|t| t.tutorial_id);
                            let source_id = prepopulation_source.as_ref().map(|s| s.tutorial_id);
                            if latest_id != source_id {
                                loaded.stale = true;
                            }
                        }
                        gel_core::semantic::DraftOrigin::Revision { source, .. } => {
                            match repository.revision_source(source.tutorial_id) {
                                Ok(ArchiveRevisionAvailability::Available { .. }) => {}
                                _ => {
                                    loaded.stale = true;
                                }
                            }
                        }
                    }
                }
            }
        }

        Ok(report)
    })
    .await
    .map_err(|e| format!("background sync task failed: {e}"))??;

    Ok(report)
}

#[tauri::command]
fn ui1_archive_status(state: State<'_, WriterAppState>) -> ArchiveStatus {
    let Some(path) = state.archive_path.as_ref() else {
        return ArchiveStatus {
            configured: false,
            readable: false,
            message: format!(
                "Set GEL_ARCHIVE_DB or use the platform default {DEFAULT_ARCHIVE_DB_NAME}; after GEL login, Sync archive can atomically create a missing schema-v2 database"
            ),
        };
    };
    match ArchiveRepository::open_read_only(path) {
        Ok(_) => ArchiveStatus {
            configured: true,
            readable: true,
            message: "Archive v2 ready (Rust A2 canonical archive)".into(),
        },
        Err(_) => ArchiveStatus {
            configured: true,
            readable: false,
            message: "Archive is missing or invalid; authenticated Sync archive may create a missing DB, but an existing invalid/non-v2 DB fails closed".into(),
        },
    }
}

#[tauri::command]
fn ui1_list_classes(state: State<'_, WriterAppState>) -> Result<Vec<ArchiveClassView>, String> {
    let repository = state.open_archive()?;
    repository
        .list_classes(false)
        .map_err(|error| format!("list archive classes: {error}"))
        .map(|items| {
            items
                .into_iter()
                .map(|item| ArchiveClassView {
                    class_id: item.class_id,
                    name: item
                        .name
                        .unwrap_or_else(|| format!("Class {}", item.class_id)),
                    course_code: item.course_code,
                    active: item.is_active,
                })
                .collect()
        })
}

#[tauri::command]
fn ui1_list_students(
    state: State<'_, WriterAppState>,
    class_id: i64,
) -> Result<Vec<StudentView>, String> {
    let repository = state.open_archive()?;
    let items = repository
        .list_students_for_class(class_id, false)
        .map_err(|error| format!("list class students: {error}"))?;
    let mut views = Vec::with_capacity(items.len());
    for item in items {
        let latest = repository
            .list_tutorials_for_student(item.student.uid, false)
            .map_err(|error| {
                format!(
                    "derive latest tutorial for student {} from canonical history: {error}",
                    item.student.uid
                )
            })?
            .into_iter()
            .next();
        views.push(StudentView {
            student_id: item.student.uid,
            name: item
                .student
                .name
                .unwrap_or_else(|| format!("Student {}", item.student.uid)),
            course_start_date: item.student.start_date,
            course_end_date: item.student.end_date,
            attendance: item.attendance,
            last_tutorial_date: latest
                .as_ref()
                .and_then(|tutorial| tutorial.custom_date.clone()),
            last_tutorial_type: latest
                .and_then(|tutorial| tutorial.tutorial_type)
                .map(tutorial_type_name),
        });
    }
    Ok(views)
}

#[tauri::command]
fn ui1_list_tutorials(
    state: State<'_, WriterAppState>,
    student_id: i64,
) -> Result<Vec<TutorialListView>, String> {
    let repository = state.open_archive()?;
    repository
        .list_tutorials_for_student(student_id, false)
        .map_err(|error| format!("list student tutorials: {error}"))
        .map(|items| {
            items
                .into_iter()
                .map(|item| TutorialListView {
                    tutorial_id: item.tutorial_id,
                    tutorial_type: item.tutorial_type.map(tutorial_type_name),
                    date: item.custom_date,
                    teacher_name: item.teacher_name,
                    absent: item.absent,
                    overall_level: compact_level_display(item.overall_level),
                    revision_available: item.revision_available,
                    authority_status: item.authority_status.map(|status| format!("{status:?}")),
                })
                .collect()
        })
}

#[tauri::command]
fn ui1_open_new_draft(
    state: State<'_, WriterAppState>,
    student_id: i64,
    tutorial_type: String,
) -> Result<DraftView, String> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;
    let tutorial_type = parse_tutorial_type_name(&tutorial_type)?;
    let repository = state.open_archive()?;
    let list = repository
        .list_tutorials_for_student(student_id, false)
        .map_err(|error| format!("list latest tutorial source: {error}"))?;
    let latest = match list.first() {
        None => None,
        Some(item) => match repository
            .revision_source(item.tutorial_id)
            .map_err(|error| format!("load latest tutorial source: {error}"))?
        {
            ArchiveRevisionAvailability::Available { tutorial } => Some(*tutorial),
            ArchiveRevisionAvailability::Blocked { reason } => {
                return Err(format!(
                    "latest tutorial cannot authoritatively prepopulate a New draft: {reason:?}"
                ))
            }
            ArchiveRevisionAvailability::NotFound => {
                return Err("latest tutorial identity disappeared from the archive".into())
            }
        },
    };

    let html = {
        let mut session = state
            .session
            .lock()
            .map_err(|_| "session lock poisoned".to_string())?;
        let session = session
            .as_mut()
            .filter(|session| session.is_authenticated())
            .ok_or_else(|| {
                "an authenticated GEL read session is required to open a New draft".to_string()
            })?;
        session
            .get_new_tutorial_form_html(student_id, tutorial_type.ttype())
            .map_err(|error| format!("fetch authoritative GEL New form: {error}"))?
    };
    let form = parse_new_tutorial_form(&html, student_id, tutorial_type.ttype())
        .map_err(|error| format!("validate authoritative GEL New form: {error}"))?;
    let semantic = build_new_form_state(latest.as_ref(), &form)
        .map_err(|error| format!("construct governed New semantic draft: {error}"))?;
    install_draft(&state, semantic)
}

#[tauri::command]
fn ui1_open_revision_draft(
    state: State<'_, WriterAppState>,
    tutorial_id: i64,
) -> Result<DraftView, String> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;
    let repository = state.open_archive()?;
    let archive = match repository
        .revision_source(tutorial_id)
        .map_err(|error| format!("load Revision authority: {error}"))?
    {
        ArchiveRevisionAvailability::Available { tutorial } => *tutorial,
        ArchiveRevisionAvailability::Blocked { reason } => {
            return Err(format!(
                "Revision is blocked by archive authority: {reason:?}"
            ))
        }
        ArchiveRevisionAvailability::NotFound => return Err("tutorial not found in archive".into()),
    };

    let html = {
        let mut session = state
            .session
            .lock()
            .map_err(|_| "session lock poisoned".to_string())?;
        let session = session
            .as_mut()
            .filter(|session| session.is_authenticated())
            .ok_or_else(|| {
                "an authenticated GEL session is required to open a Revision draft".to_string()
            })?;
        session
            .get_tutorial_edit_html(
                archive.identity.student_uid,
                archive.identity.tutorial_ts,
                archive.identity.tutorial_type.ttype(),
            )
            .map_err(|error| format!("fetch authoritative GEL Revision form: {error}"))?
    };
    let parsed =
        parse_edit_form(&html).map_err(|error| format!("parse GEL Revision form: {error}"))?;
    let validated = validate_edit_form(&parsed)
        .map_err(|error| format!("validate GEL Revision form: {error}"))?;
    let semantic = build_revision_form_state(&archive, &validated)
        .map_err(|error| format!("construct governed Revision semantic draft: {error}"))?;
    install_draft(&state, semantic)
}

#[tauri::command]
fn ui1_get_draft(state: State<'_, WriterAppState>) -> Result<Option<DraftView>, String> {
    let mut draft = state
        .draft
        .write()
        .map_err(|_| "draft lock poisoned".to_string())?;
    let Some(loaded) = draft.as_mut() else {
        return Ok(None);
    };

    let is_authenticated = state
        .session
        .lock()
        .map_err(|_| "session lock poisoned".to_string())?
        .as_ref()
        .is_some_and(GelSession::is_authenticated);
    if matches!(
        loaded.current.origin,
        gel_core::semantic::DraftOrigin::New { .. }
    ) && !is_authenticated
    {
        loaded.stale = true;
    }

    Ok(Some(draft_view(loaded)))
}

#[tauri::command]
fn ui1_apply_draft_edit(
    state: State<'_, WriterAppState>,
    edit: TutorialDraftEdit,
) -> Result<DraftView, DraftValidationIssue> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| DraftValidationIssue::internal("writer operation lock poisoned"))?;
    let mut draft = state
        .draft
        .write()
        .map_err(|_| DraftValidationIssue::internal("draft lock poisoned"))?;
    let loaded = draft
        .as_mut()
        .ok_or_else(DraftValidationIssue::no_active_draft)?;

    let is_authenticated = state
        .session
        .lock()
        .map_err(|_| DraftValidationIssue::internal("session lock poisoned"))?
        .as_ref()
        .is_some_and(GelSession::is_authenticated);
    if matches!(
        loaded.current.origin,
        gel_core::semantic::DraftOrigin::New { .. }
    ) && !is_authenticated
    {
        loaded.stale = true;
    }

    if loaded.stale {
        return Err(DraftValidationIssue::internal(
            "Draft source authority is stale; direct editing is locked until draft is discarded",
        ));
    }

    loaded.current = apply_tutorial_draft_edit(&loaded.current, edit)?;
    Ok(draft_view(loaded))
}

#[tauri::command]
fn ui1_submit_draft(state: State<'_, WriterAppState>) -> Result<SubmissionReceiptView, String> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;

    let (draft_current, is_stale) = {
        let draft_guard = state
            .draft
            .read()
            .map_err(|_| "draft lock poisoned".to_string())?;
        let loaded = draft_guard
            .as_ref()
            .ok_or_else(|| "no active draft to submit".to_string())?;
        (loaded.current.clone(), loaded.stale)
    };

    if is_stale {
        return Err(
            "cannot submit draft with stale source authority; please discard and reopen".into(),
        );
    }

    let mut session_guard = state
        .session
        .lock()
        .map_err(|_| "session lock poisoned".to_string())?;
    let session = session_guard
        .as_mut()
        .filter(|s| s.is_authenticated())
        .ok_or_else(|| {
            "an authenticated GEL session is required to submit a tutorial".to_string()
        })?;

    let receipt = gel_core::submission_transport::submit_tutorial_draft(
        session,
        &draft_current,
        state.archive_path.as_deref(),
    )
    .map_err(|error| format!("submission failed: {error}"))?;

    *state
        .draft
        .write()
        .map_err(|_| "draft lock poisoned".to_string())? = None;

    Ok(SubmissionReceiptView {
        tutorial_id: receipt.tutorial_id,
        tutorial_ts: receipt.tutorial_ts,
        tutorial_type: tutorial_type_name(receipt.tutorial_type),
        student_uid: receipt.student_uid,
        is_new: receipt.is_new,
        reconciled: receipt.reconciled,
    })
}

#[tauri::command]
fn ui1_discard_draft(state: State<'_, WriterAppState>) -> Result<(), String> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;
    *state
        .draft
        .write()
        .map_err(|_| "draft lock poisoned".to_string())? = None;
    Ok(())
}

#[tauri::command]
fn ui1_harper_check(
    state: State<'_, WriterAppState>,
    field: String,
    text: String,
    disabled_rules: Vec<String>,
    suppressed_kinds: Vec<String>,
) -> Result<HarperCheckDto, String> {
    check_harper_text(
        &state.harper_dictionary,
        &field,
        &text,
        &disabled_rules,
        &suppressed_kinds,
    )
    .map_err(|error| format!("Harper check failed: {error}"))
}

#[tauri::command]
fn ui1_harper_dictionary_list(
    state: State<'_, WriterAppState>,
) -> Result<Vec<HarperDictionaryEntry>, String> {
    state
        .harper_dictionary
        .list()
        .map(|words| {
            words
                .into_iter()
                .map(|word| HarperDictionaryEntry { word })
                .collect()
        })
        .map_err(|error| format!("list Harper dictionary: {error}"))
}

#[tauri::command]
fn ui1_harper_dictionary_add(
    state: State<'_, WriterAppState>,
    word: String,
) -> Result<HarperDictionaryMutation, String> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;
    state
        .harper_dictionary
        .add(&word)
        .map_err(|error| format!("add Harper dictionary word: {error}"))
}

#[tauri::command]
fn ui1_harper_dictionary_remove(
    state: State<'_, WriterAppState>,
    word: String,
) -> Result<HarperDictionaryMutation, String> {
    let _operation = state
        .writer_operation
        .lock()
        .map_err(|_| "writer operation lock poisoned".to_string())?;
    state
        .harper_dictionary
        .remove(&word)
        .map_err(|error| format!("remove Harper dictionary word: {error}"))
}

#[tauri::command]
async fn ui1_search_live_students(
    app: AppHandle,
    search_term: String,
) -> Result<Vec<StudentSearchResultView>, String> {
    let results = tauri::async_runtime::spawn_blocking(move || -> Result<Vec<StudentSearchResultView>, String> {
        let state = app.state::<WriterAppState>();
        let _operation = state
            .writer_operation
            .lock()
            .map_err(|_| "writer operation lock poisoned".to_string())?;
        let mut session = state
            .session
            .lock()
            .map_err(|_| "session lock poisoned".to_string())?;
        let session = session
            .as_mut()
            .filter(|s| s.is_authenticated())
            .ok_or_else(|| "an authenticated GEL session is required to search live students".to_string())?;
        
        let rows = session
            .search_live_students(&search_term)
            .map_err(|error| format!("search live students: {error}"))?;
        
        let archive = state.open_archive().ok();
        
        let mut views = Vec::with_capacity(rows.len());
        for row in rows {
            let in_archive = archive
                .as_ref()
                .map(|repo| repo.student_exists(row.student_uid).unwrap_or(false))
                .unwrap_or(false);
            
            views.push(StudentSearchResultView {
                student_uid: row.student_uid,
                code: row.code,
                name: row.name,
                created_at: row.created_at.map(|dt| dt.to_rfc3339()),
                course_start: row.course_start.map(|d| d.format("%Y-%m-%d").to_string()),
                course_end: row.course_end.map(|d| d.format("%Y-%m-%d").to_string()),
                tutorial_end: row.tutorial_end.map(|d| d.format("%Y-%m-%d").to_string()),
                tutor_date: row.tutor_date.map(|d| d.format("%Y-%m-%d").to_string()),
                tutor_name: row.tutor_name,
                absent: row.absent,
                in_archive,
            });
        }
        
        Ok(views)
    })
    .await
    .map_err(|e| format!("background search task failed: {e}"))??;
    
    Ok(results)
}

#[tauri::command]
fn ui1_student_in_archive(
    state: State<'_, WriterAppState>,
    student_uid: i64,
) -> Result<bool, String> {
    let repository = state.open_archive()?;
    repository
        .student_exists(student_uid)
        .map_err(|error| format!("check student existence in archive: {error}"))
}

fn install_draft(state: &WriterAppState, semantic: TutorialFormState) -> Result<DraftView, String> {
    let loaded = LoadedTutorialDraft {
        id: state.next_draft_id(),
        base: semantic.clone(),
        current: semantic,
        stale: false,
    };
    let view = draft_view(&loaded);
    *state
        .draft
        .write()
        .map_err(|_| "draft lock poisoned".to_string())? = Some(loaded);
    Ok(view)
}

fn draft_view(loaded: &LoadedTutorialDraft) -> DraftView {
    let state = &loaded.current;
    let (origin, teacher_authority) = match state.origin {
        gel_core::DraftOrigin::New { .. } => ("new", "authenticated_new_form"),
        gel_core::DraftOrigin::Revision { .. } => ("revision", "historical_revision"),
    };
    let status = if loaded.stale {
        "stale_source"
    } else if loaded.current == loaded.base {
        "clean"
    } else {
        "dirty"
    };
    DraftView {
        draft_id: loaded.id,
        status,
        origin,
        tutorial_type: tutorial_type_name(state.tutorial_type),
        tutorial_date: state.tutorial_date.format("%Y-%m-%d").to_string(),
        teacher_display: state.teacher.teacher_name.clone(),
        teacher_authority,
        absent: state.absent,
        overall_level: state.overall_level.map(level_name),
        form_contract: draft_form_contract_view(state.tutorial_type),
        initial_course_type: (state.tutorial_type == TutorialType::Initial)
            .then(|| initial_course_type_view(&state.teacher_comments)),
        initial: skill_view(&state.initial_scores),
        current: skill_view(&state.current_scores),
        reading: state.reading.map(level_name),
        assessment: AssessmentView {
            listening: state
                .self_assessment
                .listening
                .map(AssessmentValue::ui_value),
            reading: state.self_assessment.reading.map(AssessmentValue::ui_value),
            writing: state.self_assessment.writing.map(AssessmentValue::ui_value),
            speaking: state
                .self_assessment
                .speaking
                .map(AssessmentValue::ui_value),
            vocabulary: state
                .self_assessment
                .vocabulary
                .map(AssessmentValue::ui_value),
            grammar: state.self_assessment.grammar.map(AssessmentValue::ui_value),
            pronunciation: state
                .self_assessment
                .pronunciation
                .map(AssessmentValue::ui_value),
        },
        exam: ExamView {
            intent: state.exam.intent.clone(),
            exam_type: state.exam.exam_type.clone(),
            when: state.exam.when.clone(),
        },
        aims: state.aims.clone(),
        teacher_comments: state.teacher_comments.clone(),
        additional_comments: state.additional_comments.clone(),
    }
}

fn draft_form_contract_view(tutorial_type: TutorialType) -> DraftFormContractView {
    DraftFormContractView {
        fields: tutorial_field_rules(tutorial_type)
            .into_iter()
            .map(|rule| DraftFieldRuleView {
                field: rule.field,
                disposition: rule.disposition,
            })
            .collect(),
        level_options: CefrLevel::all()
            .iter()
            .copied()
            .map(|level| DraftOptionView {
                value: level.form_value().to_string(),
                label: level.form_value().to_string(),
            })
            .collect(),
        assessment_options: AssessmentValue::all()
            .iter()
            .copied()
            .map(|value| DraftOptionView {
                value: value.ui_value().to_string(),
                label: value.display_label().to_string(),
            })
            .collect(),
        initial_course_type_options: InitialCourseType::all()
            .iter()
            .copied()
            .map(|value| DraftOptionView {
                value: value.storage_value().to_string(),
                label: value.storage_value().to_string(),
            })
            .collect(),
        teacher_comments_max_chars: gel_core::gel_fields::TEACHER_COMMENTS_MAX_CHARS,
        additional_comments_max_chars: gel_core::gel_fields::ADDITIONAL_COMMENTS_MAX_CHARS,
        aims_assistance: AimsAssistanceView {
            available: false,
            version: None,
            items: Vec::new(),
        },
    }
}

fn initial_course_type_view(teacher_comments: &str) -> InitialCourseTypeView {
    match initial_course_type_state(teacher_comments) {
        InitialCourseTypeState::Unset => InitialCourseTypeView {
            status: "unset",
            value: None,
            preserved_text: None,
        },
        InitialCourseTypeState::Recognized { value } => InitialCourseTypeView {
            status: "recognized",
            value: Some(value.storage_value().to_string()),
            preserved_text: None,
        },
        InitialCourseTypeState::UnrecognizedPreserved { raw } => InitialCourseTypeView {
            status: "unrecognized_preserved",
            value: None,
            preserved_text: Some(raw),
        },
    }
}

fn skill_view(scores: &SkillScores) -> SkillLevelView {
    SkillLevelView {
        speaking: scores.speaking.map(level_name),
        use_of_english: scores.use_of_english.map(level_name),
        writing: scores.writing.map(level_name),
        listening: scores.listening.map(level_name),
    }
}

fn compact_level_display(raw: Option<String>) -> Option<String> {
    raw.and_then(|raw| {
        let trimmed = raw.trim();
        if trimmed.is_empty() {
            None
        } else {
            Some(
                CefrLevel::parse(trimmed)
                    .map(level_name)
                    .unwrap_or_else(|| trimmed.to_string()),
            )
        }
    })
}

fn level_name(level: CefrLevel) -> String {
    level.form_value().to_string()
}

fn tutorial_type_name(value: TutorialType) -> &'static str {
    match value {
        TutorialType::Standard => "standard",
        TutorialType::Initial => "initial",
        TutorialType::Final => "final",
    }
}

fn parse_tutorial_type_name(value: &str) -> Result<TutorialType, String> {
    match value.trim().to_ascii_lowercase().as_str() {
        "standard" => Ok(TutorialType::Standard),
        "initial" => Ok(TutorialType::Initial),
        "final" => Ok(TutorialType::Final),
        _ => Err("tutorial type must be standard, initial or final".into()),
    }
}

const DEFAULT_ARCHIVE_DB_NAME: &str = "gel-new-v2.db";

fn project_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
}

fn resolve_default_archive_path(
    project_root: &Path,
    executable_path: Option<&Path>,
    windows: bool,
) -> PathBuf {
    if windows {
        if let Some(executable_dir) = executable_path.and_then(Path::parent) {
            return executable_dir.join(DEFAULT_ARCHIVE_DB_NAME);
        }
    }
    project_root.join(DEFAULT_ARCHIVE_DB_NAME)
}

fn resolve_archive_path(
    override_path: Option<PathBuf>,
    project_root: &Path,
    executable_path: Option<&Path>,
    windows: bool,
) -> PathBuf {
    override_path
        .filter(|path| !path.as_os_str().is_empty())
        .unwrap_or_else(|| resolve_default_archive_path(project_root, executable_path, windows))
}

fn archive_path_from_environment() -> Option<PathBuf> {
    let executable_path = std::env::current_exe().ok();
    Some(resolve_archive_path(
        std::env::var_os("GEL_ARCHIVE_DB").map(PathBuf::from),
        &project_root(),
        executable_path.as_deref(),
        cfg!(target_os = "windows"),
    ))
}

fn resolve_harper_dictionary_path(
    override_path: Option<PathBuf>,
    archive_path: Option<&Path>,
    project_root: &Path,
) -> PathBuf {
    if let Some(path) = override_path.filter(|path| !path.as_os_str().is_empty()) {
        return path;
    }
    archive_path
        .and_then(Path::parent)
        .map(|parent| parent.join(HARPER_DICTIONARY_FILE_NAME))
        .unwrap_or_else(|| project_root.join(HARPER_DICTIONARY_FILE_NAME))
}

fn harper_dictionary_path_from_environment(archive_path: Option<&Path>) -> PathBuf {
    resolve_harper_dictionary_path(
        std::env::var_os(HARPER_DICTIONARY_ENV).map(PathBuf::from),
        archive_path,
        &project_root(),
    )
}

#[cfg(test)]
mod archive_path_tests {
    use super::*;

    #[test]
    fn explicit_archive_override_wins_on_windows() {
        let root = Path::new("/project-root");
        let exe = Path::new("C:/Program Files/GEL Tutorial Writer/tutorial-writer.exe");
        let override_path = PathBuf::from("C:/configured/archive-v2.db");
        assert_eq!(
            resolve_archive_path(Some(override_path.clone()), root, Some(exe), true),
            override_path
        );
    }

    #[test]
    fn windows_default_is_beside_running_binary() {
        let root = Path::new("/project-root");
        let exe = Path::new("C:/Portable/GEL Tutorial Writer/tutorial-writer.exe");
        assert_eq!(
            resolve_archive_path(None, root, Some(exe), true),
            PathBuf::from("C:/Portable/GEL Tutorial Writer").join(DEFAULT_ARCHIVE_DB_NAME)
        );
    }

    #[test]
    fn blank_windows_override_uses_binary_directory_default() {
        let root = Path::new("/project-root");
        let exe = Path::new("C:/Portable/GEL Tutorial Writer/tutorial-writer.exe");
        assert_eq!(
            resolve_archive_path(Some(PathBuf::new()), root, Some(exe), true),
            PathBuf::from("C:/Portable/GEL Tutorial Writer").join(DEFAULT_ARCHIVE_DB_NAME)
        );
    }

    #[test]
    fn non_windows_default_remains_project_root() {
        let root = Path::new("/project-root");
        let exe = Path::new("/opt/gel/tutorial-writer");
        assert_eq!(
            resolve_archive_path(None, root, Some(exe), false),
            root.join(DEFAULT_ARCHIVE_DB_NAME)
        );
    }

    #[test]
    fn windows_current_exe_failure_falls_back_to_project_root() {
        let root = Path::new("/project-root");
        assert_eq!(
            resolve_archive_path(None, root, None, true),
            root.join(DEFAULT_ARCHIVE_DB_NAME)
        );
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let archive_path = archive_path_from_environment();
            let harper_dictionary_path =
                harper_dictionary_path_from_environment(archive_path.as_deref());
            app.manage(WriterAppState::new(archive_path, harper_dictionary_path));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            ui1_session_status,
            ui1_login,
            ui1_logout,
            ui1_archive_status,
            ui1_sync_archive,
            ui1_list_classes,
            ui1_list_students,
            ui1_list_tutorials,
            ui1_open_new_draft,
            ui1_open_revision_draft,
            ui1_get_draft,
            ui1_apply_draft_edit,
            ui1_discard_draft,
            ui1_submit_draft,
            ui1_harper_check,
            ui1_harper_dictionary_list,
            ui1_harper_dictionary_add,
            ui1_harper_dictionary_remove,
            ui1_search_live_students,
            ui1_student_in_archive,
        ])
        .run(tauri::generate_context!())
        .expect("error while running GEL Tutorial Writer");
}

#[cfg(test)]
mod harper_path_tests {
    use super::*;

    #[test]
    fn explicit_dictionary_override_wins() {
        let root = Path::new("/project-root");
        let archive = Path::new("/portable/archive/gel-new-v2.db");
        let override_path = PathBuf::from("/configured/harper.json");
        assert_eq!(
            resolve_harper_dictionary_path(Some(override_path.clone()), Some(archive), root),
            override_path
        );
    }

    #[test]
    fn dictionary_defaults_beside_archive() {
        let root = Path::new("/project-root");
        let archive = Path::new("C:/Portable/GEL Tutorial Writer/gel-new-v2.db");
        assert_eq!(
            resolve_harper_dictionary_path(None, Some(archive), root),
            PathBuf::from("C:/Portable/GEL Tutorial Writer").join(HARPER_DICTIONARY_FILE_NAME)
        );
    }

    #[test]
    fn dictionary_falls_back_to_project_root_without_archive() {
        let root = Path::new("/project-root");
        assert_eq!(
            resolve_harper_dictionary_path(None, None, root),
            root.join(HARPER_DICTIONARY_FILE_NAME)
        );
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::NaiveDate;
    use gel_core::semantic::{
        BooleanFieldProvenance, DraftOrigin, FieldSource, TeacherRef, TutorialFormProvenance,
    };

    fn revision_state() -> TutorialFormState {
        TutorialFormState {
            origin: DraftOrigin::Revision {
                source: gel_core::semantic::TutorialIdentity {
                    tutorial_id: 1,
                    student_uid: 2,
                    tutorial_ts: 3,
                    tutorial_type: TutorialType::Standard,
                },
                source_teacher_id: 9,
            },
            student_uid: 2,
            tutorial_type: TutorialType::Standard,
            tutorial_date: NaiveDate::from_ymd_opt(2026, 8, 28).unwrap(),
            teacher: TeacherRef {
                teacher_id: Some(9),
                teacher_name: Some("Teacher".into()),
            },
            absent: false,
            overall_level: Some(CefrLevel::B1),
            initial_scores: SkillScores::default(),
            current_scores: SkillScores::default(),
            reading: None,
            self_assessment: Default::default(),
            exam: Default::default(),
            aims: String::new(),
            teacher_comments: String::new(),
            additional_comments: String::new(),
            provenance: TutorialFormProvenance {
                absent: BooleanFieldProvenance {
                    authoritative_value: false,
                    authoritative_source: FieldSource::Summary,
                    edit_form_value: Some(false),
                    discrepancy: None,
                },
                overall_level_source_raw: Some("B1".into()),
                aims_source_html: None,
            },
        }
    }

    #[test]
    fn typed_edit_surface_cannot_change_revision_teacher_or_identity() {
        let state = revision_state();
        let original_origin = state.origin.clone();
        let original_teacher = state.teacher.clone();
        let changed = apply_tutorial_draft_edit(
            &state,
            TutorialDraftEdit::SetTeacherComments {
                value: "changed".into(),
            },
        )
        .unwrap();
        assert_eq!(changed.origin, original_origin);
        assert_eq!(changed.teacher, original_teacher);
    }

    #[test]
    fn comment_limit_is_unicode_scalar_count() {
        let state = revision_state();
        assert!(apply_tutorial_draft_edit(
            &state,
            TutorialDraftEdit::SetTeacherComments {
                value: "é".repeat(gel_core::gel_fields::TEACHER_COMMENTS_MAX_CHARS),
            },
        )
        .is_ok());
        assert!(apply_tutorial_draft_edit(
            &state,
            TutorialDraftEdit::SetTeacherComments {
                value: "é".repeat(gel_core::gel_fields::TEACHER_COMMENTS_MAX_CHARS + 1),
            },
        )
        .is_err());
    }

    #[test]
    fn draft_status_is_derived_from_base_and_current_state() {
        let base = revision_state();
        let mut loaded = LoadedTutorialDraft {
            id: 1,
            base: base.clone(),
            current: base,
            stale: false,
        };
        assert_eq!(draft_view(&loaded).status, "clean");
        loaded.current.teacher_comments = "dirty".into();
        assert_eq!(draft_view(&loaded).status, "dirty");
        loaded.stale = true;
        assert_eq!(draft_view(&loaded).status, "stale_source");
    }

    #[test]
    fn stale_status_takes_precedence_over_clean_or_dirty() {
        let base = revision_state();
        let mut loaded = LoadedTutorialDraft {
            id: 1,
            base: base.clone(),
            current: base,
            stale: true,
        };
        assert_eq!(draft_view(&loaded).status, "stale_source");
        loaded.current.teacher_comments = "modified".into();
        assert_eq!(draft_view(&loaded).status, "stale_source");
    }

    #[test]
    fn archive_overall_level_is_projected_as_compact_cefr_code() {
        assert_eq!(
            compact_level_display(Some("A2-: pre-intermediate".into())),
            Some("A2-".into()),
        );
        assert_eq!(
            compact_level_display(Some("B1+: intermediate".into())),
            Some("B1+".into()),
        );
        assert_eq!(
            compact_level_display(Some("Ao: beginner".into())),
            Some("A0".into()),
        );
        assert_eq!(compact_level_display(Some("".into())), None);
        assert_eq!(
            compact_level_display(Some("future-level-label".into())),
            Some("future-level-label".into()),
        );
    }

    #[test]
    fn failed_candidate_edit_does_not_mutate_authoritative_draft() {
        let base = revision_state();
        let loaded = LoadedTutorialDraft {
            id: 1,
            base: base.clone(),
            current: base,
            stale: false,
        };
        let before = loaded.current.clone();
        let result = apply_tutorial_draft_edit(
            &loaded.current,
            TutorialDraftEdit::SetInitialLevel {
                skill: gel_core::FourSkill::Speaking,
                value: Some("B1".into()),
            },
        );
        assert!(result.is_err());
        assert_eq!(loaded.current, before);
    }
}
