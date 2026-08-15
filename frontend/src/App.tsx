import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from 'react-oidc-context'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { AuthCallback } from './auth/AuthCallback'
import { hasOperatorGroup } from './auth/authorization'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppShell } from './components/AppShell'
import { ConfigurationRequired } from './components/states'
import { createCognitoLogoutUrl, createCognitoSettings, getDashboardConfiguration } from './config'
import type { DashboardConfiguration } from './config'
import { FindingDetailPage } from './features/findings/FindingDetailPage'
import { FindingsPage } from './features/findings/FindingsPage'
import { OverviewPage } from './features/overview/OverviewPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})

function App() {
  const configuration = getDashboardConfiguration()

  if (!configuration) {
    return <ConfigurationRequired />
  }

  return (
    <AuthProvider
      {...createCognitoSettings(configuration)}
      onSigninCallback={() => window.history.replaceState({}, document.title, '/auth/callback')}
    >
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="*" element={<ProtectedRoute><AuthenticatedDashboard configuration={configuration} /></ProtectedRoute>} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </AuthProvider>
  )
}

function AuthenticatedDashboard({ configuration }: { configuration: DashboardConfiguration }) {
  const auth = useAuth()
  const isOperator = hasOperatorGroup(auth.user?.profile)

  async function signOut() {
    await auth.removeUser()
    window.location.assign(createCognitoLogoutUrl(configuration))
  }

  return (
    <AppShell email={auth.user?.profile.email} onSignOut={() => void signOut()}>
      <Routes>
        <Route path="/" element={<OverviewPage accessToken={auth.user?.access_token} />} />
        <Route path="/findings" element={<FindingsPage accessToken={auth.user?.access_token} />} />
        <Route
          path="/findings/:findingId"
          element={<FindingDetailPage accessToken={auth.user?.access_token} isOperator={isOperator} />}
        />
        <Route path="*" element={<Navigate replace to="/" />} />
      </Routes>
    </AppShell>
  )
}

export default App
