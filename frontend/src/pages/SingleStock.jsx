import { useState, useEffect } from 'react'
import { Search, TrendingUp, TrendingDown } from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import StockNews from '../components/StockNews'

function SingleStock() {
  const [code, setCode] = useState('')
  const [stock, setStock] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const [chartType, setChartType] = useState('cp') // 'cp' | 'price'

  // 检查快捷搜索
  useEffect(() => {
    try {
      const quickCode = localStorage.getItem('quickSearchCode')
      if (quickCode) {
        setCode(quickCode)
        localStorage.removeItem('quickSearchCode')
        handleSearch(quickCode)
      }
    } catch (e) {
      console.error('Failed to load quick search code:', e)
    }
  }, [])

  // 获取雷达图配置
  const getRadarOption = (stock) => {
    return {
      radar: {
        indicator: [
          { name: '成长分', max: 100 },
          { name: '价值分', max: 100 },
          { name: '质量分', max: 100 },
          { name: '趋势分', max: 100 },
        ],
        radius: '60%',
        splitNumber: 4,
        axisName: {
          color: '#9ca3af',
        },
        splitLine: {
          lineStyle: { color: 'rgba(255,255,255,0.1)' }
        },
        splitArea: {
          areaStyle: { color: ['rgba(0,0,0,0)'] }
        },
        axisLine: {
          lineStyle: { color: 'rgba(255,255,255,0.2)' }
        }
      },
      series: [{
        type: 'radar',
        data: [{
          value: [stock.growth_score, stock.value_score, stock.quality_score || 0, stock.momentum_score],
          name: '战力分布',
          areaStyle: {
            color: 'rgba(59, 130, 246, 0.3)'
          },
          lineStyle: {
            color: '#3b82f6',
            width: 2
          },
          itemStyle: {
            color: '#3b82f6'
          }
        }]
      }]
    }
  }

  const handleSearch = async (overrideCode) => {
    const targetCode = overrideCode || code
    if (!targetCode.trim()) return

    setLoading(true)
    setError(null)
    setStock(null)
    setHistory([])

    try {
      // 自动补全代码格式
      let searchCode = targetCode.trim().toUpperCase()
      if (!searchCode.startsWith('SH') && !searchCode.startsWith('SZ')) {
        if (searchCode.startsWith('6')) {
          searchCode = 'SH' + searchCode
        } else {
          searchCode = 'SZ' + searchCode
        }
      }

      const res = await fetch(`/api/stock/${searchCode}`)
      if (!res.ok) {
        throw new Error('股票未找到')
      }
      const data = await res.json()
      setStock(data)

      // 获取历史数据
      try {
        const historyRes = await fetch(`/api/history/${searchCode}?days=7`)
        if (historyRes.ok) {
          const historyData = await historyRes.json()
          setHistory(historyData.data || [])
        }
      } catch (e) {
        console.error('Failed to fetch stock history:', e)
      }
    } catch (e) {
      setError(e.message)
    }

    setLoading(false)
  }

  // 战力历史走势图配置
  const getHistoryOption = () => {
    if (!history || history.length === 0) return null

    if (chartType === 'price') {
      // 价格走势图
      const dates = history.map(h => h.date.slice(5))
      const priceData = history.map(h => h.price || 0)

      return {
        tooltip: { trigger: 'axis' },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: {
          type: 'category',
          data: dates,
          axisLine: { lineStyle: { color: '#374151' } },
          axisLabel: { color: '#9ca3af' }
        },
        yAxis: {
          type: 'value',
          axisLine: { show: false },
          splitLine: { lineStyle: { color: '#374151' } },
          axisLabel: { color: '#9ca3af', formatter: '¥{value}' }
        },
        series: [{
          name: '价格',
          type: 'line',
          data: priceData,
          smooth: true,
          lineStyle: { color: '#00d9ff', width: 2 },
          itemStyle: { color: '#00d9ff' },
          areaStyle: { color: 'rgba(0, 217, 255, 0.1)' }
        }]
      }
    }

    // 战力走势图（默认）
    const dates = history.map(h => h.date.slice(5))
    const cpData = history.map(h => h.total_cp)
    const growthData = history.map(h => h.growth_score)
    const valueData = history.map(h => h.value_score)
    const qualityData = history.map(h => h.quality_score || 0)
    const momentumData = history.map(h => h.momentum_score)

    return {
      tooltip: { trigger: 'axis' },
      legend: {
        data: ['总战力', '成长分', '价值分', '质量分', '趋势分'],
        textStyle: { color: '#9ca3af' }
      },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af' }
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#9ca3af' }
      },
      series: [
        { name: '总战力', type: 'line', data: cpData, smooth: true, lineStyle: { color: '#3b82f6', width: 3 }, itemStyle: { color: '#3b82f6' } },
        { name: '成长分', type: 'line', data: growthData, smooth: true, lineStyle: { color: '#22c55e', width: 2 }, itemStyle: { color: '#22c55e' } },
        { name: '价值分', type: 'line', data: valueData, smooth: true, lineStyle: { color: '#eab308', width: 2 }, itemStyle: { color: '#eab308' } },
        { name: '质量分', type: 'line', data: qualityData, smooth: true, lineStyle: { color: '#a855f7', width: 2 }, itemStyle: { color: '#a855f7' } },
        { name: '趋势分', type: 'line', data: momentumData, smooth: true, lineStyle: { color: '#ef4444', width: 2 }, itemStyle: { color: '#ef4444' } }
      ]
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const getCPColor = (cp) => {
    if (cp >= 70) return 'cp-high'
    if (cp >= 50) return 'cp-mid'
    return 'cp-low'
  }

  return (
    <div className="space-y-6">
      {/* 搜索框 */}
      <div className="bg-card-bg rounded-xl border border-border-dark p-6">
        <h2 className="text-lg font-bold mb-4">单股战力查询</h2>
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入股票代码，如 600519 或 sh600519"
              className="w-full pl-10 pr-4 py-3 bg-deep-night border border-border-dark rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={loading}
            className="px-6 py-3 bg-accent-blue text-white rounded-lg hover:bg-accent-blue/80 transition-colors disabled:opacity-50"
          >
            {loading ? '查询中...' : '查询'}
          </button>
        </div>
        <p className="text-sm text-gray-500 mt-2">
          支持：600519（茅台）、000858（五粮液）、300750（宁德时代）等
        </p>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className="bg-cp-low/10 border border-cp-low/30 rounded-xl p-4 text-cp-low">
          {error}
        </div>
      )}

      {/* 股票详情 */}
      {stock && (
        <div className="bg-card-bg rounded-xl border border-border-dark p-6">
          {/* 头部信息 */}
          <div className="flex items-start justify-between mb-6">
            <div>
              <h3 className="text-2xl font-bold text-white">{stock.name}</h3>
              <p className="text-gray-400">{stock.code}</p>
            </div>
            <div className="text-right">
              <div className={`cp-tag ${getCPColor(stock.total_cp)} text-lg px-4 py-2`}>
                CP {stock.total_cp.toFixed(1)}
              </div>
            </div>
          </div>

          {/* 当前价格 */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="bg-deep-night rounded-lg p-4">
              <p className="text-gray-400 text-sm">现价</p>
              <p className="text-2xl font-bold text-white">¥{stock.price.toFixed(2)}</p>
            </div>
            <div className="bg-deep-night rounded-lg p-4">
              <p className="text-gray-400 text-sm">涨跌幅</p>
              <div className="flex items-center gap-2">
                {stock.change_pct >= 0 ? (
                  <TrendingUp className="w-5 h-5 text-red-500" />
                ) : (
                  <TrendingDown className="w-5 h-5 text-green-500" />
                )}
                <p className={`text-2xl font-bold ${stock.change_pct >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                  {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                </p>
              </div>
            </div>
          </div>

          {/* 市场信息 */}
          {(stock.market_cap > 0 || stock.high > 0 || stock.low > 0) && (
            <div className="grid grid-cols-4 gap-3 mb-6">
              <div className="bg-deep-night rounded-lg p-3 text-center">
                <p className="text-gray-400 text-xs">市值(亿)</p>
                <p className="text-white font-bold">{stock.market_cap > 0 ? stock.market_cap.toFixed(0) : '-'}</p>
              </div>
              <div className="bg-deep-night rounded-lg p-3 text-center">
                <p className="text-gray-400 text-xs">最高价</p>
                <p className="text-red-400 font-bold">{stock.high > 0 ? stock.high.toFixed(2) : '-'}</p>
              </div>
              <div className="bg-deep-night rounded-lg p-3 text-center">
                <p className="text-gray-400 text-xs">最低价</p>
                <p className="text-green-400 font-bold">{stock.low > 0 ? stock.low.toFixed(2) : '-'}</p>
              </div>
              <div className="bg-deep-night rounded-lg p-3 text-center">
                <p className="text-gray-400 text-xs">数据质量</p>
                <p className={`font-bold ${stock.data_quality === 'high' ? 'text-green-400' : stock.data_quality === 'medium' ? 'text-yellow-400' : 'text-gray-400'}`}>
                  {stock.data_quality === 'high' ? '高' : stock.data_quality === 'medium' ? '中' : '低'}
                </p>
              </div>
            </div>
          )}

          {/* 战力分析 */}
          <div className="mb-6">
            <h4 className="text-lg font-bold mb-4">战力分析</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* 雷达图 */}
              <div className="bg-deep-night rounded-lg p-4">
                <p className="text-gray-400 text-sm mb-2">战力雷达图</p>
                <ReactECharts option={getRadarOption(stock)} style={{ height: '200px' }} />
              </div>

              {/* 分数条 */}
              <div className="space-y-4">
                <div className="bg-deep-night rounded-lg p-4">
                  <div className="flex justify-between mb-1">
                    <p className="text-gray-400 text-sm">成长分</p>
                    <p className="text-white font-bold">{stock.growth_score.toFixed(1)}</p>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div className="h-full bg-cp-high rounded-full" style={{ width: `${stock.growth_score}%` }} />
                  </div>
                </div>

                <div className="bg-deep-night rounded-lg p-4">
                  <div className="flex justify-between mb-1">
                    <p className="text-gray-400 text-sm">价值分</p>
                    <p className="text-white font-bold">{stock.value_score.toFixed(1)}</p>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div className="h-full bg-cp-mid rounded-full" style={{ width: `${stock.value_score}%` }} />
                  </div>
                </div>

                <div className="bg-deep-night rounded-lg p-4">
                  <div className="flex justify-between mb-1">
                    <p className="text-gray-400 text-sm">质量分</p>
                    <p className="text-purple-400 font-bold">{(stock.quality_score || 0).toFixed(1)}</p>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div className="h-full bg-purple-500 rounded-full" style={{ width: `${stock.quality_score || 0}%` }} />
                  </div>
                </div>

                <div className="bg-deep-night rounded-lg p-4">
                  <div className="flex justify-between mb-1">
                    <p className="text-gray-400 text-sm">趋势分</p>
                    <p className="text-white font-bold">{stock.momentum_score.toFixed(1)}</p>
                  </div>
                  <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                    <div className="h-full bg-accent-blue rounded-full" style={{ width: `${stock.momentum_score}%` }} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 基本面数据 */}
          <div>
            <h4 className="text-lg font-bold mb-4">基本面数据</h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-deep-night rounded-lg p-4">
                <p className="text-gray-400 text-sm">市盈率 (PE)</p>
                <p className="text-xl font-bold text-white">{stock.pe > 0 ? stock.pe.toFixed(1) : 'N/A'}</p>
              </div>
              <div className="bg-deep-night rounded-lg p-4">
                <p className="text-gray-400 text-sm">净资产收益率 (ROE)</p>
                <p className="text-xl font-bold text-white">{stock.roe.toFixed(1)}%</p>
              </div>
              <div className="bg-deep-night rounded-lg p-4">
                <p className="text-gray-400 text-sm">净利润增速</p>
                <p className={`text-xl font-bold ${stock.net_profit_growth >= 0 ? 'text-cp-high' : 'text-cp-low'}`}>
                  {stock.net_profit_growth >= 0 ? '+' : ''}{stock.net_profit_growth.toFixed(1)}%
                </p>
              </div>
              <div className="bg-deep-night rounded-lg p-4">
                <p className="text-gray-400 text-sm">营收增速</p>
                <p className={`text-xl font-bold ${stock.revenue_growth >= 0 ? 'text-cp-high' : 'text-cp-low'}`}>
                  {stock.revenue_growth >= 0 ? '+' : ''}{stock.revenue_growth.toFixed(1)}%
                </p>
              </div>
            </div>
          </div>

          {/* 战力历史走势 */}
          {history && history.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-lg font-bold">历史走势</h4>
                <div className="flex gap-2">
                  <button
                    onClick={() => setChartType('cp')}
                    className={`px-3 py-1 rounded text-sm ${
                      chartType === 'cp' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    战力
                  </button>
                  <button
                    onClick={() => setChartType('price')}
                    className={`px-3 py-1 rounded text-sm ${
                      chartType === 'price' ? 'bg-accent-blue/20 text-accent-blue' : 'text-gray-400 hover:text-white'
                    }`}
                  >
                    价格
                  </button>
                </div>
              </div>
              <div className="bg-deep-night rounded-lg p-4">
                <ReactECharts option={getHistoryOption()} style={{ height: '200px' }} />
              </div>
            </div>
          )}

          {/* 相关新闻 */}
          {stock && (
            <div>
              <h4 className="text-lg font-bold mb-4">相关新闻</h4>
              <div className="bg-card-bg rounded-xl border border-border-dark p-4">
                <StockNews code={stock.code} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* 空状态 */}
      {!stock && !loading && !error && (
        <div className="bg-card-bg rounded-xl border border-border-dark p-12 text-center">
          <Search className="w-16 h-16 text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">输入股票代码查询战力详情</p>
        </div>
      )}
    </div>
  )
}

export default SingleStock
