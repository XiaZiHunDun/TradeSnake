import { useState, useMemo } from 'react'
import { Filter, X, SlidersHorizontal, RotateCcw } from 'lucide-react'

const SCREENER_CRITERIA = {
  // 战力相关
  totalCP: { label: '战力值', min: 0, max: 100, step: 1, default: [0, 100] },
  growthScore: { label: '成长分', min: 0, max: 100, step: 1, default: [0, 100] },
  valueScore: { label: '价值分', min: 0, max: 100, step: 1, default: [0, 100] },
  qualityScore: { label: '质量分', min: 0, max: 100, step: 1, default: [0, 100] },
  momentumScore: { label: '趋势分', min: 0, max: 100, step: 1, default: [0, 100] },

  // 财务指标
  pe: { label: '市盈率(PE)', min: -100, max: 500, step: 1, default: [0, 500] },
  roe: { label: 'ROE(%)', min: -50, max: 100, step: 0.5, default: [-50, 100] },
  netProfitGrowth: { label: '净利润增速(%)', min: -100, max: 500, step: 1, default: [-100, 500] },
  revenueGrowth: { label: '营收增速(%)', min: -100, max: 500, step: 1, default: [-100, 500] },

  // 市场指标
  changePct: { label: '涨跌幅(%)', min: -20, max: 20, step: 0.5, default: [-20, 20] },
  price: { label: '现价(元)', min: 0, max: 1000, step: 0.1, default: [0, 1000] }
}

function StockScreener({ data, onFilter }) {
  const [isOpen, setIsOpen] = useState(false)
  const [criteria, setCriteria] = useState(() => {
    // 初始化为默认值
    const init = {}
    Object.keys(SCREENER_CRITERIA).forEach(key => {
      init[key] = [...SCREENER_CRITERIA[key].default]
    })
    return init
  })
  const [dataQualityFilter, setDataQualityFilter] = useState(['high', 'medium', 'low'])
  const [priceRange, setPriceRange] = useState([0, 1000]) // 特殊处理

  // 当前激活的筛选条件
  const activeFilterCount = useMemo(() => {
    let count = 0
    Object.keys(SCREENER_CRITERIA).forEach(key => {
      const [min, max] = SCREENER_CRITERIA[key].default
      if (criteria[key][0] !== min || criteria[key][1] !== max) {
        count++
      }
    })
    // 数据质量筛选
    if (dataQualityFilter.length < 3) count++
    return count
  }, [criteria, dataQualityFilter])

  const handleCriteriaChange = (key, index, value) => {
    const newCriteria = { ...criteria }
    newCriteria[key] = [...newCriteria[key]]
    newCriteria[key][index] = parseFloat(value) || 0
    setCriteria(newCriteria)
  }

  const resetFilters = () => {
    const reset = {}
    Object.keys(SCREENER_CRITERIA).forEach(key => {
      reset[key] = [...SCREENER_CRITERIA[key].default]
    })
    setCriteria(reset)
  }

  const applyFilters = () => {
    if (!onFilter || !data) {
      onFilter?.(data)
      return
    }

    const filtered = data.filter(stock => {
      // 战力值
      if (stock.total_cp < criteria.totalCP[0] || stock.total_cp > criteria.totalCP[1]) return false
      // 成长分
      if (stock.growth_score < criteria.growthScore[0] || stock.growth_score > criteria.growthScore[1]) return false
      // 价值分
      if (stock.value_score < criteria.valueScore[0] || stock.value_score > criteria.valueScore[1]) return false
      // 质量分
      if ((stock.quality_score || 0) < criteria.qualityScore[0] || (stock.quality_score || 0) > criteria.qualityScore[1]) return false
      // 趋势分
      if (stock.momentum_score < criteria.momentumScore[0] || stock.momentum_score > criteria.momentumScore[1]) return false
      // PE
      if (stock.pe > 0 && (stock.pe < criteria.pe[0] || stock.pe > criteria.pe[1])) return false
      // ROE
      if (stock.roe < criteria.roe[0] || stock.roe > criteria.roe[1]) return false
      // 净利润增速
      if (stock.net_profit_growth < criteria.netProfitGrowth[0] || stock.net_profit_growth > criteria.netProfitGrowth[1]) return false
      // 营收增速
      if (stock.revenue_growth < criteria.revenueGrowth[0] || stock.revenue_growth > criteria.revenueGrowth[1]) return false
      // 涨跌幅
      if (stock.change_pct < criteria.changePct[0] || stock.change_pct > criteria.changePct[1]) return false
      // 价格
      if (stock.price < criteria.price[0] || stock.price > criteria.price[1]) return false
      // 数据质量
      const stockDQ = stock.data_quality || 'low'
      if (!dataQualityFilter.includes(stockDQ)) return false

      return true
    })

    onFilter?.(filtered)
    setIsOpen(false)
  }

  const getCurrentData = () => {
    if (!data) return []
    return data.filter(stock => {
      if (stock.total_cp < criteria.totalCP[0] || stock.total_cp > criteria.totalCP[1]) return false
      if (stock.growth_score < criteria.growthScore[0] || stock.growth_score > criteria.growthScore[1]) return false
      if (stock.value_score < criteria.valueScore[0] || stock.value_score > criteria.valueScore[1]) return false
      if ((stock.quality_score || 0) < criteria.qualityScore[0] || (stock.quality_score || 0) > criteria.qualityScore[1]) return false
      if (stock.momentum_score < criteria.momentumScore[0] || stock.momentum_score > criteria.momentumScore[1]) return false
      if (stock.pe > 0 && (stock.pe < criteria.pe[0] || stock.pe > criteria.pe[1])) return false
      if (stock.roe < criteria.roe[0] || stock.roe > criteria.roe[1]) return false
      if (stock.net_profit_growth < criteria.netProfitGrowth[0] || stock.net_profit_growth > criteria.netProfitGrowth[1]) return false
      if (stock.revenue_growth < criteria.revenueGrowth[0] || stock.revenue_growth > criteria.revenueGrowth[1]) return false
      if (stock.change_pct < criteria.changePct[0] || stock.change_pct > criteria.changePct[1]) return false
      if (stock.price < criteria.price[0] || stock.price > criteria.price[1]) return false
      const stockDQ = stock.data_quality || 'low'
      if (!dataQualityFilter.includes(stockDQ)) return false
      return true
    })
  }

  const previewCount = getCurrentData().length

  return (
    <>
      {/* 筛选器按钮 */}
      <button
        onClick={() => setIsOpen(true)}
        className={`flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors ${
          activeFilterCount > 0
            ? 'bg-accent-blue/20 text-accent-blue'
            : 'bg-card-bg text-gray-400 hover:text-white'
        }`}
      >
        <SlidersHorizontal className="w-4 h-4" />
        高级筛选
        {activeFilterCount > 0 && (
          <span className="ml-1 px-1.5 py-0.5 rounded bg-accent-blue text-white text-xs">
            {activeFilterCount}
          </span>
        )}
      </button>

      {/* 筛选弹窗 */}
      {isOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card-bg border border-border-dark rounded-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
            {/* 头部 */}
            <div className="px-4 py-3 border-b border-border-dark flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Filter className="w-5 h-5 text-accent-blue" />
                <h3 className="font-bold text-white">股票筛选器</h3>
                <span className="text-xs text-gray-400">
                  (当前条件可筛选 <span className="text-accent-blue font-bold">{previewCount}</span> 只股票)
                </span>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 筛选内容 */}
            <div className="flex-1 overflow-y-auto p-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 战力值 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">战力值</span>
                    <span className="text-xs text-gray-400">{criteria.totalCP[0]} - {criteria.totalCP[1]}</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.totalCP.min}
                      max={SCREENER_CRITERIA.totalCP.max}
                      step={SCREENER_CRITERIA.totalCP.step}
                      value={criteria.totalCP[0]}
                      onChange={(e) => handleCriteriaChange('totalCP', 0, e.target.value)}
                      className="flex-1 accent-accent-blue"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.totalCP.min}
                      max={SCREENER_CRITERIA.totalCP.max}
                      step={SCREENER_CRITERIA.totalCP.step}
                      value={criteria.totalCP[1]}
                      onChange={(e) => handleCriteriaChange('totalCP', 1, e.target.value)}
                      className="flex-1 accent-accent-blue"
                    />
                  </div>
                </div>

                {/* 成长分 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">成长分</span>
                    <span className="text-xs text-gray-400">{criteria.growthScore[0]} - {criteria.growthScore[1]}</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.growthScore.min}
                      max={SCREENER_CRITERIA.growthScore.max}
                      step={SCREENER_CRITERIA.growthScore.step}
                      value={criteria.growthScore[0]}
                      onChange={(e) => handleCriteriaChange('growthScore', 0, e.target.value)}
                      className="flex-1 accent-green-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.growthScore.min}
                      max={SCREENER_CRITERIA.growthScore.max}
                      step={SCREENER_CRITERIA.growthScore.step}
                      value={criteria.growthScore[1]}
                      onChange={(e) => handleCriteriaChange('growthScore', 1, e.target.value)}
                      className="flex-1 accent-green-500"
                    />
                  </div>
                </div>

                {/* 价值分 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">价值分</span>
                    <span className="text-xs text-gray-400">{criteria.valueScore[0]} - {criteria.valueScore[1]}</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.valueScore.min}
                      max={SCREENER_CRITERIA.valueScore.max}
                      step={SCREENER_CRITERIA.valueScore.step}
                      value={criteria.valueScore[0]}
                      onChange={(e) => handleCriteriaChange('valueScore', 0, e.target.value)}
                      className="flex-1 accent-yellow-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.valueScore.min}
                      max={SCREENER_CRITERIA.valueScore.max}
                      step={SCREENER_CRITERIA.valueScore.step}
                      value={criteria.valueScore[1]}
                      onChange={(e) => handleCriteriaChange('valueScore', 1, e.target.value)}
                      className="flex-1 accent-yellow-500"
                    />
                  </div>
                </div>

                {/* 质量分 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">质量分</span>
                    <span className="text-xs text-gray-400">{criteria.qualityScore[0]} - {criteria.qualityScore[1]}</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.qualityScore.min}
                      max={SCREENER_CRITERIA.qualityScore.max}
                      step={SCREENER_CRITERIA.qualityScore.step}
                      value={criteria.qualityScore[0]}
                      onChange={(e) => handleCriteriaChange('qualityScore', 0, e.target.value)}
                      className="flex-1 accent-purple-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.qualityScore.min}
                      max={SCREENER_CRITERIA.qualityScore.max}
                      step={SCREENER_CRITERIA.qualityScore.step}
                      value={criteria.qualityScore[1]}
                      onChange={(e) => handleCriteriaChange('qualityScore', 1, e.target.value)}
                      className="flex-1 accent-purple-500"
                    />
                  </div>
                </div>

                {/* 趋势分 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">趋势分</span>
                    <span className="text-xs text-gray-400">{criteria.momentumScore[0]} - {criteria.momentumScore[1]}</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.momentumScore.min}
                      max={SCREENER_CRITERIA.momentumScore.max}
                      step={SCREENER_CRITERIA.momentumScore.step}
                      value={criteria.momentumScore[0]}
                      onChange={(e) => handleCriteriaChange('momentumScore', 0, e.target.value)}
                      className="flex-1 accent-red-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.momentumScore.min}
                      max={SCREENER_CRITERIA.momentumScore.max}
                      step={SCREENER_CRITERIA.momentumScore.step}
                      value={criteria.momentumScore[1]}
                      onChange={(e) => handleCriteriaChange('momentumScore', 1, e.target.value)}
                      className="flex-1 accent-red-500"
                    />
                  </div>
                </div>

                {/* PE */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">市盈率(PE)</span>
                    <span className="text-xs text-gray-400">{criteria.pe[0]} - {criteria.pe[1]}</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.pe.min}
                      max={SCREENER_CRITERIA.pe.max}
                      step={SCREENER_CRITERIA.pe.step}
                      value={criteria.pe[0]}
                      onChange={(e) => handleCriteriaChange('pe', 0, e.target.value)}
                      className="flex-1 accent-purple-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.pe.min}
                      max={SCREENER_CRITERIA.pe.max}
                      step={SCREENER_CRITERIA.pe.step}
                      value={criteria.pe[1]}
                      onChange={(e) => handleCriteriaChange('pe', 1, e.target.value)}
                      className="flex-1 accent-purple-500"
                    />
                  </div>
                </div>

                {/* ROE */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">ROE(%)</span>
                    <span className="text-xs text-gray-400">{criteria.roe[0]}% - {criteria.roe[1]}%</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.roe.min}
                      max={SCREENER_CRITERIA.roe.max}
                      step={SCREENER_CRITERIA.roe.step}
                      value={criteria.roe[0]}
                      onChange={(e) => handleCriteriaChange('roe', 0, e.target.value)}
                      className="flex-1 accent-cyan-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.roe.min}
                      max={SCREENER_CRITERIA.roe.max}
                      step={SCREENER_CRITERIA.roe.step}
                      value={criteria.roe[1]}
                      onChange={(e) => handleCriteriaChange('roe', 1, e.target.value)}
                      className="flex-1 accent-cyan-500"
                    />
                  </div>
                </div>

                {/* 净利润增速 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">净利润增速(%)</span>
                    <span className="text-xs text-gray-400">{criteria.netProfitGrowth[0]}% - {criteria.netProfitGrowth[1]}%</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.netProfitGrowth.min}
                      max={SCREENER_CRITERIA.netProfitGrowth.max}
                      step={SCREENER_CRITERIA.netProfitGrowth.step}
                      value={criteria.netProfitGrowth[0]}
                      onChange={(e) => handleCriteriaChange('netProfitGrowth', 0, e.target.value)}
                      className="flex-1 accent-pink-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.netProfitGrowth.min}
                      max={SCREENER_CRITERIA.netProfitGrowth.max}
                      step={SCREENER_CRITERIA.netProfitGrowth.step}
                      value={criteria.netProfitGrowth[1]}
                      onChange={(e) => handleCriteriaChange('netProfitGrowth', 1, e.target.value)}
                      className="flex-1 accent-pink-500"
                    />
                  </div>
                </div>

                {/* 营收增速 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">营收增速(%)</span>
                    <span className="text-xs text-gray-400">{criteria.revenueGrowth[0]}% - {criteria.revenueGrowth[1]}%</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.revenueGrowth.min}
                      max={SCREENER_CRITERIA.revenueGrowth.max}
                      step={SCREENER_CRITERIA.revenueGrowth.step}
                      value={criteria.revenueGrowth[0]}
                      onChange={(e) => handleCriteriaChange('revenueGrowth', 0, e.target.value)}
                      className="flex-1 accent-orange-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.revenueGrowth.min}
                      max={SCREENER_CRITERIA.revenueGrowth.max}
                      step={SCREENER_CRITERIA.revenueGrowth.step}
                      value={criteria.revenueGrowth[1]}
                      onChange={(e) => handleCriteriaChange('revenueGrowth', 1, e.target.value)}
                      className="flex-1 accent-orange-500"
                    />
                  </div>
                </div>

                {/* 涨跌幅 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">涨跌幅(%)</span>
                    <span className="text-xs text-gray-400">{criteria.changePct[0]}% - {criteria.changePct[1]}%</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.changePct.min}
                      max={SCREENER_CRITERIA.changePct.max}
                      step={SCREENER_CRITERIA.changePct.step}
                      value={criteria.changePct[0]}
                      onChange={(e) => handleCriteriaChange('changePct', 0, e.target.value)}
                      className="flex-1 accent-indigo-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.changePct.min}
                      max={SCREENER_CRITERIA.changePct.max}
                      step={SCREENER_CRITERIA.changePct.step}
                      value={criteria.changePct[1]}
                      onChange={(e) => handleCriteriaChange('changePct', 1, e.target.value)}
                      className="flex-1 accent-indigo-500"
                    />
                  </div>
                </div>

                {/* 价格 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">现价(元)</span>
                    <span className="text-xs text-gray-400">¥{criteria.price[0]} - ¥{criteria.price[1]}</span>
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.price.min}
                      max={SCREENER_CRITERIA.price.max}
                      step={SCREENER_CRITERIA.price.step}
                      value={criteria.price[0]}
                      onChange={(e) => handleCriteriaChange('price', 0, e.target.value)}
                      className="flex-1 accent-teal-500"
                    />
                    <input
                      type="range"
                      min={SCREENER_CRITERIA.price.min}
                      max={SCREENER_CRITERIA.price.max}
                      step={SCREENER_CRITERIA.price.step}
                      value={criteria.price[1]}
                      onChange={(e) => handleCriteriaChange('price', 1, e.target.value)}
                      className="flex-1 accent-teal-500"
                    />
                  </div>
                </div>

                {/* 数据质量 */}
                <div className="bg-deep-night rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-white font-medium">数据质量</span>
                    <span className="text-xs text-gray-400">
                      {dataQualityFilter.length === 3 ? '全部' : dataQualityFilter.join(', ')}
                    </span>
                  </div>
                  <div className="flex gap-4">
                    {[
                      { key: 'high', label: '高', color: 'green' },
                      { key: 'medium', label: '中', color: 'yellow' },
                      { key: 'low', label: '低', color: 'gray' }
                    ].map(item => (
                      <label key={item.key} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={dataQualityFilter.includes(item.key)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setDataQualityFilter([...dataQualityFilter, item.key])
                            } else {
                              setDataQualityFilter(dataQualityFilter.filter(k => k !== item.key))
                            }
                          }}
                          className={`w-4 h-4 rounded border-gray-500 text-${item.color}-500 focus:ring-${item.color}-500`}
                        />
                        <span className={`text-sm text-${item.color}-400`}>{item.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            {/* 底部操作栏 */}
            <div className="px-4 py-3 border-t border-border-dark flex items-center justify-between">
              <button
                onClick={resetFilters}
                className="flex items-center gap-1 px-3 py-1.5 rounded text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                重置
              </button>
              <div className="flex gap-2">
                <button
                  onClick={() => setIsOpen(false)}
                  className="px-4 py-1.5 rounded text-sm text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
                >
                  取消
                </button>
                <button
                  onClick={applyFilters}
                  className="px-4 py-1.5 rounded text-sm bg-accent-blue text-white hover:bg-accent-blue/80 transition-colors"
                >
                  应用筛选 ({previewCount}只)
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default StockScreener
