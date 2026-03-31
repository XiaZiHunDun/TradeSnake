import { useState, useEffect } from 'react'
import { Plus, Trash2, Calculator, Zap } from 'lucide-react'
import ReactECharts from 'echarts-for-react'

function PortfolioSimulator() {
  const [stocks, setStocks] = useState([]) // 模拟持仓
  const [newStock, setNewStock] = useState({ code: '', quantity: 100 })
  const [searchResult, setSearchResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [simResult, setSimResult] = useState(null)
  const [simChange, setSimChange] = useState(10) // 模拟战力变化值

  // 搜索股票
  const searchStock = async (code) => {
    if (!code.trim()) return

    setLoading(true)
    setError(null)
    setSearchResult(null)
    try {
      let searchCode = code.trim().toUpperCase()
      if (!searchCode.startsWith('SH') && !searchCode.startsWith('SZ')) {
        if (searchCode.startsWith('6')) searchCode = 'SH' + searchCode
        else searchCode = 'SZ' + searchCode
      }

      const res = await fetch(`/api/stock/${searchCode}`)
      if (res.ok) {
        const data = await res.json()
        setSearchResult(data)
      } else if (res.status === 404) {
        setError('股票代码不存在')
      } else {
        setError('搜索失败，请稍后重试')
      }
    } catch (e) {
      console.error('Search failed:', e)
      setError('网络错误，请检查连接')
    }
    setLoading(false)
  }

  // 添加到模拟组合
  const addToSim = () => {
    if (!searchResult) return

    const existing = stocks.find(s => s.code === searchResult.code)
    if (existing) {
      setStocks(stocks.map(s =>
        s.code === searchResult.code
          ? { ...s, quantity: s.quantity + newStock.quantity }
          : s
      ))
    } else {
      setStocks([...stocks, {
        code: searchResult.code,
        name: searchResult.name,
        price: searchResult.price,
        total_cp: searchResult.total_cp,
        quantity: newStock.quantity
      }])
    }

    setSearchResult(null)
    setNewStock({ code: '', quantity: 100 })
  }

  // 从模拟组合移除
  const removeFromSim = (code) => {
    setStocks(stocks.filter(s => s.code !== code))
  }

  // 计算模拟结果
  const calculateSim = () => {
    if (stocks.length === 0) return

    // 计算当前状态
    const currentCP = stocks.reduce((sum, s) => sum + s.total_cp * s.quantity, 0)
    const currentValue = stocks.reduce((sum, s) => sum + s.price * s.quantity, 0)
    const totalQuantity = stocks.reduce((sum, s) => sum + s.quantity, 0)
    const avgCP = totalQuantity > 0 ? currentCP / totalQuantity : 0

    // 模拟：按百分比变化
    const changeAmount = simChange
    const improvedCP = stocks.reduce((sum, s) => {
      const newCP = Math.min(100, s.total_cp + changeAmount)
      return sum + newCP * s.quantity
    }, 0)

    const reducedCP = stocks.reduce((sum, s) => {
      const newCP = Math.max(0, s.total_cp - changeAmount)
      return sum + newCP * s.quantity
    }, 0)

    const improvementRate = currentCP > 0 ? ((improvedCP - currentCP) / currentCP * 100).toFixed(1) : 0
    const reductionRate = currentCP > 0 ? ((reducedCP - currentCP) / currentCP * 100).toFixed(1) : 0

    setSimResult({
      current: currentCP,
      improved: improvedCP,
      reduced: reducedCP,
      currentValue: currentValue,
      improvementRate: improvementRate,
      reductionRate: reductionRate,
      avgCP: avgCP
    })
  }

  // 获取模拟结果对比图表
  const getCompareChartOption = () => {
    if (!simResult) return null
    return {
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['当前战力', '提升后', '下降后'],
        textStyle: { color: '#9ca3af' }
      },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: stocks.map(s => s.name),
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af', rotate: 30 }
      },
      yAxis: {
        type: 'value',
        name: '战力贡献',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af' }
      },
      series: [
        {
          name: '当前战力',
          type: 'bar',
          data: stocks.map(s => (s.total_cp * s.quantity).toFixed(0)),
          itemStyle: { color: '#3b82f6' }
        },
        {
          name: '提升后',
          type: 'bar',
          data: stocks.map(s => {
            const newCP = Math.min(100, s.total_cp + simChange)
            return (newCP * s.quantity).toFixed(0)
          }),
          itemStyle: { color: '#22c55e' }
        },
        {
          name: '下降后',
          type: 'bar',
          data: stocks.map(s => {
            const newCP = Math.max(0, s.total_cp - simChange)
            return (newCP * s.quantity).toFixed(0)
          }),
          itemStyle: { color: '#ef4444' }
        }
      ]
    }
  }

  // 清空模拟
  const clearSim = () => {
    setStocks([])
    setSimResult(null)
  }

  return (
    <div className="space-y-6">
      <div className="bg-card-bg rounded-xl border border-border-dark p-6">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
          <Calculator className="w-5 h-5 text-accent-blue" />
          组合战力模拟器
        </h2>
        <p className="text-gray-400 text-sm mb-4">
          添加股票到模拟组合，预估战力提升或下降的影响
        </p>

        {/* 搜索添加 */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div>
            <label className="block text-sm text-gray-400 mb-1">股票代码</label>
            <input
              type="text"
              value={newStock.code}
              onChange={(e) => {
                setNewStock({ ...newStock, code: e.target.value })
                if (e.target.value.length >= 6) {
                  searchStock(e.target.value)
                }
              }}
              placeholder="600519"
              className="w-full px-3 py-2 bg-deep-night border border-border-dark rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
            />
            {searchResult && (
              <div className="mt-2 p-2 bg-deep-night rounded text-sm">
                <p className="text-white font-bold">{searchResult.name}</p>
                <p className="text-gray-400">
                  ¥{searchResult.price.toFixed(2)} | CP {searchResult.total_cp.toFixed(1)}
                </p>
              </div>
            )}
            {error && (
              <p className="mt-2 text-sm text-cp-low">{error}</p>
            )}
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">持股数量</label>
            <input
              type="number"
              min="0"
              value={newStock.quantity}
              onChange={(e) => setNewStock({ ...newStock, quantity: Number(e.target.value) })}
              className="w-full px-3 py-2 bg-deep-night border border-border-dark rounded-lg text-white focus:outline-none focus:border-accent-blue"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={addToSim}
              disabled={!searchResult}
              className="flex items-center gap-2 px-4 py-2 bg-accent-blue text-white rounded-lg hover:bg-accent-blue/80 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="w-4 h-4" />
              添加
            </button>
          </div>
        </div>

        {/* 模拟持仓列表 */}
        {stocks.length > 0 && (
          <div className="mb-6">
            <h3 className="font-bold text-white mb-3">模拟持仓 ({stocks.length})</h3>
            <div className="space-y-2">
              {stocks.map(stock => (
                <div key={stock.code} className="flex items-center justify-between p-3 bg-deep-night rounded-lg">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <div>
                        <p className="text-white font-bold">{stock.name}</p>
                        <p className="text-gray-400 text-xs">{stock.code}</p>
                      </div>
                      {stock.data_quality && (
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          stock.data_quality === 'high' ? 'bg-green-400' :
                          stock.data_quality === 'medium' ? 'bg-yellow-400' : 'bg-gray-500'
                        }`} title={`数据质量: ${stock.data_quality === 'high' ? '高' : stock.data_quality === 'medium' ? '中' : '低'}`} />
                      )}
                    </div>
                    <div className="text-sm text-gray-300">
                      {stock.quantity}股 × ¥{stock.price.toFixed(2)} = ¥{(stock.quantity * stock.price).toFixed(0)}
                    </div>
                    {stock.market_cap > 0 && (
                      <div className="text-xs text-gray-500">
                        市值{stock.market_cap.toFixed(0)}亿
                      </div>
                    )}
                    <div className="text-sm">
                      <span className={`cp-tag ${stock.total_cp >= 70 ? 'cp-high' : stock.total_cp >= 50 ? 'cp-mid' : 'cp-low'}`}>
                        CP {stock.total_cp.toFixed(1)}
                      </span>
                    </div>
                    <div className="text-sm text-accent-blue">
                      战力贡献: {(stock.total_cp * stock.quantity).toFixed(0)}
                    </div>
                  </div>
                  <button
                    onClick={() => removeFromSim(stock.code)}
                    className="text-gray-400 hover:text-red-500"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="flex gap-3 items-end">
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-400">战力变化</label>
            <input
              type="number"
              value={simChange}
              onChange={(e) => setSimChange(Number(e.target.value))}
              className="w-20 px-3 py-2 bg-deep-night border border-border-dark rounded-lg text-white text-sm focus:outline-none focus:border-accent-blue"
            />
            <span className="text-gray-400 text-sm">点</span>
          </div>
          <button
            onClick={calculateSim}
            disabled={stocks.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-cp-high/20 text-cp-high rounded-lg hover:bg-cp-high/30 disabled:opacity-50"
          >
            <Zap className="w-4 h-4" />
            计算模拟
          </button>
          {stocks.length > 0 && (
            <button
              onClick={clearSim}
              className="px-4 py-2 text-gray-400 hover:text-white"
            >
              清空
            </button>
          )}
        </div>
      </div>

      {/* 模拟结果 */}
      {simResult && (
        <div className="bg-card-bg rounded-xl border border-border-dark p-6">
          <h3 className="font-bold text-white mb-4">模拟结果</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
            <div className="bg-deep-night rounded-lg p-4 text-center">
              <p className="text-gray-400 text-sm mb-1">当前总战力</p>
              <p className="text-2xl font-bold text-white">{simResult.current.toFixed(0)}</p>
            </div>
            <div className="bg-deep-night rounded-lg p-4 text-center">
              <p className="text-gray-400 text-sm mb-1">提升后</p>
              <p className="text-2xl font-bold text-green-500">{simResult.improved.toFixed(0)}</p>
              <p className="text-xs text-green-500">+{simResult.improvementRate}%</p>
            </div>
            <div className="bg-deep-night rounded-lg p-4 text-center">
              <p className="text-gray-400 text-sm mb-1">下降后</p>
              <p className="text-2xl font-bold text-red-500">{simResult.reduced.toFixed(0)}</p>
              <p className="text-xs text-red-500">{simResult.reductionRate}%</p>
            </div>
            <div className="bg-deep-night rounded-lg p-4 text-center">
              <p className="text-gray-400 text-sm mb-1">组合市值</p>
              <p className="text-2xl font-bold text-white">¥{simResult.currentValue.toFixed(0)}</p>
            </div>
            <div className="bg-deep-night rounded-lg p-4 text-center">
              <p className="text-gray-400 text-sm mb-1">平均战力</p>
              <p className="text-2xl font-bold text-accent-blue">{simResult.avgCP.toFixed(1)}</p>
            </div>
          </div>

          {/* 对比图表 */}
          {stocks.length > 0 && (
            <div className="mb-4 bg-deep-night rounded-lg p-4">
              <p className="text-gray-400 text-sm mb-2">战力贡献对比</p>
              <ReactECharts option={getCompareChartOption()} style={{ height: '250px' }} />
            </div>
          )}

          <div className="p-4 bg-deep-night rounded-lg">
            <p className="text-gray-300 text-sm">
              {`提示：如果将组合内所有股票的战力各${simChange > 0 ? '提升' : '下降'}${Math.abs(simChange)}点，总战力将从 `}
              <span className="text-white font-bold">{simResult.current.toFixed(0)}</span>
              {simChange > 0 ? ' 提升到 ' : ' 下降到 '}
              <span className={simChange > 0 ? 'text-green-500' : 'text-red-500'}>{simChange > 0 ? simResult.improved.toFixed(0) : simResult.reduced.toFixed(0)}</span>，
              {'变化 '}<span className={simChange > 0 ? 'text-green-500' : 'text-red-500'}>{simChange > 0 ? '+' : ''}{simChange > 0 ? simResult.improvementRate : simResult.reductionRate}%</span>。
              {'市值 ¥'}{simResult.currentValue.toFixed(0)} 不随战力变化。
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default PortfolioSimulator
