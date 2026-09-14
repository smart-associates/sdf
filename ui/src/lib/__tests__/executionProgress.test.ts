import { computeExecutionProgress } from '../executionProgress'
import { Execution } from '../../api/executions'

function execution(overrides: Partial<Execution>): Execution {
  return {
    id: 100,
    job_id: 1,
    status: 'running',
    started_at: '2026-01-01T00:00:00Z',
    record_count: 0,
    tables: [],
    ...overrides,
  }
}

describe('computeExecutionProgress', () => {
  it('returns null when the execution has no tables', () => {
    expect(computeExecutionProgress(execution({ tables: [] }))).toBeNull()
  })

  it('weights by rows when every table has an estimate', () => {
    const result = computeExecutionProgress(execution({
      status: 'running',
      tables: [
        { id: 1, execution_id: 100, table_name: 'orders', status: 'running', started_at: '', record_count: 50, estimated_row_count: 100 },
        { id: 2, execution_id: 100, table_name: 'customers', status: 'success', started_at: '', record_count: 10, estimated_row_count: 10 },
      ],
    }))
    // (min(50,100) + min(10,10)) / (100 + 10) = 60/110
    expect(result).toEqual({ total: 2, completed: 1, pct: 55 })
  })

  it('caps a table at its estimate so an overrun cannot push the total past 100%', () => {
    const result = computeExecutionProgress(execution({
      status: 'running',
      tables: [
        { id: 1, execution_id: 100, table_name: 'orders', status: 'running', started_at: '', record_count: 150, estimated_row_count: 100 },
      ],
    }))
    expect(result).toEqual({ total: 1, completed: 0, pct: 100 })
  })

  it('falls back to completed-table-count when any table lacks an estimate', () => {
    const result = computeExecutionProgress(execution({
      status: 'running',
      tables: [
        { id: 1, execution_id: 100, table_name: 'orders', status: 'success', started_at: '', record_count: 10 },
        { id: 2, execution_id: 100, table_name: 'customers', status: 'running', started_at: '', record_count: 0 },
        { id: 3, execution_id: 100, table_name: 'items', status: 'running', started_at: '', record_count: 0 },
      ],
    }))
    expect(result).toEqual({ total: 3, completed: 1, pct: 33 })
  })

  it('reports 100% once the execution has left the running state, regardless of estimates', () => {
    const result = computeExecutionProgress(execution({
      status: 'failed',
      tables: [
        { id: 1, execution_id: 100, table_name: 'orders', status: 'failed', started_at: '', record_count: 3, estimated_row_count: 100 },
      ],
    }))
    expect(result).toEqual({ total: 1, completed: 1, pct: 100 })
  })
})
