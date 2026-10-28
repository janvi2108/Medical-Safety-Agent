const SAMPLE_NOTES = [
  {
    id: 'known-interaction',
    label: 'Warfarin + aspirin',
    text: 'Patient is currently taking warfarin 5 mg once daily and aspirin 81 mg once daily. They also take metformin 500 mg twice daily.',
  },
  {
    id: 'no-interaction',
    label: 'Metformin + lisinopril',
    text: 'Patient reports good adherence to Metformin 500mg twice daily and Lisinopril 10mg once daily. Blood pressure well controlled at last visit.',
  },
  {
    id: 'multiple',
    label: 'Four medications',
    text: "Patient's current medication list includes Simvastatin 20mg at bedtime, Lisinopril 10mg daily, Omeprazole 20mg daily, and Ibuprofen 400mg as needed for joint pain.",
  },
]

export default function ClinicalNoteInput({ value, onChange, onNoteChange, onSubmit, disabled, validationError }) {
  const updateNote = onNoteChange || onChange

  return (
    <section className="panel note-panel" aria-labelledby="note-input-heading">
      <form onSubmit={onSubmit} noValidate>
        <div className="note-heading-row">
          <div>
            <span className="section-kicker">Start a review</span>
            <h2 id="note-input-heading" className="panel-heading">Clinical note</h2>
            <p id="clinical-note-help" className="panel-helper">Use a synthetic note for this educational prototype. Include only details needed to identify medications.</p>
          </div>
          <span className="input-count" aria-label={`${value.length} characters`}>{value.length} characters</span>
        </div>

        <div className="sample-row" role="group" aria-label="Choose an example clinical note">
          <span className="sample-label">Try an example</span>
          {SAMPLE_NOTES.map((sample) => (
            <button
              key={sample.id}
              type="button"
              className="sample-chip"
              onClick={() => updateNote(sample.text)}
              disabled={disabled}
            >
              {sample.label}
            </button>
          ))}
        </div>

        <label htmlFor="clinical-note" className="input-label">Note text</label>
        <textarea
          id="clinical-note"
          className={`note-textarea${validationError ? ' note-textarea--invalid' : ''}`}
          value={value}
          onChange={(event) => updateNote(event.target.value)}
          placeholder="For example: Patient takes warfarin 5 mg once daily and aspirin 81 mg once daily."
          maxLength={20000}
          disabled={disabled}
          aria-describedby={`clinical-note-help${validationError ? ' clinical-note-error' : ''}`}
          aria-invalid={Boolean(validationError)}
        />
        {validationError && <p className="field-error" id="clinical-note-error" role="alert">{validationError}</p>}

        <div className="panel-actions">
          <p className="privacy-hint">Use fictional or de-identified information only.</p>
          <button type="submit" className="primary-button" disabled={disabled}>
            {disabled ? <><span className="button-spinner" aria-hidden="true" />Analyzing...</> : <>Analyze medications <span aria-hidden="true">-&gt;</span></>}
          </button>
        </div>
      </form>
    </section>
  )
}
