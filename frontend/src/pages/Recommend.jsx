import { useState, useEffect, useCallback } from 'react'
import { TrendingUp, TrendingDown, Star, Zap, X, ArrowRight, Shield, AlertTriangle } from 'lucide-react'
import ReactECharts from 'echarts-for-react'
import { useWatchlist } from '../hooks/useWatchlist'
import { useHoldings } from '../hooks/useHoldings'

function Recommend() {
  const [recommendType, setRecommendType] = useState('value')
  const [riskPreference, setRiskPreference] = useState('aggressive')
  const [excludeHoldings, setExcludeHoldings] = useState(false)
  const [data, setData] = useState([])
  const [swapSuggestions, setSwapSuggestions] = useState([])
  const [portfolioDiversity, setPortfolioDiversity] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedStock, setSelectedStock] = useState(null)
  const [stockDetail, setStockDetail] = useState(null)
  const { watchlist, toggle, isInWatchlist } = useWatchlist()
  const { holdings } = useHoldings()

  // 雷达图配置
  const getRadarOption = (stock) => {
    return {
      radar: {
        indicator: [
          { name: '成长分', max: 100 },
          { name: '价值分', max: 100 },
          { name: '质量分', max: 100 },
          { name: '趋势分', max: 100 },
        ],
        radius: '55%',
        splitNumber: 4,
        axisName: { color: '#9ca3af' },
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } },
        splitArea: { areaStyle: { color: ['rgba(0,0,0,0)'] } },
        axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } }
      },
      series: [{
        type: 'radar',
        data: [{
          value: [stock.growth_score, stock.value_score, stock.quality_score || 0, stock.momentum_score],
          name: '战力分布',
          areaStyle: { color: 'rgba(59, 130, 246, 0.3)' },
          lineStyle: { color: '#3b82f6', width: 2 },
          itemStyle: { color: '#3b82f6' }
        }]
      }]
    }
  }

  // 点击查看股票详情
  const handleStockClick = async (stock) => {
    setSelectedStock(stock)
    try {
      const res = await fetch(`/api/stock/${stock.code}`)
      if (res.ok) {
        const detail = await res.json()
        setStockDetail(detail)
      }
    } catch (e) {
      console.error('Failed to load stock detail')
    }
  }

  useEffect(() => {
    fetchRecommend()
  }, [recommendType, riskPreference, excludeHoldings])

  const fetchRecommend = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = new URLSearchParams({
        category: recommendType,
        risk_preference: riskPreference,
        exclude_holdings: excludeHoldings.toString()
      })
      const res = await fetch(`/api/cp/recommend?${params}`)
      if (!res.ok) {
        throw new Error('请求失败')
      }
      const json = await res.json()
      if (json.error) {
        setError(json.error)
        setData([])
      } else {
        setData(json.data || [])
        setSwapSuggestions(json.swap_suggestions || [])
        setPortfolioDiversity(json.portfolio_diversity || {})
      }
    } catch (e) {
      console.error('Failed to fetch:', e)
      setError(e.message || '数据加载失败，请检查网络连接')
    }
    setLoading(false)
  }, [recommendType, riskPreference, excludeHoldings])

  const getCPColor = (cp) => {
    if (cp >= 70) return 'cp-high'
    if (cp >= 50) return 'cp-mid'
    return 'cp-low'
  }

  const getRiskColor = (riskLevel) => {
    if (riskLevel === '较低') return 'text-green-400'
    if (riskLevel === '中等') return 'text-yellow-400'
    return 'text-red-400'
  }

  const getRiskBg = (riskLevel) => {
    if (riskLevel === '较低') return 'bg-green-400/10 border-green-400/30'
    if (riskLevel === '中等') return 'bg-yellow-400/10 border-yellow-400/30'
    return 'bg-red-400/10 border-red-400/30'
  }

  const getSwapActionColor = (level) => {
    if (level === 'strong_buy') return 'text-green-400 bg-green-400/10'
    if (level === 'buy') return 'text-blue-400 bg-blue-400/10'
    if (level === 'hold') return 'text-yellow-400 bg-yellow-400/10'
    return 'text-red-400 bg-red-400/10'
  }

  const types = [
    { id: 'value', name: '价值型', desc: '高ROE + 低PE + 正增长', icon: '💰' },
    { id: 'growth', name: '成长型', desc: '高增长 + 中等ROE', icon: '📈' },
    { id: 'momentum', name: '趋势型', desc: '高动量 + 正增长', icon: '⚡' },
    { id: 'quality', name: '质量型', desc: '高质量 + 稳健ROE', icon: '🏆' },
    { id: 'allround', name: '综合型', desc: '均衡发展 + 全面战力', icon: '🎯' },
  ]

  const riskOptions = [
    { id: 'conservative', name: '保守', desc: '风险<30' },
    { id: 'balanced', name: '平衡', desc: '风险<50' },
    { id: 'aggressive', name: '激进', desc: 不过滤 },
  ]

  return (
    <div className="space-y-6">
      {/* 风险偏好 + 排除持仓 */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-gray-400" />
          <span className="text-sm text-gray-400">风险偏好:</span>
          <div className="flex gap-1">
            {riskOptions.map(opt => (
              <button
                key={opt.id}
                onClick={() => setRiskPreference(opt.id)}
                className={`px-3 py-1 text-xs rounded-lg border transition-all ${
                  riskPreference === opt.id
                    ? 'bg-accent-blue/20 border-accent-blue text-white'
                    : 'bg-card-bg border-border-dark text-gray-400 hover:border-accent-blue/50'
                }`}
              >
                {opt.name}
              </button>
            ))}
          </div>
        </div>

        {holdings && holdings.length > 0 && (
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={excludeHoldings}
              onChange={(e) => setExcludeHoldings(e.target.checked)}
              className="w-4 h-4 rounded border-border-dark bg-card-bg text-accent-blue focus:ring-accent-blue"
            />
            <span className="text-sm text-gray-400">隐藏已持仓</span>
          </label>
        )}
      </div>

      {/* 类型选择 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {types.map(type => (
          <button
            key={type.id}
            onClick={() => setRecommendType(type.id)}
            className={`p-4 rounded-xl border transition-all ${
              recommendType === type.id
                ? 'bg-accent-blue/20 border-accent-blue text-white'
                : 'bg-card-bg border-border-dark text-gray-400 hover:border-accent-blue/50'
            }`}
          >
            <div className="text-2xl mb-2">{type.icon}</div>
            <div className="font-bold">{type.name}</div>
            <div className="text-xs mt-1 opacity-70">{type.desc}</div>
          </button>
        ))}
      </div>

      {/* 换股建议 */}
      {swapSuggestions.length > 0 && (
        <div className="bg-card-bg rounded-xl border border-border-dark overflow-hidden">
          <div className="px-4 py-3 border-b border-border-dark flex items-center gap-2">
            <ArrowRight className="w-5 h-5 text-cp-high" />
            <span className="font-bold text-white">换股建议（基于当前持仓）</span>
            <span className="text-xs text-gray-400 ml-auto">{swapSuggestions.length} 条建议</span>
          </div>
          <div className="divide-y divide-border-dark/50">
            {swapSuggestions.map((swap, idx) => (
              <div key={idx} className="px-4 py-3 flex items-center justify-between hover:bg-white/5">
                <div className="flex items-center gap-3">
                  <div className="text-center">
                    <p className="text-sm text-gray-400">{swap.from_name}</p>
                    <p className="text-xs text-gray-500">战力 {swap.from_cp.toFixed(1)}</p>
                  </div>
                  <ArrowRight className="w-5 h-5 text-gray-500" />
                  <div className="text-center">
                    <p className="text-sm text-white font-bold">{swap.to_name}</p>
                    <p className="text-xs text-cp-high">战力 {swap.to_cp.toFixed(1)} → +{swap.cp_improvement.toFixed(1)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <p className="text-xs text-gray-400">成本: ¥{swap.trade_cost.toFixed(0)}</p>
                    <p className={`text-xs font-bold ${swap.net_benefit > 0 ? 'text-green-400' : 'text-red-400'}`}>
                      净收益: {swap.net_benefit > 0 ? '+' : ''}{swap.net_benefit.toFixed(0)}
                    </p>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-bold ${getSwapActionColor(swap.action_level)}`}>
                    {swap.action_label}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 行业分散度 */}
      {Object.keys(portfolioDiversity).length > 0 && (
        <div className="flex flex-wrap gap-2">
          <span className="text-sm text-gray-400">行业分散:</span>
          {Object.entries(portfolioDiversity).map(([sector, count]) => (
            <span key={sector} className="px-2 py-1 bg-card-bg border border-border-dark rounded text-xs text-gray-300">
              {sector}: {count}
            </span>
          ))}
        </div>
      )}

      {/* 推荐列表 */}
      <div className="bg-card-bg rounded-xl border border-border-dark overflow-hidden">
        <div className="px-4 py-3 border-b border-border-dark flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-cp-high" />
            <span className="font-bold text-white">
              {types.find(t => t.id === recommendType)?.name}推荐
            </span>
          </div>
          <span className="text-sm text-gray-400">{data.length} 只股票</span>
        </div>

        {loading ? (
          <div className="py-20 text-center text-gray-400">加载中...</div>
        ) : error ? (
          <div className="p-8 text-center">
            <p className="text-cp-low text-lg mb-4">{error}</p>
            <button
              onClick={() => fetchRecommend()}
              className="px-4 py-2 bg-cp-low/20 hover:bg-cp-low/30 text-cp-low rounded-lg transition-colors"
            >
              重试
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border-dark text-left text-sm text-gray-400">
                  <th className="px-4 py-3">股票</th>
                  <th className="px-4 py-3 text-right">战力</th>
                  <th className="px-4 py-3 text-right">ROE</th>
                  <th className="px-4 py-3 text-right">增长</th>
                  <th className="px-4 py-3 text-right">股息率</th>
                  <th className="px-4 py-3 text-right">风险</th>
                  <th className="px-4 py-3 text-right">市值(亿)</th>
                  <th className="px-4 py-3 text-right">今日涨跌</th>
                  <th className="px-4 py-3 text-right">净收益提示</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {data.map((stock, index) => (
                  <tr
                    key={stock.code}
                    onClick={() => handleStockClick(stock)}
                    className="border-b border-border-dark/50 hover:bg-white/5 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div>
                          <p className="font-bold text-white">{stock.name}</p>
                          <p className="text-xs text-gray-500">{stock.code}</p>
                        </div>
                        {stock.data_quality && (
                          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            stock.data_quality === 'high' ? 'bg-green-400' :
                            stock.data_quality === 'medium' ? 'bg-yellow-400' : 'bg-gray-500'
                          }`} title={`数据质量: ${stock.data_quality === 'high' ? '高' : stock.data_quality === 'medium' ? '中' : '低'}`} />
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`cp-tag ${getCPColor(stock.total_cp)}`}>
                        {stock.total_cp.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-gray-300">
                      {stock.roe.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-gray-300">
                      {stock.net_profit_growth >= 0 ? '+' : ''}{stock.net_profit_growth.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-right text-sm">
                      <span className={stock.dividend_yield > 0 ? 'text-green-400' : 'text-gray-500'}>
                        {stock.dividend_yield > 0 ? stock.dividend_yield.toFixed(2) + '%' : 'N/A'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`px-2 py-0.5 rounded text-xs border ${getRiskBg(stock.risk_level)} ${getRiskColor(stock.risk_level)}`}>
                        {stock.risk_level}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-gray-300">
                      {stock.market_cap > 0 ? stock.market_cap.toFixed(0) : 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {stock.change_pct > 0 ? (
                          <TrendingUp className="w-4 h-4 text-red-500" />
                        ) : (
                          <TrendingDown className="w-4 h-4 text-green-500" />
                        )}
                        <span className={`text-sm font-mono ${
                          stock.change_pct > 0 ? 'text-red-500' : 'text-green-500'
                        }`}>
                          {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`text-xs ${stock.net_benefit_hint.includes('+') ? 'text-green-400' : stock.net_benefit_hint.includes('成本过高') ? 'text-red-400' : 'text-gray-400'}`}>
                        {stock.net_benefit_hint || '-'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={(e) => { e.stopPropagation(); toggle(stock.code); }}
                        className="transition-colors"
                      >
                        <Star
                          className={`w-5 h-5 ${
                            isInWatchlist(stock.code)
                              ? 'text-cp-high fill-cp-high'
                              : 'text-gray-500 hover:text-cp-high'
                          }`}
                        />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && data.length === 0 && (
          <div className="py-20 text-center text-gray-400">
            暂无推荐股票
          </div>
        )}
      </div>

      {/* 股票详情弹窗 */}
      {selectedStock && stockDetail && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setSelectedStock(null)}>
          <div className="bg-card-bg rounded-xl border border-border-dark p-6 max-w-lg w-full" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-xl font-bold text-white">{stockDetail.name}</h3>
                <p className="text-gray-400 text-sm">{stockDetail.code}</p>
              </div>
              <button onClick={() => setSelectedStock(null)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex items-center gap-3 mb-4">
              <span className={`cp-tag ${getCPColor(stockDetail.total_cp)} text-lg px-4 py-2`}>
                CP {stockDetail.total_cp.toFixed(1)}
              </span>
              <span className="text-2xl font-bold text-white">¥{stockDetail.price.toFixed(2)}</span>
              <span className={`font-mono ${stockDetail.change_pct >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                {stockDetail.change_pct >= 0 ? '+' : ''}{stockDetail.change_pct.toFixed(2)}%
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="bg-deep-night rounded-lg p-3">
                <p className="text-gray-400 text-xs">市盈率</p>
                <p className="text-lg font-bold text-white">{stockDetail.pe > 0 ? stockDetail.pe.toFixed(1) : 'N/A'}</p>
              </div>
              <div className="bg-deep-night rounded-lg p-3">
                <p className="text-gray-400 text-xs">ROE</p>
                <p className="text-lg font-bold text-white">{stockDetail.roe.toFixed(1)}%</p>
              </div>
              <div className="bg-deep-night rounded-lg p-3">
                <p className="text-gray-400 text-xs">净利润增速</p>
                <p className={`text-lg font-bold ${stockDetail.net_profit_growth >= 0 ? 'text-cp-high' : 'text-cp-low'}`}>
                  {stockDetail.net_profit_growth >= 0 ? '+' : ''}{stockDetail.net_profit_growth.toFixed(1)}%
                </p>
              </div>
              <div className="bg-deep-night rounded-lg p-3">
                <p className="text-gray-400 text-xs">营收增速</p>
                <p className={`text-lg font-bold ${stockDetail.revenue_growth >= 0 ? 'text-cp-high' : 'text-cp-low'}`}>
                  {stockDetail.revenue_growth >= 0 ? '+' : ''}{stockDetail.revenue_growth.toFixed(1)}%
                </p>
              </div>
            </div>

            {/* 增强信息 */}
            <div className="grid grid-cols-3 gap-2 mb-4">
              <div className="bg-deep-night rounded-lg p-2 text-center">
                <p className="text-gray-400 text-xs">股息率</p>
                <p className="text-sm font-bold text-green-400">{stockDetail.dividend_yield > 0 ? stockDetail.dividend_yield.toFixed(2) + '%' : 'N/A'}</p>
              </div>
              <div className="bg-deep-night rounded-lg p-2 text-center">
                <p className="text-gray-400 text-xs">风险等级</p>
                <p className={`text-sm font-bold ${getRiskColor(stockDetail.risk_level)}`}>{stockDetail.risk_level}</p>
              </div>
              <div className="bg-deep-night rounded-lg p-2 text-center">
                <p className="text-gray-400 text-xs">市值(亿)</p>
                <p className="text-sm font-bold text-white">{stockDetail.market_cap > 0 ? stockDetail.market_cap.toFixed(0) : 'N/A'}</p>
              </div>
            </div>

            <div className="bg-deep-night rounded-lg p-4">
              <p className="text-gray-400 text-sm mb-2">战力雷达图</p>
              <ReactECharts option={getRadarOption(stockDetail)} style={{ height: '180px' }} />
            </div>

            <div className="flex justify-between mt-4 text-sm text-gray-400">
              <div>成长分: <span className="text-white font-bold">{stockDetail.growth_score.toFixed(1)}</span></div>
              <div>价值分: <span className="text-white font-bold">{stockDetail.value_score.toFixed(1)}</span></div>
              <div>质量分: <span className="text-purple-400 font-bold">{(stockDetail.quality_score || 0).toFixed(1)}</span></div>
              <div>趋势分: <span className="text-white font-bold">{stockDetail.momentum_score.toFixed(1)}</span></div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Recommend
