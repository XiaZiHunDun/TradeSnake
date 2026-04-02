import { Bell, X, Check, CheckCheck, Trash2, Settings, TrendingUp, TrendingDown, Star, AlertCircle } from 'lucide-react'
import { useNotification } from '../hooks/useNotification'
import { useState, useEffect, useRef } from 'react'

function NotificationCenter({ isOpen, onClose }) {
  const {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    dismissNotification,
    clearAll,
    settings,
    updateSettings,
    NOTIFICATION_TYPES
  } = useNotification()

  const [showSettings, setShowSettings] = useState(false)
  const dropdownRef = useRef(null)

  // 点击外部关闭
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        onClose()
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const getNotificationIcon = (type) => {
    switch (type) {
      case NOTIFICATION_TYPES.PRICE_ALERT:
        return <TrendingUp className="w-4 h-4 text-red-500" />
      case NOTIFICATION_TYPES.CP_DROP:
      case 'cp_drop':
        return <TrendingDown className="w-4 h-4 text-red-500" />
      case 'cp_drop_danger':
        return <TrendingDown className="w-4 h-4 text-red-700" />
      case 'cp_trend_drop':
        return <TrendingDown className="w-4 h-4 text-orange-500" />
      case NOTIFICATION_TYPES.CP_RISE:
      case 'new_opportunity':
        return <TrendingUp className="w-4 h-4 text-green-500" />
      case 'swap_signal':
        return <Star className="w-4 h-4 text-yellow-500" />
      case 'risk_level_up':
        return <AlertCircle className="w-4 h-4 text-orange-500" />
      default:
        return <AlertCircle className="w-4 h-4 text-blue-500" />
    }
  }

  // 获取通知级别颜色
  const getLevelColor = (notification) => {
    // 优先使用data中的level
    const level = notification.data?.level
    if (level === 'danger') return 'border-l-red-500'
    if (level === 'warning') return 'border-l-yellow-500'
    return 'border-l-blue-500'
  }

  const formatTime = (isoString) => {
    const date = new Date(isoString)
    const now = new Date()
    const diff = now - date

    if (diff < 60000) return '刚刚'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
    return date.toLocaleDateString()
  }

  return (
    <div ref={dropdownRef} className="absolute right-4 top-full mt-2 w-96 bg-card-bg border border-border-dark rounded-xl shadow-2xl z-50 overflow-hidden">
      {/* 头部 */}
      <div className="px-4 py-3 border-b border-border-dark flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell className="w-5 h-5 text-accent-blue" />
          <h3 className="font-bold text-white">通知中心</h3>
          {unreadCount > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-red-500 text-white text-xs font-bold">
              {unreadCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
            title="设置"
          >
            <Settings className="w-4 h-4" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* 设置面板 */}
      {showSettings && (
        <div className="px-4 py-3 border-b border-border-dark bg-deep-night/50">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">启用通知</span>
              <button
                onClick={() => updateSettings({ enabled: !settings.enabled })}
                className={`w-10 h-6 rounded-full transition-colors ${
                  settings.enabled ? 'bg-accent-blue' : 'bg-gray-600'
                }`}
              >
                <div className={`w-4 h-4 bg-white rounded-full transition-transform ${
                  settings.enabled ? 'translate-x-5' : 'translate-x-1'
                }`} />
              </button>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">提示音</span>
              <button
                onClick={() => updateSettings({ soundEnabled: !settings.soundEnabled })}
                className={`w-10 h-6 rounded-full transition-colors ${
                  settings.soundEnabled ? 'bg-accent-blue' : 'bg-gray-600'
                }`}
              >
                <div className={`w-4 h-4 bg-white rounded-full transition-transform ${
                  settings.soundEnabled ? 'translate-x-5' : 'translate-x-1'
                }`} />
              </button>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">价格提醒阈值</span>
              <select
                value={settings.priceAlertThreshold}
                onChange={(e) => updateSettings({ priceAlertThreshold: Number(e.target.value) })}
                className="bg-deep-night border border-border-dark rounded px-2 py-1 text-white text-sm"
              >
                <option value={3}>±3%</option>
                <option value={5}>±5%</option>
                <option value={10}>±10%</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* 操作栏 */}
      <div className="px-4 py-2 border-b border-border-dark flex items-center justify-between bg-deep-night/30">
        <button
          onClick={async () => {
            try {
              await fetch('/api/alerts/check')
              window.location.reload()
            } catch (e) {
              console.error('Failed to check alerts:', e)
            }
          }}
          className="flex items-center gap-1 text-xs text-accent-blue hover:text-white transition-colors"
        >
          <Bell className="w-3 h-3" />
          检查预警
        </button>
        {notifications.length > 0 && (
          <>
            <button
              onClick={markAllAsRead}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
            >
              <CheckCheck className="w-3 h-3" />
              全部已读
            </button>
            <button
              onClick={clearAll}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-3 h-3" />
              清空
            </button>
          </>
        )}
      </div>

      {/* 通知列表 */}
      <div className="max-h-80 overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="py-12 text-center text-gray-400">
            <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">暂无通知</p>
          </div>
        ) : (
          notifications.map((notification) => (
            <div
              key={notification.id}
              className={`px-4 py-3 border-b border-border-dark/50 hover:bg-white/5 transition-colors border-l-2 ${getLevelColor(notification)} ${
                notification.status === 'unread' ? 'bg-accent-blue/5' : ''
              }`}
            >
              <div className="flex gap-3">
                <div className="flex-shrink-0 mt-0.5">
                  {getNotificationIcon(notification.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-white truncate">
                      {notification.title}
                    </p>
                    <button
                      onClick={() => dismissNotification(notification.id)}
                      className="flex-shrink-0 p-1 text-gray-500 hover:text-white transition-colors"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">
                    {notification.message}
                  </p>
                  <div className="flex items-center justify-between mt-1.5">
                    <span className="text-xs text-gray-500">
                      {formatTime(notification.createdAt)}
                    </span>
                    {notification.status === 'unread' && (
                      <button
                        onClick={() => markAsRead(notification.id)}
                        className="flex items-center gap-1 text-xs text-accent-blue hover:text-white transition-colors"
                      >
                        <Check className="w-3 h-3" />
                        标记已读
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default NotificationCenter
