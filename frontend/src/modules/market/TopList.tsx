import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCPTop } from '../../shared/hooks/useApi'
import { SortableTable } from '../../shared/components/organisms'
import type { StockCP } from '../../shared/types'

const PAGE_TITLE = '战力榜'

export function TopList() {
  const navigate = useNavigate()
  const { data, isLoading, error, refetch } = useCPTop(200)
  const [filter, setFilter] = useState<'all' | 'up' | 'down'>('all')

  const filteredStocks = useMemo(() => {
    if (!data?.data) return []
    switch (filter) {
      case 'up':
        return data.data.filter((s) => s.change_pct > 0)
      case 'down':
        return data.data.filter((s) => s.change_pct < 0)
      default:
        return data.data
    }
  }, [data, filter])

  const columns = [
    {
      key: 'rank',
      title: '排名',
      width: 60,
      align: 'center' as const,
      render: (_: unknown, __: StockCP, index: number) => (
        <span className="text-gray-900 dark:text-white">{index + 1}</span>
      ),
    },
    {
      key: 'name',
      title: '名称',
      width: 120,
      render: (value: unknown, row: StockCP) => (
        <div className="flex items-center gap-2">
          <span className="font-medium text-gray-900 dark:text-white">{value as string}</span>
          <span className="text-xs text-gray-400 dark:text-gray-500">{row.code}</span>
        </div>
      ),
    },
    {
      key: 'total_cp',
      title: '战力',
      width: 80,
      align: 'right' as const,
      sortable: true,
      render: (value: unknown) => (
        <span className="font-mono font-bold text-blue-600">{(value as number).toFixed(1)}</span>
      ),
    },
    {
      key: 'price',
      title: '现价',
      width: 100,
      align: 'right' as const,
      sortable: true,
      render: (value: unknown, row: StockCP) => (
        <span className={`font-mono ${row.change_pct >= 0 ? 'text-red-500' : 'text-green-500'}`}>
          {(value as number).toFixed(2)}
        </span>
      ),
    },
    {
      key: 'change_pct',
      title: '涨跌幅',
      width: 100,
      align: 'right' as const,
      sortable: true,
      render: (value: unknown) => {
        const v = value as number
        const isUp = v >= 0
        return (
          <span className={`font-mono ${isUp ? 'text-red-500' : 'text-green-500'}`}>
            {isUp ? '+' : ''}{v.toFixed(2)}%
          </span>
        )
      },
    },
    {
      key: 'growth_score',
      title: '成长',
      width: 80,
      align: 'right' as const,
      sortable: true,
      render: (value: unknown) => (
        <span className="font-mono text-purple-600">{(value as number).toFixed(1)}</span>
      ),
    },
    {
      key: 'value_score',
      title: '价值',
      width: 80,
      align: 'right' as const,
      sortable: true,
      render: (value: unknown) => (
        <span className="font-mono text-orange-600">{(value as number).toFixed(1)}</span>
      ),
    },
    {
      key: 'quality_score',
      title: '质量',
      width: 80,
      align: 'right' as const,
      sortable: true,
      render: (value: unknown) => (
        <span className="font-mono text-cyan-600">{(value as number).toFixed(1)}</span>
      ),
    },
    {
      key: 'momentum_score',
      title: '动量',
      width: 80,
      align: 'right' as const,
      sortable: true,
      render: (value: unknown) => (
        <span className="font-mono text-green-600">{(value as number).toFixed(1)}</span>
      ),
    },
  ]

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-4">加载失败: {error.message}</p>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          重试
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{PAGE_TITLE}</h1>
        <div className="text-sm text-gray-500">
          {data?.updated_at && `更新时间: ${data.updated_at}`}
        </div>
      </div>

      {/* 筛选 */}
      <div className="flex gap-2">
        {(['all', 'up', 'down'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`
              px-4 py-2 rounded-lg text-sm font-medium transition-colors
              ${filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
              }
            `}
          >
            {f === 'all' ? '全部' : f === 'up' ? '上涨' : '下跌'}
          </button>
        ))}
        <div className="flex-1" />
        <span className="self-center text-sm text-gray-500">
          共 {filteredStocks.length} 只
        </span>
      </div>

      {/* 榜单表格 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <SortableTable
          data={filteredStocks}
          columns={columns}
          onRowClick={(row) => navigate(`/stock/${row.code}`)}
          rowHeight={52}
          virtualized={false}
          emptyMessage={isLoading ? '加载中...' : '暂无数据'}
        />
      </div>

      {/* 加载更多 */}
      {isLoading && (
        <div className="text-center py-4 text-gray-500">加载中...</div>
      )}
    </div>
  )
}
