import { useState, useEffect } from 'react'

const STORAGE_KEY = 'tradesnake_watchlist'

// 从localStorage加载自选股
export function loadWatchlist() {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    return data ? JSON.parse(data) : []
  } catch (e) {
    console.error('Failed to load watchlist:', e)
    return []
  }
}

// 保存自选股到localStorage
export function saveWatchlist(watchlist) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(watchlist))
}

// 添加自选股
export function addToWatchlist(code) {
  const watchlist = loadWatchlist()
  if (!watchlist.includes(code)) {
    watchlist.push(code)
    saveWatchlist(watchlist)
  }
  return watchlist
}

// 删除自选股
export function removeFromWatchlist(code) {
  const watchlist = loadWatchlist().filter(c => c !== code)
  saveWatchlist(watchlist)
  return watchlist
}

// 自选股Hook
export function useWatchlist() {
  const [watchlist, setWatchlist] = useState([])

  useEffect(() => {
    setWatchlist(loadWatchlist())
  }, [])

  const add = (code) => {
    const updated = addToWatchlist(code)
    setWatchlist(updated)
  }

  const remove = (code) => {
    const updated = removeFromWatchlist(code)
    setWatchlist(updated)
  }

  const isInWatchlist = (code) => {
    return watchlist.includes(code)
  }

  const toggle = (code) => {
    if (isInWatchlist(code)) {
      remove(code)
    } else {
      add(code)
    }
  }

  return { watchlist, add, remove, toggle, isInWatchlist }
}
