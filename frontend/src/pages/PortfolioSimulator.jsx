import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Plus, Trash2, Calculator, Zap } from 'lucide-react'

function PortfolioSimulator() {
  const [stocks, setStocks] = useState([]) // 模拟持仓
  const [totalCP, setTotalCP] = useState(0)
  const [totalValue, setTotalValue] = useState(0)
  const [potentialGain, setPotentialGain] = useState(0)
  const [newStock, setNewStock] = useState({ code: '', quantity: 100 })
  const [searchResult, setSearchResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [simResult, setSimResult] = useState(null)

  // 搜索股票
  const searchStock = async (code) => {
    if (!code.trim()) return

    setLoading(true)
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
      }
    } catch (e) {
      console.error('Search failed:', e)
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

    // 模拟：如果每只股票战力+10
    const improvedCP = stocks.reduce((sum, s) => {
      const improvedStock = { ...s, total_cp: Math.min(100, s.total_cp + 10) }
      return sum + improvedStock.total_cp * improvedStock.quantity
    }, 0)

    // 模拟：如果每只股票战力-10
    const reducedCP = stocks.reduce((sum, s) => {
      const reducedStock = { ...s, total_cp: Math.max(0, s.total_cp - 10) }
      return sum + reducedStock.total_cp * reducedStock.quantity
    }, 0)

    setTotalCP(currentCP)
    setTotalValue(currentValue)
    setPotentialGain(improvedCP - currentCP)
    setSimResult({
      current: currentCP,
      improved: improvedCP,
      reduced: reducedCP,
      improvementRate: ((improvedCP - currentCP) / currentCP * 100).toFixed(1)
    })
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
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">持股数量</label>
            <input
              type="number"
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
                    <div>
                      <p className="text-white font-bold">{stock.name}</p>
                      <p className="text-gray-400 text-xs">{stock.code}</p>
                    </div>
                    <div className="text-sm text-gray-300">
                      {stock.quantity}股 × ¥{stock.price.toFixed(2)} = ¥{(stock.quantity * stock.price).toFixed(0)}
                    </div>
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
        <div className="flex gap-3">
          <button
            onClick={calculateSim}
            disabled={stocks.length === 0}
            className="flex items-center gap-2 px-4 py-2 bg-cp-high/20 text-cp-high rounded-lg hover:bg-cp-high/30 disabled:opacity-50"
          >
            <Zap className="w-4 h-4" />
            计算模拟结果
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
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-deep-night rounded-lg p-4 text-center">
              <p className="text-gray-400 text-sm mb-1">当前总战力</p>
              <p className="text-2xl font-bold text-white">{simResult.current.toFixed(0)}</p>
            </div>
            <div className="bg-deep-night rounded-lg p-4 text-center">
              <p className="text-gray-400 text-sm mb-1">战力+10后</p>
              <p className="text-2xl font-bold text-green-500">{simResult.improved.toFixed(0)}</p>
            </div>
            <div className="bg-deep-night rounded-lg p-4 text-center">
              <p className="text-gray-400 text-sm mb-1">战力-10后</p>
              <p className="text-2xl font-bold text-red-500">{simResult.reduced.toFixed(0)}</p>
            </div>
            <div className="bg-deep-night rounded-lg p-4 text-center">
              <p className="text-gray-400 text-sm mb-1">提升潜力</p>
              <p className="text-2xl font-bold text-accent-blue">+{simResult.improvementRate}%</p>
            </div>
          </div>
          <div className="mt-4 p-4 bg-deep-night rounded-lg">
            <p className="text-gray-300 text-sm">
              提示：如果将组合内所有股票的战力各提升10点，总战力将从 <span className="text-white font-bold">{simResult.current.toFixed(0)}</span> 提升到
              <span className="text-green-500 font-bold"> {simResult.improved.toFixed(0)}</span>，
              增长 <span className="text-green-500 font-bold">{simResult.improvementRate}%</span>。
              这可以帮助你评估换股策略的潜在收益。
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

export default PortfolioSimulator
