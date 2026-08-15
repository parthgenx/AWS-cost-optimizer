import { WebStorageStateStore, type UserManagerSettings } from 'oidc-client-ts'

export interface DashboardConfiguration {
  apiBaseUrl: string
  cognitoClientId: string
  cognitoDomain: string
  cognitoIssuer: string
}

const requiredEnvironmentVariables = [
  'VITE_API_BASE_URL',
  'VITE_COGNITO_ISSUER',
  'VITE_COGNITO_DOMAIN',
  'VITE_COGNITO_CLIENT_ID',
] as const

export function getDashboardConfiguration(): DashboardConfiguration | null {
  const values = {
    apiBaseUrl: import.meta.env.VITE_API_BASE_URL?.trim(),
    cognitoIssuer: import.meta.env.VITE_COGNITO_ISSUER?.trim(),
    cognitoDomain: import.meta.env.VITE_COGNITO_DOMAIN?.trim(),
    cognitoClientId: import.meta.env.VITE_COGNITO_CLIENT_ID?.trim(),
  }

  if (Object.values(values).some((value) => !value)) {
    return null
  }

  return {
    apiBaseUrl: removeTrailingSlash(values.apiBaseUrl),
    cognitoIssuer: removeTrailingSlash(values.cognitoIssuer),
    cognitoDomain: removeTrailingSlash(values.cognitoDomain),
    cognitoClientId: values.cognitoClientId,
  }
}

export function getMissingConfigurationVariables(): readonly string[] {
  return requiredEnvironmentVariables.filter((name) => !import.meta.env[name]?.trim())
}

export function createCognitoSettings(
  configuration: DashboardConfiguration,
): UserManagerSettings {
  const callbackUrl = `${window.location.origin}/auth/callback`

  return {
    authority: configuration.cognitoIssuer,
    client_id: configuration.cognitoClientId,
    redirect_uri: callbackUrl,
    response_type: 'code',
    scope: 'openid email',
    loadUserInfo: false,
    userStore: new WebStorageStateStore({ store: window.sessionStorage }),
    metadata: {
      issuer: configuration.cognitoIssuer,
      authorization_endpoint: `${configuration.cognitoDomain}/oauth2/authorize`,
      token_endpoint: `${configuration.cognitoDomain}/oauth2/token`,
      end_session_endpoint: `${configuration.cognitoDomain}/logout`,
      jwks_uri: `${configuration.cognitoIssuer}/.well-known/jwks.json`,
    },
  }
}

export function createCognitoLogoutUrl(configuration: DashboardConfiguration): string {
  const parameters = new URLSearchParams({
    client_id: configuration.cognitoClientId,
    logout_uri: `${window.location.origin}/`,
  })
  return `${configuration.cognitoDomain}/logout?${parameters.toString()}`
}

function removeTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '')
}
