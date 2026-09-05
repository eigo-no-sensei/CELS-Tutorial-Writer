use gel_core::gel_fields;
use gel_core::models::ParsedControlStatus;
use gel_core::{parse_edit_form, validate_edit_form};

fn select(name: &str, values: &[&str], selected: Option<&str>) -> String {
    let mut html = format!(r#"<select name="{name}" id="{name}">"#);
    for value in values {
        let selected_attr = if selected == Some(*value) {
            " selected"
        } else {
            ""
        };
        html.push_str(&format!(
            r#"<option value="{value}"{selected_attr}>{value}</option>"#
        ));
    }
    html.push_str("</select>");
    html
}

fn radio_group(name: &str, checked: Option<&str>) -> String {
    ["1", "2", "3"]
        .into_iter()
        .map(|value| {
            let checked_attr = if checked == Some(value) {
                " checked"
            } else {
                ""
            };
            format!(r#"<input type="radio" name="{name}" value="{value}"{checked_attr}>"#)
        })
        .collect::<Vec<_>>()
        .join("")
}

fn common(ttype: &str) -> String {
    format!(
        r##"<select name="tid" id="tid"><option value="0">Choose...</option><option value="9">Teacher</option></select>
<script>$("#tid").val("9");</script>
<input type="hidden" name="uid" value="55">
<input type="hidden" name="datetime" value="1780000000">
<input type="hidden" name="ttype" value="{ttype}">
<input type="checkbox" name="absent">
<input type="text" name="customdate" value="05-08-2026">
{}"##,
        select(
            gel_fields::OVERALL_LEVEL,
            &[gel_fields::OVERALL_PLACEHOLDER, "B1: intermediate"],
            Some("B1: intermediate")
        )
    )
}

fn final_form(reading_selected: Option<&str>) -> String {
    let mut html = String::from("<form>");
    html.push_str(&common(gel_fields::TTYPE_FINAL));
    for name in [
        gel_fields::INITIAL_SPEAKING,
        gel_fields::INITIAL_USE_OF_ENGLISH,
        gel_fields::INITIAL_WRITING,
        gel_fields::INITIAL_LISTENING,
        gel_fields::SPEAKING,
        gel_fields::USE_OF_ENGLISH,
        gel_fields::WRITING,
        gel_fields::LISTENING,
    ] {
        html.push_str(&select(
            name,
            &[gel_fields::SKILL_PLACEHOLDER, "A2", "B1"],
            Some("A2"),
        ));
    }
    html.push_str(&select(
        gel_fields::READING,
        &[gel_fields::SKILL_PLACEHOLDER, "B1"],
        reading_selected,
    ));
    html.push_str(
        r#"<textarea name="text-225"></textarea><textarea name="text-226"></textarea></form>"#,
    );
    html
}

fn standard_form() -> String {
    let mut html = String::from("<form>");
    html.push_str(&common(gel_fields::TTYPE_STANDARD));
    for name in [
        gel_fields::SPEAKING,
        gel_fields::USE_OF_ENGLISH,
        gel_fields::WRITING,
        gel_fields::LISTENING,
        gel_fields::READING,
    ] {
        html.push_str(&select(
            name,
            &[gel_fields::SKILL_PLACEHOLDER, "A2"],
            Some("A2"),
        ));
    }
    for name in [
        gel_fields::ASSESSMENT_LISTENING,
        gel_fields::ASSESSMENT_READING,
        gel_fields::ASSESSMENT_WRITING,
        gel_fields::ASSESSMENT_SPEAKING,
        gel_fields::ASSESSMENT_VOCABULARY,
        gel_fields::ASSESSMENT_GRAMMAR,
        gel_fields::ASSESSMENT_PRONUNCIATION,
    ] {
        html.push_str(&radio_group(name, None));
    }
    html.push_str(r#"<input type="hidden" name="trecs-79" value=""><div id="tcinput" name="trecs-79" contenteditable="true"></div><textarea name="text-225"></textarea></form>"#);
    html
}

#[test]
fn browser_default_placeholder_is_present_unset_not_missing() {
    let edit = parse_edit_form(&final_form(None)).unwrap();
    let validated = validate_edit_form(&edit).unwrap();
    let status = validated.controls.get(gel_fields::READING).unwrap();
    assert_eq!(
        status,
        &ParsedControlStatus::PresentUnset {
            raw_value: Some(gel_fields::SKILL_PLACEHOLDER.to_string())
        }
    );
    assert!(validated.is_unset(gel_fields::READING));
    assert_eq!(
        validated.raw_value_for_name(gel_fields::READING),
        Some(gel_fields::SKILL_PLACEHOLDER)
    );
}

#[test]
fn missing_applicable_control_fails_closed_and_reports_missing() {
    let html = final_form(Some("B1")).replace(
        &select(
            gel_fields::READING,
            &[gel_fields::SKILL_PLACEHOLDER, "B1"],
            Some("B1"),
        ),
        "",
    );
    let edit = parse_edit_form(&html).unwrap();
    let error = validate_edit_form(&edit).unwrap_err();
    let row = error.report.control(gel_fields::READING).unwrap();
    assert_eq!(row.status, ParsedControlStatus::Missing);
}

#[test]
fn wrong_control_kind_is_malformed() {
    let html = final_form(Some("B1")).replace(
        &select(
            gel_fields::READING,
            &[gel_fields::SKILL_PLACEHOLDER, "B1"],
            Some("B1"),
        ),
        r#"<input type="text" name="dropdown-476" value="B1">"#,
    );
    let edit = parse_edit_form(&html).unwrap();
    let error = validate_edit_form(&edit).unwrap_err();
    let row = error.report.control(gel_fields::READING).unwrap();
    assert!(matches!(row.status, ParsedControlStatus::Malformed { .. }));
}

#[test]
fn blank_standard_assessment_groups_are_valid_present_unset() {
    let edit = parse_edit_form(&standard_form()).unwrap();
    let validated = validate_edit_form(&edit).unwrap();
    for field in [
        gel_fields::ASSESSMENT_LISTENING,
        gel_fields::ASSESSMENT_READING,
        gel_fields::ASSESSMENT_WRITING,
        gel_fields::ASSESSMENT_SPEAKING,
        gel_fields::ASSESSMENT_VOCABULARY,
        gel_fields::ASSESSMENT_GRAMMAR,
        gel_fields::ASSESSMENT_PRONUNCIATION,
    ] {
        assert_eq!(
            validated.controls.get(field),
            Some(&ParsedControlStatus::PresentUnset { raw_value: None })
        );
    }
}

#[test]
fn incomplete_standard_radio_group_is_malformed() {
    let html = standard_form().replace(
        &radio_group(gel_fields::ASSESSMENT_PRONUNCIATION, None),
        r#"<input type="radio" name="sp-89" value="1"><input type="radio" name="sp-89" value="2">"#,
    );
    let edit = parse_edit_form(&html).unwrap();
    let error = validate_edit_form(&edit).unwrap_err();
    let row = error
        .report
        .control(gel_fields::ASSESSMENT_PRONUNCIATION)
        .unwrap();
    assert!(matches!(row.status, ParsedControlStatus::Malformed { .. }));
}

#[test]
fn unknown_cefr_option_is_malformed_not_semantic_unset() {
    let html = final_form(Some("B1")).replace(
        &select(
            gel_fields::READING,
            &[gel_fields::SKILL_PLACEHOLDER, "B1"],
            Some("B1"),
        ),
        &select(
            gel_fields::READING,
            &[gel_fields::SKILL_PLACEHOLDER, "B3"],
            Some("B3"),
        ),
    );
    let edit = parse_edit_form(&html).unwrap();
    let error = validate_edit_form(&edit).unwrap_err();
    let row = error.report.control(gel_fields::READING).unwrap();
    assert!(matches!(row.status, ParsedControlStatus::Malformed { .. }));
}

#[test]
fn unselected_unknown_cefr_option_is_still_contract_drift() {
    let html = final_form(Some("B1")).replace(
        &select(
            gel_fields::READING,
            &[gel_fields::SKILL_PLACEHOLDER, "B1"],
            Some("B1"),
        ),
        &select(
            gel_fields::READING,
            &[gel_fields::SKILL_PLACEHOLDER, "B1", "B3"],
            Some("B1"),
        ),
    );
    let edit = parse_edit_form(&html).unwrap();
    let error = validate_edit_form(&edit).unwrap_err();
    let row = error.report.control(gel_fields::READING).unwrap();
    assert!(matches!(row.status, ParsedControlStatus::Malformed { .. }));
}

#[test]
fn invalid_date_is_malformed() {
    let html = final_form(Some("B1")).replace("05-08-2026", "2026-08-05");
    let edit = parse_edit_form(&html).unwrap();
    let error = validate_edit_form(&edit).unwrap_err();
    let row = error.report.control(gel_fields::CUSTOM_DATE).unwrap();
    assert!(matches!(row.status, ParsedControlStatus::Malformed { .. }));
}

#[test]
fn known_type_inapplicable_control_is_rejected() {
    let html =
        standard_form().replace("</form>", r#"<textarea name="text-226"></textarea></form>"#);
    let edit = parse_edit_form(&html).unwrap();
    let error = validate_edit_form(&edit).unwrap_err();
    assert!(error
        .report
        .errors
        .iter()
        .any(|message| message.contains("additional_comments")));
}
