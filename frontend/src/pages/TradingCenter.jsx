import { useState, useEffect } from 'react'
import { Wallet, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, Clock, X, Search, AlertCircle, RefreshCw } from 'lucide-react'
import { useAccount } from '../hooks/useAccount'

// 股票搜索组件
function StockSearch({ onSelect, excludeCodes = [] }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      return
    }

    const fetchResults = async () => {
      setLoading(true)
      try {
        const res = await fetch(`/api/cp/top?limit=50`)
        if (res.ok) {
          const json = await res.json()
          const q = query.toLowerCase()
          const filtered = json.data
            .filter(s => !excludeCodes.includes(s.code))
            .filter(s => s.code.toLowerCase().includes(q) || s.name.toLowerCase().includes(q))
            .slice(0, 10)
          setResults(filtered)
        }
      } catch (e) {
        console.error('Search failed:', e)
      }
      setLoading(false)
    }

    const debounce = setTimeout(fetchResults, 200)
    return () => clearTimeout(debounce)
  }, [query, excludeCodes])

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="搜索股票代码或名称..."
          className="w-full pl-10 pr-4 py-2 bg-deep-night border border-border-dark rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-accent-blue"
        />
      </div>
      {results.length > 0 && (
        <div className="absolute left-0 right-0 top-full mt-2 bg-card-bg border border-border-dark rounded-lg shadow-xl z-10 max-h-64 overflow-y-auto">
          {results.map(stock => (
            <button
              key={stock.code}
              onClick={() => { onSelect(stock); setQuery('') }}
              className="w-full px-4 py-2 flex items-center justify-between hover:bg-white/5 transition-colors"
            >
              <div className="text-left">
                <p className="text-white font-medium">{stock.name}</p>
                <p className="text-gray-500 text-sm">{stock.code}</p>
              </div>
              <div className="text-right">
                <p className="text-white">¥{stock.price.toFixed(3)}</p>
                <p className={`text-sm ${stock.change_pct >= 0 ? 'text-cp-high' : 'text-cp-low'}`}>
                  {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                </p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// 账户卡片组件
function AccountCard({ account }) {
  if (!account) {
    return (
      <div className="bg-card-bg rounded-xl border border-border-dark p-6">
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-700 rounded w-1/3"></div>
          <div className="h-8 bg-gray-700 rounded w-2/3"></div>
        </div>
      </div>
    )
  }

  const isProfit = account.total_profit >= 0

  return (
    <div className="bg-card-bg rounded-xl border border-border-dark p-6">
      <div className="flex items-center gap-2 mb-4">
        <Wallet className="w-5 h-5 text-accent-blue" />
        <h2 className="text-lg font-bold text-white">模拟账户</h2>
      </div>

      <div className="space-y-4">
        <div className="flex justify-between items-end">
          <div>
            <p className="text-gray-400 text-sm">可用资金</p>
            <p className="text-2xl font-bold text-white">¥{account.cash.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</p>
          </div>
          <div className="text-right">
            <p className="text-gray-400 text-sm">持仓市值</p>
            <p className="text-xl font-semibold text-white">¥{account.total_market_value.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</p>
          </div>
        </div>

        <div className="border-t border-border-dark pt-4">
          <div className="flex justify-between items-end">
            <div>
              <p className="text-gray-400 text-sm">总资产</p>
              <p className="text-3xl font-bold text-white">¥{account.total_assets.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</p>
            </div>
            <div className={`flex items-center gap-1 px-3 py-1.5 rounded-lg ${isProfit ? 'bg-cp-high/20' : 'bg-cp-low/20'}`}>
              {isProfit ? <TrendingUp className="w-4 h-4 text-cp-high" /> : <TrendingDown className="w-4 h-4 text-cp-low" />}
              <span className={`font-semibold ${isProfit ? 'text-cp-high' : 'text-cp-low'}`}>
                {isProfit ? '+' : ''}{account.total_profit.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>
          <div className="flex justify-between items-end mt-2">
            <p className="text-gray-500 text-sm">初始资金: ¥{account.initial_cash.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</p>
            <p className={`text-sm font-medium ${isProfit ? 'text-cp-high' : 'text-cp-low'}`}>
              {isProfit ? '+' : ''}{account.profit_rate.toFixed(2)}%
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

// 持仓列表组件
function HoldingsList({ portfolio, onBuy, onSell }) {
  if (!portfolio || !portfolio.holdings || portfolio.holdings.length === 0) {
    return (
      <div className="bg-card-bg rounded-xl border border-border-dark p-6">
        <h2 className="text-lg font-bold text-white mb-4">当前持仓</h2>
        <div className="text-center py-8 text-gray-500">
          <Wallet className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>暂无持仓</p>
          <p className="text-sm mt-1">开始买卖股票来管理你的投资组合</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card-bg rounded-xl border border-border-dark p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-white">当前持仓</h2>
        <div className="text-sm text-gray-400">
          {portfolio.holdings.length} 只股票
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-gray-400 text-sm border-b border-border-dark">
              <th className="text-left py-2 px-2">股票</th>
              <th className="text-right py-2 px-2">持股数</th>
              <th className="text-right py-2 px-2">成本价</th>
              <th className="text-right py-2 px-2">现价</th>
              <th className="text-right py-2 px-2">市值</th>
              <th className="text-right py-2 px-2">盈亏</th>
              <th className="text-right py-2 px-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {portfolio.holdings.map(holding => {
              const isProfit = holding.profit >= 0
              return (
                <tr key={holding.code} className="border-b border-border-dark/50 hover:bg-white/5">
                  <td className="py-3 px-2">
                    <div>
                      <p className="text-white font-medium">{holding.name}</p>
                      <p className="text-gray-500 text-xs">{holding.code}</p>
                    </div>
                  </td>
                  <td className="text-right text-white py-3 px-2">{holding.quantity}</td>
                  <td className="text-right text-gray-300 py-3 px-2">¥{holding.cost_price.toFixed(3)}</td>
                  <td className="text-right text-white py-3 px-2">¥{holding.current_price.toFixed(3)}</td>
                  <td className="text-right text-white py-3 px-2">¥{holding.market_value.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</td>
                  <td className={`text-right py-3 px-2 ${isProfit ? 'text-cp-high' : 'text-cp-low'}`}>
                    <div className="flex items-center justify-end gap-1">
                      {isProfit ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      <span className="font-medium">{isProfit ? '+' : ''}{holding.profit.toFixed(2)}</span>
                      <span className="text-xs">({isProfit ? '+' : ''}{holding.profit_rate.toFixed(1)}%)</span>
                    </div>
                  </td>
                  <td className="text-right py-3 px-2">
                    <button
                      onClick={() => onSell(holding)}
                      className="px-3 py-1 text-sm bg-cp-low/20 text-cp-low rounded hover:bg-cp-low/30 transition-colors"
                    >
                      卖出
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4 pt-4 border-t border-border-dark flex justify-between items-center">
        <div className="text-gray-400">
          持仓总市值: <span className="text-white font-medium">¥{portfolio.total_market_value.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</span>
        </div>
        <div className="text-gray-400">
          总盈亏: <span className={`font-medium ${portfolio.total_profit >= 0 ? 'text-cp-high' : 'text-cp-low'}`}>
            {portfolio.total_profit >= 0 ? '+' : ''}¥{portfolio.total_profit.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
          </span>
        </div>
      </div>
    </div>
  )
}

// 交易历史组件
function TradeHistory({ trades }) {
  if (!trades || trades.length === 0) {
    return (
      <div className="bg-card-bg rounded-xl border border-border-dark p-6">
        <h2 className="text-lg font-bold text-white mb-4">交易历史</h2>
        <div className="text-center py-8 text-gray-500">
          <Clock className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>暂无交易记录</p>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-card-bg rounded-xl border border-border-dark p-6">
      <h2 className="text-lg font-bold text-white mb-4">交易历史</h2>

      <div className="space-y-2 max-h-80 overflow-y-auto">
        {trades.map(trade => (
          <div key={trade.id} className="flex items-center justify-between p-3 bg-deep-night rounded-lg">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center ${trade.action === 'buy' ? 'bg-cp-high/20' : 'bg-cp-low/20'}`}>
                {trade.action === 'buy' ? (
                  <ArrowUpRight className="w-4 h-4 text-cp-high" />
                ) : (
                  <ArrowDownRight className="w-4 h-4 text-cp-low" />
                )}
              </div>
              <div>
                <p className="text-white font-medium">{trade.name}</p>
                <p className="text-gray-500 text-xs">{trade.code}</p>
              </div>
            </div>
            <div className="text-right">
              <p className={`text-sm font-medium ${trade.action === 'buy' ? 'text-cp-high' : 'text-cp-low'}`}>
                {trade.action === 'buy' ? '买入' : '卖出'} {trade.quantity}股
              </p>
              <p className="text-gray-500 text-xs">@{trade.price.toFixed(3)}</p>
            </div>
            <div className="text-right w-24">
              <p className="text-white">¥{trade.total_amount.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</p>
              <p className="text-gray-500 text-xs">
                {new Date(trade.recorded_at).toLocaleDateString('zh-CN')}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// 买卖弹窗组件
function TradeModal({ isOpen, onClose, mode, stock, account, onTrade, loading }) {
  const [quantity, setQuantity] = useState(100)
  const [error, setError] = useState('')

  useEffect(() => {
    if (isOpen) {
      setQuantity(100)
      setError('')
    }
  }, [isOpen])

  if (!isOpen || !stock) return null

  const isBuy = mode === 'buy'
  const price = stock.price || 0
  const principal = price * quantity
  const commission = Math.max(principal * 0.0003, 5)
  const stampTax = isBuy ? 0 : principal * 0.0005
  // 过户费：仅沪市(sh)收取，深市(sz)免收
  const isShanghai = stock.code.startsWith('sh')
  const transferFee = isShanghai ? principal * 0.00001 : 0
  const totalCost = isBuy ? principal + commission + transferFee : principal - commission - stampTax - transferFee

  // 买入成本率：佣金0.03% + 过户费0.001%(仅沪市)
  const buyCostRate = 0.0003 + (isShanghai ? 0.00001 : 0)
  const maxQuantity = isBuy
    ? Math.floor((account?.cash || 0) / (price * (1 + buyCostRate)))
    : 0

  const handleSubmit = async () => {
    if (quantity % 100 !== 0) {
      setError('买卖数量必须是100的倍数')
      return
    }
    if (isBuy && totalCost > (account?.cash || 0)) {
      setError('资金不足')
      return
    }

    try {
      await onTrade(stock.code, quantity)
      onClose()
    } catch (e) {
      setError(e.message)
    }
  }


  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-card-bg rounded-xl border border-border-dark p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white">
            {isBuy ? '买入' : '卖出'} {stock.name}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="mb-4 p-4 bg-deep-night rounded-lg">
          <div className="flex justify-between mb-2">
            <span className="text-gray-400">股票代码</span>
            <span className="text-white">{stock.code}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">当前价格</span>
            <span className="text-white font-medium">¥{price.toFixed(3)}</span>
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-white font-medium mb-2">买卖数量（手）</label>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setQuantity(Math.max(100, quantity - 100))}
              className="px-4 py-2 bg-deep-night text-white rounded-lg hover:bg-white/10"
            >
              -100
            </button>
            <input
              type="number"
              value={quantity}
              onChange={e => setQuantity(Math.max(100, parseInt(e.target.value) || 0))}
              className="flex-1 px-4 py-2 bg-deep-night border border-border-dark rounded-lg text-white text-center focus:outline-none focus:border-accent-blue"
            />
            <button
              onClick={() => setQuantity(quantity + 100)}
              className="px-4 py-2 bg-deep-night text-white rounded-lg hover:bg-white/10"
            >
              +100
            </button>
          </div>
          <p className="text-gray-500 text-sm mt-2 text-center">
            每手 = 100股，合计 {quantity} 股
          </p>
        </div>

        <div className="mb-4 p-4 bg-deep-night rounded-lg space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">成交金额</span>
            <span className="text-white">¥{principal.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">佣金 (0.03%)</span>
            <span className="text-white">¥{commission.toFixed(2)}</span>
          </div>
          {!isBuy && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">印花税 (0.05%)</span>
              <span className="text-white">¥{stampTax.toFixed(2)}</span>
            </div>
          )}
          <div className="flex justify-between text-sm">
            <span className="text-gray-400">过户费 {isShanghai ? '(0.001%)' : '(深市免)'}</span>
            <span className={transferFee > 0 ? 'text-white' : 'text-gray-500'}>¥{transferFee.toFixed(2)}</span>
          </div>
          <div className="border-t border-border-dark pt-2 flex justify-between">
            <span className="text-white font-medium">{isBuy ? '需支付' : '将获得'}</span>
            <span className="text-white font-bold text-lg">¥{Math.abs(totalCost).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</span>
          </div>
          <div className="flex justify-between text-sm text-gray-400">
            <span>可用资金</span>
            <span>¥{(account?.cash || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}</span>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-cp-low/20 border border-cp-low/30 rounded-lg text-cp-low text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {error}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading || quantity < 100}
          className={`w-full py-3 rounded-lg font-semibold transition-colors disabled:opacity-50 ${
            isBuy
              ? 'bg-cp-high hover:bg-cp-high/80 text-white'
              : 'bg-cp-low hover:bg-cp-low/80 text-white'
          }`}
        >
          {loading ? '处理中...' : isBuy ? `确认买入` : `确认卖出`}
        </button>
      </div>
    </div>
  )
}

// 主页面组件
export default function TradingCenter() {
  const { account, portfolio, trades, loading, error, buyStock, sellStock, refreshAll } = useAccount()
  const [showTradeModal, setShowTradeModal] = useState(false)
  const [tradeMode, setTradeMode] = useState('buy')
  const [selectedStock, setSelectedStock] = useState(null)
  const [sellHolding, setSellHolding] = useState(null)

  const handleBuy = (stock) => {
    setSelectedStock(stock)
    setTradeMode('buy')
    setShowTradeModal(true)
  }

  const handleSell = (holding) => {
    setSellHolding(holding)
    setSelectedStock({
      code: holding.code,
      name: holding.name,
      price: holding.current_price
    })
    setTradeMode('sell')
    setShowTradeModal(true)
  }

  const handleTrade = async (code, quantity) => {
    if (tradeMode === 'buy') {
      await buyStock(code, quantity)
    } else {
      await sellStock(code, quantity)
    }
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">模拟交易</h1>
          <p className="text-gray-400 text-sm mt-1">使用虚拟资金练习股票买卖</p>
        </div>
        <button
          onClick={refreshAll}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-accent-blue/20 text-accent-blue rounded-lg hover:bg-accent-blue/30 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          刷新
        </button>
      </div>

      {error && (
        <div className="p-4 bg-cp-low/20 border border-cp-low/30 rounded-lg text-cp-low flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：账户卡片 + 快速买入 */}
        <div className="space-y-6">
          <AccountCard account={account} />

          {/* 快速买入 */}
          <div className="bg-card-bg rounded-xl border border-border-dark p-6">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <ArrowUpRight className="w-5 h-5 text-cp-high" />
              快速买入
            </h3>
            <StockSearch
              onSelect={handleBuy}
              excludeCodes={[]}
            />
          </div>
        </div>

        {/* 中间：持仓列表 */}
        <div className="lg:col-span-2 space-y-6">
          <HoldingsList
            portfolio={portfolio}
            onBuy={handleBuy}
            onSell={handleSell}
          />

          <TradeHistory trades={trades} />
        </div>
      </div>

      {/* 交易弹窗 */}
      <TradeModal
        isOpen={showTradeModal}
        onClose={() => { setShowTradeModal(false); setSelectedStock(null); setSellHolding(null) }}
        mode={tradeMode}
        stock={selectedStock}
        account={account}
        onTrade={handleTrade}
        loading={loading}
      />
    </div>
  )
}