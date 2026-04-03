import { useState, useEffect, useCallback } from 'react'
import { X, RotateCcw, Save, AlertCircle } from 'lucide-react'
import { useTourGuide } from '../components/TourGuide'

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

// 用户配置默认值
const defaultUserProfile = {
  capital: 20000,
  allowed_boards: ['main'],
  risk_preference: 'aggressive',
  consider_dividend: true,
  keep_cash_reserve: false
}

export function useSettings() {
  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem(SETTINGS_KEY)
      return saved ? { ...defaultSettings, ...JSON.parse(saved) } : defaultSettings
    } catch (e) {
      console.error('Failed to load settings:', e)
      return defaultSettings
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
    } catch (e) {
      console.error('Failed to save settings:', e)
    }
  }, [settings])

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  const resetSettings = () => {
    setSettings(defaultSettings)
  }

  return { settings, updateSetting, resetSettings }
}

// 用户配置 Hook
export function useUserProfile() {
  const [profile, setProfile] = useState(defaultUserProfile)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [saveStatus, setSaveStatus] = useState(null) // 'saving' | 'saved' | 'error'

  const fetchProfile = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/user/profile')
      if (res.ok) {
        const data = await res.json()
        setProfile(data.profile)
      } else {
        setError('获取配置失败')
      }
    } catch (e) {
      setError('网络错误')
      console.error('Failed to fetch user profile:', e)
    }
    setLoading(false)
  }, [])

  const saveProfile = useCallback(async (newProfile) => {
    setSaveStatus('saving')
    setError(null)
    try {
      const res = await fetch('/api/user/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newProfile)
      })
      if (res.ok) {
        const data = await res.json()
        setProfile(data.profile)
        setSaveStatus('saved')
        setTimeout(() => setSaveStatus(null), 2000)
      } else {
        const err = await res.json()
        setError(err.detail || '保存失败')
        setSaveStatus('error')
      }
    } catch (e) {
      setError('网络错误')
      setSaveStatus('error')
      console.error('Failed to save user profile:', e)
    }
  }, [])

  useEffect(() => {
    fetchProfile()
  }, [fetchProfile])

  return { profile, loading, error, saveProfile, fetchProfile }
}

export function SettingsModal({ isOpen, onClose }) {
  const { settings, updateSetting, resetSettings } = useSettings()
  const { resetTour } = useTourGuide()
  const { profile, loading, error, saveProfile, fetchProfile } = useUserProfile()
  const [localProfile, setLocalProfile] = useState(profile)

  // 当profile加载完成后同步到local state
  useEffect(() => {
    setLocalProfile(profile)
  }, [profile])

  const handleSave = async () => {
    await saveProfile(localProfile)
  }

  const handleBoardToggle = (board) => {
    const boards = localProfile.allowed_boards || []
    if (boards.includes(board)) {
      // 不能取消最后一个板块
      if (boards.length === 1) return
      setLocalProfile({ ...localProfile, allowed_boards: boards.filter(b => b !== board) })
    } else {
      setLocalProfile({ ...localProfile, allowed_boards: [...boards, board] })
    }
  }

  const boardLabels = {
    main: '主板（沪深）',
    gem: '创业板',
    star: '科创板',
    bge: '北交所'
  }

  const riskLabels = {
    conservative: '保守',
    balanced: '平衡',
    aggressive: '激进'
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-card-bg rounded-xl border border-border-dark p-6 max-w-lg w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-white">设置</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-6">
          {/* 用户配置区域 */}
          <div className="border-b border-border-dark pb-6">
            <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
              <span className="w-2 h-2 bg-cp-high rounded-full"></span>
              个人约束配置
            </h3>

            {loading ? (
              <div className="p-4 bg-deep-night rounded-lg text-center text-gray-400">
                加载中...
              </div>
            ) : error ? (
              <div className="p-4 bg-cp-low/10 border border-cp-low/30 rounded-lg text-cp-low text-sm">
                <AlertCircle className="w-4 h-4 inline mr-1" />
                {error}
                <button onClick={fetchProfile} className="ml-2 underline">重试</button>
              </div>
            ) : (
              <div className="space-y-4">
                {/* 资金量 */}
                <div className="p-3 bg-deep-night rounded-lg">
                  <label className="block text-white font-medium mb-2">资金量（元）</label>
                  <input
                    type="number"
                    value={localProfile.capital}
                    onChange={(e) => setLocalProfile({ ...localProfile, capital: Number(e.target.value) })}
                    min="100"
                    className="w-full px-3 py-2 bg-card-bg border border-border-dark rounded-lg text-white focus:outline-none focus:border-accent-blue"
                  />
                  <p className="text-gray-500 text-xs mt-1">用于计算"买得起"的股票范围</p>
                </div>

                {/* 可交易板块 */}
                <div className="p-3 bg-deep-night rounded-lg">
                  <label className="block text-white font-medium mb-2">可交易板块</label>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(boardLabels).map(([board, label]) => (
                      <button
                        key={board}
                        onClick={() => handleBoardToggle(board)}
                        disabled={localProfile.allowed_boards?.length === 1 && localProfile.allowed_boards.includes(board)}
                        className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                          localProfile.allowed_boards?.includes(board)
                            ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue'
                            : 'bg-card-bg text-gray-400 border border-border-dark hover:border-accent-blue/50'
                        } disabled:opacity-50`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <p className="text-gray-500 text-xs mt-2">选中的板块会在推荐中显示，不选的自动过滤</p>
                </div>

                {/* 风险偏好 */}
                <div className="p-3 bg-deep-night rounded-lg">
                  <label className="block text-white font-medium mb-2">风险偏好</label>
                  <div className="flex gap-2">
                    {Object.entries(riskLabels).map(([risk, label]) => (
                      <button
                        key={risk}
                        onClick={() => setLocalProfile({ ...localProfile, risk_preference: risk })}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm transition-colors ${
                          localProfile.risk_preference === risk
                            ? risk === 'aggressive' ? 'bg-red-500/20 text-red-400 border border-red-500/50' :
                              risk === 'balanced' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/50' :
                              'bg-green-500/20 text-green-400 border border-green-500/50'
                            : 'bg-card-bg text-gray-400 border border-border-dark hover:border-accent-blue/50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 股息考虑 */}
                <div className="flex items-center justify-between p-3 bg-deep-night rounded-lg">
                  <div>
                    <p className="text-white font-medium">考虑股息</p>
                    <p className="text-gray-400 text-sm">推荐时优先显示有股息的股票</p>
                  </div>
                  <button
                    onClick={() => setLocalProfile({ ...localProfile, consider_dividend: !localProfile.consider_dividend })}
                    className={`w-12 h-6 rounded-full transition-colors ${
                      localProfile.consider_dividend ? 'bg-accent-blue' : 'bg-gray-600'
                    }`}
                  >
                    <div className={`w-5 h-5 bg-white rounded-full transition-transform ${
                      localProfile.consider_dividend ? 'translate-x-6' : 'translate-x-0.5'
                    }`} />
                  </button>
                </div>

                {/* 保存按钮 */}
                <button
                  onClick={handleSave}
                  disabled={saveStatus === 'saving'}
                  className={`w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                    saveStatus === 'saved'
                      ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                      : 'bg-accent-blue text-white hover:bg-accent-blue/80'
                  } disabled:opacity-50`}
                >
                  <Save className="w-4 h-4" />
                  {saveStatus === 'saving' ? '保存中...' : saveStatus === 'saved' ? '已保存' : '保存配置'}
                </button>
              </div>
            )}
          </div>

          {/* 偏好设置区域 */}
          <div>
            <h3 className="text-lg font-bold text-white mb-4">偏好设置</h3>

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
                <p className="text-white font-medium mb-2">战力公式 (v18)</p>
                <p className="text-gray-400 text-sm">
                  战力 = 成长×40% + 价值×40% + 动量×20% × 风险调整
                </p>
                <p className="text-gray-400 text-sm mt-1">
                  成长分 = 净利润增长×0.6 + 营收增长×0.4<br/>
                  价值分 = ROE（负值当0）<br/>
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
                  <option value="quality">质量型</option>
                  <option value="allround">综合型</option>
                </select>
              </div>

              {/* 重置设置 */}
              <button
                onClick={resetSettings}
                className="w-full px-4 py-2 text-gray-400 hover:text-red-500 border border-border-dark rounded-lg transition-colors"
              >
                重置为默认设置
              </button>

              {/* 重新观看引导 */}
              <button
                onClick={() => {
                  resetTour()
                  onClose()
                }}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 text-accent-blue hover:text-accent-blue/80 border border-accent-blue/30 hover:border-accent-blue/50 rounded-lg transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
                重新观看引导教程
              </button>

              {/* 键盘快捷键说明 */}
              <div className="p-3 bg-deep-night rounded-lg border border-border-dark">
                <p className="text-white font-medium mb-2">键盘快捷键</p>
                <div className="grid grid-cols-2 gap-1 text-xs text-gray-400">
                  <div><kbd className="px-1.5 py-0.5 bg-card-bg rounded">1-7</kbd> 切换页面</div>
                  <div><kbd className="px-1.5 py-0.5 bg-card-bg rounded">R</kbd> 刷新数据</div>
                  <div><kbd className="px-1.5 py-0.5 bg-card-bg rounded">S</kbd> 打开设置</div>
                  <div><kbd className="px-1.5 py-0.5 bg-card-bg rounded">E</kbd> 战法学堂</div>
                  <div><kbd className="px-1.5 py-0.5 bg-card-bg rounded">D</kbd> 数据说明</div>
                  <div><kbd className="px-1.5 py-0.5 bg-card-bg rounded">T</kbd> 切换主题</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
