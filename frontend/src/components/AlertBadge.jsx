import { Bell, BellOff, X, TrendingUp, TrendingDown } from 'lucide-react'
import { useState } from 'react'

export function AlertBadge({ alerts, onClick }) {
  const [showPanel, setShowPanel] = useState(false)

  if (!alerts || alerts.length === 0) return null

  return (
    <div className="relative">
      <button
        onClick={() => setShowPanel(!showPanel)}
        className="relative p-2 rounded-lg bg-card-bg text-gray-400 hover:text-white transition-colors"
      >
        <Bell className="w-5 h-5" />
        {alerts.length > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
            {alerts.length}
          </span>
        )}
      </button>

      {showPanel && (
        <div className="absolute right-0 top-full mt-2 w-72 bg-card-bg border border-border-dark rounded-lg shadow-xl z-50">
          <div className="p-3 border-b border-border-dark flex items-center justify-between">
            <span className="font-bold text-white">战力预警 ({alerts.length})</span>
            <button onClick={() => setShowPanel(false)} className="text-gray-400 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="max-h-64 overflow-y-auto">
            {alerts.map(alert => (
              <div key={alert.id} className="p-3 border-b border-border-dark/50 last:border-0">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-white text-sm font-medium">{alert.stockName || alert.code}</p>
                    <p className="text-gray-400 text-xs mt-1">
                      {alert.type === 'cp_drop' && '战力跌破'}
                      {alert.type === 'cp_rise' && '战力突破'}
                      {alert.type === 'price_drop' && '价格跌破'}
                      {alert.type === 'price_rise' && '价格突破'}
                      : {alert.threshold}
                    </p>
                  </div>
                  <button
                    onClick={() => onClick(alert.id)}
                    className="text-gray-500 hover:text-red-500"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function AlertToast({ alert, onDismiss }) {
  if (!alert) return null

  const isPositive = alert.type === 'cp_rise' || alert.type === 'price_rise'

  return (
    <div className="fixed bottom-4 left-4 bg-card-bg border border-border-dark rounded-lg p-4 shadow-xl z-50 animate-slide-in">
      <div className="flex items-start gap-3">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
          isPositive ? 'bg-green-500/20' : 'bg-red-500/20'
        }`}>
          {isPositive ? (
            <TrendingUp className="w-5 h-5 text-green-500" />
          ) : (
            <TrendingDown className="w-5 h-5 text-red-500" />
          )}
        </div>
        <div className="flex-1">
          <p className="text-white font-medium">{alert.message}</p>
          <p className="text-gray-400 text-sm mt-1">
            {new Date().toLocaleTimeString()}
          </p>
        </div>
        <button onClick={onDismiss} className="text-gray-400 hover:text-white">
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
