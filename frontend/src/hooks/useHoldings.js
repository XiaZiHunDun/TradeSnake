import { useState, useEffect } from 'react'

const STORAGE_KEY = 'tradesnake_holdings'

// 从localStorage加载持仓
export function loadHoldings() {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    return data ? JSON.parse(data) : []
  } catch (e) {
    console.error('Failed to load holdings:', e)
    return []
  }
}

// 保存持仓到localStorage
export function saveHoldings(holdings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(holdings))
}

// 添加持仓
export function addHolding(holding) {
  const holdings = loadHoldings()
  // 检查是否已存在
  const existing = holdings.find(h => h.code === holding.code)
  if (existing) {
    // 更新数量
    existing.quantity += holding.quantity
    existing.costPrice = holding.costPrice
  } else {
    holdings.push(holding)
  }
  saveHoldings(holdings)
  return holdings
}

// 更新持仓
export function updateHolding(code, updates) {
  const holdings = loadHoldings()
  const index = holdings.findIndex(h => h.code === code)
  if (index !== -1) {
    holdings[index] = { ...holdings[index], ...updates }
    saveHoldings(holdings)
  }
  return holdings
}

// 删除持仓
export function deleteHolding(code) {
  const holdings = loadHoldings()
  const filtered = holdings.filter(h => h.code !== code)
  saveHoldings(filtered)
  return filtered
}

// 清空所有持仓
export function clearHoldings() {
  saveHoldings([])
  return []
}

// 自定义Hook
export function useHoldings() {
  const [holdings, setHoldings] = useState([])

  useEffect(() => {
    setHoldings(loadHoldings())
  }, [])

  const refresh = () => {
    setHoldings(loadHoldings())
  }

  const add = (holding) => {
    const updated = addHolding(holding)
    setHoldings(updated)
  }

  const update = (code, updates) => {
    const updated = updateHolding(code, updates)
    setHoldings(updated)
  }

  const remove = (code) => {
    const updated = deleteHolding(code)
    setHoldings(updated)
  }

  const clear = () => {
    const updated = clearHoldings()
    setHoldings(updated)
  }

  return { holdings, refresh, add, update, remove, clear }
}
