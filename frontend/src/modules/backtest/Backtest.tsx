import { useState } from 'react'
import { useBacktest } from '../../shared/hooks/useApi'
import { Button, Input } from '../../shared/components/atoms'

export function Backtest() {
  const { mutate: runBacktest, data: result, isPending, error } = useBacktest()
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [holdingDays, setHoldingDays] = useState('30')
  const [topN, setTopN] = useState('10')

  const handleRun = () => {
    runBacktest({
      start_date: startDate,
      end_date: endDate,
      holding_days: parseInt(holdingDays),
      top_n: parseInt(topN),
    })
  }

  return (
    <div className="space-y-6">
      {/* 回测参数 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">回测参数</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm text-gray-500 mb-1">开始日期</label>
            <Input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">结束日期</label>
            <Input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">持仓天数</label>
            <Input
              type="number"
              value={holdingDays}
              onChange={(e) => setHoldingDays(e.target.value)}
              min="1"
              max="365"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">Top N</label>
            <Input
              type="number"
              value={topN}
              onChange={(e) => setTopN(e.target.value)}
              min="1"
              max="50"
            />
          </div>
        </div>
        <div className="mt-4">
          <Button onClick={handleRun} disabled={isPending} variant="primary">
            {isPending ? '运行中...' : '运行回测'}
          </Button>
        </div>
      </div>

      {/* 回测结果 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">回测结果</h2>
        {isPending ? (
          <div className="text-center py-12 text-gray-500">回测运行中...</div>
        ) : error ? (
          <div className="text-center py-12 text-red-500">
            回测失败: {(error as Error).message}
          </div>
        ) : result ? (
          <div className="space-y-6">
            {/* 关键指标 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <ResultCard
                label="总收益率"
                value={result.total_return != null ? `${result.total_return.toFixed(2)}%` : '-'}
                color={result.total_return && result.total_return >= 0 ? 'text-red-500' : 'text-green-500'}
              />
              <ResultCard
                label="年化收益率"
                value={result.annualized_return != null ? `${result.annualized_return.toFixed(2)}%` : '-'}
                color={result.annualized_return && result.annualized_return >= 0 ? 'text-red-500' : 'text-green-500'}
              />
              <ResultCard
                label="夏普比率"
                value={result.sharpe_ratio != null ? result.sharpe_ratio.toFixed(2) : '-'}
              />
              <ResultCard
                label="最大回撤"
                value={result.max_drawdown != null ? `${result.max_drawdown.toFixed(2)}%` : '-'}
                color="text-red-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <ResultCard
                label="胜率"
                value={result.win_rate != null ? `${result.win_rate.toFixed(2)}%` : '-'}
              />
              <ResultCard
                label="总交易次数"
                value={result.total_trades?.toString() || '-'}
              />
            </div>

            {/* 月度收益 */}
            {result.monthly_returns && result.monthly_returns.length > 0 && (
              <div>
                <h3 className="text-md font-semibold text-gray-900 dark:text-white mb-3">月度收益</h3>
                <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                  {result.monthly_returns.map((m, i) => (
                    <div
                      key={i}
                      className={`p-2 rounded text-center ${
                        m.return >= 0 ? 'bg-red-50 dark:bg-red-900/20' : 'bg-green-50 dark:bg-green-900/20'
                      }`}
                    >
                      <div className="text-xs text-gray-500">{m.month}</div>
                      <div className={`font-mono text-sm ${m.return >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                        {m.return >= 0 ? '+' : ''}{m.return.toFixed(1)}%
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-12 text-gray-500">
            点击"运行回测"开始分析
          </div>
        )}
      </div>
    </div>
  )
}

function ResultCard({
  label,
  value,
  color = 'text-gray-900 dark:text-white',
}: {
  label: string
  value: string
  color?: string
}) {
  return (
    <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
      <div className="text-sm text-gray-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold font-mono ${color}`}>{value}</div>
    </div>
  )
}