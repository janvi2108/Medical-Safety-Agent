const STAGES = [
  'Extracting medications from the note',
  'Checking matched pairs against DDInter 2.0',
  'Preparing a clear summary of the findings',
]

export default function LoadingState() {
  return (
    <div className="loading-state" role="status" aria-live="polite" aria-label="Analysis in progress">
      <div className="loading-spinner" aria-hidden="true" />
      <div>
        <p className="loading-title">Review in progress...</p>
        <ul className="loading-stage-list">
          {STAGES.map((stage) => <li key={stage}>{stage}</li>)}
        </ul>
      </div>
    </div>
  )
}
