interface Props {
  open: boolean;
  action: string;
  onDiscard: () => void;
  onStay: () => void;
}

export function DiscardDraftDialog({ open, action, onDiscard, onStay }: Props) {
  if (!open) return null;
  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="discard-title">
        <h2 id="discard-title">Discard unsaved tutorial changes?</h2>
        <p>The current UI1 draft exists only in memory. Discard it before {action}?</p>
        <div className="dialog-actions">
          <button className="danger" type="button" onClick={onDiscard}>Discard draft</button>
          <button type="button" onClick={onStay} autoFocus>Stay</button>
        </div>
      </section>
    </div>
  );
}
