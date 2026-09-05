use gel_core::fixture_compare::{compare_edit_fixture_dirs, ComparisonStatus};
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

fn temp_fixture_root() -> PathBuf {
    let nonce = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    let root = std::env::temp_dir().join(format!("gel-core-fixture-compare-{nonce}"));
    fs::create_dir_all(root.join("expected")).unwrap();
    fs::create_dir_all(root.join("raw")).unwrap();
    root
}

#[test]
fn standard_fixture_detects_absent_disagreement_but_matches_teacher_and_assessment() {
    let root = temp_fixture_root();
    let expected = root.join("expected");
    let raw = root.join("raw");

    fs::write(
        expected.join("standard_case.json"),
        r#"{
          "spec": {"label":"standard_case","ttype":"0"},
          "normalized_db_reference": {
            "student_uid": 123,
            "created_at": 1000,
            "custom_date": "2026-06-16",
            "teacher_id": 77,
            "teacher_name": "Teacher One",
            "absent": 0,
            "overall_level": "A2: pre-intermediate",
            "speaking": "A2",
            "use_of_english": "A2-",
            "writing": "A1+",
            "listening": "A2",
            "reading": "A2-",
            "self_listening": "Good for the current level",
            "self_reading": "Good for the current level",
            "self_writing": "OK for the current level",
            "self_speaking": "OK for the current level",
            "self_vocabulary": "OK for the current level",
            "self_grammar": "OK for the current level",
            "self_pronunciation": "Good for the current level",
            "aims": "Read one graded reader\nAttend one social programme event",
            "teacher_comments": "A comment",
            "additional_comments": ""
          }
        }"#,
    )
    .unwrap();

    fs::write(
        raw.join("standard_case.html"),
        r##"<html><body><form>
          <input type="hidden" name="uid" value="123"><input type="hidden" name="datetime" value="1000">
          <input type="hidden" name="ttype" value="0"><input id="absent" name="absent" type="checkbox" checked>
          <input name="customdate" value="16-06-2026">
          <select name="tid" id="tid"><option value="0">Choose...</option><option value="77">Teacher One</option></select>
          <script>$("#tid").val("77");</script>
          <select name="dropdown-475"><option value="A2: pre-intermediate" selected>A2</option></select>
          <select name="dropdown-233"><option value="A2" selected>A2</option></select>
          <select name="dropdown-234"><option value="A2-" selected>A2-</option></select>
          <select name="dropdown-235"><option value="A1+" selected>A1+</option></select>
          <select name="dropdown-236"><option value="A2" selected>A2</option></select>
          <select name="dropdown-476"><option value="A2-" selected>A2-</option></select>
          <input type="radio" name="sl-89" value="1"><input type="radio" name="sl-89" value="2"><input type="radio" name="sl-89" value="3" checked>
          <input type="radio" name="sr-89" value="1"><input type="radio" name="sr-89" value="2"><input type="radio" name="sr-89" value="3" checked>
          <input type="radio" name="sw-89" value="1"><input type="radio" name="sw-89" value="2" checked><input type="radio" name="sw-89" value="3">
          <input type="radio" name="ss-89" value="1"><input type="radio" name="ss-89" value="2" checked><input type="radio" name="ss-89" value="3">
          <input type="radio" name="sv-89" value="1"><input type="radio" name="sv-89" value="2" checked><input type="radio" name="sv-89" value="3">
          <input type="radio" name="sg-89" value="1"><input type="radio" name="sg-89" value="2" checked><input type="radio" name="sg-89" value="3">
          <input type="radio" name="sp-89" value="1"><input type="radio" name="sp-89" value="2"><input type="radio" name="sp-89" value="3" checked>
          <input type="hidden" name="trecs-79" value="">
          <div contenteditable="true" id="tcinput" name="trecs-79">Read one graded reader<br>Attend one social programme event</div>
          <textarea name="text-225">A comment</textarea>
        </form></body></html>"##,
    )
    .unwrap();

    let report = compare_edit_fixture_dirs(&expected, &raw).unwrap();
    let absent = report
        .comparisons
        .iter()
        .find(|r| r.field == "absent")
        .unwrap();
    assert_eq!(absent.status, ComparisonStatus::Mismatch);
    let teacher = report
        .comparisons
        .iter()
        .find(|r| r.field == "teacher_id")
        .unwrap();
    assert_eq!(teacher.status, ComparisonStatus::Ok);
    let listening = report
        .comparisons
        .iter()
        .find(|r| r.field == "self_listening")
        .unwrap();
    assert_eq!(listening.status, ComparisonStatus::Ok);

    let aims = report
        .comparisons
        .iter()
        .find(|r| r.field == "aims")
        .unwrap();
    assert_eq!(aims.status, ComparisonStatus::Ok);
    assert!(aims.edit_source.contains("contenteditable#tcinput"));

    fs::remove_dir_all(root).ok();
}

#[test]
fn initial_uses_primary_skill_columns_and_does_not_require_additional_comments() {
    let root = temp_fixture_root();
    let expected = root.join("expected");
    let raw = root.join("raw");
    fs::write(
        expected.join("initial_case.json"),
        r#"{
          "spec": {"label":"initial_case","ttype":"2"},
          "normalized_db_reference": {
            "student_uid": 1, "created_at": 2, "custom_date":"2026-01-01",
            "teacher_id": 77, "teacher_name":"Teacher One", "absent":0, "overall_level":"Choose...",
            "speaking":"A1", "use_of_english":"A1", "writing":"A1+", "listening":"A1",
            "speaking_before":"", "uoe_before":"", "writing_before":"", "listening_before":"",
            "exam_want":"Please choose:", "exam_which":"Please choose:", "exam_when":"Please choose:",
            "teacher_comments":"", "additional_comments":""
          }
        }"#,
    )
    .unwrap();
    fs::write(
        raw.join("initial_case.html"),
        r##"<form>
          <select name="tid" id="tid"><option value="0">Choose...</option><option value="77">Teacher One</option></select>
          <script>$("#tid").val("77");</script>
          <input type="hidden" name="uid" value="1"><input type="hidden" name="datetime" value="2"><input type="hidden" name="ttype" value="2">
          <input name="customdate" value="01-01-2026"><input name="absent" type="checkbox">
          <select name="dropdown-475"><option value="Choose...">Choose...</option></select>
          <select name="dropdown-264"><option value="A1">A1</option></select>
          <select name="dropdown-265"><option value="A1">A1</option></select>
          <select name="dropdown-266"><option value="A1+">A1+</option></select>
          <select name="dropdown-267"><option value="A1">A1</option></select>
          <select name="dropdown-413"><option value="Please choose:">Please choose:</option></select>
          <select name="dropdown-414"><option value="Please choose:">Please choose:</option></select>
          <select name="dropdown-415"><option value="Please choose:">Please choose:</option></select>
          <textarea name="text-225"></textarea>
        </form>"##,
    )
    .unwrap();

    let report = compare_edit_fixture_dirs(&expected, &raw).unwrap();
    for field in [
        "initial_speaking",
        "initial_use_of_english",
        "initial_writing",
        "initial_listening",
    ] {
        let comparison = report
            .comparisons
            .iter()
            .find(|r| r.field == field)
            .unwrap();
        assert_eq!(comparison.status, ComparisonStatus::Ok, "{field}");
    }
    assert!(report
        .comparisons
        .iter()
        .all(|r| r.field != "additional_comments"));

    fs::remove_dir_all(root).ok();
}

#[test]
fn final_compares_reading_and_treats_placeholder_as_unset() {
    let root = temp_fixture_root();
    let expected = root.join("expected");
    let raw = root.join("raw");

    fs::write(
        expected.join("final_case.json"),
        r#"{
          "spec": {"label":"final_case","ttype":"1"},
          "normalized_db_reference": {
            "student_uid": 9, "created_at": 10, "custom_date":"2026-02-23",
            "teacher_id": 77, "teacher_name":"Teacher One", "absent":0,
            "overall_level":"A2: pre-intermediate",
            "speaking_before":"A2-", "uoe_before":"A2-", "writing_before":"A2-", "listening_before":"A2-",
            "speaking":"A2-", "use_of_english":"A2-", "writing":"A2-", "listening":"A2-",
            "reading":"none", "teacher_comments":"Comment", "additional_comments":""
          }
        }"#,
    )
    .unwrap();

    fs::write(
        raw.join("final_case.html"),
        r##"<form>
          <select name="tid" id="tid"><option value="77">Teacher One</option></select>
          <script>$("#tid").val("77");</script>
          <input type="hidden" name="uid" value="9"><input type="hidden" name="datetime" value="10"><input type="hidden" name="ttype" value="1">
          <input name="customdate" value="23-02-2026"><input name="absent" type="checkbox">
          <select name="dropdown-475"><option value="A2: pre-intermediate" selected>A2</option></select>
          <select name="dropdown-264"><option value="A2-" selected>A2-</option></select>
          <select name="dropdown-265"><option value="A2-" selected>A2-</option></select>
          <select name="dropdown-266"><option value="A2-" selected>A2-</option></select>
          <select name="dropdown-267"><option value="A2-" selected>A2-</option></select>
          <select name="dropdown-233"><option value="A2-" selected>A2-</option></select>
          <select name="dropdown-234"><option value="A2-" selected>A2-</option></select>
          <select name="dropdown-235"><option value="A2-" selected>A2-</option></select>
          <select name="dropdown-236"><option value="A2-" selected>A2-</option></select>
          <select name="dropdown-476"><option value="Please choose level">Please choose level</option><option value="A2-">A2-</option></select>
          <textarea name="text-225">Comment</textarea><textarea name="text-226"></textarea>
        </form>"##,
    )
    .unwrap();

    let report = compare_edit_fixture_dirs(&expected, &raw).unwrap();
    let reading = report
        .comparisons
        .iter()
        .find(|r| r.field == "reading")
        .expect("Final reading comparison");
    assert_eq!(reading.status, ComparisonStatus::Ok);
    assert_eq!(reading.edit_value.as_deref(), Some("Please choose level"));
    assert_eq!(report.fixtures[0].total, 19);

    fs::remove_dir_all(root).ok();
}
