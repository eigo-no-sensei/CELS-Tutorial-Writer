import { useEffect, useState } from "react";
import { harperDictionaryAdd, harperDictionaryList, harperDictionaryRemove } from "../api";
import type { HarperDictionaryEntry } from "../types";

interface Props {
  /** Called after a successful add/remove so the parent can bump its
   * `harperDictionaryRevision` and trigger a re-lint on every mounted
   * HarperFieldAssistant. */
  onMutation?: () => void;
}

export function HarperDictionaryPanel({ onMutation }: Props) {
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState<HarperDictionaryEntry[]>([]);
  const [word, setWord] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    void harperDictionaryList().then(setEntries).catch(() => setError("Unable to load Harper dictionary"));
  }, [open]);

  async function addWord() {
    setError(null);
    try {
      const result = await harperDictionaryAdd(word);
      setEntries(result.words);
      setWord("");
      onMutation?.();
    } catch (reason) {
      setError(typeof reason === "string" ? reason : "Unable to add dictionary word");
    }
  }

  async function removeWord(value: string) {
    setError(null);
    try {
      const result = await harperDictionaryRemove(value);
      setEntries(result.words);
      onMutation?.();
    } catch (reason) {
      setError(typeof reason === "string" ? reason : "Unable to remove dictionary word");
    }
  }

  return (
    <div className="harper-dictionary">
      <button type="button" className="secondary" onClick={() => setOpen((current) => !current)}>
        {open ? "Hide dictionary" : "Dictionary"}
      </button>
      {open && (
        <div className="harper-dictionary-panel">
          <div className="harper-dictionary-add">
            <input
              value={word}
              placeholder="Add a word…"
              onChange={(event) => setWord(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void addWord();
              }}
            />
            <button type="button" className="secondary" disabled={!word.trim()} onClick={() => void addWord()}>
              Add
            </button>
          </div>
          {error && <p className="field-validation field-validation-error" role="alert">{error}</p>}
          {entries.length === 0 ? (
            <p className="subtle">No user dictionary words.</p>
          ) : (
            <ul className="harper-dictionary-list">
              {entries.map((entry) => (
                <li key={entry.word}>
                  <span>{entry.word}</span>
                  <button type="button" className="secondary" onClick={() => void removeWord(entry.word)}>Remove</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
