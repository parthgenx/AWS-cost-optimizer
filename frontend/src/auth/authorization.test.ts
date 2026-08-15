import { describe, expect, it } from 'vitest'

import { hasOperatorGroup } from './authorization'

describe('hasOperatorGroup', () => {
  it('recognizes Cognito group arrays and comma-delimited claims for UI affordances', () => {
    expect(hasOperatorGroup({ 'cognito:groups': ['readers', 'cost-optimizer-operators'] })).toBe(true)
    expect(hasOperatorGroup({ 'cognito:groups': 'readers,cost-optimizer-operators' })).toBe(true)
  })

  it('does not mistake a similarly named group for the operator group', () => {
    expect(hasOperatorGroup({ 'cognito:groups': ['cost-optimizer-operators-readonly'] })).toBe(false)
    expect(hasOperatorGroup(undefined)).toBe(false)
  })
})
