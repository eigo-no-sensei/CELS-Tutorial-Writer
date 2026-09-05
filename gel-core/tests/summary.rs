use gel_core::parse_tutorial_summary;

#[test]
fn parses_server_rendered_fixedtables_summary() {
    let html = include_str!("../fixtures/synthetic/summary_direct.html");
    let rows = parse_tutorial_summary(html).unwrap();
    assert_eq!(rows.len(), 2);
    assert_eq!(rows[0].ttype_label, "Standard");
    assert_eq!(rows[0].tutorial_ts, 1900000001);
    assert_eq!(rows[0].fields.get("absent").map(String::as_str), Some("no"));
    assert_eq!(
        rows[0].fields.get("Assessment").map(String::as_str),
        Some("listening: Good for this level reading: OK for the current level")
    );
    assert_eq!(rows[1].ttype_label, "Final");
    assert_eq!(
        rows[1].fields.get("absent").map(String::as_str),
        Some("yes")
    );
    assert_eq!(
        rows[1].fields.get("Teacher's Comments").map(String::as_str),
        Some("Full final comment")
    );
}

#[test]
fn parses_sanitized_live_summary_shape_with_all_nine_columns() {
    let html = include_str!("../fixtures/synthetic/summary_live_shape_sanitized.html");
    let rows = parse_tutorial_summary(html).unwrap();
    assert_eq!(rows.len(), 9);
    assert_eq!(rows[0].ttype_label, "Final");
    assert_eq!(rows[1].ttype_label, "Standard");
    assert_eq!(rows[7].ttype_label, "Initial");
    assert_eq!(rows[8].ttype_label, "Initial");
    assert_eq!(
        rows[1].fields.get("Teacher").map(String::as_str),
        Some("Teacher A")
    );
    assert!(rows[1]
        .fields
        .get("Assessment")
        .expect("assessment")
        .contains("pronunciation: Good for this level"));
}
