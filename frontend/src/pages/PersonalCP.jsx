import { useState, useEffect } from 'react'
import { Plus, Trash2, Save, X, Zap, TrendingUp, TrendingDown, AlertTriangle, Sparkles, Bell, ArrowRightLeft, Activity, RefreshCw } from 'lucide-react'
import { useHoldings, loadHoldings, saveHoldings } from '../hooks/useHoldings'
import { useNotification } from '../hooks/useNotification'
import DEFAULT_HOLDINGS from '../data/defaultHoldings'

function PersonalCP() {
  const { holdings, refresh, add, update, remove, clear } = useHoldings()
  const [stockData, setStockData] = useState({}) // 存储股票的战力数据
  const [showAddForm, setShowAddForm] = useState(false)
  const [editingCode, setEditingCode] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showInitPrompt, setShowInitPrompt] = useState(false)
  const [alerts, setAlerts] = useState([]) // 战力预警
  const [showAlertForm, setShowAlertForm] = useState(false)
  const [alertConfig, setAlertConfig] = useState({ code: '', threshold: 50, type: 'cp_drop' })
  const [topStocks, setTopStocks] = useState([]) // 全市场TOP股票用于推荐
  const { addNotification } = useNotification()

  // 检查是否需要加载初始数据
  useEffect(() => {
    const currentHoldings = loadHoldings()
    if (currentHoldings.length === 0) {
      setShowInitPrompt(true)
    }
  }, [])

  // 加载默认持仓
  const loadDefaultHoldings = () => {
    DEFAULT_HOLDINGS.forEach(h => add(h))
    setShowInitPrompt(false)
    refresh()
  }

  // 新增/编辑表单
  const [formData, setFormData] = useState({
    code: '',
    name: '',
    quantity: 0,
    costPrice: 0
  })

  // 加载持仓股票的战力数据（批量获取）
  useEffect(() => {
    loadStockData()
    loadTopStocks()
  }, [holdings])

  // 计算调仓建议
  const getRebalanceSuggestions = () => {
    if (holdings.length === 0 || topStocks.length === 0) return { swapOut: [], swapIn: [], assessment: null }

    // 持仓中战力最低的股票（考虑数据质量）
    const holdingCPs = holdings.map(h => ({
      ...h,
      cp: stockData[h.code]?.total_cp || 0,
      cpData: stockData[h.code],
      score: stockData[h.code] ? stockData[h.code].total_cp * h.quantity : 0
    })).sort((a, b) => a.cp - b.cp)

    // 市场TOP股票（不在持仓中，数据质量高优先）
    const holdingCodes = new Set(holdings.map(h => h.code))
    const availableTopStocks = topStocks
      .filter(s => !holdingCodes.has(s.code) && s.total_cp >= 50)
      .sort((a, b) => {
        // 战力相同时，高数据质量的优先
        if (b.total_cp === a.total_cp) {
          const qualityOrder = { high: 0, medium: 1, low: 2 }
          return (qualityOrder[a.data_quality] || 2) - (qualityOrder[b.data_quality] || 2)
        }
        return b.total_cp - a.total_cp
      })

    // 找出可以替换的组合
    const suggestions = { swapOut: [], swapIn: [], assessment: null }

    // 计算持仓平均战力
    const avgHoldingCP = holdings.reduce((sum, h) => sum + (stockData[h.code]?.total_cp || 0), 0) / holdings.length
    const avgTopCP = availableTopStocks.slice(0, 10).reduce((sum, s) => sum + s.total_cp, 0) / Math.min(10, availableTopStocks.length)

    // 评估
    if (avgHoldingCP < avgTopCP * 0.8) {
      suggestions.assessment = {
        level: 'low',
        message: '持仓整体战力偏低，建议进行优化',
        detail: `持仓平均战力${avgHoldingCP.toFixed(1)}，市场TOP10平均战力${avgTopCP.toFixed(1)}`
      }
    } else if (avgHoldingCP >= avgTopCP * 0.9) {
      suggestions.assessment = {
        level: 'high',
        message: '持仓战力良好，继续保持',
        detail: `持仓平均战力${avgHoldingCP.toFixed(1)}，接近市场TOP10水平`
      }
    } else {
      suggestions.assessment = {
        level: 'medium',
        message: '持仓有优化空间',
        detail: `持仓平均战力${avgHoldingCP.toFixed(1)}，可通过小幅调整提升`
      }
    }

    // 找出最弱的持仓股和最强的外来股（最多3个组合）
    if (holdingCPs.length > 0 && availableTopStocks.length > 0) {
      const maxSwaps = Math.min(3, holdingCPs.length, availableTopStocks.length)
      for (let i = 0; i < maxSwaps; i++) {
        const weakest = holdingCPs[i]
        const strongest = availableTopStocks[i]
        const cpDiff = strongest.total_cp - weakest.cp

        // 只显示战力差大于5的建议
        if (cpDiff > 5) {
          suggestions.swapOut.push({
            ...weakest,
            reason: `战力${weakest.cp.toFixed(1)}${weakest.cpData?.data_quality === 'low' ? '(数据低)' : ''}，可替换为战力${strongest.total_cp.toFixed(1)}的${strongest.name}${strongest.data_quality === 'high' ? '(数据高)' : ''}`
          })
          suggestions.swapIn.push({
            ...strongest,
            reason: `战力${strongest.total_cp.toFixed(1)}，高于被替换${cpDiff.toFixed(1)}点${strongest.data_quality === 'high' ? '，数据质量高' : ''}`
          })
        }
      }
    }

    return suggestions
  }

  const rebalanceSuggestions = getRebalanceSuggestions()

  const loadStockData = async () => {
    if (holdings.length === 0) return

    setLoading(true)
    setError(null)
    try {
      // 批量获取所有持仓股票
      const codes = holdings.map(h => h.code)
      const res = await fetch('/api/stocks/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(codes)
      })
      if (!res.ok) {
        throw new Error('请求失败')
      }
      const json = await res.json()
      if (json.error) {
        setError(json.error)
        setStockData({})
      } else {
        const newData = {}
        for (const stock of json.data || []) {
          newData[stock.code] = stock
        }
        setStockData(newData)
      }
    } catch (e) {
      console.error('Failed to load stock data:', e)
      setError(e.message || '数据加载失败，请检查网络连接')
    }
    setLoading(false)
  }

  // 加载市场TOP股票用于推荐
  const loadTopStocks = async () => {
    try {
      const res = await fetch('/api/cp/top?limit=50')
      if (!res.ok) {
        throw new Error('请求失败')
      }
      const json = await res.json()
      if (json.error) {
        setTopStocks([])
      } else {
        setTopStocks(json.data || [])
      }
    } catch (e) {
      console.error('Failed to load top stocks:', e)
    }
  }

  // 计算个人总战力
  const calculatePersonalCP = () => {
    let totalCP = 0
    holdings.forEach(h => {
      if (stockData[h.code]) {
        totalCP += stockData[h.code].total_cp * h.quantity
      }
    })
    return totalCP
  }

  // 计算持仓战力贡献
  const getHoldingCP = (holding) => {
    if (!stockData[holding.code]) return 0
    return stockData[holding.code].total_cp * holding.quantity
  }

  // 获取战力标签颜色
  const getCPColor = (cp) => {
    if (cp >= 70) return 'cp-high'
    if (cp >= 50) return 'cp-mid'
    return 'cp-low'
  }

  // 添加持仓
  const handleAdd = async () => {
    if (!formData.code || formData.quantity <= 0) return

    // 自动获取股票名称
    let name = formData.name
    if (!name) {
      try {
        const res = await fetch(`/api/stock/${formData.code}`)
        if (res.ok) {
          const data = await res.json()
          name = data.name
        }
      } catch (e) {
        console.error('Failed to fetch stock name:', e)
      }
    }

    add({
      code: formData.code.toUpperCase(),
      name: name || formData.code,
      quantity: Number(formData.quantity),
      costPrice: Number(formData.costPrice)
    })

    setFormData({ code: '', name: '', quantity: 0, costPrice: 0 })
    setShowAddForm(false)
    refresh()
  }

  // 删除持仓
  const handleDelete = (code) => {
    if (confirm('确定要删除这只股票吗？')) {
      remove(code)
      refresh()
    }
  }

  // 计算战力变化（简化版：用今日涨跌幅估算）
  const getEstimatedChange = () => {
    let totalChange = 0
    holdings.forEach(h => {
      if (stockData[h.code]) {
        const changePct = stockData[h.code].change_pct / 100
        const cpValue = stockData[h.code].total_cp * h.quantity
        totalChange += cpValue * changePct
      }
    })
    return totalChange
  }

  // 添加战力预警
  const handleAddAlert = () => {
    if (!alertConfig.code || alertConfig.threshold <= 0) return
    const newAlert = {
      id: Date.now(),
      code: alertConfig.code.toUpperCase(),
      threshold: Number(alertConfig.threshold),
      type: alertConfig.type,
      triggered: false
    }
    setAlerts([...alerts, newAlert])
    setAlertConfig({ code: '', threshold: 50, type: 'cp_drop' })
    setShowAlertForm(false)
  }

  // 删除预警
  const handleRemoveAlert = (id) => {
    setAlerts(alerts.filter(a => a.id !== id))
  }

  // 检查预警是否触发
  const checkAlerts = () => {
    const triggered = []
    alerts.forEach(alert => {
      const stock = stockData[alert.code]
      if (!stock) return

      let isTriggered = false
      if (alert.type === 'cp_drop' && stock.total_cp < alert.threshold) isTriggered = true
      if (alert.type === 'cp_rise' && stock.total_cp > alert.threshold) isTriggered = true
      if (alert.type === 'price_drop' && stock.price < alert.threshold) isTriggered = true
      if (alert.type === 'price_rise' && stock.price > alert.threshold) isTriggered = true

      if (isTriggered) {
        triggered.push({ ...alert, stock })
      }
    })
    return triggered
  }

  const totalCP = calculatePersonalCP()
  const estimatedChange = getEstimatedChange()

  // 计算预估变化率
  const getChangeRate = () => {
    if (holdings.length === 0 || totalCP === 0) return 0
    let totalYesterdayCP = 0
    holdings.forEach(h => {
      if (stockData[h.code]) {
        const changePct = stockData[h.code].change_pct
        const yesterdayCP = stockData[h.code].total_cp * h.quantity / (1 + changePct / 100)
        totalYesterdayCP += yesterdayCP
      }
    })
    if (totalYesterdayCP === 0) return 0
    return (totalCP - totalYesterdayCP) / totalYesterdayCP * 100
  }

  const changeRate = getChangeRate()

  return (
    <div className="space-y-6">
      {/* 错误提示 */}
      {error && (
        <div className="bg-cp-low/10 border border-cp-low/30 rounded-xl p-4 flex items-center justify-between">
          <p className="text-cp-low">{error}</p>
          <button
            onClick={() => { setError(null); loadStockData() }}
            className="px-3 py-1 bg-cp-low/20 hover:bg-cp-low/30 text-cp-low rounded-lg transition-colors text-sm"
          >
            重试
          </button>
        </div>
      )}

      {/* 战力概览 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 总战力 */}
        <div className="bg-card-bg rounded-xl border border-border-dark p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg bg-cp-high/20 flex items-center justify-center">
              <Zap className="w-6 h-6 text-cp-high" />
            </div>
            <div>
              <p className="text-gray-400 text-sm">个人总战力</p>
              <p className="text-3xl font-bold text-white">{totalCP.toFixed(0)}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {estimatedChange >= 0 ? (
              <TrendingUp className="w-4 h-4 text-red-500" />
            ) : (
              <TrendingDown className="w-4 h-4 text-green-500" />
            )}
            <span className={`text-sm ${estimatedChange >= 0 ? 'text-red-500' : 'text-green-500'}`}>
              {estimatedChange >= 0 ? '+' : ''}{estimatedChange.toFixed(0)} CP
              ({changeRate >= 0 ? '+' : ''}{changeRate.toFixed(2)}%)
            </span>
            {loading && (
              <span className="text-xs text-gray-500">(更新中...)</span>
            )}
          </div>
        </div>

        {/* 持仓数量 */}
        <div className="bg-card-bg rounded-xl border border-border-dark p-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-lg bg-accent-blue/20 flex items-center justify-center">
              <span className="text-xl font-bold text-accent-blue">{holdings.length}</span>
            </div>
            <div className="flex-1">
              <p className="text-gray-400 text-sm">持仓股票</p>
              <p className="text-lg font-bold text-white">只</p>
            </div>
            <button
              onClick={() => { loadStockData(); loadTopStocks() }}
              disabled={loading}
              className="p-2 text-gray-400 hover:text-accent-blue disabled:opacity-50 transition-colors"
              title="刷新数据"
            >
              <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* 操作按钮 */}
        <div className="bg-card-bg rounded-xl border border-border-dark p-6">
          <button
            onClick={() => setShowAddForm(true)}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-cp-high/20 text-cp-high rounded-lg hover:bg-cp-high/30 transition-colors"
          >
            <Plus className="w-5 h-5" />
            添加持仓
          </button>
          {holdings.length > 0 && (
            <button
              onClick={() => {
                if (confirm('确定要清空所有持仓吗？')) {
                  clear()
                  refresh()
                }
              }}
              className="w-full mt-2 flex items-center justify-center gap-2 px-4 py-2 text-gray-400 hover:text-cp-low transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              清空持仓
            </button>
          )}
        </div>
      </div>

      {/* 调仓建议 */}
      {holdings.length > 0 && topStocks.length > 0 && rebalanceSuggestions.assessment && (
        <div className="bg-card-bg rounded-xl border border-border-dark p-4">
          <div className="flex items-center gap-2 mb-4">
            <ArrowRightLeft className="w-5 h-5 text-accent-blue" />
            <h3 className="font-bold text-white">智能调仓建议</h3>
            <span className={`px-2 py-0.5 rounded text-xs ${
              rebalanceSuggestions.assessment.level === 'high' ? 'bg-green-500/20 text-green-500' :
              rebalanceSuggestions.assessment.level === 'medium' ? 'bg-yellow-500/20 text-yellow-500' :
              'bg-red-500/20 text-red-500'
            }`}>
              {rebalanceSuggestions.assessment.level === 'high' ? '良好' :
               rebalanceSuggestions.assessment.level === 'medium' ? '一般' : '需优化'}
            </span>
          </div>

          <p className="text-sm text-gray-300 mb-4">
            {rebalanceSuggestions.assessment.message}
            <span className="text-gray-500 ml-2">{rebalanceSuggestions.assessment.detail}</span>
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 建议替换组合 */}
            {rebalanceSuggestions.swapOut.length > 0 && (
              <div className="bg-deep-night rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingDown className="w-4 h-4 text-red-500" />
                  <span className="text-sm font-medium text-white">建议替换方案</span>
                </div>
                <div className="space-y-3">
                  {rebalanceSuggestions.swapOut.map((swapOut, idx) => {
                    const swapIn = rebalanceSuggestions.swapIn[idx]
                    const cpDiff = swapIn ? (swapIn.total_cp - swapOut.cp).toFixed(1) : 0
                    return (
                      <div key={idx} className="flex items-center justify-between p-2 bg-card-bg rounded-lg">
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <div className="text-red-400 text-xs">卖出</div>
                          <div className="min-w-0">
                            <p className="text-white text-sm font-medium truncate">{swapOut.name || swapOut.code}</p>
                            <div className="flex items-center gap-1">
                              <span className="text-xs text-gray-500">CP {swapOut.cp.toFixed(1)}</span>
                              {swapOut.cpData?.data_quality && (
                                <span className={`w-1.5 h-1.5 rounded-full ${
                                  swapOut.cpData.data_quality === 'high' ? 'bg-green-400' :
                                  swapOut.cpData.data_quality === 'medium' ? 'bg-yellow-400' : 'bg-gray-500'
                                }`} />
                              )}
                            </div>
                          </div>
                        </div>
                        <ArrowRightLeft className="w-4 h-4 text-gray-500 mx-2 flex-shrink-0" />
                        <div className="flex items-center gap-2 flex-1 min-w-0">
                          <div className="text-green-400 text-xs">买入</div>
                          <div className="min-w-0">
                            <p className="text-green-400 text-sm font-medium truncate">{swapIn?.name}</p>
                            <div className="flex items-center gap-1">
                              <span className="text-xs text-gray-500">CP {swapIn?.total_cp.toFixed(1)}</span>
                              {swapIn?.data_quality && (
                                <span className={`w-1.5 h-1.5 rounded-full ${
                                  swapIn.data_quality === 'high' ? 'bg-green-400' :
                                  swapIn.data_quality === 'medium' ? 'bg-yellow-400' : 'bg-gray-500'
                                }`} />
                              )}
                            </div>
                          </div>
                        </div>
                        <span className="text-xs text-green-500 ml-2">+{cpDiff}</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* 市场机会 */}
            <div className="bg-deep-night rounded-lg p-4">
              <div className="flex items-center gap-2 mb-3">
                <Activity className="w-4 h-4 text-accent-blue" />
                <span className="text-sm font-medium text-white">市场高战力股票</span>
              </div>
              <div className="space-y-2">
                {topStocks.slice(0, 5).filter(s => !holdings.find(h => h.code === s.code)).map(stock => (
                  <div key={stock.code} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`cp-tag ${stock.total_cp >= 70 ? 'cp-high' : stock.total_cp >= 50 ? 'cp-mid' : 'cp-low'}`}>
                        {stock.total_cp.toFixed(1)}
                      </span>
                      <span className="text-white text-sm">{stock.name}</span>
                    </div>
                    <button
                      onClick={() => {
                        setFormData({ code: stock.code, name: stock.name, quantity: 100, costPrice: 0 })
                        setShowAddForm(true)
                      }}
                      className="text-xs text-accent-blue hover:text-white"
                    >
                      + 添加
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 添加持仓表单 */}
      {showAddForm && (
        <div className="bg-card-bg rounded-xl border border-border-dark p-6">
          <h3 className="text-lg font-bold mb-4">添加持仓</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">股票代码</label>
              <input
                type="text"
                value={formData.code}
                onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                placeholder="600519"
                className="w-full px-3 py-2 bg-deep-night border border-border-dark rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">股票名称</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="自动获取"
                className="w-full px-3 py-2 bg-deep-night border border-border-dark rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">持股数量</label>
              <input
                type="number"
                min="0"
                value={formData.quantity}
                onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
                placeholder="100"
                className="w-full px-3 py-2 bg-deep-night border border-border-dark rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">成本价</label>
              <input
                type="number"
                min="0"
                step="0.01"
                value={formData.costPrice}
                onChange={(e) => setFormData({ ...formData, costPrice: e.target.value })}
                placeholder="0.00"
                className="w-full px-3 py-2 bg-deep-night border border-border-dark rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
              />
            </div>
          </div>
          <div className="flex gap-3 mt-4">
            <button
              onClick={handleAdd}
              className="flex items-center gap-2 px-4 py-2 bg-cp-high text-deep-night rounded-lg hover:bg-cp-high/80"
            >
              <Save className="w-4 h-4" />
              保存
            </button>
            <button
              onClick={() => {
                setShowAddForm(false)
                setFormData({ code: '', name: '', quantity: 0, costPrice: 0 })
              }}
              className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white"
            >
              <X className="w-4 h-4" />
              取消
            </button>
          </div>
        </div>
      )}

      {/* 战力预警设置 */}
      {holdings.length > 0 && (
        <div className="bg-card-bg rounded-xl border border-border-dark p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Bell className="w-5 h-5 text-accent-blue" />
              <h3 className="font-bold text-white">战力预警</h3>
              {alerts.length > 0 && (
                <span className="px-2 py-0.5 bg-accent-blue/20 text-accent-blue text-xs rounded-full">
                  {alerts.length}个预警
                </span>
              )}
            </div>
            <button
              onClick={() => setShowAlertForm(!showAlertForm)}
              className="text-sm text-accent-blue hover:text-accent-blue/80"
            >
              {showAlertForm ? '取消' : '+ 添加预警'}
            </button>
          </div>

          {showAlertForm && (
            <div className="grid grid-cols-3 gap-4 mb-4 p-4 bg-deep-night rounded-lg">
              <div>
                <label className="block text-sm text-gray-400 mb-1">股票代码</label>
                <input
                  type="text"
                  value={alertConfig.code}
                  onChange={(e) => setAlertConfig({ ...alertConfig, code: e.target.value })}
                  placeholder="600519"
                  className="w-full px-3 py-2 bg-card-bg border border-border-dark rounded-lg text-white text-sm focus:outline-none focus:border-accent-blue"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">预警类型</label>
                <select
                  value={alertConfig.type}
                  onChange={(e) => setAlertConfig({ ...alertConfig, type: e.target.value })}
                  className="w-full px-3 py-2 bg-card-bg border border-border-dark rounded-lg text-white text-sm focus:outline-none focus:border-accent-blue"
                >
                  <option value="cp_drop">战力跌破</option>
                  <option value="cp_rise">战力突破</option>
                  <option value="price_drop">价格跌破</option>
                  <option value="price_rise">价格突破</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">阈值</label>
                <input
                  type="number"
                  min="0"
                  value={alertConfig.threshold}
                  onChange={(e) => setAlertConfig({ ...alertConfig, threshold: e.target.value })}
                  placeholder="50"
                  className="w-full px-3 py-2 bg-card-bg border border-border-dark rounded-lg text-white text-sm focus:outline-none focus:border-accent-blue"
                />
              </div>
              <div className="col-span-3">
                <button
                  onClick={handleAddAlert}
                  className="px-4 py-2 bg-accent-blue text-white rounded-lg hover:bg-accent-blue/80 text-sm"
                >
                  确认添加
                </button>
              </div>
            </div>
          )}

          {alerts.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {alerts.map(alert => {
                const stock = stockData[alert.code]
                const isTriggered = stock && (
                  (alert.type === 'cp_drop' && stock.total_cp < alert.threshold) ||
                  (alert.type === 'cp_rise' && stock.total_cp > alert.threshold) ||
                  (alert.type === 'price_drop' && stock.price < alert.threshold) ||
                  (alert.type === 'price_rise' && stock.price > alert.threshold)
                )
                return (
                  <div
                    key={alert.id}
                    className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
                      isTriggered ? 'bg-red-500/20 text-red-500 border border-red-500/50' : 'bg-deep-night text-gray-300'
                    }`}
                  >
                    <span>{stock?.name || alert.code}</span>
                    <span className="text-xs opacity-70">
                      {alert.type === 'cp_drop' || alert.type === 'cp_rise' ? 'CP' : '¥'}{alert.threshold}
                    </span>
                    <button
                      onClick={() => handleRemoveAlert(alert.id)}
                      className="hover:text-white"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* 持仓列表 */}
      {holdings.length === 0 ? (
        <div className="bg-card-bg rounded-xl border border-border-dark p-12 text-center">
          {showInitPrompt ? (
            <>
              <Sparkles className="w-16 h-16 text-cp-high mx-auto mb-4" />
              <p className="text-lg text-white mb-2">欢迎使用股市贪吃蛇</p>
              <p className="text-gray-400 mb-6">点击下方按钮加载示例持仓，开始体验战力分析</p>
              <button
                onClick={loadDefaultHoldings}
                className="flex items-center gap-2 px-6 py-3 bg-cp-high text-deep-night rounded-lg hover:bg-cp-high/80 mx-auto transition-colors"
              >
                <Sparkles className="w-5 h-5" />
                加载示例持仓
              </button>
              <p className="text-xs text-gray-500 mt-4">示例持仓：贵州茅台、宁德时代、招商银行等5只蓝筹股</p>
            </>
          ) : (
            <>
              <AlertTriangle className="w-16 h-16 text-gray-600 mx-auto mb-4" />
              <p className="text-gray-400 mb-2">暂无持仓</p>
              <p className="text-sm text-gray-500">点击上方"添加持仓"按钮开始记录</p>
            </>
          )}
        </div>
      ) : (
        <div className="bg-card-bg rounded-xl border border-border-dark overflow-hidden">
          {loading && holdings.length > 0 && Object.keys(stockData).length === 0 && (
            <div className="p-4 text-center text-gray-400 text-sm">
              <div className="w-4 h-4 border-2 border-accent-blue/30 border-t-accent-blue rounded-full animate-spin inline-block mr-2"></div>
              正在加载持仓数据...
            </div>
          )}
          <table className="w-full">
            <thead>
              <tr className="border-b border-border-dark text-left text-sm text-gray-400">
                <th className="px-4 py-3">股票</th>
                <th className="px-4 py-3 text-right">持股数</th>
                <th className="px-4 py-3 text-right">成本价</th>
                <th className="px-4 py-3 text-right">现价</th>
                <th className="px-4 py-3 text-right">战力值</th>
                <th className="px-4 py-3 text-right">战力贡献</th>
                <th className="px-4 py-3 text-right">涨跌幅</th>
                <th className="px-4 py-3 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((holding) => {
                const data = stockData[holding.code]
                return (
                  <tr
                    key={holding.code}
                    className="border-b border-border-dark/50 hover:bg-white/5 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-bold text-white">{holding.name || holding.code}</p>
                        <p className="text-xs text-gray-500">{holding.code}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-white">
                      {holding.quantity}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-gray-300">
                      {holding.costPrice > 0 ? `¥${holding.costPrice.toFixed(2)}` : '-'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-white">
                      {data ? `¥${data.price.toFixed(2)}` : '-'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {data ? (
                        <div className="flex items-center justify-end gap-2">
                          <span className={`cp-tag ${getCPColor(data.total_cp)}`}>
                            {data.total_cp.toFixed(1)}
                          </span>
                          {data.data_quality && (
                            <span className={`w-2 h-2 rounded-full ${
                              data.data_quality === 'high' ? 'bg-green-400' :
                              data.data_quality === 'medium' ? 'bg-yellow-400' : 'bg-gray-500'
                            }`} title={`数据质量: ${data.data_quality === 'high' ? '高' : data.data_quality === 'medium' ? '中' : '低'}`} />
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-cp-high">
                      {data ? getHoldingCP(holding).toFixed(0) : '-'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {data ? (
                        <span className={`font-mono text-sm ${data.change_pct >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                          {data.change_pct >= 0 ? '+' : ''}{data.change_pct.toFixed(2)}%
                        </span>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleDelete(holding.code)}
                        className="p-2 text-gray-400 hover:text-cp-low transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 战力说明 */}
      <div className="bg-card-bg rounded-xl border border-border-dark p-6">
        <h4 className="font-bold mb-3">战力说明</h4>
        <ul className="text-sm text-gray-400 space-y-2">
          <li>• <span className="text-cp-high">战力贡献</span> = 持股数量 × 股票战力值</li>
          <li>• <span className="text-cp-high">个人总战力</span> = 所有持仓的战力贡献之和</li>
          <li>• 战力变化为估算值，仅供参考</li>
          <li>• 数据每日更新，战力值基于成长、价值、趋势三因子计算</li>
        </ul>
      </div>
    </div>
  )
}

export default PersonalCP
