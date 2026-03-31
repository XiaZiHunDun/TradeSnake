// 本地数据缓存管理
import { useState, useEffect } from 'react'

const CACHE_PREFIX = 'tradesnake_cache_'
const DEFAULT_TTL = 5 * 60 * 1000 // 5分钟

/**
 * 设置缓存
 */
export function setCache(key, data, ttl = DEFAULT_TTL) {
  const cacheData = {
    data,
    timestamp: Date.now(),
    expiry: Date.now() + ttl
  }
  try {
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(cacheData))
    return true
  } catch (e) {
    // 如果localStorage满了，尝试清理
    if (e.name === 'QuotaExceededError') {
      clearExpiredCache()
      try {
        localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(cacheData))
        return true
      } catch (e2) {
        console.error('Cache write failed after cleanup:', e2)
        return false
      }
    }
    return false
  }
}

/**
 * 获取缓存
 */
export function getCache(key) {
  try {
    const cached = localStorage.getItem(CACHE_PREFIX + key)
    if (!cached) return null

    const cacheData = JSON.parse(cached)

    // 检查是否过期
    if (Date.now() > cacheData.expiry) {
      localStorage.removeItem(CACHE_PREFIX + key)
      return null
    }

    return cacheData.data
  } catch (e) {
    return null
  }
}

/**
 * 清除过期缓存
 */
export function clearExpiredCache() {
  const keysToRemove = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(CACHE_PREFIX)) {
      try {
        const cached = localStorage.getItem(key)
        if (cached) {
          const cacheData = JSON.parse(cached)
          if (Date.now() > cacheData.expiry) {
            keysToRemove.push(key)
          }
        }
      } catch (e) {
        keysToRemove.push(key)
      }
    }
  }
  keysToRemove.forEach(key => localStorage.removeItem(key))
  return keysToRemove.length
}

/**
 * 清除所有缓存
 */
export function clearAllCache() {
  const keysToRemove = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(CACHE_PREFIX)) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach(key => localStorage.removeItem(key))
  return keysToRemove.length
}

/**
 * 带缓存的fetch
 */
export async function fetchWithCache(url, options = {}, cacheKey = null, ttl = DEFAULT_TTL) {
  // 如果没有指定cacheKey，生成一个
  if (!cacheKey) {
    cacheKey = url.replace(/[^a-zA-Z0-9]/g, '_')
  }

  // 尝试从缓存获取
  const cached = getCache(cacheKey)
  if (cached) {
    return cached
  }

  // 从网络获取
  const response = await fetch(url, options)
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const data = await response.json()

  // 存入缓存
  setCache(cacheKey, data, ttl)

  return data
}

// 缓存hook
export function useLocalCache(key, fetcher, ttl = DEFAULT_TTL) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let mounted = true

    const loadData = async () => {
      // 先尝试缓存
      const cached = getCache(key)
      if (cached) {
        if (mounted) {
          setData(cached)
          setLoading(false)
        }
        return
      }

      // 获取新数据
      try {
        const freshData = await fetcher()
        if (mounted) {
          setData(freshData)
          setCache(key, freshData, ttl)
          setLoading(false)
        }
      } catch (e) {
        if (mounted) {
          setError(e)
          setLoading(false)
        }
      }
    }

    loadData()

    return () => { mounted = false }
  }, [key, ttl])

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const freshData = await fetcher()
      setData(freshData)
      setCache(key, freshData, ttl)
    } catch (e) {
      setError(e)
    }
    setLoading(false)
  }

  return { data, loading, error, refresh }
}
