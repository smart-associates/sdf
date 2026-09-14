import clsx from 'clsx'
import { Execution } from '../api/executions'
import { computeExecutionProgress } from '../lib/executionProgress'

export default function ExecutionProgressBar({ execution }: { execution: Execution }) {
  const progress = computeExecutionProgress(execution)
  if (!progress) return null
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div
          className={clsx('h-2 rounded-full transition-all', {
            'bg-green-500': execution.status === 'success',
            'bg-red-500': execution.status === 'failed',
            'bg-gray-400': execution.status === 'cancelled',
            'bg-blue-500': execution.status === 'running',
          })}
          style={{ width: `${progress.pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-500 whitespace-nowrap">
        {progress.completed}/{progress.total} tables · {progress.pct}%
      </span>
    </div>
  )
}
