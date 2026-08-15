import type { ReactNode } from 'react'

import { Activity, BellRing, CloudCog, LayoutDashboard, LogOut, ShieldCheck } from 'lucide-react'
import { NavLink } from 'react-router-dom'

interface AppShellProps {
  children: ReactNode
  email: string | undefined
  onSignOut: () => void
}

export function AppShell({ children, email, onSignOut }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <strong>AWS Cost Optimizer</strong>
            <span>Operator console</span>
          </div>
        </div>

        <nav aria-label="Primary navigation" className="navigation">
          <NavLink className={({ isActive }) => `nav-item${isActive ? ' nav-item-active' : ''}`} end to="/">
            <LayoutDashboard aria-hidden="true" size={18} />
            Overview
          </NavLink>
          <NavLink className={({ isActive }) => `nav-item${isActive ? ' nav-item-active' : ''}`} to="/findings">
            <CloudCog aria-hidden="true" size={18} />
            Findings
          </NavLink>
          <span className="nav-item nav-item-disabled">
            <Activity aria-hidden="true" size={18} />
            Activity <em>Overview</em>
          </span>
        </nav>

        <div className="sidebar-safety">
          <ShieldCheck aria-hidden="true" size={18} />
          <div>
            <strong>Safety controls enabled</strong>
            <span>EBS cleanup remains approval-gated.</span>
          </div>
        </div>

        <div className="account-panel">
          <div className="account-avatar" aria-hidden="true">
            {(email?.[0] ?? 'O').toUpperCase()}
          </div>
          <div className="account-copy">
            <strong>{email ?? 'Authenticated operator'}</strong>
            <span>Cognito session</span>
          </div>
          <button aria-label="Sign out" className="icon-button" type="button" onClick={onSignOut}>
            <LogOut aria-hidden="true" size={17} />
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="mobile-header">
          <div className="brand brand-compact">
            <div className="brand-mark" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <strong>AWS Cost Optimizer</strong>
          </div>
          <button aria-label="Sign out" className="icon-button" type="button" onClick={onSignOut}>
            <LogOut aria-hidden="true" size={17} />
          </button>
        </header>
        <div className="content-frame">
          <div className="environment-label">
            <BellRing aria-hidden="true" size={15} />
            Self-hosted AWS account
          </div>
          {children}
        </div>
      </main>
    </div>
  )
}
