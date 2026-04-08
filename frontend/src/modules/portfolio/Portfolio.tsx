import { useState } from 'react'
import { useAccount, usePortfolio, useBuyTrade, useSellTrade } from '../../shared/hooks/useApi'
import { Button, Input } from '../../shared/components/atoms'

export function Portfolio() {
  const { data: account, isLoading: accountLoading } = useAccount()
  const { data: portfolio, isLoading: portfolioLoading } = usePortfolio()
  const { mutate: buy, isPending: buying } = useBuyTrade()
  const { mutate: sell, isPending: selling } = useSellTrade()
  const [tradeCode, setTradeCode] = useState('')
  const [tradeQty, setTradeQty] = useState('')

  const handleBuy = () => {
    if (!tradeCode || !tradeQty) return
    buy({ code: tradeCode, quantity: parseInt(tradeQty) * 100 })
    setTradeCode('')
    setTradeQty('')
  }

  const handleSell = () => {
    if (!tradeCode || !tradeQty) return
    sell({ code: tradeCode, quantity: parseInt(tradeQty) * 100 })
    setTradeCode('')
    setTradeQty('')
  }

  if (accountLoading) {
    return <div className="text-center py-12 text-gray-500">加载中...</div>
  }

  return (
    <div className="space-y-6">
      {/* 账户概览 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">账户概览</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <InfoCard label="总资产" value={account?.total_assets?.toFixed(2) || '0'} unit="元" />
          <InfoCard label="可用资金" value={account?.cash?.toFixed(2) || '0'} unit="元" />
          <InfoCard label="持仓市值" value={account?.total_market_value?.toFixed(2) || '0'} unit="元" />
          <InfoCard
            label="总盈亏"
            value={account?.total_profit?.toFixed(2) || '0'}
            unit="元"
            color={account?.total_profit >= 0 ? 'text-red-500' : 'text-green-500'}
          />
        </div>
        <div className="mt-4">
          <InfoCard
            label="盈亏比例"
            value={account?.profit_rate ? `${account.profit_rate.toFixed(2)}%` : '0%'}
            color={account?.profit_rate >= 0 ? 'text-red-500' : 'text-green-500'}
          />
        </div>
      </div>

      {/* 快速交易 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">快速交易</h2>
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm text-gray-500 mb-1">股票代码</label>
            <Input
              value={tradeCode}
              onChange={(e) => setTradeCode(e.target.value)}
              placeholder="如: 000001"
            />
          </div>
          <div className="w-32">
            <label className="block text-sm text-gray-500 mb-1">数量(手)</label>
            <Input
              type="number"
              value={tradeQty}
              onChange={(e) => setTradeQty(e.target.value)}
              placeholder="1"
              min="1"
            />
          </div>
          <Button onClick={handleBuy} disabled={buying} variant="primary">
            买入
          </Button>
          <Button onClick={handleSell} disabled={selling} variant="danger">
            卖出
          </Button>
        </div>
      </div>

      {/* 持仓明细 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">持仓明细</h2>
        {portfolio?.holdings && portfolio.holdings.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-gray-500 border-b">
                  <th className="pb-2">股票</th>
                  <th className="pb-2 text-right">持仓数量</th>
                  <th className="pb-2 text-right">成本价</th>
                  <th className="pb-2 text-right">现价</th>
                  <th className="pb-2 text-right">市值</th>
                  <th className="pb-2 text-right">盈亏</th>
                  <th className="pb-2 text-right">盈亏比例</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.holdings.map((h) => (
                  <tr key={h.code} className="border-b border-gray-100 dark:border-gray-700">
                    <td className="py-3">
                      <div className="font-medium">{h.name}</div>
                      <div className="text-xs text-gray-400">{h.code}</div>
                    </td>
                    <td className="text-right font-mono">{h.quantity}</td>
                    <td className="text-right font-mono">{h.cost_price.toFixed(2)}</td>
                    <td className="text-right font-mono">{h.current_price.toFixed(2)}</td>
                    <td className="text-right font-mono">{h.market_value.toFixed(2)}</td>
                    <td className={`text-right font-mono ${h.profit >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                      {h.profit >= 0 ? '+' : ''}{h.profit.toFixed(2)}
                    </td>
                    <td className={`text-right font-mono ${h.profit_rate >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                      {h.profit_rate >= 0 ? '+' : ''}{h.profit_rate.toFixed(2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            暂无持仓
          </div>
        )}
      </div>
    </div>
  )
}

function InfoCard({
  label,
  value,
  unit,
  color = 'text-gray-900 dark:text-white',
}: {
  label: string
  value: string
  unit?: string
  color?: string
}) {
  return (
    <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-xl font-bold font-mono ${color}`}>
        {value}
        {unit && <span className="text-sm font-normal">{unit}</span>}
      </div>
    </div>
  )
}