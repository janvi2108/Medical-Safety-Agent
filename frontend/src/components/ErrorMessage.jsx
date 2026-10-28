export default function ErrorMessage({ message }) {
  if (!message) return null
  return (
    <div className="error-message" role="alert">
      <p className="error-title">Analysis could not be completed</p>
      <p>{message}</p>
    </div>
  )
}
