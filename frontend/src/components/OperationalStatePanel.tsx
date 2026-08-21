import type { ReactNode } from 'react'

import { CircleCheckBig, Info, TriangleAlert } from 'lucide-react'

interface OperationalStatePanelProps {
  action?: ReactNode
  children: ReactNode
  title: string
  tone?: 'empty' | 'error' | 'info'
}

export function OperationalStatePanel({ action, children, title, tone = 'info' }: OperationalStatePanelProps) {
  const Icon = tone === 'error' ? TriangleAlert : tone === 'empty' ? CircleCheckBig : Info

  return (
    <section className={`operational-state operational-state-${tone}`} role={tone === 'error' ? 'alert' : undefined}>
      <span className="operational-state-icon" aria-hidden="true"><Icon size={18} /></span>
      <div className="operational-state-copy">
        <strong>{title}</strong>
        <div>{children}</div>
      </div>
      {action && <div className="operational-state-action">{action}</div>}
    </section>
  )
}
