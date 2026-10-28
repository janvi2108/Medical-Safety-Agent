export default function PatientSummary({ summary }) {
  if (!summary) return null

  return (
    <section className="panel" aria-labelledby="summary-heading">
      <span className="section-kicker">Plain-language review</span>
      <h2 id="summary-heading" className="panel-heading result-section-heading">For the patient</h2>

      <p className="summary-explanation">{summary.explanation}</p>

      {summary.what_to_know?.length > 0 && (
        <ul className="summary-list">
          {summary.what_to_know.map((point, i) => (
            <li key={i}>{point}</li>
          ))}
        </ul>
      )}

      <div className="summary-next-step">
        <span className="summary-next-step-label">Next step</span>
        <p>{summary.next_step}</p>
      </div>
    </section>
  )
}
