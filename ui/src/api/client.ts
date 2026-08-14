import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

/**
 * Normalize an axios error into a human-readable message.
 * FastAPI returns `detail` as a string for HTTPException, but as an array of
 * `{loc, msg, type}` objects for Pydantic 422 validation errors — passing the
 * latter straight to setState yields an unrenderable React child (e.g. "[object Object]").
 */
export function errorMessage(err: unknown, fallback = 'Error'): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } } | undefined)?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d: any) => {
        const msg = String(d?.msg ?? '').replace(/^Value error,\s*/i, '')
        const loc = Array.isArray(d?.loc)
          ? d.loc.filter((s: unknown) => s !== 'body').join('.')
          : ''
        return loc ? `${loc}: ${msg}` : msg
      })
      .filter(Boolean)
    if (parts.length) return parts.join('; ')
  }
  return fallback
}

export default client
