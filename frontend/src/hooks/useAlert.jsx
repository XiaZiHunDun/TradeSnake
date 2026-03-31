import { useState, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'tradesnake_alerts'

// 告警配置
export const ALERT_TYPES = {
  CP_DROP: 'cp_drop',        // 战力跌破阈值
  CP_RISE: 'cp_rise',        // 战力突破阈值
  PRICE_DROP: 'price_drop',  // 价格跌破阈值
  PRICE_RISE: 'price_rise',  // 价格突破阈值
}

export function loadAlerts() {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    return data ? JSON.parse(data) : []
  } catch {
    return []
  }
}

export function saveAlerts(alerts) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(alerts))
}

export function useAlerts(stockDataMap) {
  const [alerts, setAlerts] = useState([])
  const [triggeredAlerts, setTriggeredAlerts] = useState([])

  useEffect(() => {
    setAlerts(loadAlerts())
  }, [])

  // 检查告警
  useEffect(() => {
    if (!stockDataMap || Object.keys(stockDataMap).length === 0) return

    const newTriggered = []
    alerts.forEach(alert => {
      const stock = stockDataMap[alert.code]
      if (!stock) return

      let triggered = false
      let message = ''

      switch (alert.type) {
        case ALERT_TYPES.CP_DROP:
          if (stock.total_cp < alert.threshold) {
            triggered = true
            message = `${stock.name} 战力跌破 ${alert.threshold}`
          }
          break
        case ALERT_TYPES.CP_RISE:
          if (stock.total_cp > alert.threshold) {
            triggered = true
            message = `${stock.name} 战力突破 ${alert.threshold}`
          }
          break
        case ALERT_TYPES.PRICE_DROP:
          if (stock.price < alert.threshold) {
            triggered = true
            message = `${stock.name} 价格跌破 ¥${alert.threshold}`
          }
          break
        case ALERT_TYPES.PRICE_RISE:
          if (stock.price > alert.threshold) {
            triggered = true
            message = `${stock.name} 价格突破 ¥${alert.threshold}`
          }
          break
      }

      if (triggered && !alert.triggered) {
        newTriggered.push({ ...alert, message, stockName: stock.name })
      }
    })

    if (newTriggered.length > 0) {
      setTriggeredAlerts(prev => [...prev, ...newTriggered])
    }
  }, [stockDataMap, alerts])

  const addAlert = useCallback((alert) => {
    const newAlert = {
      id: Date.now(),
      ...alert,
      triggered: false,
      createdAt: new Date().toISOString()
    }
    const updated = [...alerts, newAlert]
    setAlerts(updated)
    saveAlerts(updated)
    return newAlert
  }, [alerts])

  const removeAlert = useCallback((id) => {
    const updated = alerts.filter(a => a.id !== id)
    setAlerts(updated)
    saveAlerts(updated)
  }, [alerts])

  const clearTriggered = useCallback(() => {
    setTriggeredAlerts([])
  }, [])

  const dismissTriggered = useCallback((id) => {
    setTriggeredAlerts(prev => prev.filter(a => a.id !== id))
  }, [])

  return {
    alerts,
    triggeredAlerts,
    addAlert,
    removeAlert,
    clearTriggered,
    dismissTriggered
  }
}
