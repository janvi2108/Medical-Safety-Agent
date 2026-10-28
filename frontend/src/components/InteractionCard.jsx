import { CircleHelp, Database, SearchCheck } from 'lucide-react'
import RiskBadge from './RiskBadge.jsx'

export default function InteractionCard({ interactions }) {
  const { interactions_found: found = [], unmatched_drugs: unmatched = [], pairs_checked: pairsChecked = 0 } = interactions || {}

  return (
    <section className="panel results-panel" aria-labelledby="interaction-heading">
      <div className="results-heading-row">
        <div>
          <span className="section-kicker">Database review</span>
          <h2 id="interaction-heading" className="panel-heading">Interaction review</h2>
        </div>
        <span className="result-count"><Database size={15} aria-hidden="true" />{pairsChecked} {pairsChecked === 1 ? 'pair' : 'pairs'} checked</span>
      </div>

      <div className="clinical-context" role="note">
        <CircleHelp size={18} aria-hidden="true" />
        <p>DDInter classifications are source records, not personalized clinical risk assessments. Their significance depends on individual health conditions, other medications, doses, and clinical context. Review relevant findings with a qualified healthcare professional.</p>
      </div>

      {pairsChecked === 0 && unmatched.length === 0 && (
        <div className="empty-state"><SearchCheck size={20} aria-hidden="true" /><p>Fewer than two matched medications were available, so no pair could be checked.</p></div>
      )}

      {found.length === 0 && pairsChecked > 0 && (
        <div className="no-record-state">
          <span className="status-mark" aria-hidden="true">—</span>
          <div><h3>No matching record found</h3><p>No matching interaction record was found in the available DDInter dataset for the pairs checked. This does not establish that a combination is safe.</p></div>
        </div>
      )}

      {found.map((interaction, index) => {
        const severityUnknown = interaction.normalized_risk === 'unknown'
        return (
          <article key={`${interaction.drug_a}-${interaction.drug_b}-${index}`} className={`interaction-item${severityUnknown ? ' interaction-item--unknown' : ''}`}>
            <div className="interaction-item-header">
              <h3 className="interaction-pair">{interaction.drug_a} <span aria-hidden="true">+</span> {interaction.drug_b}</h3>
              <RiskBadge normalizedRisk={interaction.normalized_risk} sourceRisk={interaction.source_risk} />
            </div>
            <p className={`record-status${severityUnknown ? ' record-status--unknown' : ''}`}>
              {severityUnknown
                ? `DDInter record found — severity unknown. Recorded level: ${interaction.source_risk}.`
                : 'A DDInter source classification is recorded for this pair.'}
            </p>

            {interaction.mechanism && (
              <div className="interaction-detail">
                <span className="interaction-detail-label">Source note</span>
                <p>{interaction.mechanism}</p>
              </div>
            )}
            {interaction.management && (
              <div className="interaction-detail">
                <span className="interaction-detail-label">Source management information</span>
                <p>{interaction.management}</p>
              </div>
            )}
            {interaction.alternative_medications && (
              <div className="interaction-detail">
                <span className="interaction-detail-label">Source alternatives</span>
                <p>{interaction.alternative_medications}</p>
              </div>
            )}
            <div className="interaction-source">Source attribution: <strong>{interaction.source}</strong></div>
          </article>
        )
      })}

      {unmatched.length > 0 && (
        <div className="unmatched-block" role="note">
          <h3 className="unmatched-heading">Some medications were not matched</h3>
          <p>These names could not be matched to a DDInter medication record and were not checked against the other medications:</p>
          <ul>{unmatched.map((medication, index) => <li key={`${medication.drug_name}-${index}`}>{medication.drug_name}</li>)}</ul>
        </div>
      )}
    </section>
  )
}
