import { describe, expect, it } from 'vitest'
import { errorMessage } from '../client'

describe('errorMessage', () => {
  it('returns a string detail as-is', () => {
    const err = { response: { data: { detail: 'Connection name already exists' } } }
    expect(errorMessage(err)).toBe('Connection name already exists')
  })

  it('joins Pydantic validation error objects with their field path', () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ['body', 'incremental_column'], msg: 'Field required', type: 'missing' },
          ],
        },
      },
    }
    expect(errorMessage(err)).toBe('incremental_column: Field required')
  })

  it('joins multiple Pydantic validation errors and strips "body" from loc', () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ['body', 'name'], msg: 'Field required' },
            { loc: ['body', 'port'], msg: 'value is not a valid integer' },
          ],
        },
      },
    }
    expect(errorMessage(err)).toBe('name: Field required; port: value is not a valid integer')
  })

  it('strips a leading "Value error," prefix from custom validator messages', () => {
    const err = {
      response: {
        data: {
          detail: [{ loc: ['body', 'migration_mode'], msg: 'Value error, Incremental column is required' }],
        },
      },
    }
    expect(errorMessage(err)).toBe('migration_mode: Incremental column is required')
  })

  it('falls back to the provided default when detail is missing', () => {
    const err = { response: { data: {} } }
    expect(errorMessage(err, 'Save failed')).toBe('Save failed')
  })

  it('falls back to "Error" by default when there is no response at all', () => {
    expect(errorMessage(new Error('network error'))).toBe('Error')
  })
})
