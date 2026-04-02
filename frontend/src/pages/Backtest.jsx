import { useState, useEffect } from 'react'
import { BarChart3, TrendingUp, TrendingDown, AlertTriangle, Info, RefreshCw } from 'lucide-react'

// 回测报告页面组件
export default function Backtest() {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [startDate, setStartDate] = useState('2026-03-01')
  const [endDate, setEndDate] = useState('2026-04-02')
  const [holdingDays, setHoldingDays] = useState(30)
  const [topN, setTopN] = useState(10)
  const [compareResult, setCompareResult] = useState(null)

  const runBacktest = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    setCompareResult(null)

    try {
      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate,
        holding_days: holdingDays,
        top_n: topN
      })
      const res = await fetch(`/api/backtest/simple?${params}`)
      const data = await res.json()
      setResult(data)

      // 同时运行对比回测
      const compareRes = await fetch(`/api/backtest/compare?${params}`)
      const compareData = await compareRes.json()
      setCompareResult(compareData)
    } catch (e) {
      setError('回测请求失败: ' + e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    runBacktest()
  }, [])

  // 格式化数字
  const formatNum = (num, suffix = '%') => {
    if (num === null || num === undefined) return '-'
    return `${num >= 0 ? '+' : ''}${num.toFixed(2)}${suffix}`
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-accent-blue/20 flex items-center justify-center">
            <BarChart3 className="w-6 h-6 text-accent-blue" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">回测报告</h1>
            <p className="text-sm text-gray-400">验证战力公式有效性</p>
          </div>
        </div>
        <button
          onClick={runBacktest}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent-blue/10 text-accent-blue hover:bg-accent-blue/20 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          重新回测
        </button>
      </div>

      {/* 免责声明 */}
      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-bold text-yellow-500 mb-1">重要声明</h3>
            <p className="text-sm text-gray-300">
              回测结果仅供参考，不构成投资建议。过去表现不代表未来收益。
              回测未考虑滑点、冲击成本、分红再投资。
            </p>
          </div>
        </div>
      </div>

      {/* 参数配置 */}
      <div className="bg-card-bg rounded-xl border border-border-dark p-4">
        <h2 className="font-bold text-white mb-4">回测参数</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">开始日期</label>
            <input
              type="date"
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
              className="w-full bg-deep-night border border-border-dark rounded-lg px-3 py-2 text-white text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">结束日期</label>
            <input
              type="date"
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
              className="w-full bg-deep-night border border-border-dark rounded-lg px-3 py-2 text-white text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">持有天数</label>
            <select
              value={holdingDays}
              onChange={e => setHoldingDays(Number(e.target.value))}
              className="w-full bg-deep-night border border-border-dark rounded-lg px-3 py-2 text-white text-sm"
            >
              <option value={7}>7天</option>
              <option value={14}>14天</option>
              <option value={30}>30天</option>
              <option value={60}>60天</option>
            </select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">TOP N</label>
            <select
              value={topN}
              onChange={e => setTopN(Number(e.target.value))}
              className="w-full bg-deep-night border border-border-dark rounded-lg px-3 py-2 text-white text-sm"
            >
              <option value={10}>TOP 10</option>
              <option value={20}>TOP 20</option>
              <option value={50}>TOP 50</option>
            </select>
          </div>
        </div>
      </div>

      {/* 加载状态 */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 text-accent-blue animate-spin" />
          <span className="ml-3 text-gray-400">回测运行中...</span>
        </div>
      )}

      {/* 错误状态 */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
          <p className="text-red-400">{error}</p>
        </div>
      )}

      {/* 回测结果 */}
      {result && !loading && (
        <>
          {/* 主要指标 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="总收益率"
              value={formatNum(result.total_return)}
              icon={result.total_return >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
              color={result.total_return >= 0 ? 'green' : 'red'}
            />
            <MetricCard
              label="年化收益率"
              value={formatNum(result.annual_return)}
              icon={result.annual_return >= 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
              color={result.annual_return >= 0 ? 'green' : 'red'}
            />
            <MetricCard
              label="夏普比率"
              value={result.sharpe_ratio?.toFixed(2) || '-'}
              icon={<BarChart3 className="w-5 h-5" />}
              color="blue"
            />
            <MetricCard
              label="胜率"
              value={formatNum(result.win_rate)}
              icon={<Info className="w-5 h-5" />}
              color="purple"
            />
          </div>

          {/* 最大回撤 */}
          <div className="bg-card-bg rounded-xl border border-border-dark p-4">
            <h3 className="font-bold text-white mb-2">风险指标</h3>
            <div className="flex items-center gap-6">
              <div>
                <span className="text-sm text-gray-400">最大回撤</span>
                <p className={`text-2xl font-bold ${result.max_drawdown < 0 ? 'text-red-400' : 'text-green-400'}`}>
                  {formatNum(result.max_drawdown)}
                </p>
              </div>
              <div>
                <span className="text-sm text-gray-400">波动率</span>
                <p className="text-2xl font-bold text-white">{result.volatility?.toFixed(2) || '-'}%</p>
              </div>
            </div>
          </div>

          {/* 月度收益 */}
          {result.monthly_returns && result.monthly_returns.length > 0 && (
            <div className="bg-card-bg rounded-xl border border-border-dark p-4">
              <h3 className="font-bold text-white mb-4">月度收益</h3>
              <div className="flex items-end gap-2 h-32">
                {result.monthly_returns.map((ret, i) => (
                  <div key={i} className="flex-1 flex flex-col items-center">
                    <div
                      className={`w-full rounded-t transition-all ${
                        ret >= 0 ? 'bg-green-500' : 'bg-red-500'
                      }`}
                      style={{
                        height: `${Math.min(Math.abs(ret) * 2, 100)}%`
                      }}
                    />
                    <span className="text-xs text-gray-500 mt-1">{i + 1}月</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 对比结果 */}
          {compareResult && !compareResult.error && (
            <div className="bg-card-bg rounded-xl border border-border-dark p-4">
              <h3 className="font-bold text-white mb-4">对比回测</h3>
              <div className="space-y-3">
                {Object.entries(compareResult.results || {}).map(([key, data]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-gray-400">{key.toUpperCase()}</span>
                    <div className="flex items-center gap-4">
                      <span className="text-sm text-gray-500">收益: {formatNum(data.total_return)}</span>
                      <span className="text-sm text-gray-500">夏普: {data.sharpe_ratio}</span>
                      <span className="text-sm text-gray-500">胜率: {formatNum(data.win_rate)}</span>
                    </div>
                  </div>
                ))}
              </div>
              {compareResult.conclusion && (
                <div className="mt-4 pt-4 border-t border-border-dark">
                  <p className="text-sm text-accent-blue">{compareResult.conclusion}</p>
                </div>
              )}
            </div>
          )}

          {/* 幸存者偏差说明 */}
          {result.survivorship_note && (
            <div className="bg-gray-500/10 border border-gray-500/30 rounded-lg p-4">
              <p className="text-sm text-gray-400">{result.survivorship_note}</p>
            </div>
          )}
        </>
      )}

      {/* 无数据状态 */}
      {result && result.error && !loading && (
        <div className="bg-card-bg rounded-xl border border-border-dark p-8 text-center">
          <BarChart3 className="w-12 h-12 text-gray-500 mx-auto mb-4" />
          <h3 className="text-lg font-bold text-white mb-2">{result.error}</h3>
          <p className="text-sm text-gray-400">
            当前时间范围内没有足够的战力历史数据用于回测。
            <br />
            请选择更早的日期范围。
          </p>
        </div>
      )}
    </div>
  )
}

// 指标卡片组件
function MetricCard({ label, value, icon, color = 'blue' }) {
  const colorMap = {
    green: 'text-green-400 bg-green-500/10',
    red: 'text-red-400 bg-red-500/10',
    blue: 'text-accent-blue bg-accent-blue/10',
    purple: 'text-purple-400 bg-purple-500/10',
    yellow: 'text-yellow-400 bg-yellow-500/10'
  }

  return (
    <div className="bg-card-bg rounded-xl border border-border-dark p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-2 rounded-lg ${colorMap[color]}`}>
          {icon}
        </div>
        <span className="text-sm text-gray-400">{label}</span>
      </div>
      <p className={`text-2xl font-bold ${colorMap[color].split(' ')[0]}`}>
        {value}
      </p>
    </div>
  )
}
