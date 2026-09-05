import type { ChangeEvent, ReactNode } from "react";
import type { DraftFieldRuleView, DraftOptionView, DraftValidationIssue } from "../types";

type SemanticField = DraftFieldRuleView["field"];

interface FieldShellProps {
  field: SemanticField;
  label: string;
  rule: DraftFieldRuleView | undefined;
  issue: DraftValidationIssue | null;
  children: (editable: boolean) => ReactNode;
  className?: string;
}

function issueForField(issue: DraftValidationIssue | null, field: SemanticField) {
  return issue?.field === field ? issue : null;
}

function FieldShell({ field, label, rule, issue, children, className = "" }: FieldShellProps) {
  if (!rule || rule.disposition === "inapplicable" || rule.disposition === "hidden_preserved") {
    return null;
  }
  const fieldIssue = issueForField(issue, field);
  const editable = rule.disposition === "editable";
  return (
    <label className={`semantic-field ${className}`.trim()} data-semantic-field={field}>
      <span className="semantic-field-label">{label}</span>
      {children(editable)}
      {fieldIssue && (
        <span className={`field-validation field-validation-${fieldIssue.severity}`} role="alert">
          {fieldIssue.message}
        </span>
      )}
    </label>
  );
}

interface DateProps {
  field: SemanticField;
  label: string;
  rule: DraftFieldRuleView | undefined;
  issue: DraftValidationIssue | null;
  value: string;
  onChange: (value: string) => void;
}

export function SemanticDateField({ field, label, rule, issue, value, onChange }: DateProps) {
  return (
    <FieldShell field={field} label={label} rule={rule} issue={issue}>
      {(editable) => (
        <input
          type="date"
          value={value}
          disabled={!editable}
          aria-invalid={issueForField(issue, field)?.severity === "error" || undefined}
          onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
        />
      )}
    </FieldShell>
  );
}

interface SelectProps {
  field: SemanticField;
  label: string;
  rule: DraftFieldRuleView | undefined;
  issue: DraftValidationIssue | null;
  value: string | null;
  options: DraftOptionView[];
  emptyLabel?: string;
  onChange: (value: string | null) => void;
}

export function SemanticSelectField({ field, label, rule, issue, value, options, emptyLabel = "Choose…", onChange }: SelectProps) {
  return (
    <FieldShell field={field} label={label} rule={rule} issue={issue}>
      {(editable) => (
        <select
          value={value ?? ""}
          disabled={!editable}
          aria-invalid={issueForField(issue, field)?.severity === "error" || undefined}
          onChange={(event: ChangeEvent<HTMLSelectElement>) => onChange(event.target.value || null)}
        >
          <option value="">{emptyLabel}</option>
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      )}
    </FieldShell>
  );
}

interface CheckboxProps {
  field: SemanticField;
  label: string;
  rule: DraftFieldRuleView | undefined;
  issue: DraftValidationIssue | null;
  checked: boolean;
  onChange: (value: boolean) => void;
}

export function SemanticCheckboxField({ field, label, rule, issue, checked, onChange }: CheckboxProps) {
  if (!rule || rule.disposition === "inapplicable" || rule.disposition === "hidden_preserved") {
    return null;
  }
  const fieldIssue = issueForField(issue, field);
  const editable = rule.disposition === "editable";
  return (
    <div className="semantic-checkbox" data-semantic-field={field}>
      <label className="checkbox-label">
        <input
          type="checkbox"
          checked={checked}
          disabled={!editable}
          aria-invalid={fieldIssue?.severity === "error" || undefined}
          onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.checked)}
        />
        {label}
      </label>
      {fieldIssue && <span className={`field-validation field-validation-${fieldIssue.severity}`} role="alert">{fieldIssue.message}</span>}
    </div>
  );
}

interface TextAreaProps {
  field: SemanticField;
  label: string;
  rule: DraftFieldRuleView | undefined;
  issue: DraftValidationIssue | null;
  value: string;
  maxLength?: number;
  rows?: number;
  onChange: (value: string) => void;
}

export function SemanticTextAreaField({ field, label, rule, issue, value, maxLength, rows = 8, onChange }: TextAreaProps) {
  return (
    <FieldShell field={field} label={label} rule={rule} issue={issue} className="text-field">
      {(editable) => (
        <>
          <textarea
            value={value}
            maxLength={maxLength}
            rows={rows}
            disabled={!editable}
            aria-invalid={issueForField(issue, field)?.severity === "error" || undefined}
            onChange={(event: ChangeEvent<HTMLTextAreaElement>) => onChange(event.target.value)}
          />
          {maxLength == null ? null : <span className="char-count">{Array.from(value).length}/{maxLength}</span>}
        </>
      )}
    </FieldShell>
  );
}

interface ReadOnlyProps {
  field: SemanticField;
  label: string;
  rule: DraftFieldRuleView | undefined;
  issue: DraftValidationIssue | null;
  value: string;
}

export function SemanticReadOnlyField({ field, label, rule, issue, value }: ReadOnlyProps) {
  return (
    <FieldShell field={field} label={label} rule={rule} issue={issue}>
      {() => <output className="read-only-value">{value}</output>}
    </FieldShell>
  );
}

export function DraftValidationIssueSummary({ issue }: { issue: DraftValidationIssue | null }) {
  if (!issue) return null;
  return (
    <div className={`draft-validation-summary draft-validation-${issue.severity}`} role="alert">
      <strong>{issue.code}</strong>
      <span>{issue.message}</span>
    </div>
  );
}
