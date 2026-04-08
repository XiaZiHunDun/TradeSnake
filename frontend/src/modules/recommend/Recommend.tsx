import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useRecommendations, useSwapSuggestions } from '../../shared/hooks/useApi'
import { Button } from '../../shared/components/atoms'
import type { SwapSuggestion } from '../../shared/types'

const CATEGORIES = [
  { key: 'value', label: '价值型', desc: '低估值的价值股票' },
  { key: 'growth', label: '成长型', desc: '高增长的成长股票' },
  { key: 'momentum', label: '趋势型', desc: '动量强劲的趋势股票' },
  { key: 'quality', label: '质量型', desc: '高ROE的质量股票' },
]

export function Recommend() {
  const navigate = useNavigate()
  const [category, setCategory] = useState('value')
  const { data: recommendations, isLoading: recLoading } = useRecommendations(category)
  const { data: swapSuggestions, isLoading: swapLoading } = useSwapSuggestions()

  return (
    <div className="space-y-6">
      {/* 分类选择 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">推荐分类</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              onClick={() => setCategory(cat.key)}
              className={`p-4 rounded-lg border transition-colors ${
                category === cat.key
                  ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
              }`}
            >
              <div className={`font-semibold ${category === cat.key ? 'text-blue-600' : 'text-gray-900 dark:text-white'}`}>
                {cat.label}
              </div>
              <div className="text-xs text-gray-500 mt-1">{cat.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {/* 推荐结果 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {CATEGORIES.find(c => c.key === category)?.label}推荐
        </h2>
        {recLoading ? (
          <div className="text-center py-8 text-gray-500">加载中...</div>
        ) : recommendations?.data && recommendations.data.length > 0 ? (
          <div className="space-y-3">
            {recommendations.data.slice(0, 20).map((stock) => (
              <div
                key={stock.code}
                className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
                onClick={() => navigate(`/stock/${stock.code}`)}
              >
                <div className="flex items-center gap-4">
                  <div>
                    <div className="font-medium text-gray-900 dark:text-white">{stock.name}</div>
                    <div className="text-xs text-gray-400">{stock.code}</div>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <div className="text-xs text-gray-500">战力</div>
                    <div className="font-mono font-bold text-blue-600">{stock.total_cp.toFixed(1)}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-500">现价</div>
                    <div className="font-mono text-gray-900 dark:text-white">{stock.price.toFixed(2)}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-500">涨跌幅</div>
                    <div className={`font-mono ${stock.change_pct >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                      {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">暂无推荐数据</div>
        )}
      </div>

      {/* 换股建议 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">换股建议</h2>
        {swapLoading ? (
          <div className="text-center py-8 text-gray-500">加载中...</div>
        ) : swapSuggestions && swapSuggestions.length > 0 ? (
          <div className="space-y-4">
            {swapSuggestions.map((suggestion: SwapSuggestion, index: number) => (
              <div
                key={index}
                className="border border-gray-200 dark:border-gray-700 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      suggestion.action_level === 'strong_buy' ? 'bg-green-100 text-green-700' :
                      suggestion.action_level === 'buy' ? 'bg-blue-100 text-blue-700' :
                      suggestion.action_level === 'hold' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {suggestion.action_label}
                    </span>
                    <span className="text-sm text-gray-500">
                      战力提升: {suggestion.cp_improvement > 0 ? '+' : ''}{suggestion.cp_improvement.toFixed(1)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex-1 text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
                    <div className="text-xs text-gray-500">换出</div>
                    <div className="font-medium">{suggestion.from_name}</div>
                    <div className="text-xs text-gray-400">{suggestion.from_code}</div>
                    <div className="font-mono text-red-600 mt-1">战力 {suggestion.from_cp.toFixed(1)}</div>
                  </div>
                  <div className="text-2xl text-gray-400">→</div>
                  <div className="flex-1 text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                    <div className="text-xs text-gray-500">换入</div>
                    <div className="font-medium">{suggestion.to_name}</div>
                    <div className="text-xs text-gray-400">{suggestion.to_code}</div>
                    <div className="font-mono text-green-600 mt-1">战力 {suggestion.to_cp.toFixed(1)}</div>
                  </div>
                </div>
                <div className="mt-3 flex justify-between text-sm text-gray-500">
                  <span>交易成本: {suggestion.trade_cost.toFixed(2)}元</span>
                  <span>等效持仓: {suggestion.holding_days_equivalent}天</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">暂无换股建议 (请先添加持仓)</div>
        )}
      </div>
    </div>
  )
}