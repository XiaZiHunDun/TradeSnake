import { useState, useMemo, useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'

interface Column<T> {
  key: keyof T | string
  title: string
  sortable?: boolean
  width?: number | string
  align?: 'left' | 'center' | 'right'
  render?: (value: unknown, row: T, index: number) => React.ReactNode
}

interface SortableTableProps<T> {
  data: T[]
  columns: Column<T>[]
  onRowClick?: (row: T) => void
  rowHeight?: number
  virtualized?: boolean
  emptyMessage?: string
  className?: string
}

export function SortableTable<T extends { [key: string]: unknown }>({
  data,
  columns,
  onRowClick,
  rowHeight = 48,
  virtualized = true,
  emptyMessage = '暂无数据',
  className = '',
}: SortableTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const parentRef = useRef<HTMLDivElement>(null)

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortKey(key)
      setSortOrder('desc')
    }
  }

  const sortedData = useMemo(() => {
    if (!sortKey) return data
    return [...data].sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      if (aVal == null) return 1
      if (bVal == null) return -1
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0
      return sortOrder === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortOrder])

  const virtualizer = useVirtualizer({
    count: sortedData.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 10,
  })

  const alignStyles = {
    left: 'text-left',
    center: 'text-center',
    right: 'text-right',
  }

  return (
    <div className={`overflow-hidden ${className}`}>
      <div
        ref={parentRef}
        className="overflow-auto"
        style={{ maxHeight: 'calc(100vh - 250px)' }}
      >
        <table className="w-full table-fixed">
          <colgroup>
            {columns.map((col) => (
              <col key={col.key as string} style={{ width: col.width, minWidth: col.width }} />
            ))}
          </colgroup>
          <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0 z-10">
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key as string}
                  onClick={() => col.sortable && handleSort(col.key as string)}
                  className={`
                    px-4 py-3 text-sm font-semibold text-gray-600 dark:text-gray-400 whitespace-nowrap
                    ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'}
                    ${col.sortable ? 'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700' : ''}
                  `}
                  style={{ width: col.width, minWidth: col.width }}
                >
                  {col.title}
                  {col.sortable && sortKey === col.key && (
                    <span className="ml-1 text-blue-500">{sortOrder === 'asc' ? '↑' : '↓'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedData.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="text-center py-12 text-gray-400">
                  {emptyMessage}
                </td>
              </tr>
            ) : virtualized ? (
              virtualizer.getVirtualItems().map((virtualRow) => {
                const row = sortedData[virtualRow.index]
                return (
                  <tr
                    key={virtualRow.key}
                    onClick={() => onRowClick?.(row)}
                    className={`
                      border-b border-gray-100 dark:border-gray-800
                      hover:bg-gray-50 dark:hover:bg-gray-800/50
                      cursor-pointer
                    `}
                    style={{ height: rowHeight }}
                  >
                    {columns.map((col) => (
                      <td
                      key={col.key as string}
                      className={`px-4 py-3 text-sm overflow-hidden text-ellipsis whitespace-nowrap ${alignStyles[col.align || 'left']}`}
                      style={{ width: col.width, minWidth: col.width }}
                    >
                      {col.render
                        ? col.render(row[col.key as keyof T], row, virtualRow.index)
                        : String(row[col.key as keyof T] ?? '')}
                    </td>
                    ))}
                  </tr>
                )
              })
            ) : (
              sortedData.map((row, index) => (
                <tr
                  key={index}
                  onClick={() => onRowClick?.(row)}
                  className="
                    border-b border-gray-100 dark:border-gray-800
                    hover:bg-gray-50 dark:hover:bg-gray-800/50
                    cursor-pointer
                  "
                >
                  {columns.map((col) => (
                    <td
                      key={col.key as string}
                      className={`px-4 py-3 text-sm overflow-hidden text-ellipsis whitespace-nowrap ${alignStyles[col.align || 'left']}`}
                      style={{ width: col.width, minWidth: col.width }}
                    >
                      {col.render
                        ? col.render(row[col.key as keyof T], row, index)
                        : String(row[col.key as keyof T] ?? '')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
