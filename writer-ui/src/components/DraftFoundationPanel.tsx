import type {
  DraftFieldRuleView,
  DraftValidationIssue,
  DraftView,
  TutorialDraftEdit,
  TutorialSemanticField,
} from "../types";
import {
  DraftValidationIssueSummary,
  SemanticCheckboxField,
  SemanticDateField,
  SemanticReadOnlyField,
  SemanticSelectField,
  SemanticTextAreaField,
} from "./SemanticFieldControl";
import { FinalAdditionalCommentsField, TutorialTypeFields } from "./TutorialTypeFields";
import { HarperDictionaryPanel } from "./HarperDictionaryPanel";
import { HarperFieldAssistant } from "./HarperFieldAssistant";

interface Props {
  draft: DraftView | null;
  validationIssue: DraftValidationIssue | null;
  onEdit: (edit: TutorialDraftEdit) => void;
  onDiscard: () => void;
  onSubmit: () => void;
  isSubmitting?: boolean;
  /** Session-only Harper suppression state, hoisted to App. */
  disabledHarperRules: string[];
  ignoredHarperFindings: Set<string>;
  onDisableHarperRule: (rule: string) => void;
  onIgnoreHarperFinding: (key: string) => void;
  onAddHarperDictionaryTerm: (word: string) => Promise<void>;
  /** Bumped by App whenever the Harper dictionary changes. */
  harperDictionaryRevision: number;
  /** Called by the standalone HarperDictionaryPanel after it has directly
   * invoked harperDictionaryAdd/harperDictionaryRemove. Bumps the App-side
   * revision counter so every mounted HarperFieldAssistant re-lints. */
  onHarperDictionaryMutation: () => void;

  // Presentation compatibility only. New Standard / Initial / Final remain
  // owned by the selected-student browse context in the accepted A+D hybrid.
  [key: string]: unknown;
}

function ruleFor(draft: DraftView, field: TutorialSemanticField): DraftFieldRuleView | undefined {
  const rule = draft.formContract.fields.find((r) => r.field === field);
  if (!rule) return undefined;
  if (draft.status === "stale_source" || draft.status === "invalid") {
    return {
      ...rule,
      disposition: rule.disposition === "editable" ? "read_only" : rule.disposition,
    };
  }
  return rule;
}

export function isEditable(draft: DraftView, field: TutorialSemanticField): boolean {
  if (draft.status === "stale_source" || draft.status === "invalid") {
    return false;
  }
  return ruleFor(draft, field)?.disposition === "editable";
}

export function DraftFoundationPanel({
  draft,
  validationIssue,
  onEdit,
  onDiscard,
  onSubmit,
  isSubmitting = false,
  disabledHarperRules,
  ignoredHarperFindings,
  onDisableHarperRule,
  onIgnoreHarperFinding,
  onAddHarperDictionaryTerm,
  harperDictionaryRevision,
  onHarperDictionaryMutation,
}: Props) {
  const harperFieldAssistantCommon = {
    disabledRules: disabledHarperRules,
    ignoredFindingKeys: ignoredHarperFindings,
    onDisableRule: onDisableHarperRule,
    onIgnoreFinding: onIgnoreHarperFinding,
    onAddDictionaryTerm: onAddHarperDictionaryTerm,
    dictionaryRevision: harperDictionaryRevision,
  };

  return (
    <section className="draft-panel">
      <div className="draft-toolbar">
        <div>
          <h2>Tutorial draft</h2>
          <p className="subtle">
            UI1c2–c4 semantic forms: Rust owns applicability, domains, draft
            authority, prepopulation/regression semantics and validation; React
            composes Standard, Initial and Final controls and emits typed
            semantic edits only.
          </p>
        </div>
      </div>

      {!draft ? (
        <div className="empty-state">
          Open New Standard, New Initial, New Final, or an eligible Revision
          from the selected-student context.
        </div>
      ) : (
        <div className="draft-foundation-form">
          <div className="draft-meta">
            <span className={`status-pill status-${draft.status}`}>{draft.status}</span>
            <span>{draft.origin === "new" ? "New" : "Revision"} · {draft.tutorialType}</span>
            <button
              type="button"
              className="primary"
              disabled={isSubmitting || draft.status === "clean" || draft.status === "stale_source" || draft.status === "invalid"}
              onClick={onSubmit}
            >
              {isSubmitting ? "Submitting…" : "Submit tutorial"}
            </button>
            <button type="button" className="secondary" onClick={onDiscard}>Discard</button>
            <HarperDictionaryPanel onMutation={onHarperDictionaryMutation} />
          </div>

          <DraftValidationIssueSummary issue={validationIssue} />

          {draft.status === "stale_source" && (
            <div className="error-banner draft-stale-banner" role="alert">
              <div>
                <strong>Draft source authority invalidated.</strong>
                <p style={{ margin: "4px 0 0" }}>
                  {draft.origin === "new"
                    ? "The authenticated GEL session has expired or the student's latest tutorial has drifted. Direct editing is locked."
                    : "The historical tutorial source in the archive is no longer available or has drifted. Direct editing is locked."}
                </p>
              </div>
              <button type="button" className="secondary" onClick={onDiscard}>
                Discard draft
              </button>
            </div>
          )}

          <section className="semantic-section semantic-common-section">
            <div className="semantic-section-heading">
              <h3>Common</h3>
              <span>Rust field-disposition rules remain authoritative</span>
            </div>
            <div className="form-grid semantic-common-grid">
              <SemanticDateField
                field="tutorial_date"
                label="Date"
                rule={ruleFor(draft, "tutorial_date")}
                issue={validationIssue}
                value={draft.tutorialDate}
                onChange={(value) => onEdit({ kind: "set_tutorial_date", value })}
              />
              <SemanticSelectField
                field="overall_level"
                label="Overall level"
                rule={ruleFor(draft, "overall_level")}
                issue={validationIssue}
                value={draft.overallLevel}
                options={draft.formContract.levelOptions}
                onChange={(value) => onEdit({ kind: "set_overall_level", value })}
              />
              <SemanticReadOnlyField
                field="teacher_read_only"
                label="Teacher"
                rule={ruleFor(draft, "teacher_read_only")}
                issue={validationIssue}
                value={draft.teacherDisplay ?? (draft.teacherAuthority === "authenticated_new_form" ? "Authenticated GEL teacher" : "Historical teacher")}
              />
              <SemanticCheckboxField
                field="absent"
                label="Absent"
                rule={
                  isEditable(draft, "absent")
                    ? ruleFor(draft, "absent")
                    : undefined
                }
                issue={validationIssue}
                checked={draft.absent}
                onChange={(value) => onEdit({ kind: "set_absent", value })}
              />
            </div>
          </section>

          <TutorialTypeFields
            draft={draft}
            validationIssue={validationIssue}
            onEdit={onEdit}
            disabledHarperRules={disabledHarperRules}
            ignoredHarperFindings={ignoredHarperFindings}
            onDisableHarperRule={onDisableHarperRule}
            onIgnoreHarperFinding={onIgnoreHarperFinding}
            onAddHarperDictionaryTerm={onAddHarperDictionaryTerm}
            harperDictionaryRevision={harperDictionaryRevision}
          />

          {isEditable(draft, "teacher_comments") ? (
            <HarperFieldAssistant
              field="teacher_comments"
              variant="inline"
              label="Teacher comments"
              rule={ruleFor(draft, "teacher_comments")}
              issue={validationIssue}
              value={draft.teacherComments}
              maxLength={draft.formContract.teacherCommentsMaxChars}
              rows={8}
              onChange={(value) => onEdit({ kind: "set_teacher_comments", value })}
              onAccept={(value) => onEdit({ kind: "set_teacher_comments", value })}
              {...harperFieldAssistantCommon}
            />
          ) : (
            <SemanticTextAreaField
              field="teacher_comments"
              label="Teacher comments"
              rule={ruleFor(draft, "teacher_comments")}
              issue={validationIssue}
              value={draft.teacherComments}
              maxLength={draft.formContract.teacherCommentsMaxChars}
              rows={8}
              onChange={(value) => onEdit({ kind: "set_teacher_comments", value })}
            />
          )}

          <FinalAdditionalCommentsField
            draft={draft}
            validationIssue={validationIssue}
            onEdit={onEdit}
            disabledHarperRules={disabledHarperRules}
            ignoredHarperFindings={ignoredHarperFindings}
            onDisableHarperRule={onDisableHarperRule}
            onIgnoreHarperFinding={onIgnoreHarperFinding}
            onAddHarperDictionaryTerm={onAddHarperDictionaryTerm}
            harperDictionaryRevision={harperDictionaryRevision}
          />

          <div className="foundation-note">
            UI1c2–c4 render the complete governed Standard, Initial and Final
            semantic field sets. New-type actions remain in selected-student
            context. Submission, durable tutorial drafts, teacher reassignment and GEL/archive write
            capability remain out of scope. Harper checking is Rust-owned assistance;
            its local dictionary is separate Writer preference state and never tutorial authority.
            Teacher comments and Final additional comments render inline Harper
            highlights (CELS-style mirror-div wavy underlines) and per-finding
            actions (apply suggestion, add to dictionary, disable rule, skip issue);
            aims remain a side-panel-only assistant.
          </div>
        </div>
      )}
    </section>
  );
}
