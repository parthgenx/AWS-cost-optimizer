import { useAuth } from 'react-oidc-context'

import { AuthFailure, CenteredState, SignInPrompt } from '../components/states'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const auth = useAuth()

  if (auth.isLoading) {
    return <CenteredState label="Verifying your secure session…" />
  }

  if (auth.error) {
    return <AuthFailure message={auth.error.message} />
  }

  if (!auth.isAuthenticated) {
    return <SignInPrompt onSignIn={() => void auth.signinRedirect()} />
  }

  return <>{children}</>
}
