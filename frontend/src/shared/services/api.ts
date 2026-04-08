import { QueryClient } from '@tanstack/react-query'
import type {
  CPTopResponse,
  StockDetail,
  AccountResponse,
  PortfolioResponse,
  TradeResult,
  TradeHistoryResponse,
  RecommendResponse,
  BacktestParams,
  BacktestResult,
  WatchlistGroup,
} from '../types'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30秒内不重新请求
      gcTime: 5 * 60 * 1000, // 缓存5分钟
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})

const API_BASE = '/api'

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(error.message || `API Error: ${res.status}`)
  }
  return res.json()
}

// 战力相关 API
export const cpApi = {
  getTop: (limit = 200): Promise<CPTopResponse> =>
    request<CPTopResponse>(`/cp/top?limit=${limit}`),

  getStock: (code: string): Promise<StockDetail> =>
    request<StockDetail>(`/cp/stock/${code}`),
}

// 推荐相关 API
export const recommendApi = {
  getRecommendations: (category: string): Promise<RecommendResponse> =>
    request<RecommendResponse>(`/cp/recommend?category=${category}`),

  getSwapSuggestions: (principal?: number): Promise<unknown[]> =>
    request<unknown[]>(`/cp/swap?principal=${principal || 100000}`),
}

// 模拟交易 API
export const tradeApi = {
  getAccount: (): Promise<AccountResponse> => request<AccountResponse>('/account'),

  getPortfolio: (): Promise<PortfolioResponse> =>
    request<PortfolioResponse>('/portfolio'),

  buy: (code: string, quantity: number): Promise<TradeResult> =>
    request<TradeResult>('/trade/buy', {
      method: 'POST',
      body: JSON.stringify({ code, quantity }),
    }),

  sell: (code: string, quantity: number): Promise<TradeResult> =>
    request<TradeResult>('/trade/sell', {
      method: 'POST',
      body: JSON.stringify({ code, quantity }),
    }),

  getTrades: (): Promise<TradeHistoryResponse> => request<TradeHistoryResponse>('/trades'),
}

// 回测 API
export const backtestApi = {
  runSimple: (params: BacktestParams): Promise<BacktestResult> =>
    request<BacktestResult>('/backtest/simple', {
      method: 'GET',
    }),
}

// 自选股 API (本地存储)
export const watchlistApi = {
  getGroups: (): Promise<WatchlistGroup[]> => {
    const stored = localStorage.getItem('watchlist_groups')
    return Promise.resolve(stored ? JSON.parse(stored) : [])
  },

  saveGroups: (groups: WatchlistGroup[]): Promise<void> => {
    localStorage.setItem('watchlist_groups', JSON.stringify(groups))
    return Promise.resolve()
  },
}

// 版本检查
export const systemApi = {
  health: (): Promise<{ version: string }> => request<{ version: string }>('/health'),
}
