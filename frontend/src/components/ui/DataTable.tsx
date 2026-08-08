import { type ReactNode } from 'react'
import { clsx } from 'clsx'
import { LoadingSpinner } from './LoadingSpinner'

export interface Column<T> {
  key: string
  header: string
  render: (row: T) => ReactNode
  width?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  keyExtractor: (row: T) => string | number
  isLoading?: boolean
  emptyMessage?: string
  onRowClick?: (row: T) => void
}

export function DataTable<T>({
  columns, data, keyExtractor, isLoading, emptyMessage, onRowClick,
}: DataTableProps<T>) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-48">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 scrollbar-thin">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {columns.map(col => (
              <th
                key={col.key}
                className={clsx(
                  'px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider',
                  col.width,
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-100">
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-12 text-center text-sm text-gray-500">
                {emptyMessage ?? 'No data found'}
              </td>
            </tr>
          ) : (
            data.map(row => (
              <tr
                key={keyExtractor(row)}
                onClick={() => onRowClick?.(row)}
                className={clsx(
                  'transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-gray-50',
                )}
              >
                {columns.map(col => (
                  <td key={col.key} className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
