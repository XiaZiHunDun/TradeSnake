import { QueryClient } from '@tanstack/react-query'
import type {
  CPTopResponse,
  StockDetail,
  AccountResponse,
  PortfolioResponse,
  TradeExecutionDetail,
  TradeHistoryResponse,
  RecommendResponse,
  BacktestParams,
  BacktestResult,
  WatchlistGroup,
  // v19.8 Prediction Types
  GainPrediction,
  GainPredictionResponse,
  ProbabilityPrediction,
  ProbabilityPredictionResponse,
  VerifyReport,
  UserProfileResponse,
  HealthResponse,
  SwapSuggestion,
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

  getSwapSuggestions: (principal?: number): Promise<SwapSuggestion[]> =>
    request<SwapSuggestion[]>(`/cp/swap?principal=${principal || 100000}`),
}

// 模拟交易 API
export const tradeApi = {
  getAccount: (): Promise<AccountResponse> => request<AccountResponse>('/account'),

  getPortfolio: (): Promise<PortfolioResponse> =>
    request<PortfolioResponse>('/portfolio'),

  buy: (code: string, quantity: number): Promise<TradeExecutionDetail> =>
    request<TradeExecutionDetail>('/trade/buy', {
      method: 'POST',
      body: JSON.stringify({ code, quantity }),
    }),

  sell: (code: string, quantity: number): Promise<TradeExecutionDetail> =>
    request<TradeExecutionDetail>('/trade/sell', {
      method: 'POST',
      body: JSON.stringify({ code, quantity }),
    }),

  getTrades: (): Promise<TradeHistoryResponse> => request<TradeHistoryResponse>('/trades'),
}

// 回测 API
export const backtestApi = {
  runSimple: (params: BacktestParams): Promise<BacktestResult> => {
    const searchParams = new URLSearchParams()
    if (params.start_date) searchParams.set('start_date', params.start_date)
    if (params.end_date) searchParams.set('end_date', params.end_date)
    if (params.holding_days) searchParams.set('holding_days', String(params.holding_days))
    if (params.top_n) searchParams.set('top_n', String(params.top_n))
    const query = searchParams.toString()
    return request<BacktestResult>(`/backtest/simple${query ? `?${query}` : ''}`)
  },
}

// 自选股 API (本地存储)
export const watchlistApi = {
  getGroups: (): Promise<WatchlistGroup[]> => {
    const stored = localStorage.getItem('watchlist_groups')
    try {
      return Promise.resolve(stored ? JSON.parse(stored) : [])
    } catch {
      return Promise.resolve([])
    }
  },

  saveGroups: (groups: WatchlistGroup[]): Promise<void> => {
    localStorage.setItem('watchlist_groups', JSON.stringify(groups))
    return Promise.resolve()
  },
}

// 版本检查
export const systemApi = {
  health: (): Promise<HealthResponse> => request<HealthResponse>('/health'),
}

// 预测分析 API (v19.8)
export const predictionApi = {
  getGainTop: (limit = 50): Promise<GainPredictionResponse> =>
    request<GainPredictionResponse>(`/prediction/gain/top?limit=${limit}`),

  getGainStock: (code: string): Promise<GainPrediction> =>
    request<GainPrediction>(`/prediction/gain/${code}`),

  getProbabilityTop: (limit = 50): Promise<ProbabilityPredictionResponse> =>
    request<ProbabilityPredictionResponse>(`/prediction/probability/top?limit=${limit}`),

  getProbabilityStock: (code: string): Promise<ProbabilityPrediction> =>
    request<ProbabilityPrediction>(`/prediction/probability/${code}`),
}

// 验证报告 API (v19.8)
export const verifyApi = {
  getReport: (): Promise<VerifyReport> => request<VerifyReport>('/verify/report'),
  getSwapEffectiveness: (): Promise<unknown> => request<unknown>('/verify/swap'),
  getCPAccuracy: (): Promise<unknown> => request<unknown>('/verify/cp_accuracy'),
  getGainAccuracy: (): Promise<unknown> => request<unknown>('/verify/gain_accuracy'),
  getProbabilityAccuracy: (): Promise<unknown> => request<unknown>('/verify/probability_accuracy'),
}

// 用户配置 API
export const userApi = {
  getProfile: (): Promise<UserProfileResponse> => request<UserProfileResponse>('/user/profile'),
  updateProfile: (profile: unknown): Promise<{ success: boolean }> =>
    request<{ success: boolean }>('/user/profile', {
      method: 'PUT',
      body: JSON.stringify(profile),
    }),
}
