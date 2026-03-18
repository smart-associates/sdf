import clsx from 'clsx'

interface Props {
  status: string
  className?: string
}

const styles: Record<string, string> = {
  success: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  running: 'bg-blue-100 text-blue-700',
  cancelled: 'bg-yellow-100 text-yellow-700',
  untested: 'bg-gray-100 text-gray-600',
}

export default function StatusBadge({ status, className }: Props) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        styles[status] || 'bg-gray-100 text-gray-600',
        className
      )}
    >
      {status === 'running' && (
        <span className="mr-1 h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
      )}
      {status}
    </span>
  )
}
