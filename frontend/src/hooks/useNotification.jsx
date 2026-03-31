import { createContext, useContext, useState, useEffect, useCallback } from 'react'

const NotificationContext = createContext(null)

// 通知类型
const NOTIFICATION_TYPES = {
  PRICE_ALERT: 'price_alert',
  CP_DROP: 'cp_drop',
  CP_RISE: 'cp_rise',
  NEW_TOP10: 'new_top10',
  SYSTEM: 'system'
}

// 通知状态
const NOTIFICATION_STATUS = {
  UNREAD: 'unread',
  READ: 'read',
  DISMISSED: 'dismissed'
}

export function NotificationProvider({ children }) {
  const [notifications, setNotifications] = useState([])
  const [settings, setSettings] = useState({
    enabled: true,
    priceAlertThreshold: 5, // 涨跌幅超过5%
    cpAlertThreshold: 10,  // CP变化超过10
    soundEnabled: true
  })

  // 从localStorage加载通知
  useEffect(() => {
    const saved = localStorage.getItem('notifications')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        setNotifications(parsed)
      } catch (e) {
        console.error('Failed to load notifications:', e)
      }
    }
  }, [])

  // 保存通知到localStorage
  useEffect(() => {
    try {
      if (notifications.length > 0) {
        localStorage.setItem('notifications', JSON.stringify(notifications.slice(0, 100))) // 最多保存100条
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

    setNotifications(prev => [newNotification, ...prev].slice(0, 100))

    // 播放提示音
    if (settings.soundEnabled && settings.enabled) {
      playNotificationSound()
    }

    return newNotification.id
  }, [settings.soundEnabled, settings.enabled])

  // 标记已读
  const markAsRead = useCallback((notificationId) => {
    setNotifications(prev =>
      prev.map(n =>
        n.id === notificationId ? { ...n, status: NOTIFICATION_STATUS.READ } : n
      )
    )
  }, [])

  // 标记全部已读
  const markAllAsRead = useCallback(() => {
    setNotifications(prev =>
      prev.map(n => ({ ...n, status: NOTIFICATION_STATUS.READ })))
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

  // 获取未读数量
  const unreadCount = notifications.filter(n => n.status === NOTIFICATION_STATUS.UNREAD).length

  // 获取可见通知（未删除的）
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
        setSettings(JSON.parse(savedSettings))
      } catch (e) {
      console.error('Failed to load notification settings:', e)
    }
    }
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
