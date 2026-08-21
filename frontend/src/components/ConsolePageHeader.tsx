import type { ReactNode } from 'react'

interface ConsolePageHeaderProps {
  action?: ReactNode
  eyebrow?: string
  summary?: string
  title: string
}

/**
 * A deliberately small shared header for authenticated operator views.
 * It keeps page hierarchy consistent without introducing a component library.
 */
export function ConsolePageHeader({ action, eyebrow, summary, title }: ConsolePageHeaderProps) {
  return (
    <header className="console-page-header">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        {summary && <p className="console-page-summary">{summary}</p>}
      </div>
      {action && <div className="console-page-action">{action}</div>}
    </header>
  )
}
