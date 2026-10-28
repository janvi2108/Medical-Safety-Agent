export function getApiBaseUrl(viteEnv = import.meta.env) {
  const configuredBase = viteEnv.VITE_API_BASE_URL?.trim()
  const developmentFallback = viteEnv.DEV ? 'http://127.0.0.1:8001' : ''
  return (configuredBase || developmentFallback).replace(/\/+$/, '')
}

const API_BASE = getApiBaseUrl()

function isAnalysisResponse(data) {
  return Boolean(
    data &&
    Array.isArray(data.medications) &&
    data.medications.every((medication) => (
      medication && typeof medication.name === 'string' &&
      ['dose', 'frequency', 'route'].every((field) => medication[field] == null || typeof medication[field] === 'string')
    )) &&
    data.interactions &&
    Number.isInteger(data.interactions.pairs_checked) &&
    Array.isArray(data.interactions.interactions_found) &&
    data.interactions.interactions_found.every((record) => (
      record && typeof record.drug_a === 'string' && typeof record.drug_b === 'string' &&
      typeof record.source_risk === 'string' &&
      ['major', 'moderate', 'minor', 'unknown'].includes(record.normalized_risk) &&
      typeof record.source === 'string'
    )) &&
    Array.isArray(data.interactions.unmatched_drugs) &&
    data.interactions.unmatched_drugs.every((match) => match && typeof match.drug_name === 'string') &&
    data.safety &&
    ['none', 'caution', 'critical', 'unverified'].includes(data.safety.safety_level) &&
    typeof data.safety.show_critical_banner === 'boolean' &&
    (data.patient_summary == null || (
      typeof data.patient_summary === 'object' &&
      typeof data.patient_summary.explanation === 'string' &&
      Array.isArray(data.patient_summary.what_to_know) &&
      data.patient_summary.what_to_know.every((point) => typeof point === 'string') &&
      typeof data.patient_summary.next_step === 'string'
    )) &&
    (data.warnings == null || (Array.isArray(data.warnings) && data.warnings.every((warning) => typeof warning === 'string')))
  )
}

/**
 * Calls POST /analyze on the backend.
 * Throws an Error with a user-facing message on failure - components
 * should catch this and render it via <ErrorMessage />.
 */
export async function analyzeClinicalNote(clinicalNote) {
  if (!API_BASE) {
    throw new Error('The backend URL is not configured. Set VITE_API_BASE_URL for this deployment.')
  }

  let response
  try {
    response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clinical_note: clinicalNote }),
    })
  } catch (networkError) {
    throw new Error('Could not reach the server. Check that the backend is running.')
  }

  if (!response.ok) {
    let detail = 'The request could not be completed. Review the note and try again.'
    try {
      const body = await response.json()
      if (typeof body.detail === 'string' && body.detail.trim()) detail = body.detail
    } catch {
      // Keep a safe message if the response isn't JSON.
    }
    if (response.status === 503 && /database/i.test(detail)) {
      detail = `Interaction lookup could not be completed. ${detail}`
    }
    throw new Error(detail)
  }

  let data
  try {
    data = await response.json()
  } catch {
    throw new Error('The server returned an unreadable analysis response. Please retry.')
  }
  if (!isAnalysisResponse(data)) {
    throw new Error('The server returned an incomplete analysis response. No results were displayed. Please retry.')
  }
  return { ...data, warnings: data.warnings || [] }
}
