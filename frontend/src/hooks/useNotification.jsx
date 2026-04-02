import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const NotificationContext = createContext(null)

// 通知类型（与后端alert_type对应）
const NOTIFICATION_TYPES = {
  PRICE_ALERT: 'price_alert',
  CP_DROP: 'cp_drop',
  CP_DROP_DANGER: 'cp_drop_danger',
  CP_TREND_DROP: 'cp_trend_drop',
  RISK_LEVEL_UP: 'risk_level_up',
  SWAP_SIGNAL: 'swap_signal',
  NEW_OPPORTUNITY: 'new_opportunity',
  SYSTEM: 'system'
}

// 通知状态
const NOTIFICATION_STATUS = {
  UNREAD: 'unread',
  READ: 'read',
  DISMISSED: 'dismissed'
}

const API_BASE = ''

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([])
  const [settings, setSettings] = useState({
    enabled: true,
    priceAlertThreshold: 5,
    cpAlertThreshold: 10,
    soundEnabled: true,
    alertConfig: {}
  })

  // 从API获取预警列表
  const fetchAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/alerts?limit=100`)
      if (res.ok) {
        const data = await res.json()
        const apiAlerts = data.alerts || []
        const converted = apiAlerts.map(alert => ({
          id: alert.id,
          type: alert.type || NOTIFICATION_TYPES.SYSTEM,
          title: alert.title || getDefaultTitle(alert.type),
          message: alert.message || '',
          data: {
            code: alert.code,
            name: alert.name,
            level: alert.level,
            cp_before: alert.cp_before,
            cp_after: alert.cp_after
          },
          status: alert.is_read ? NOTIFICATION_STATUS.READ : NOTIFICATION_STATUS.UNREAD,
          createdAt: alert.created_at || new Date().toISOString(),
          expires_at: alert.expires_at
        }))
        setNotifications(prev => mergeAndSort(prev, converted))
      }
    } catch (e) {
      console.error('Failed to fetch alerts:', e)
    }
  }, [])

  // 合并并排序通知
  const mergeAndSort = (local, api) => {
    const merged = [...api]
    local.forEach(n => {
      if (!n.id || String(n.id).length > 13) {
        const exists = merged.find(m => m.id === n.id)
        if (!exists) merged.push(n)
      }
    })
    return merged.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
  }

  const getDefaultTitle = (type) => {
    const titles = {
      'cp_drop': '战力下降预警',
      'cp_drop_danger': '战力大幅下降',
      'cp_trend_drop': '连续下跌预警',
      'risk_level_up': '风险等级变化',
      'swap_signal': '换股信号',
      'new_opportunity': '新股机会',
      'system': '系统通知'
    }
    return titles[type] || '预警通知'
  }

  // 初始化
  useEffect(() => {
    fetchAlerts()
    const interval = setInterval(fetchAlerts, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [fetchAlerts])

  // 从localStorage加载本地通知
  useEffect(() => {
    const saved = localStorage.getItem('notifications')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        const localOnly = parsed.filter(n => !n.id || String(n.id).length > 13)
        if (localOnly.length > 0) {
          setNotifications(prev => mergeAndSort(prev, localOnly))
        }
      } catch (e) {
        console.error('Failed to load notifications:', e)
      }
    }
  }, [])

  // 保存通知到localStorage
  useEffect(() => {
    try {
      if (notifications.length > 0) {
        localStorage.setItem('notifications', JSON.stringify(notifications.slice(0, 100)))
      }
    } catch (e) {
      console.error('Failed to save notifications:', e)
    }
  }, [notifications])

  // 添加通知
  const addNotification = useCallback((notification) => {
    const newNotification = {
      id: Date.now() + Math.random(),
      type: notification.type || NOTIFICATION_TYPES.SYSTEM,
      title: notification.title,
      message: notification.message,
      data: notification.data || {},
      status: NOTIFICATION_STATUS.UNREAD,
      createdAt: new Date().toISOString()
    }
    setNotifications(prev => mergeAndSort(prev, [newNotification]))
    if (settings.soundEnabled && settings.enabled) {
      playNotificationSound()
    }
    return newNotification.id
  }, [settings.soundEnabled, settings.enabled])

  // 标记已读
  const markAsRead = useCallback(async (notificationId) => {
    setNotifications(prev =>
      prev.map(n =>
        n.id === notificationId ? { ...n, status: NOTIFICATION_STATUS.READ } : n
      )
    )
    if (Number.isInteger(notificationId) && notificationId > 0) {
      try {
        await fetch(`${API_BASE}/api/alerts/read`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ alert_ids: [notificationId] })
        })
      } catch (e) {
        console.error('Failed to mark alert as read:', e)
      }
    }
  }, [])

  // 标记全部已读
  const markAllAsRead = useCallback(async () => {
    setNotifications(prev =>
      prev.map(n => ({ ...n, status: NOTIFICATION_STATUS.READ })))
    try {
      await fetch(`${API_BASE}/api/alerts/read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ all: true })
      })
    } catch (e) {
      console.error('Failed to mark all alerts as read:', e)
    }
  }, [])

  // 删除通知
  const dismissNotification = useCallback((notificationId) => {
    setNotifications(prev =>
      prev.map(n =>
        n.id === notificationId ? { ...n, status: NOTIFICATION_STATUS.DISMISSED } : n
      )
    )
  }, [])

  // 清除所有通知
  const clearAll = useCallback(() => {
    setNotifications([])
  }, [])

  const unreadCount = notifications.filter(n => n.status === NOTIFICATION_STATUS.UNREAD).length
  const visibleNotifications = notifications.filter(n => n.status !== NOTIFICATION_STATUS.DISMISSED)

  // 更新设置
  const updateSettings = useCallback((newSettings) => {
    setSettings(prev => ({ ...prev, ...newSettings }))
    try {
      localStorage.setItem('notificationSettings', JSON.stringify({ ...settings, ...newSettings }))
    } catch (e) {
      console.error('Failed to save notification settings:', e)
    }
  }, [settings])

  // 加载设置
  useEffect(() => {
    const savedSettings = localStorage.getItem('notificationSettings')
    if (savedSettings) {
      try {
        setSettings(prev => ({ ...prev, ...JSON.parse(savedSettings) }))
      } catch (e) {
        console.error('Failed to load notification settings:', e)
      }
    }
  }, [])

  // 加载预警配置
  useEffect(() => {
    const fetchAlertConfig = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/alerts/config`)
        if (res.ok) {
          const data = await res.json()
          setSettings(prev => ({ ...prev, alertConfig: data.configs || {} }))
        }
      } catch (e) {
        console.error('Failed to fetch alert config:', e)
      }
    }
    fetchAlertConfig()
  }, [])

  const value = {
    notifications: visibleNotifications,
    unreadCount,
    addNotification,
    markAsRead,
    markAllAsRead,
    dismissNotification,
    clearAll,
    settings,
    updateSettings,
    NOTIFICATION_TYPES
  }

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  )
}

export function useNotification() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotification must be used within NotificationProvider')
  }
  return context
}

// 简单的提示音
function playNotificationSound() {
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)()
    const oscillator = audioContext.createOscillator()
    const gainNode = audioContext.createGain()
    oscillator.connect(gainNode)
    gainNode.connect(audioContext.destination)
    oscillator.frequency.value = 800
    oscillator.type = 'sine'
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime)
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3)
    oscillator.start(audioContext.currentTime)
    oscillator.stop(audioContext.currentTime + 0.3)
  } catch (e) {
    // 音频播放失败，静默处理
  }
}

export default useNotification
