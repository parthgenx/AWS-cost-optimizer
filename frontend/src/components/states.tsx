import { AlertCircle, ArrowRight, KeyRound, LoaderCircle, Settings2 } from 'lucide-react'

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
      <section className="sign-in-card">
        <div className="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <p className="eyebrow">AWS cost optimization</p>
        <h1>Make cloud cost reviews deliberate, not dangerous.</h1>
        <p>
          Sign in with an administrator-provisioned Cognito account to view findings and scan
          activity for this AWS account.
        </p>
        <button className="primary-button" type="button" onClick={onSignIn}>
          <KeyRound aria-hidden="true" size={18} />
          Sign in securely
        </button>
        <p className="sign-in-footnote">
          Public registration is disabled. Access is managed by this deployment&apos;s administrator.
        </p>
      </section>
      <aside className="sign-in-aside" aria-label="Dashboard capabilities">
        <p className="eyebrow">Designed for safe operations</p>
        <ul>
          <li>Evidence-backed findings</li>
          <li>Approval-gated EBS cleanup</li>
          <li>Auditable cloud automation</li>
        </ul>
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
