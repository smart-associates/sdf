import { Execution } from '../api/executions'

export interface ExecutionProgress {
  total: number
  completed: number
  pct: number
}

// Weighted by rows when every table has an estimate; otherwise falls back to
// a completed-table-count fraction. Always reports 100% once the execution
// itself has left the 'running' state, regardless of per-table estimates.
export function computeExecutionProgress(execution: Execution): ExecutionProgress | null {
  const { tables } = execution
  if (tables.length === 0) return null
  const total = tables.length
  const completed = tables.filter(t => t.status !== 'running').length
  const allEstimated = tables.every(t => t.estimated_row_count != null && t.estimated_row_count > 0)
  const pct = execution.status !== 'running'
    ? 100
    : allEstimated
      ? Math.min(100, Math.round(
          tables.reduce((sum, t) => sum + Math.min(t.record_count, t.estimated_row_count!), 0) /
          tables.reduce((sum, t) => sum + t.estimated_row_count!, 0) * 100
        ))
      : Math.round(completed / total * 100)
  return { total, completed, pct }
}
