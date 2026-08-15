import { Navigate } from 'react-router-dom'
import { useAuth } from 'react-oidc-context'

import { AuthFailure, CenteredState } from '../components/states'

export function AuthCallback() {
  const auth = useAuth()

  if (auth.isLoading) {
    return <CenteredState label="Completing secure sign-in…" />
  }

  if (auth.error) {
    return <AuthFailure message={auth.error.message} />
  }

  if (auth.isAuthenticated) {
    return <Navigate replace to="/" />
  }

  return <AuthFailure message="Cognito did not return an authenticated session." />
}
