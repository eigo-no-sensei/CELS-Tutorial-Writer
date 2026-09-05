use gel_core::parse_edit_form;

#[test]
fn parses_original_teacher_from_inline_tid_js() {
    let html = include_str!("../fixtures/synthetic/edit_tid_inline_js.html");
    let state = parse_edit_form(html).unwrap();
    assert_eq!(state.teacher.teacher_id, Some(910002));
    assert_eq!(state.teacher.teacher_name.as_deref(), Some("Teacher B"));
    assert_eq!(state.teacher.source.as_deref(), Some("edit_form_inline_js"));
    assert_eq!(state.checkbox_checked("absent"), Some(true));
    assert_eq!(state.value_for_name("ttype").as_deref(), Some("1"));
    assert_eq!(
        state.value_for_name("text-225").as_deref(),
        Some("Example comment")
    );
}

#[test]
fn selected_option_is_supported_as_fallback() {
    let html = include_str!("../fixtures/synthetic/edit_tid_selected_option.html");
    let state = parse_edit_form(html).unwrap();
    assert_eq!(state.teacher.teacher_id, Some(910001));
    assert_eq!(state.teacher.teacher_name.as_deref(), Some("Teacher A"));
    assert_eq!(
        state.teacher.source.as_deref(),
        Some("edit_form_selected_option")
    );
}

#[test]
fn parses_standard_aims_from_contenteditable_without_overwriting_raw_hidden_field() {
    let html = r#"
      <form>
        <input type="hidden" id="hidden-rec-content" name="trecs-79" value="">
        <div contenteditable="true" id="tcinput" name="trecs-79">
          Read one graded reader&nbsp; - build vocabulary.<br>
          <div>Try to use English outside the classroom.</div>
        </div>
      </form>
    "#;
    let state = parse_edit_form(html).unwrap();

    // Raw successful-control state remains the blank hidden input.
    assert_eq!(state.value_for_name("trecs-79").as_deref(), Some(""));
    // Semantic editor state comes from #tcinput and preserves visual breaks.
    assert_eq!(
        state.contenteditable_value_for_id("tcinput").as_deref(),
        Some(
            "Read one graded reader - build vocabulary.\nTry to use English outside the classroom."
        )
    );
    assert_eq!(
        state.semantic_value_for_name("trecs-79").as_deref(),
        Some(
            "Read one graded reader - build vocabulary.\nTry to use English outside the classroom."
        )
    );
}
