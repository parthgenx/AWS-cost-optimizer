const OPERATOR_GROUP = 'cost-optimizer-operators'

/**
 * Uses the Cognito group claim only to tailor the browser interface. The API
 * independently verifies the JWT and group on every state-changing request.
 */
export function hasOperatorGroup(profile: unknown): boolean {
  if (!profile || typeof profile !== 'object') {
    return false
  }

  const groups = (profile as Record<string, unknown>)['cognito:groups']
  if (typeof groups === 'string') {
    return groups.split(',').some((group) => group.trim() === OPERATOR_GROUP)
  }
  if (Array.isArray(groups)) {
    return groups.some((group) => group === OPERATOR_GROUP)
  }
  return false
}
