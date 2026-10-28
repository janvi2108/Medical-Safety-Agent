import { useRef, useState } from 'react'
import './App.css'
import Header from './components/Header.jsx'
import ClinicalNoteInput from './components/ClinicalNoteInput.jsx'
import MedicationTable from './components/MedicationTable.jsx'
import InteractionCard from './components/InteractionCard.jsx'
import PatientSummary from './components/PatientSummary.jsx'
import LoadingState from './components/LoadingState.jsx'
import ErrorMessage from './components/ErrorMessage.jsx'
import Disclaimer from './components/Disclaimer.jsx'
import WorkflowSteps from './components/WorkflowSteps.jsx'
import { analyzeClinicalNote } from './services/api.js'

export default function App() {
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [validationError, setValidationError] = useState('')
  const requestInFlight = useRef(false)

  const handleAnalyze = async (event) => {
    event?.preventDefault()
    if (requestInFlight.current) return
    if (!note.trim()) {
      setValidationError('Enter a synthetic clinical note before analyzing.')
      return
    }
    requestInFlight.current = true
    setValidationError('')
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const data = await analyzeClinicalNote(note)
      setResult(data)
    } catch (err) {
      setError(err.message)
    } finally {
      requestInFlight.current = false
      setLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <Header />

      <main className="app-main">
        <ClinicalNoteInput
          value={note}
          onChange={setNote}
          onSubmit={handleAnalyze}
          disabled={loading}
          validationError={validationError}
          onNoteChange={(value) => {
            setNote(value)
            if (validationError && value.trim()) setValidationError('')
          }}
        />

        <ErrorMessage message={error} />

        <WorkflowSteps />

        {loading && <LoadingState />}

        {result && !loading && (
          <>
            {result.warnings?.length > 0 && (
              <div className="warnings-block">
                {result.warnings.map((w, i) => (
                  <p key={i}>{w}</p>
                ))}
              </div>
            )}

            <section className="panel" aria-labelledby="meds-heading">
              <span className="section-kicker">From the note</span>
              <h2 id="meds-heading" className="panel-heading result-section-heading">Extracted medications</h2>
              <MedicationTable medications={result.medications} />
            </section>

            <InteractionCard interactions={result.interactions} />

            <PatientSummary summary={result.patient_summary} />
          </>
        )}
      </main>

      <Disclaimer />
    </div>
  )
}
