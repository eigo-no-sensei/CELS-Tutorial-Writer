import { useEffect, useMemo, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { harperCheck, harperDictionaryAdd } from "../api";
import type {
  DraftFieldRuleView,
  DraftValidationIssue,
  HarperCheckDto,
  HarperFindingDto,
  HarperSuggestionDto,
} from "../types";

interface BaseProps {
  field: HarperCheckDto["field"];
  value: string;
  onAccept: (value: string) => void;
  /** When "inline", the assistant renders its own textarea with a mirror-div
   * highlight overlay (CELS-style wavy underlines). When "side-panel" (the
   * default and the original behavior), only the side-panel finding list is
   * rendered and the parent is expected to own the textarea. */
  variant?: "side-panel" | "inline";
  /** Session-only state hoisted to App so it survives per-field editor unmount/remount. */
  disabledRules?: string[];
  ignoredFindingKeys?: Set<string>;
  onDisableRule?: (rule: string) => void;
  onIgnoreFinding?: (findingKey: string) => void;
  onAddDictionaryTerm?: (word: string) => Promise<void>;
  /** Bumped by the parent (App) whenever the Harper user dictionary changes,
   * whether through a finding-card Add-to-dictionary action or through the
   * standalone HarperDictionaryPanel. Triggers a debounced re-lint against
   * the new dictionary. */
  dictionaryRevision?: number;
}

interface InlineProps extends BaseProps {
  variant: "inline";
  label: string;
  rule: DraftFieldRuleView | undefined;
  issue: DraftValidationIssue | null;
  maxLength?: number;
  rows?: number;
  onChange: (value: string) => void;
}

interface SidePanelProps extends BaseProps {
  variant?: "side-panel";
}

type Props = InlineProps | SidePanelProps;

const DEBOUNCE_MS = 350;

/** Single-token gate for the "Add to dictionary" action on a finding card.
 * Matches the CELS pattern: only single alphanumeric/apostrophe/hyphen tokens
 * can be added; multi-word excerpts are silently excluded. */
function dictionaryCandidate(excerpt: string): string | null {
  const trimmed = excerpt.trim();
  if (!trimmed) return null;
  return /^[\p{L}\p{N}'’-]+$/u.test(trimmed) ? trimmed : null;
}

/** Stable identity for a finding. Mirrors CELS's `lintKey`/`harperIssueKey`
 * pattern: a NUL-separated composite of the immutable finding attributes so
 * skip/active-highlight state can be keyed by identity rather than index. */
function findingKey(field: string, finding: HarperFindingDto): string {
  return `${field}\u0000${finding.rule}\u0000${finding.spanStart}:${finding.spanEnd}\u0000${finding.lintKind}\u0000${finding.originalText}\u0000${finding.message}`;
}

export function HarperFieldAssistant(props: Props) {
  const {
    field,
    value,
    onAccept,
    variant = "side-panel",
    disabledRules = [],
    ignoredFindingKeys = new Set<string>(),
    onDisableRule,
    onIgnoreFinding,
    onAddDictionaryTerm,
    dictionaryRevision = 0,
  } = props;

  const [result, setResult] = useState<HarperCheckDto | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeFindingKey, setActiveFindingKey] = useState<string | null>(null);
  const [dictionaryBusyKey, setDictionaryBusyKey] = useState<string | null>(null);
  const [addDictionaryError, setAddDictionaryError] = useState<string | null>(null);
  const requestId = useRef(0);
  const sourceSnapshot = useRef(value);
  const highlightMirrorRef = useRef<HTMLDivElement | null>(null);

  // Debounced + stale-result-safe Harper check. The structural gate at
  // tools/check_ui1d_harper.py asserts that this component still contains the
  // literal "350" debounce constant, the `requestId` race-guard ref, the
  // `sourceSnapshot` source-snapshot ref, and the `sourceText !== value`
  // stale-result rejection. All four invariants are preserved here.
  useEffect(() => {
    sourceSnapshot.current = value;
    const id = ++requestId.current;
    const timer = window.setTimeout(() => {
      if (!value.trim()) {
        setResult(null);
        setBusy(false);
        setError(null);
        return;
      }
      setBusy(true);
      setError(null);
      void harperCheck(field, value, disabledRules, [])
        .then((next) => {
          if (id !== requestId.current || sourceSnapshot.current !== value) return;
          setResult(next);
        })
        .catch((reason) => {
          if (id !== requestId.current || sourceSnapshot.current !== value) return;
          setResult(null);
          setError(typeof reason === "string" ? reason : "Harper check failed");
        })
        .finally(() => {
          if (id === requestId.current && sourceSnapshot.current === value) setBusy(false);
        });
    }, DEBOUNCE_MS);

    return () => window.clearTimeout(timer);
    // `disabledRules` is a dep because changes to it must trigger a re-check so
    // that a newly-disabled rule disappears from the side panel. We deliberately
    // include `field` and `value` too; `dictionaryRevision` is included because a
    // successful Add-to-dictionary must force a re-lint against the new dict.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [field, value, disabledRules, dictionaryRevision]);

  useEffect(() => {
    if (result && result.sourceText !== value) setResult(null);
  }, [result, value]);

  const findings = result?.findings ?? [];

  // Filter findings against the session-only ignored set. Skipped findings
  // disappear instantly without waiting for a re-lint, mirroring CELS.
  const visibleFindings = useMemo(
    () => findings.filter((finding) => !ignoredFindingKeys.has(findingKey(field, finding))),
    [field, findings, ignoredFindingKeys],
  );

  // The tokenizer / span renderer. Ported from CELS-Report-Generator's
  // StudentDetail.tsx highlightedComment useMemo: builds a Set of segment
  // boundaries from `0`, `characters.length`, and every (clamped) finding
  // spanStart/spanEnd, then renders each adjacent pair as a `<span>` or `<mark>`
  // with the spelling/grammar/active color variant chosen from the covering
  // findings. Used only when `variant === "inline"`.
  const highlightedContent = useMemo<ReactNode>(() => {
    if (variant !== "inline") return null;
    const characters = Array.from(value);
    if (characters.length === 0 || visibleFindings.length === 0) return value;
    const boundaries = new Set<number>([0, characters.length]);
    for (const finding of visibleFindings) {
      boundaries.add(Math.max(0, Math.min(characters.length, finding.spanStart)));
      boundaries.add(Math.max(0, Math.min(characters.length, finding.spanEnd)));
    }
    const sorted = Array.from(boundaries).sort((a, b) => a - b);
    return sorted.slice(0, -1).map((start, index) => {
      const end = sorted[index + 1];
      const text = characters.slice(start, end).join("");
      const covering = visibleFindings.filter(
        (finding) => finding.spanStart < end && finding.spanEnd > start,
      );
      if (covering.length === 0) return <span key={`${start}-${end}`}>{text}</span>;
      const spelling = covering.some((finding) => finding.lintKind === "Spelling");
      const active = covering.some(
        (finding) => findingKey(field, finding) === activeFindingKey,
      );
      const className = [
        "comment-editor__highlight",
        spelling ? "comment-editor__highlight--spelling" : "comment-editor__highlight--grammar",
        active ? "comment-editor__highlight--active" : "",
      ]
        .filter(Boolean)
        .join(" ");
      return (
        <mark className={className} key={`${start}-${end}`}>
          {text}
        </mark>
      );
    });
  }, [variant, value, visibleFindings, activeFindingKey, field]);

  async function handleAddDictionary(finding: HarperFindingDto, key: string) {
    if (!onAddDictionaryTerm) return;
    const candidate = dictionaryCandidate(finding.originalText);
    if (!candidate) return;
    setDictionaryBusyKey(key);
    setAddDictionaryError(null);
    try {
      await onAddDictionaryTerm(candidate);
      // The parent bumps `dictionaryRevision` on success, which triggers the
      // debounced re-lint effect via its dep list. The finding (if it was a
      // Spelling finding) disappears from the new lint set.
    } catch (reason) {
      setAddDictionaryError(typeof reason === "string" ? reason : "Unable to add dictionary word");
    } finally {
      setDictionaryBusyKey(null);
    }
  }

  function handleApplySuggestion(suggestion: HarperSuggestionDto) {
    setResult(null);
    setActiveFindingKey(null);
    onAccept(suggestion.replacementText);
  }

  function renderSuggestionButtons(finding: HarperFindingDto, key: string) {
    if (finding.suggestions.length === 0) return null;
    return (
      <div className="harper-lint__suggestions">
        {finding.suggestions.map((suggestion, suggestionIndex) => (
          <button
            key={`${suggestion.label}-${suggestionIndex}`}
            type="button"
            className="secondary harper-suggestion"
            title={suggestion.label}
            onClick={() => handleApplySuggestion(suggestion)}
            disabled={sourceSnapshot.current !== value}
          >
            {suggestion.label || `Apply suggestion ${suggestionIndex + 1}`}
          </button>
        ))}
      </div>
    );
  }

  function renderFindingCard(finding: HarperFindingDto, index: number) {
    const key = findingKey(field, finding);
    const candidate = dictionaryCandidate(finding.originalText);
    const isActive = activeFindingKey === key;
    const dictionaryActionEnabled = candidate !== null && onAddDictionaryTerm !== undefined;
    return (
      <article
        className={`harper-lint${isActive ? " harper-lint--active" : ""}`}
        key={`${finding.lintKind}-${index}`}
        tabIndex={0}
        onMouseEnter={() => setActiveFindingKey(key)}
        onMouseLeave={() => setActiveFindingKey((current) => (current === key ? null : current))}
        onFocus={() => setActiveFindingKey(key)}
        onBlur={() => setActiveFindingKey((current) => (current === key ? null : current))}
      >
        <div className="harper-lint__topline">
          <span className="harper-lint__kind">{finding.lintKind}</span>
          <span className="harper-lint__rule" title={`Harper rule: ${finding.rule}`}>
            {finding.rule}
          </span>
          {finding.originalText ? <code>{finding.originalText}</code> : null}
        </div>
        <p>{finding.message}</p>
        {renderSuggestionButtons(finding, key)}
        <div className="harper-lint__actions">
          {dictionaryActionEnabled ? (
            <button
              type="button"
              className="harper-lint__action"
              disabled={dictionaryBusyKey === key}
              onClick={() => void handleAddDictionary(finding, key)}
            >
              {dictionaryBusyKey === key ? "Adding…" : "Add to dictionary"}
            </button>
          ) : null}
          {onDisableRule ? (
            <button
              type="button"
              className="harper-lint__action"
              disabled={disabledRules.includes(finding.rule)}
              title={`Disable ${finding.rule} for the rest of this session`}
              onClick={() => onDisableRule(finding.rule)}
            >
              Disable rule
            </button>
          ) : null}
          {onIgnoreFinding ? (
            <button
              type="button"
              className="harper-lint__action"
              title="Ignore this specific issue until the current session ends"
              onClick={() => onIgnoreFinding(key)}
            >
              Skip issue
            </button>
          ) : null}
        </div>
      </article>
    );
  }

  function renderSidePanel() {
    if (!busy && !error && visibleFindings.length === 0 && !addDictionaryError) return null;
    return (
      <div className="harper-assistant" data-harper-field={field}>
        <div className="harper-assistant-heading">
          <span>Harper {result?.engineVersion ?? ""}</span>
          {busy && <span className="subtle">Checking…</span>}
          {!busy && visibleFindings.length > 0 && (
            <span className="subtle">
              {visibleFindings.length} {visibleFindings.length === 1 ? "issue" : "issues"}
            </span>
          )}
        </div>
        {error && (
          <span className="field-validation field-validation-warning" role="status">
            {error}
          </span>
        )}
        {addDictionaryError && (
          <span className="field-validation field-validation-error" role="alert">
            {addDictionaryError}
          </span>
        )}
        <div className="harper-lints">
          {visibleFindings.map((finding, index) => renderFindingCard(finding, index))}
        </div>
      </div>
    );
  }

  if (variant === "side-panel") {
    return renderSidePanel();
  }

  // Inline variant: render a label + the highlight surface (mirror + textarea)
  // + the side panel. Mirrors CELS StudentDetail's comment-editor DOM, but
  // adapted to the gel-rust-bootstrap SemanticFieldControl shell contract.
  const inlineProps = props as InlineProps;
  const fieldRule = inlineProps.rule;
  if (!fieldRule || fieldRule.disposition === "inapplicable" || fieldRule.disposition === "hidden_preserved") {
    return null;
  }
  const editable = fieldRule.disposition === "editable";
  const fieldIssue = inlineProps.issue?.field === field ? inlineProps.issue : null;
  const rows = inlineProps.rows ?? 8;
  const maxLength = inlineProps.maxLength;
  const charCount = Array.from(value).length;
  return (
    <label className="semantic-field text-field" data-semantic-field={field}>
      <span className="semantic-field-label">{inlineProps.label}</span>
      <div className="comment-editor__surface" data-harper-field={field}>
        <div className="comment-editor__highlights" aria-hidden="true" ref={highlightMirrorRef}>
          <div className="comment-editor__highlights-content">{highlightedContent}</div>
        </div>
        <textarea
          className="comment-editor__textarea"
          value={value}
          rows={rows}
          maxLength={maxLength}
          disabled={!editable}
          spellCheck={false}
          aria-invalid={fieldIssue?.severity === "error" || undefined}
          aria-label={inlineProps.label}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => inlineProps.onChange(event.target.value)}
          onScroll={(event) => {
            const mirror = highlightMirrorRef.current;
            if (!mirror) return;
            mirror.scrollTop = event.currentTarget.scrollTop;
            mirror.scrollLeft = event.currentTarget.scrollLeft;
          }}
        />
      </div>
      {maxLength == null ? null : (
        <span className="char-count">
          {charCount}/{maxLength}
        </span>
      )}
      {fieldIssue && (
        <span className={`field-validation field-validation-${fieldIssue.severity}`} role="alert">
          {fieldIssue.message}
        </span>
      )}
      {renderSidePanel()}
    </label>
  );
}
