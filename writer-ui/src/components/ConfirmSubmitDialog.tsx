interface Props {
  open: boolean;
  studentName: string;
  tutorialType: string;
  tutorialDate: string;
  isNew: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmSubmitDialog({
  open,
  studentName,
  tutorialType,
  tutorialDate,
  isNew,
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null;
  return (
    <div className="dialog-backdrop" role="presentation">
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="submit-title">
        <h2 id="submit-title">Submit tutorial to GEL server?</h2>
        <p>
          You are about to {isNew ? "create a new" : "update the historical"} <strong>{tutorialType}</strong> tutorial for <strong>{studentName}</strong> dated <strong>{tutorialDate}</strong>.
        </p>
        <p className="subtle" style={{ margin: "6px 0 12px" }}>
          This will dispatch a live HTTP POST to the school server and reconcile the record into your local archive.
        </p>
        <div className="dialog-actions">
          <button className="primary" type="button" onClick={onConfirm} autoFocus>
            Submit to GEL
          </button>
          <button type="button" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </section>
    </div>
  );
}
