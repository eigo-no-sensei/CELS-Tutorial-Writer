use gel_core::parse_print_page;

#[test]
fn print_parser_respects_row_boundaries_inside_teacher_prose() {
    let html = r#"
      <html><body>
        <p>Tutorial with Teacher X (teacher) and Student X (student) on 19-02-2026</p>
        <table>
          <tr><td>Tutorial Type</td><td>final</td></tr>
          <tr><td>absent</td><td>yes</td></tr>
          <tr><td>Tutorial Overall Level</td><td>A2: pre-intermediate</td></tr>
          <tr><td>Teacher's Comments</td><td>Student is working well. Listening is probably his strongest skill. Speaking is the area to work on.</td></tr>
          <tr><td>Listening</td><td>B1+</td></tr>
          <tr><td>Speaking</td><td>A2-</td></tr>
        </table>
      </body></html>
    "#;

    let record = parse_print_page(html).unwrap();
    assert_eq!(record.fields.get("absent").map(String::as_str), Some("yes"));
    assert_eq!(
        record.fields.get("Listening").map(String::as_str),
        Some("B1+")
    );
    assert_eq!(
        record.fields.get("Speaking").map(String::as_str),
        Some("A2-")
    );
    assert_eq!(
        record.fields.get("Teacher's Comments").map(String::as_str),
        Some("Student is working well. Listening is probably his strongest skill. Speaking is the area to work on.")
    );
    assert_eq!(record.teacher_name.as_deref(), Some("Teacher X"));
    assert_eq!(record.student_name.as_deref(), Some("Student X"));
    assert_eq!(record.custom_date.as_deref(), Some("19-02-2026"));
    assert_eq!(
        record.direct_fields.get("Type").map(String::as_str),
        Some("final")
    );
    assert!(record
        .print_text
        .as_deref()
        .is_some_and(|value| value.contains("Teacher's Comments")));
}
