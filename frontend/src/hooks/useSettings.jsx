import { useState, useEffect } from 'react'
import { X } from 'lucide-react'

const SETTINGS_KEY = 'tradesnake_settings'

const defaultSettings = {
  theme: 'dark', // 'dark' | 'light'
  autoRefresh: true,
  refreshInterval: 300, // seconds
  defaultSortBy: 'total_cp',
  defaultSortOrder: 'desc',
  showWelcome: true,
  defaultRecommendType: 'value',
  chartDays: 7,
  currency: '¥'
}

export function useSettings() {
  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem(SETTINGS_KEY)
      return saved ? { ...defaultSettings, ...JSON.parse(saved) } : defaultSettings
    } catch {
      return defaultSettings
    }
  })

  useEffect(() => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
  }, [settings])

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  const resetSettings = () => {
    setSettings(defaultSettings)
  }

  return { settings, updateSetting, resetSettings }
}

export function SettingsModal({ isOpen, onClose }) {
  const { settings, updateSetting, resetSettings } = useSettings()

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-card-bg rounded-xl border border-border-dark p-6 max-w-lg w-full" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white">偏好设置</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* 自动刷新 */}
          <div className="flex items-center justify-between p-3 bg-deep-night rounded-lg">
            <div>
              <p className="text-white font-medium">自动刷新数据</p>
              <p className="text-gray-400 text-sm">每5分钟自动更新战力榜</p>
            </div>
            <button
              onClick={() => updateSetting('autoRefresh', !settings.autoRefresh)}
              className={`w-12 h-6 rounded-full transition-colors ${
                settings.autoRefresh ? 'bg-accent-blue' : 'bg-gray-600'
              }`}
            >
              <div className={`w-5 h-5 bg-white rounded-full transition-transform ${
                settings.autoRefresh ? 'translate-x-6' : 'translate-x-0.5'
              }`} />
            </button>
          </div>

          {/* 战力公式说明 */}
          <div className="p-3 bg-deep-night rounded-lg">
            <p className="text-white font-medium mb-2">战力公式 (v13)</p>
            <p className="text-gray-400 text-sm">
              战力 = 成长分×40% + 价值分×40% + 趋势分×20%
            </p>
            <p className="text-gray-400 text-sm mt-1">
              成长分 = 净利润增长×0.6 + 营收增长×0.4<br/>
              价值分 = ROE + PE健康度<br/>
              趋势分 = 当日涨跌幅
            </p>
          </div>

          {/* 图表默认天数 */}
          <div className="p-3 bg-deep-night rounded-lg">
            <p className="text-white font-medium mb-2">历史图表天数</p>
            <select
              value={settings.chartDays}
              onChange={(e) => updateSetting('chartDays', Number(e.target.value))}
              className="w-full px-3 py-2 bg-card-bg border border-border-dark rounded-lg text-white focus:outline-none focus:border-accent-blue"
            >
              <option value={7}>7天</option>
              <option value={14}>14天</option>
              <option value={30}>30天</option>
            </select>
          </div>

          {/* 默认推荐类型 */}
          <div className="p-3 bg-deep-night rounded-lg">
            <p className="text-white font-medium mb-2">默认推荐类型</p>
            <select
              value={settings.defaultRecommendType}
              onChange={(e) => updateSetting('defaultRecommendType', e.target.value)}
              className="w-full px-3 py-2 bg-card-bg border border-border-dark rounded-lg text-white focus:outline-none focus:border-accent-blue"
            >
              <option value="value">价值型</option>
              <option value="growth">成长型</option>
              <option value="momentum">趋势型</option>
            </select>
          </div>

          {/* 重置设置 */}
          <button
            onClick={resetSettings}
            className="w-full px-4 py-2 text-gray-400 hover:text-red-500 border border-border-dark rounded-lg transition-colors"
          >
            重置为默认设置
          </button>
        </div>
      </div>
    </div>
  )
}
