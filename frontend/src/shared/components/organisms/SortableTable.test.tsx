import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SortableTable } from './SortableTable'
import type { Column } from './SortableTable'

interface TestRow {
  name: string
  value: number
  rank: number
}

const mockData: TestRow[] = [
  { name: '苹果', value: 100, rank: 1 },
  { name: '香蕉', value: 50, rank: 2 },
  { name: '橙子', value: 75, rank: 3 },
]

describe('SortableTable', () => {
  it('renders column headers', () => {
    const columns: Column<TestRow>[] = [
      { key: 'name', title: '名称' },
      { key: 'value', title: '数值' },
      { key: 'rank', title: '排名' },
    ]
    render(<SortableTable data={mockData} columns={columns} virtualized={false} />)
    expect(screen.getByText('名称')).toBeInTheDocument()
    expect(screen.getByText('数值')).toBeInTheDocument()
    expect(screen.getByText('排名')).toBeInTheDocument()
  })

  it('renders data rows', () => {
    const columns: Column<TestRow>[] = [
      { key: 'name', title: '名称' },
      { key: 'value', title: '数值' },
    ]
    render(<SortableTable data={mockData} columns={columns} virtualized={false} />)
    expect(screen.getByText('苹果')).toBeInTheDocument()
    expect(screen.getByText('香蕉')).toBeInTheDocument()
    expect(screen.getByText('橙子')).toBeInTheDocument()
  })

  it('calls onRowClick when row is clicked', () => {
    const handleClick = vi.fn()
    const columns: Column<TestRow>[] = [
      { key: 'name', title: '名称' },
    ]
    render(<SortableTable data={mockData} columns={columns} onRowClick={handleClick} virtualized={false} />)
    fireEvent.click(screen.getByText('香蕉'))
    expect(handleClick).toHaveBeenCalledWith(mockData[1])
  })

  it('toggles sort order when clicking sortable column header', async () => {
    const columns: Column<TestRow>[] = [
      { key: 'name', title: '名称', sortable: true },
      { key: 'value', title: '数值', sortable: true },
    ]
    render(<SortableTable data={mockData} columns={columns} virtualized={false} />)

    // Click to sort by name (descending first)
    const nameHeader = screen.getByText('名称')
    fireEvent.click(nameHeader)
    expect(screen.getByText('名称').closest('th')?.textContent).toContain('↓')

    // Click again to toggle (ascending)
    fireEvent.click(nameHeader)
    expect(screen.getByText('名称').closest('th')?.textContent).toContain('↑')
  })

  it('shows empty message when no data', () => {
    const columns: Column<TestRow>[] = [
      { key: 'name', title: '名称' },
    ]
    render(<SortableTable data={[]} columns={columns} emptyMessage="暂无数据" virtualized={false} />)
    expect(screen.getByText('暂无数据')).toBeInTheDocument()
  })

  it('renders with custom render function', () => {
    const columns: Column<TestRow>[] = [
      { key: 'name', title: '名称' },
      {
        key: 'value',
        title: '数值',
        render: (val: unknown) => `¥${(val as number).toFixed(0)}`,
      },
    ]
    render(<SortableTable data={mockData} columns={columns} virtualized={false} />)
    expect(screen.getByText('¥100')).toBeInTheDocument()
    expect(screen.getByText('¥50')).toBeInTheDocument()
  })
})
