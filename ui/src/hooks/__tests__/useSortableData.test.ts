import { renderHook, act } from '@testing-library/react'
import { useSortableData } from '../useSortableData'

const data = [
  { name: 'Charlie', age: 30 },
  { name: 'Alice', age: 25 },
  { name: 'Bob', age: 35 },
]

describe('useSortableData', () => {
  it('sorts ascending by default key', () => {
    const { result } = renderHook(() => useSortableData(data, 'name'))
    expect(result.current.sortedData.map((d: any) => d.name)).toEqual(['Alice', 'Bob', 'Charlie'])
    expect(result.current.sortDirection).toBe('asc')
  })

  it('toggles to descending when sorting by same key', () => {
    const { result } = renderHook(() => useSortableData(data, 'name'))
    act(() => result.current.onSort('name'))
    expect(result.current.sortDirection).toBe('desc')
    expect(result.current.sortedData.map((d: any) => d.name)).toEqual(['Charlie', 'Bob', 'Alice'])
  })

  it('resets to ascending when switching to a different key', () => {
    const { result } = renderHook(() => useSortableData(data, 'name'))
    act(() => result.current.onSort('name')) // desc
    act(() => result.current.onSort('age'))  // asc on age
    expect(result.current.sortKey).toBe('age')
    expect(result.current.sortDirection).toBe('asc')
    expect(result.current.sortedData.map((d: any) => d.age)).toEqual([25, 30, 35])
  })

  it('sorts nulls to the end', () => {
    const dataWithNull = [
      { name: 'Bob', age: 30 },
      { name: null, age: 25 },
      { name: 'Alice', age: 35 },
    ]
    const { result } = renderHook(() => useSortableData(dataWithNull, 'name'))
    expect(result.current.sortedData.map((d: any) => d.name)).toEqual(['Alice', 'Bob', null])
  })

  it('uses custom key extractors', () => {
    const { result } = renderHook(() =>
      useSortableData(data, 'name', 'asc', {
        name: (item: any) => item.name.length,
      })
    )
    // Sort by name length: Bob(3), Alice(5), Charlie(7)
    expect(result.current.sortedData.map((d: any) => d.name)).toEqual(['Bob', 'Alice', 'Charlie'])
  })
})
