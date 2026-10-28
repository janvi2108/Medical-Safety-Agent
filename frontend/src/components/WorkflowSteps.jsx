import { Database, FileText, MessageCircle } from 'lucide-react'

const STEPS = [
  { title: 'Extract', detail: 'Identify medication names, doses, frequencies and routes.', Icon: FileText },
  { title: 'Verify', detail: 'Check matched pairs against DDInter 2.0.', Icon: Database },
  { title: 'Explain', detail: 'Review recorded findings and limits.', Icon: MessageCircle },
]

export default function WorkflowSteps() {
  return (
    <section className="workflow" aria-label="How the review works">
      {STEPS.map(({ title, detail, Icon }, index) => (
        <article className="workflow-step" key={title}>
          <span className="workflow-icon"><Icon size={17} strokeWidth={1.8} aria-hidden="true" /></span>
          <div>
            <p className="workflow-overline">0{index + 1}</p>
            <h2>{title}</h2>
            <p className="workflow-detail">{detail}</p>
          </div>
        </article>
      ))}
    </section>
  )
}
