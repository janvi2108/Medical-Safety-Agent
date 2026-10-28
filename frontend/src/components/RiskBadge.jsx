const RISK_STYLES = {
  major: 'risk-badge risk-badge--major',
  moderate: 'risk-badge risk-badge--moderate',
  minor: 'risk-badge risk-badge--minor',
  unknown: 'risk-badge risk-badge--unknown',
}

export default function RiskBadge({ normalizedRisk, sourceRisk }) {
  const isUnknown = normalizedRisk === 'unknown'
  const className = RISK_STYLES[normalizedRisk] || RISK_STYLES.unknown
  const label = isUnknown ? 'Severity unknown' : `DDInter classification: ${sourceRisk}`

  return <span className={className}>{label}</span>
}
