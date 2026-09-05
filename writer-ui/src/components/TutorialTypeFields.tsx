import type {
  AssessmentSkill,
  DraftFieldRuleView,
  DraftValidationIssue,
  DraftView,
  FourSkill,
  TutorialDraftEdit,
  TutorialSemanticField,
} from "../types";
import { HarperFieldAssistant } from "./HarperFieldAssistant";
import { SemanticSelectField, SemanticTextAreaField } from "./SemanticFieldControl";

interface BaseFieldProps {
  draft: DraftView;
  validationIssue: DraftValidationIssue | null;
  onEdit: (edit: TutorialDraftEdit) => void;
}

interface HarperSessionProps {
  disabledHarperRules: string[];
  ignoredHarperFindings: Set<string>;
  onDisableHarperRule: (rule: string) => void;
  onIgnoreHarperFinding: (key: string) => void;
  onAddHarperDictionaryTerm: (word: string) => Promise<void>;
  harperDictionaryRevision: number;
}

interface Props extends BaseFieldProps, HarperSessionProps {}

function ruleFor(draft: DraftView, field: TutorialSemanticField): DraftFieldRuleView | undefined {
  return draft.formContract.fields.find((rule) => rule.field === field);
}

function LevelField({
  draft,
  validationIssue,
  onEdit,
  field,
  label,
  value,
  edit,
}: BaseFieldProps & {
  field: TutorialSemanticField;
  label: string;
  value: string | null;
  edit: (value: string | null) => TutorialDraftEdit;
}) {
  return (
    <SemanticSelectField
      field={field}
      label={label}
      rule={ruleFor(draft, field)}
      issue={validationIssue}
      value={value}
      options={draft.formContract.levelOptions}
      onChange={(next) => onEdit(edit(next))}
    />
  );
}

function CurrentSkillField({ draft, validationIssue, onEdit, skill, field, label, value }: BaseFieldProps & {
  skill: FourSkill;
  field: TutorialSemanticField;
  label: string;
  value: string | null;
}) {
  return (
    <LevelField
      draft={draft}
      validationIssue={validationIssue}
      onEdit={onEdit}
      field={field}
      label={label}
      value={value}
      edit={(next) => ({ kind: "set_current_level", skill, value: next })}
    />
  );
}

function InitialSkillField({ draft, validationIssue, onEdit, skill, field, label, value }: BaseFieldProps & {
  skill: FourSkill;
  field: TutorialSemanticField;
  label: string;
  value: string | null;
}) {
  return (
    <LevelField
      draft={draft}
      validationIssue={validationIssue}
      onEdit={onEdit}
      field={field}
      label={label}
      value={value}
      edit={(next) => ({ kind: "set_initial_level", skill, value: next })}
    />
  );
}

function AssessmentField({ draft, validationIssue, onEdit, skill, field, label, value }: BaseFieldProps & {
  skill: AssessmentSkill;
  field: TutorialSemanticField;
  label: string;
  value: string | null;
}) {
  return (
    <SemanticSelectField
      field={field}
      label={label}
      rule={ruleFor(draft, field)}
      issue={validationIssue}
      value={value}
      options={draft.formContract.assessmentOptions}
      onChange={(next) => onEdit({ kind: "set_assessment", skill, value: next })}
    />
  );
}

function StandardFields(props: Props) {
  const {
    draft,
    validationIssue,
    onEdit,
    disabledHarperRules,
    ignoredHarperFindings,
    onDisableHarperRule,
    onIgnoreHarperFinding,
    onAddHarperDictionaryTerm,
    harperDictionaryRevision,
  } = props;
  return (
    <div className="type-form-sections" data-tutorial-form="standard">
      <section className="semantic-section">
        <div className="semantic-section-heading">
          <h3>Levels</h3>
          <span>Current tutorial levels</span>
        </div>
        <div className="form-grid semantic-level-grid">
          <CurrentSkillField {...props} skill="speaking" field="current_speaking" label="Speaking" value={draft.current.speaking} />
          <CurrentSkillField {...props} skill="use_of_english" field="current_use_of_english" label="Use of English" value={draft.current.useOfEnglish} />
          <CurrentSkillField {...props} skill="writing" field="current_writing" label="Writing" value={draft.current.writing} />
          <CurrentSkillField {...props} skill="listening" field="current_listening" label="Listening" value={draft.current.listening} />
          <LevelField
            draft={draft}
            validationIssue={validationIssue}
            onEdit={onEdit}
            field="reading"
            label="Reading"
            value={draft.reading}
            edit={(next) => ({ kind: "set_reading", value: next })}
          />
        </div>
      </section>

      <section className="semantic-section">
        <div className="semantic-section-heading">
          <h3>Assessment</h3>
          <span>Rust-projected assessment domain</span>
        </div>
        <div className="form-grid semantic-assessment-grid">
          <AssessmentField {...props} skill="listening" field="assessment_listening" label="Listening" value={draft.assessment.listening} />
          <AssessmentField {...props} skill="reading" field="assessment_reading" label="Reading" value={draft.assessment.reading} />
          <AssessmentField {...props} skill="writing" field="assessment_writing" label="Writing" value={draft.assessment.writing} />
          <AssessmentField {...props} skill="speaking" field="assessment_speaking" label="Speaking" value={draft.assessment.speaking} />
          <AssessmentField {...props} skill="vocabulary" field="assessment_vocabulary" label="Vocabulary" value={draft.assessment.vocabulary} />
          <AssessmentField {...props} skill="grammar" field="assessment_grammar" label="Grammar" value={draft.assessment.grammar} />
          <AssessmentField {...props} skill="pronunciation" field="assessment_pronunciation" label="Pronunciation" value={draft.assessment.pronunciation} />
        </div>
      </section>

      <section className="semantic-section">
        <div className="semantic-section-heading">
          <h3>Aims</h3>
          <span>Direct editing; no preset source is active</span>
        </div>
        <SemanticTextAreaField
          field="aims"
          label="Aims"
          rule={ruleFor(draft, "aims")}
          issue={validationIssue}
          value={draft.aims}
          rows={6}
          onChange={(value) => onEdit({ kind: "set_aims", value })}
        />
        <HarperFieldAssistant
          field="aims"
          variant="side-panel"
          value={draft.aims}
          onAccept={(value) => onEdit({ kind: "set_aims", value })}
          disabledRules={disabledHarperRules}
          ignoredFindingKeys={ignoredHarperFindings}
          onDisableRule={onDisableHarperRule}
          onIgnoreFinding={onIgnoreHarperFinding}
          onAddDictionaryTerm={onAddHarperDictionaryTerm}
          dictionaryRevision={harperDictionaryRevision}
        />
      </section>
    </div>
  );
}

function InitialFields(props: Props) {
  const { draft, validationIssue, onEdit } = props;
  const courseType = draft.initialCourseType;
  return (
    <div className="type-form-sections" data-tutorial-form="initial">
      <section className="semantic-section">
        <div className="semantic-section-heading">
          <h3>Initial levels</h3>
          <span>Initial-role fields only</span>
        </div>
        <div className="form-grid semantic-level-grid">
          <InitialSkillField {...props} skill="speaking" field="initial_speaking" label="Initial speaking" value={draft.initial.speaking} />
          <InitialSkillField {...props} skill="use_of_english" field="initial_use_of_english" label="Initial Use of English" value={draft.initial.useOfEnglish} />
          <InitialSkillField {...props} skill="writing" field="initial_writing" label="Initial writing" value={draft.initial.writing} />
          <InitialSkillField {...props} skill="listening" field="initial_listening" label="Initial listening" value={draft.initial.listening} />
        </div>
      </section>

      <section className="semantic-section">
        <div className="semantic-section-heading">
          <h3>Course type</h3>
          <span>Stored through the Rust Initial course-type adapter</span>
        </div>
        <SemanticSelectField
          field="initial_course_type"
          label="Course type"
          rule={ruleFor(draft, "initial_course_type")}
          issue={validationIssue}
          value={courseType?.value ?? null}
          options={draft.formContract.initialCourseTypeOptions}
          emptyLabel="No course type"
          onChange={(value) => {
            if (value !== null) onEdit({ kind: "set_initial_course_type", value });
          }}
        />
        {courseType?.status === "unrecognized_preserved" && (
          <p className="preserved-state-note" role="status">
            Unrecognized historical Initial course metadata is being preserved unchanged. Choosing a course type explicitly replaces it.
          </p>
        )}
      </section>
    </div>
  );
}

function FinalFields(props: Props) {
  const { draft, validationIssue, onEdit } = props;
  return (
    <div className="type-form-sections" data-tutorial-form="final">
      <section className="semantic-section final-level-section">
        <div className="semantic-section-heading">
          <h3>Initial and final levels</h3>
          <span>Paired canonical roles; no cross-role inference</span>
        </div>
        <div className="paired-level-grid">
          <div className="paired-level-column">
            <h4>Initial</h4>
            <InitialSkillField {...props} skill="speaking" field="initial_speaking" label="Speaking" value={draft.initial.speaking} />
            <InitialSkillField {...props} skill="use_of_english" field="initial_use_of_english" label="Use of English" value={draft.initial.useOfEnglish} />
            <InitialSkillField {...props} skill="writing" field="initial_writing" label="Writing" value={draft.initial.writing} />
            <InitialSkillField {...props} skill="listening" field="initial_listening" label="Listening" value={draft.initial.listening} />
          </div>
          <div className="paired-level-column">
            <h4>Final</h4>
            <CurrentSkillField {...props} skill="speaking" field="current_speaking" label="Speaking" value={draft.current.speaking} />
            <CurrentSkillField {...props} skill="use_of_english" field="current_use_of_english" label="Use of English" value={draft.current.useOfEnglish} />
            <CurrentSkillField {...props} skill="writing" field="current_writing" label="Writing" value={draft.current.writing} />
            <CurrentSkillField {...props} skill="listening" field="current_listening" label="Listening" value={draft.current.listening} />
          </div>
        </div>
        <div className="form-grid final-reading-grid">
          <LevelField
            draft={draft}
            validationIssue={validationIssue}
            onEdit={onEdit}
            field="reading"
            label="Final reading"
            value={draft.reading}
            edit={(next) => ({ kind: "set_reading", value: next })}
          />
        </div>
      </section>
    </div>
  );
}

export function TutorialTypeFields(props: Props) {
  switch (props.draft.tutorialType) {
    case "standard":
      return <StandardFields {...props} />;
    case "initial":
      return <InitialFields {...props} />;
    case "final":
      return <FinalFields {...props} />;
  }
}

export function FinalAdditionalCommentsField({
  draft,
  validationIssue,
  onEdit,
  disabledHarperRules,
  ignoredHarperFindings,
  onDisableHarperRule,
  onIgnoreHarperFinding,
  onAddHarperDictionaryTerm,
  harperDictionaryRevision,
}: Props) {
  if (draft.tutorialType !== "final") return null;
  const rule = ruleFor(draft, "additional_comments");
  const isAdditionalCommentsEditable = rule?.disposition === "editable";
  if (!isAdditionalCommentsEditable) {
    return (
      <SemanticTextAreaField
        field="additional_comments"
        label="Additional comments"
        rule={rule}
        issue={validationIssue}
        value={draft.additionalComments}
        maxLength={draft.formContract.additionalCommentsMaxChars}
        rows={6}
        onChange={(value) => onEdit({ kind: "set_additional_comments", value })}
      />
    );
  }
  return (
    <HarperFieldAssistant
      field="additional_comments"
      variant="inline"
      label="Additional comments"
      rule={rule}
      issue={validationIssue}
      value={draft.additionalComments}
      maxLength={draft.formContract.additionalCommentsMaxChars}
      rows={6}
      onChange={(value) => onEdit({ kind: "set_additional_comments", value })}
      onAccept={(value) => onEdit({ kind: "set_additional_comments", value })}
      disabledRules={disabledHarperRules}
      ignoredFindingKeys={ignoredHarperFindings}
      onDisableRule={onDisableHarperRule}
      onIgnoreFinding={onIgnoreHarperFinding}
      onAddDictionaryTerm={onAddHarperDictionaryTerm}
      dictionaryRevision={harperDictionaryRevision}
    />
  );
}
