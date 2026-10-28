import { Stethoscope } from 'lucide-react'

export default function Header() {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <div className="brand-lockup">
          <span className="app-mark" aria-hidden="true"><Stethoscope size={20} strokeWidth={1.8} /></span>
          <div>
            <p className="brand-name">Medication Safety Agent Chain</p>
            <p className="app-subtitle">Recorded interaction information, grounded in a source dataset</p>
          </div>
        </div>
        <span className="source-indicator"><span className="source-dot" aria-hidden="true" />DDInter 2.0 dataset</span>
      </div>
      <div className="hero-copy">
        <p className="hero-eyebrow">Medication interaction screening</p>
        <h1 className="hero-title">Understand medication interactions with greater clarity.</h1>
        <p className="hero-description">Extract medications from a clinical note, review recorded drug interaction data, and understand which findings may need professional review.</p>
      </div>
    </header>
  )
}
