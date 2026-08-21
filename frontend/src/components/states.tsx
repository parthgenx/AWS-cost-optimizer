import {
  AlertCircle,
  ArrowRight,
  BadgeDollarSign,
  Check,
  CircleCheckBig,
  CloudCog,
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
      <section className="sign-in-intro" aria-labelledby="sign-in-heading">
        <div className="sign-in-brand">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <strong>AWS Cost Optimizer</strong>
            <span>Self-hosted operator console</span>
          </div>
        </div>

        <div className="sign-in-copy">
          <p className="eyebrow">AWS cost operations</p>
          <h1 id="sign-in-heading">Find cloud cost waste. Act only when it&apos;s safe.</h1>
          <p>
            Scan AWS resources for avoidable spend, review evidence-backed findings, and estimate
            savings before an authorized operator requests any cleanup.
          </p>
          <ul className="sign-in-benefits" aria-label="Dashboard capabilities">
            <li><ScanSearch aria-hidden="true" size={17} /> Detect costly unused resources</li>
            <li><BadgeDollarSign aria-hidden="true" size={17} /> Review estimated monthly savings</li>
            <li><ShieldCheck aria-hidden="true" size={17} /> Keep EBS cleanup approval-gated</li>
          </ul>
        </div>

        <section className="sign-in-access-card" aria-label="Secure sign in">
          <div className="sign-in-access-heading">
            <span className="sign-in-access-icon" aria-hidden="true"><KeyRound size={18} /></span>
            <div>
              <p className="eyebrow">Secure operator access</p>
              <h2>Sign in to your workspace</h2>
            </div>
          </div>
          <p>
            Use an administrator-provisioned Cognito account to view findings and scan activity
            for this AWS account.
          </p>
          <button className="primary-button sign-in-button" type="button" onClick={onSignIn}>
            Continue with secure sign in
            <ArrowRight aria-hidden="true" size={18} />
          </button>
          <p className="sign-in-footnote">
            Public registration is disabled. Access is managed by this deployment&apos;s administrator.
          </p>
        </section>
      </section>

      <aside className="sign-in-preview" aria-labelledby="preview-heading">
        <div className="preview-orb preview-orb-top" aria-hidden="true" />
        <div className="preview-orb preview-orb-bottom" aria-hidden="true" />
        <section className="preview-workspace">
          <div className="preview-topline">
            <span className="preview-label"><Sparkles aria-hidden="true" size={14} /> Illustrative preview</span>
            <span className="preview-not-live">Not live AWS data</span>
          </div>
          <div className="preview-heading">
            <div>
              <p className="eyebrow">Cost review workspace</p>
              <h2 id="preview-heading">Evidence before action.</h2>
            </div>
            <span className="preview-status"><CircleCheckBig aria-hidden="true" size={15} /> Guardrails on</span>
          </div>

          <article className="preview-finding">
            <div className="preview-finding-heading">
              <span className="preview-resource-icon" aria-hidden="true"><CloudCog size={19} /></span>
              <div>
                <span>Illustrative finding</span>
                <strong>Unattached EBS volume</strong>
              </div>
              <span className="preview-severity">Review</span>
            </div>
            <div className="preview-evidence">
              <span><Check aria-hidden="true" size={13} /> State: available</span>
              <span><Check aria-hidden="true" size={13} /> Attachment: none</span>
              <span><Check aria-hidden="true" size={13} /> Age threshold met</span>
            </div>
            <div className="preview-savings">
              <span>Illustrative monthly estimate</span>
              <strong>$24.00 <small>/ month</small></strong>
            </div>
          </article>

          <ol className="preview-flow" aria-label="Safe cleanup workflow">
            <li><span>1</span><div><strong>Scan</strong><small>Detect waste</small></div></li>
            <li><span>2</span><div><strong>Review</strong><small>Inspect evidence</small></div></li>
            <li><span>3</span><div><strong>Approve</strong><small>Operator decision</small></div></li>
            <li><span>4</span><div><strong>Revalidate</strong><small>Before cleanup</small></div></li>
          </ol>
          <p className="preview-disclaimer">Example interface only. No live account data is shown before sign in.</p>
        </section>
      </aside>
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
