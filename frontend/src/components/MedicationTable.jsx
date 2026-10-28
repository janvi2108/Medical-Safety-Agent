export default function MedicationTable({ medications }) {
  if (!medications || medications.length === 0) {
    return <p className="empty-note">No medications were found in this note.</p>
  }

  return (
    <div className="med-table-wrap">
      <table className="med-table">
        <thead>
          <tr>
            <th scope="col">Medication</th>
            <th scope="col">Dose</th>
            <th scope="col">Frequency</th>
            <th scope="col">Route</th>
          </tr>
        </thead>
        <tbody>
          {medications.map((medication, index) => (
            <tr key={`${medication.name}-${index}`}>
              <td data-label="Medication" className="med-name">{medication.name}</td>
              <td data-label="Dose">{medication.dose || <span className="not-stated">Not stated</span>}</td>
              <td data-label="Frequency">{medication.frequency || <span className="not-stated">Not stated</span>}</td>
              <td data-label="Route">{medication.route || <span className="not-stated">Not stated</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
