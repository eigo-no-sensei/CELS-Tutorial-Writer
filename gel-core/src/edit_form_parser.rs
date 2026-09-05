use crate::form_parser_common::parse_form_controls;
use crate::gel_fields;
use crate::models::{EditFormState, FormControl, TeacherSelection};
use anyhow::{Context, Result};

pub fn parse_edit_form(html: &str) -> Result<EditFormState> {
    let (controls, js_values_by_id) = parse_form_controls(html)?;
    let teacher = extract_teacher(&controls).context("extract teacher from edit form")?;

    Ok(EditFormState {
        controls,
        js_values_by_id,
        teacher,
    })
}

fn extract_teacher(controls: &[FormControl]) -> Result<TeacherSelection> {
    for control in controls {
        if let FormControl::Select {
            name,
            id,
            options,
            effective_value,
            value_source,
            ..
        } = control
        {
            if name != gel_fields::TEACHER_ID && id.as_deref() != Some(gel_fields::TEACHER_ID) {
                continue;
            }

            let teacher_id = effective_value
                .as_deref()
                .filter(|v| *v != "0" && !v.trim().is_empty())
                .and_then(|v| v.parse::<i64>().ok());

            let mut teacher_name = None;
            let mut teacher_option_found = false;
            if let Some(tid) = teacher_id {
                if let Some(option) = options.iter().find(|o| o.value == tid.to_string()) {
                    teacher_option_found = true;
                    teacher_name = Some(option.text.clone());
                }
            }

            let source = match value_source.as_deref() {
                Some("inline_js") => Some("edit_form_inline_js".to_string()),
                Some("selected_option") => Some("edit_form_selected_option".to_string()),
                _ => None,
            };

            return Ok(TeacherSelection {
                teacher_id,
                teacher_name,
                source,
                tid_select_present: true,
                teacher_option_found,
            });
        }
    }

    Ok(TeacherSelection::default())
}
