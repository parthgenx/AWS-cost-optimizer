import {
  AlertCircle,
  ArrowRight,
  BadgeDollarSign,
  BarChart3,
  Check,
  CloudCog,
  FileSearch,
  HardDrive,
  KeyRound,
  LoaderCircle,
  ScanSearch,
  Settings2,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'

import { getMissingConfigurationVariables } from '../config'

export function CenteredState({ label }: { label: string }) {
  return (
    <main className="centered-state" aria-live="polite">
      <LoaderCircle aria-hidden="true" className="spin" size={28} />
      <p>{label}</p>
    </main>
  )
}

export function AuthFailure({ message }: { message: string }) {
  return (
    <main className="centered-state state-card" role="alert">
      <AlertCircle aria-hidden="true" className="state-icon state-icon-error" size={30} />
      <div>
        <p className="eyebrow">Secure access unavailable</p>
        <h1>We could not verify your session.</h1>
        <p className="state-copy">{message}</p>
      </div>
      <a className="text-link" href="/">
        Return to sign in <ArrowRight aria-hidden="true" size={16} />
      </a>
    </main>
  )
}

export function SignInPrompt({ onSignIn }: { onSignIn: () => void }) {
  return (
    <main className="sign-in-page">
      <header className="sign-in-header">
        <div className="sign-in-shell sign-in-header-content">
          <div className="sign-in-brand">
            <div className="brand-mark" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
            <div>
              <strong>AWS Cost Optimizer</strong>
              <span>Cost operations workspace</span>
            </div>
          </div>
          <span className="sign-in-context"><ShieldCheck aria-hidden="true" size={15} /> Self-hosted AWS operator console</span>
        </div>
      </header>

      <section className="sign-in-shell sign-in-canvas">
        <section className="sign-in-narrative" aria-labelledby="sign-in-heading">
          <p className="eyebrow">AWS cost operations</p>
          <h1 id="sign-in-heading">Identify avoidable cloud spend. Review it with confidence.</h1>
          <p className="sign-in-description">
            A safe operator workspace for surfacing unused AWS resources, retaining the evidence,
            and estimating savings before any approved cleanup is requested.
          </p>

          <ul className="sign-in-capabilities" aria-label="Product capabilities">
            <li>
              <span className="sign-in-capability-icon" aria-hidden="true"><ScanSearch size={17} /></span>
              <div><strong>Detect waste</strong><span>Prioritize costly unused resources</span></div>
            </li>
            <li>
              <span className="sign-in-capability-icon" aria-hidden="true"><FileSearch size={17} /></span>
              <div><strong>Review evidence</strong><span>Inspect the signals behind each finding</span></div>
            </li>
            <li>
              <span className="sign-in-capability-icon" aria-hidden="true"><ShieldCheck size={17} /></span>
              <div><strong>Act with guardrails</strong><span>EBS cleanup requires approval and revalidation</span></div>
            </li>
          </ul>

          <div className="sign-in-action">
            <button className="primary-button sign-in-button" type="button" onClick={onSignIn}>
              Continue with secure sign in
              <ArrowRight aria-hidden="true" size={18} />
            </button>
            <span><KeyRound aria-hidden="true" size={14} /> Cognito-protected operator access</span>
          </div>
          <p className="sign-in-footnote">
            Public registration is disabled. Access is managed by this deployment&apos;s administrator.
          </p>
        </section>

        <aside className="sign-in-preview" aria-labelledby="preview-heading">
          <div className="preview-app-header">
            <div>
              <p className="preview-kicker"><Sparkles aria-hidden="true" size={14} /> Illustrative interface</p>
              <h2 id="preview-heading">Cost review workspace</h2>
            </div>
            <span className="preview-not-live">Not live AWS data</span>
          </div>

          <section className="preview-metrics" aria-label="Illustrative overview metrics">
            <article>
              <span><CloudCog aria-hidden="true" size={16} /> Open findings</span>
              <strong>03</strong>
              <small>Illustrative review queue</small>
            </article>
            <article>
              <span><BadgeDollarSign aria-hidden="true" size={16} /> Potential savings</span>
              <strong>$168<span>/mo</span></strong>
              <small>Illustrative estimates</small>
            </article>
            <article>
              <span><BarChart3 aria-hidden="true" size={16} /> Latest scan</span>
              <strong>Ready</strong>
              <small>Illustrative scanner state</small>
            </article>
          </section>

          <div className="preview-workspace">
            <section className="preview-findings" aria-label="Illustrative findings list">
              <div className="preview-section-heading">
                <div><span>Review queue</span><strong>Findings requiring attention</strong></div>
                <span className="preview-count">3 items</span>
              </div>
              <article className="preview-finding preview-finding-selected">
                <span className="preview-resource-icon" aria-hidden="true"><HardDrive size={17} /></span>
                <div><strong>Unattached EBS volume</strong><span>vol-illustrative-01 · ap-south-1</span></div>
                <em>$24/mo</em>
              </article>
              <article className="preview-finding">
                <span className="preview-resource-icon preview-resource-icon-muted" aria-hidden="true"><CloudCog size={17} /></span>
                <div><strong>Unused Elastic IP</strong><span>eipalloc-illustrative-02</span></div>
                <em>$4/mo</em>
              </article>
              <article className="preview-finding">
                <span className="preview-resource-icon preview-resource-icon-muted" aria-hidden="true"><BarChart3 size={17} /></span>
                <div><strong>Idle RDS instance</strong><span>db-illustrative-dev</span></div>
                <em>$140/mo</em>
              </article>
            </section>

            <section className="preview-detail" aria-label="Illustrative finding evidence">
              <div className="preview-section-heading">
                <div><span>Selected finding</span><strong>Evidence and safety state</strong></div>
                <span className="preview-severity">Review</span>
              </div>
              <div className="preview-detail-resource"><HardDrive aria-hidden="true" size={17} /><span>Unattached EBS volume</span></div>
              <dl className="preview-evidence">
                <div><dt>State</dt><dd><Check aria-hidden="true" size={13} /> Available</dd></div>
                <div><dt>Attachment</dt><dd><Check aria-hidden="true" size={13} /> None detected</dd></div>
                <div><dt>Age threshold</dt><dd><Check aria-hidden="true" size={13} /> Requirement met</dd></div>
              </dl>
              <div className="preview-savings">
                <span>Illustrative monthly estimate</span>
                <strong>$24.00 <small>/ month</small></strong>
              </div>
              <div className="preview-approval-note"><ShieldCheck aria-hidden="true" size={15} /> Approval required before an EBS cleanup request.</div>
            </section>
          </div>

          <ol className="preview-flow" aria-label="Illustrative safe cleanup workflow">
            <li><span>1</span><div><strong>Scan</strong><small>Detect waste</small></div></li>
            <li><span>2</span><div><strong>Review</strong><small>Inspect evidence</small></div></li>
            <li><span>3</span><div><strong>Approve</strong><small>Operator decision</small></div></li>
            <li><span>4</span><div><strong>Revalidate</strong><small>Before cleanup</small></div></li>
          </ol>
          <p className="preview-disclaimer">All values and resources in this preview are illustrative only.</p>
        </aside>
      </section>
    </main>
  )
}

export function ConfigurationRequired() {
  const missing = getMissingConfigurationVariables()

  return (
    <main className="centered-state state-card configuration-card">
      <Settings2 aria-hidden="true" className="state-icon" size={30} />
      <div>
        <p className="eyebrow">Local setup required</p>
        <h1>Connect this dashboard to your AWS deployment.</h1>
        <p className="state-copy">
          Add the public deployment values to <code>frontend/.env.local</code>. No AWS secrets
          belong in this application.
        </p>
      </div>
      <ul className="configuration-list">
        {missing.map((name) => (
          <li key={name}>{name}</li>
        ))}
      </ul>
    </main>
  )
}
