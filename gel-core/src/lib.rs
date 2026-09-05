pub mod archive_repository;
mod archive_sync_repository;
pub mod archiver;
pub mod edit_form_parser;
pub mod edit_form_validation;
pub mod fixture_compare;
pub mod fixture_support;
mod form_parser_common;
pub mod gel_fields;
pub mod gel_session;
pub mod harper;
pub mod live_student_search_parser;
pub mod models;
pub mod new_form_parser;
pub mod post_mapper;
pub mod print_parser;
pub mod reconciliation;
pub mod semantic;
pub mod summary_parser;

pub use archive_repository::{
    ArchiveClass, ArchiveClassStudent, ArchiveRepository, ArchiveRevisionAvailability,
    ArchiveRevisionBlockReason, ArchiveStudent, ArchiveTutorialListItem, ARCHIVE_SCHEMA_VERSION,
};
pub use archiver::{ArchiveSyncReport, RustArchiver};
pub use edit_form_parser::parse_edit_form;
pub use edit_form_validation::{validate_edit_form, EditFormValidationError};
pub use fixture_compare::{
    compare_edit_fixture_dirs, ComparisonStatus, FieldComparison, FixtureComparisonReport,
    FixtureSummary,
};
pub use gel_session::GelSession;
pub use harper::{
    check_text as check_harper_text, HarperCheckDto, HarperDictionaryEntry,
    HarperDictionaryMutation, HarperDictionaryRepository, HarperFindingDto, HarperSuggestionDto,
    HARPER_DICTIONARY_ENV, HARPER_DICTIONARY_FILE_NAME, HARPER_VERSION,
};
pub use live_student_search_parser::{
    LiveStudentSearchInfoFooter, LiveStudentSearchParseReport, LiveStudentSearchResponse,
    LiveStudentSearchResult, LiveStudentSearchRow, LiveStudentSearchRowView, parse_optional_iso_date,
};
pub use models::{
    CollisionStateKind, HistoricalStateAuthority, HistoricalStateAuthorityStatus,
    RevisionBlockReason, RevisionStateError, RevisionStateEvidence,
};
pub use new_form_parser::{
    parse_new_tutorial_form, NewTutorialFormError, NewTutorialFormFailureKind,
    ValidatedNewTutorialForm,
};
pub use post_mapper::{
    build_new_tutorial_post_payload, build_revision_tutorial_post_payload,
    build_tutorial_post_payload, NewTutorialSubmission, RevisionTutorialSubmission,
    TutorialPostPayload,
};
pub use print_parser::parse_print_page;
pub use reconciliation::pair_tutorials_with_summary;
pub use semantic::{
    apply_tutorial_draft_edit, build_revision_form_state, initial_course_type_state,
    tutorial_field_disposition, tutorial_field_rules, validate_semantic_form_state,
    ArchivedTutorial, AssessmentSkill, DraftOrigin, DraftValidationCode, DraftValidationIssue,
    DraftValidationSeverity, FieldDisposition, FourSkill, InitialCourseType,
    InitialCourseTypeState, LevelRegressionBaseline, TutorialDraftEdit, TutorialFieldRule,
    TutorialFormState, TutorialSemanticField, TutorialType, ValidatedNewFormTeacher,
    UI1C_FORM_FIELDS,
};
pub use summary_parser::parse_tutorial_summary;

pub mod submission_transport;
pub use submission_transport::{submit_tutorial_draft, SubmissionError, SubmissionReceipt};
