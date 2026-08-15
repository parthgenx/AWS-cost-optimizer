import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from 'react-oidc-context'
import { BrowserRouter, Route, Routes } from 'react-router-dom'

import { AuthCallback } from './auth/AuthCallback'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppShell } from './components/AppShell'
import { ConfigurationRequired } from './components/states'
import { createCognitoLogoutUrl, createCognitoSettings, getDashboardConfiguration } from './config'
import type { DashboardConfiguration } from './config'
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
            <Route
              path="*"
              element={
                <ProtectedRoute>
                  <AuthenticatedDashboard configuration={configuration} />
                </ProtectedRoute>
              }
            />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    </AuthProvider>
  )
}

function AuthenticatedDashboard({ configuration }: { configuration: DashboardConfiguration }) {
  const auth = useAuth()

  async function signOut() {
    await auth.removeUser()
    window.location.assign(createCognitoLogoutUrl(configuration))
  }

  return (
    <AppShell email={auth.user?.profile.email} onSignOut={() => void signOut()}>
      <OverviewPage accessToken={auth.user?.access_token} />
    </AppShell>
  )
}

export default App
