import { useState, useEffect } from 'react'
import { Info, ExternalLink, Clock, Database, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react'

export function DataSourceInfo() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHealth()
    const interval = setInterval(fetchHealth, 60000) // 每分钟更新
    return () => clearInterval(interval)
  }, [])

  const fetchHealth = async () => {
    try {
      const res = await fetch('/api/health')
      if (res.ok) {
        const data = await res.json()
        setHealth(data)
      }
    } catch (e) {
      console.error('Failed to fetch health')
    }
    setLoading(false)
  }

  const getFreshnessStatus = () => {
    if (!health?.last_update) return { status: 'unknown', text: '未知', color: 'gray' }
    const lastUpdate = new Date(health.last_update)
    const now = new Date()
    const diffMinutes = (now - lastUpdate) / 1000 / 60

    if (diffMinutes < 5) return { status: 'fresh', text: '实时', color: 'green' }
    if (diffMinutes < 30) return { status: 'normal', text: `${Math.round(diffMinutes)}分钟前`, color: 'green' }
    if (diffMinutes < 60) return { status: 'aging', text: `${Math.round(diffMinutes)}分钟前`, color: 'yellow' }
    if (diffMinutes < 120) return { status: 'stale', text: '1小时前', color: 'orange' }
    return { status: 'old', text: '需刷新', color: 'red' }
  }

  const freshness = getFreshnessStatus()

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <RefreshCw className="w-4 h-4 animate-spin" />
        <span>加载中...</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-4 text-xs">
      {/* 数据状态 */}
      <div className="flex items-center gap-1.5">
        {freshness.status === 'fresh' || freshness.status === 'normal' ? (
          <CheckCircle className={`w-3.5 h-3.5 text-${freshness.color}-500`} />
        ) : (
          <AlertCircle className={`w-3.5 h-3.5 text-${freshness.color}-500`} />
        )}
        <span className={`text-${freshness.color}-400`}>
          数据{freshness.text}
        </span>
      </div>

      {/* 数据量 */}
      {health?.stocks_count > 0 && (
        <div className="flex items-center gap-1.5 text-gray-400">
          <Database className="w-3.5 h-3.5" />
          <span>{health.stocks_count}只股票</span>
        </div>
      )}

      {/* 更新时间 */}
      {health?.last_update && (
        <div className="flex items-center gap-1.5 text-gray-500">
          <Clock className="w-3.5 h-3.5" />
          <span>{new Date(health.last_update).toLocaleTimeString()}</span>
        </div>
      )}

      {/* 数据来源 */}
      <div className="flex items-center gap-1.5 text-gray-500">
        <span>数据源:</span>
        <a
          href="https://data.eastmoney.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="text-accent-blue hover:underline flex items-center gap-0.5"
        >
          东方财富
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  )
}

// 数据说明弹窗
export function DataSourceModal({ isOpen, onClose }) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-card-bg rounded-xl border border-border-dark max-w-lg w-full shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <div className="p-5 border-b border-border-dark">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-accent-blue/20 flex items-center justify-center">
              <Info className="w-5 h-5 text-accent-blue" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">数据说明</h2>
              <p className="text-xs text-gray-400">了解数据的来源和局限性</p>
            </div>
          </div>
        </div>

        <div className="p-5 space-y-4">
          {/* 数据来源 */}
          <div>
            <h3 className="text-white font-medium mb-2">数据来源</h3>
            <p className="text-gray-400 text-sm">
              实时行情数据来自腾讯股票API，财务数据来自东方财富数据中心。
              我们不对数据准确性做任何保证。
            </p>
          </div>

          {/* 更新频率 */}
          <div>
            <h3 className="text-white font-medium mb-2">更新频率</h3>
            <ul className="text-gray-400 text-sm space-y-1">
              <li>• 行情数据：交易时间内实时更新</li>
              <li>• 战力榜单：手动刷新或自动每小时刷新</li>
              <li>• 财务数据：每交易日收盘后更新</li>
            </ul>
          </div>

          {/* 数据局限 */}
          <div className="bg-yellow-500/10 rounded-lg p-4 border border-yellow-500/20">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="text-yellow-500 font-medium mb-1">数据局限性</h4>
                <ul className="text-gray-400 text-sm space-y-1">
                  <li>• 财务数据可能存在滞后（季报）</li>
                  <li>• 部分股票数据可能缺失</li>
                  <li>• 历史数据仅供参考，不代表未来表现</li>
                </ul>
              </div>
            </div>
          </div>

          {/* 免责声明 */}
          <div className="text-xs text-gray-500 pt-2 border-t border-border-dark">
            <p className="mb-1">
              <strong className="text-gray-400">免责声明：</strong>
            </p>
            <p>
              战力值仅供娱乐和参考，不构成任何投资建议。
              股票市场有风险，投资需谨慎。过往表现不代表未来收益。
            </p>
          </div>
        </div>

        <div className="p-4 border-t border-border-dark flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-accent-blue text-white rounded-lg hover:bg-accent-blue/80 transition-colors text-sm"
          >
            我知道了
          </button>
        </div>
      </div>
    </div>
  )
}
