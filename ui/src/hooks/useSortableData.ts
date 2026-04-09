import { useState, useMemo } from 'react'

export type SortDirection = 'asc' | 'desc'

interface SortConfig<K extends string> {
  sortKey: K
  sortDirection: SortDirection
  sortedData: any[]
  onSort: (key: K) => void
}

export function useSortableData<T, K extends string>(
  data: T[],
  defaultKey: K,
  defaultDirection: SortDirection = 'asc',
  keyExtractors?: Partial<Record<K, (item: T) => any>>
): SortConfig<K> {
  const [sortKey, setSortKey] = useState<K>(defaultKey)
  const [sortDirection, setSortDirection] = useState<SortDirection>(defaultDirection)

  const onSort = (key: K) => {
    if (key === sortKey) {
      setSortDirection(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortDirection('asc')
    }
  }

  const sortedData = useMemo(() => {
    const sorted = [...data].sort((a, b) => {
      const extractor = keyExtractors?.[sortKey]
      const aVal = extractor ? extractor(a) : (a as any)[sortKey]
      const bVal = extractor ? extractor(b) : (b as any)[sortKey]

      if (aVal == null && bVal == null) return 0
      if (aVal == null) return 1
      if (bVal == null) return -1

      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return aVal - bVal
      }

      return String(aVal).localeCompare(String(bVal), undefined, { sensitivity: 'base' })
    })

    if (sortDirection === 'desc') sorted.reverse()
    return sorted
  }, [data, sortKey, sortDirection, keyExtractors])

  return { sortKey, sortDirection, sortedData, onSort }
}
