import { useState, useEffect, useCallback } from 'react'

const API_BASE = ''

export function useAccount() {
  const [account, setAccount] = useState(null)
  const [portfolio, setPortfolio] = useState(null)
  const [trades, setTrades] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchAccount = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/account`)
      if (res.ok) {
        const data = await res.json()
        setAccount(data)
      }
    } catch (e) {
      console.error('Failed to fetch account:', e)
    }
  }, [])

  const fetchPortfolio = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/portfolio`)
      if (res.ok) {
        const data = await res.json()
        setPortfolio(data)
      }
    } catch (e) {
      console.error('Failed to fetch portfolio:', e)
    }
  }, [])

  const fetchTrades = useCallback(async (limit = 50) => {
    try {
      const res = await fetch(`${API_BASE}/api/trades?limit=${limit}`)
      if (res.ok) {
        const data = await res.json()
        setTrades(data.trades || [])
      }
    } catch (e) {
      console.error('Failed to fetch trades:', e)
    }
  }, [])

  const buyStock = useCallback(async (code, quantity) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/trade/buy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, quantity })
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || '买入失败')
      }
      // 刷新数据
      await Promise.all([fetchAccount(), fetchPortfolio(), fetchTrades()])
      return data
    } catch (e) {
      setError(e.message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [fetchAccount, fetchPortfolio, fetchTrades])

  const sellStock = useCallback(async (code, quantity) => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/api/trade/sell`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, quantity })
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || '卖出失败')
      }
      // 刷新数据
      await Promise.all([fetchAccount(), fetchPortfolio(), fetchTrades()])
      return data
    } catch (e) {
      setError(e.message)
      throw e
    } finally {
      setLoading(false)
    }
  }, [fetchAccount, fetchPortfolio, fetchTrades])

  const refreshAll = useCallback(async () => {
    setLoading(true)
    await Promise.all([fetchAccount(), fetchPortfolio(), fetchTrades()])
    setLoading(false)
  }, [fetchAccount, fetchPortfolio, fetchTrades])

  useEffect(() => {
    refreshAll()
  }, [refreshAll])

  return {
    account,
    portfolio,
    trades,
    loading,
    error,
    fetchAccount,
    fetchPortfolio,
    fetchTrades,
    buyStock,
    sellStock,
    refreshAll
  }
}