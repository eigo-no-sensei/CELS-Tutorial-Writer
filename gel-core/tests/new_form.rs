use gel_core::semantic::TutorialIdentity;
use gel_core::{parse_new_tutorial_form, DraftOrigin, NewTutorialFormFailureKind, TutorialType};

const NEW_STANDARD: &str = include_str!("../fixtures/synthetic/new_standard.html");
const NEW_INITIAL: &str = include_str!("../fixtures/synthetic/new_initial.html");
const NEW_FINAL: &str = include_str!("../fixtures/synthetic/new_final.html");

#[test]
fn validates_sanitized_standard_initial_and_final_new_forms() {
    for (html, code) in [(NEW_STANDARD, "0"), (NEW_INITIAL, "2"), (NEW_FINAL, "1")] {
        let form = parse_new_tutorial_form(html, 200, code).unwrap();
        assert_eq!(form.student_uid(), 200);
        assert_eq!(form.tutorial_type_raw(), code);
        assert_eq!(form.teacher().teacher_id(), 326743);
        assert_eq!(form.default_date().to_string(), "2026-08-27");
        assert!(form.source_fingerprint().starts_with("sha256:"));
    }
}

#[test]
fn new_datetime_presence_is_contract_drift() {
    let html = NEW_FINAL.replace(
        "<input type=\"hidden\" name=\"ttype\" value=\"1\">",
        "<input type=\"hidden\" name=\"ttype\" value=\"1\"><input type=\"hidden\" name=\"datetime\" value=\"1780000000\">",
    );
    let err = parse_new_tutorial_form(&html, 200, "1").unwrap_err();
    assert_eq!(err.kind, NewTutorialFormFailureKind::ContractDrift);
}

#[test]
fn new_teacher_must_be_one_hidden_positive_control() {
    let select = NEW_FINAL.replace(
        "<input type=\"hidden\" name=\"tid\" value=\"326743\">",
        "<select name=\"tid\"><option value=\"326743\" selected>Teacher</option></select>",
    );
    let err = parse_new_tutorial_form(&select, 200, "1").unwrap_err();
    assert_eq!(err.kind, NewTutorialFormFailureKind::ContractDrift);

    let missing = NEW_FINAL.replace("<input type=\"hidden\" name=\"tid\" value=\"326743\">", "");
    assert!(parse_new_tutorial_form(&missing, 200, "1").is_err());

    let zero = NEW_FINAL.replace("name=\"tid\" value=\"326743\"", "name=\"tid\" value=\"0\"");
    assert!(parse_new_tutorial_form(&zero, 200, "1").is_err());
}

#[test]
fn route_student_and_requested_type_must_match_form() {
    let student = parse_new_tutorial_form(NEW_FINAL, 201, "1").unwrap_err();
    assert_eq!(student.kind, NewTutorialFormFailureKind::StudentMismatch);

    // A complete canonical form for another requested type must be classified
    // as a route/form type mismatch before type-specific applicability checks.
    let ttype = parse_new_tutorial_form(NEW_FINAL, 200, "0").unwrap_err();
    assert_eq!(
        ttype.kind,
        NewTutorialFormFailureKind::RequestedTypeMismatch
    );
}

#[test]
fn known_inapplicable_control_is_contract_drift() {
    let html = NEW_INITIAL.replace(
        "</form>",
        "<select name=\"dropdown-476\"><option value=\"Please choose level\" selected>Please choose level</option></select></form>",
    );
    let err = parse_new_tutorial_form(&html, 200, "2").unwrap_err();
    assert_eq!(err.kind, NewTutorialFormFailureKind::ContractDrift);
}

#[test]
fn unknown_cefr_option_fails_closed_even_when_not_selected() {
    let html = NEW_STANDARD.replace(
        "<option value=\"B1\" selected>B1</option>",
        "<option value=\"B1\" selected>B1</option><option value=\"NOT-CEFR\">bad</option>",
    );
    let err = parse_new_tutorial_form(&html, 200, "0").unwrap_err();
    assert_eq!(err.kind, NewTutorialFormFailureKind::MalformedForm);
}

#[test]
fn invalid_customdate_fails_closed() {
    let html = NEW_FINAL.replace("value=\"27-08-2026\"", "value=\"2026-08-27\"");
    let err = parse_new_tutorial_form(&html, 200, "1").unwrap_err();
    assert_eq!(err.kind, NewTutorialFormFailureKind::MalformedForm);
}

#[test]
fn fingerprint_ignores_irrelevant_layout_but_changes_with_source_semantics() {
    let a = parse_new_tutorial_form(NEW_FINAL, 200, "1").unwrap();
    let layout_only = NEW_FINAL.replace("<body>", "<body><div class=\"decorative\"></div>");
    let b = parse_new_tutorial_form(&layout_only, 200, "1").unwrap();
    assert_eq!(a.source_fingerprint(), b.source_fingerprint());

    let changed_teacher = NEW_FINAL.replace("value=\"326743\"", "value=\"326744\"");
    let c = parse_new_tutorial_form(&changed_teacher, 200, "1").unwrap();
    assert_ne!(a.source_fingerprint(), c.source_fingerprint());
}

#[test]
fn validated_new_form_is_the_origin_teacher_authority() {
    let form = parse_new_tutorial_form(NEW_FINAL, 200, "1").unwrap();
    let source = TutorialIdentity {
        tutorial_id: 99,
        student_uid: 200,
        tutorial_ts: 1780000000,
        tutorial_type: TutorialType::Standard,
    };
    let origin = DraftOrigin::New {
        prepopulation_source: Some(source),
        form_teacher: form.teacher().clone(),
        level_regression_baseline: Default::default(),
    };
    assert_eq!(origin.authoritative_teacher_id(), 326743);
    assert!(origin.authoritative_identity().is_none());
    assert!(origin.prepopulation_source().is_some());
    assert!(matches!(origin, DraftOrigin::New { .. }));
}

#[test]
fn first_ever_new_origin_needs_no_prepopulation_source() {
    let form = parse_new_tutorial_form(NEW_INITIAL, 200, "2").unwrap();
    let origin = DraftOrigin::New {
        prepopulation_source: None,
        form_teacher: form.teacher().clone(),
        level_regression_baseline: Default::default(),
    };
    assert!(origin.prepopulation_source().is_none());
    assert!(origin.authoritative_identity().is_none());
}
