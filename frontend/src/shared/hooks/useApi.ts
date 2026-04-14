import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { cpApi, recommendApi, tradeApi, backtestApi, watchlistApi, predictionApi, verifyApi, userApi, systemApi } from '../services/api'
import type { BacktestParams, WatchlistGroup } from '../types'

// 战力相关 Hooks
export function useCPTop(limit = 200) {
  return useQuery({
    queryKey: ['cp', 'top', limit],
    queryFn: () => cpApi.getTop(limit),
  })
}

export function useStockDetail(code: string) {
  return useQuery({
    queryKey: ['cp', 'stock', code],
    queryFn: () => cpApi.getStock(code),
    enabled: !!code,
  })
}

// 推荐相关 Hooks
export function useRecommendations(category: string) {
  return useQuery({
    queryKey: ['recommend', category],
    queryFn: () => recommendApi.getRecommendations(category),
  })
}

export function useSwapSuggestions() {
  return useQuery({
    queryKey: ['recommend', 'swap'],
    queryFn: () => recommendApi.getSwapSuggestions(),
  })
}

// 模拟交易 Hooks
export function useAccount() {
  return useQuery({
    queryKey: ['account'],
    queryFn: () => tradeApi.getAccount(),
  })
}

export function usePortfolio() {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: () => tradeApi.getPortfolio(),
  })
}

export function useBuyTrade() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ code, quantity }: { code: string; quantity: number }) =>
      tradeApi.buy(code, quantity),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['account'] })
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
    },
  })
}

export function useSellTrade() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ code, quantity }: { code: string; quantity: number }) =>
      tradeApi.sell(code, quantity),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['account'] })
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
    },
  })
}

// 回测 Hooks
export function useBacktest() {
  return useMutation({
    mutationFn: (params: BacktestParams) => backtestApi.runSimple(params),
  })
}

// 自选股 Hooks
export function useWatchlistGroups() {
  return useQuery({
    queryKey: ['watchlist', 'groups'],
    queryFn: () => watchlistApi.getGroups(),
  })
}

export function useSaveWatchlistGroups() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (groups: WatchlistGroup[]) => watchlistApi.saveGroups(groups),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist', 'groups'] })
    },
  })
}

// ==================== 预测分析 Hooks (v19.8) ====================

export function useGainPredictionTop(limit = 50) {
  return useQuery({
    queryKey: ['prediction', 'gain', 'top', limit],
    queryFn: () => predictionApi.getGainTop(limit),
  })
}

export function useGainPredictionStock(code: string) {
  return useQuery({
    queryKey: ['prediction', 'gain', code],
    queryFn: () => predictionApi.getGainStock(code),
    enabled: !!code,
  })
}

export function useProbabilityPredictionTop(limit = 50) {
  return useQuery({
    queryKey: ['prediction', 'probability', 'top', limit],
    queryFn: () => predictionApi.getProbabilityTop(limit),
  })
}

export function useProbabilityPredictionStock(code: string) {
  return useQuery({
    queryKey: ['prediction', 'probability', code],
    queryFn: () => predictionApi.getProbabilityStock(code),
    enabled: !!code,
  })
}

// ==================== 验证报告 Hooks (v19.8) ====================

export function useVerifyReport() {
  return useQuery({
    queryKey: ['verify', 'report'],
    queryFn: () => verifyApi.getReport(),
  })
}

export function useSwapEffectiveness() {
  return useQuery({
    queryKey: ['verify', 'swap'],
    queryFn: () => verifyApi.getSwapEffectiveness(),
  })
}

export function useGainAccuracy() {
  return useQuery({
    queryKey: ['verify', 'gain_accuracy'],
    queryFn: () => verifyApi.getGainAccuracy(),
  })
}

export function useProbabilityAccuracy() {
  return useQuery({
    queryKey: ['verify', 'probability_accuracy'],
    queryFn: () => verifyApi.getProbabilityAccuracy(),
  })
}

// ==================== 用户配置 Hooks ====================

export function useUserProfile() {
  return useQuery({
    queryKey: ['user', 'profile'],
    queryFn: () => userApi.getProfile(),
  })
}

export function useUpdateUserProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (profile: unknown) => userApi.updateProfile(profile),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user', 'profile'] })
    },
  })
}

// ==================== 系统 Hooks ====================

export function useHealth() {
  return useQuery({
    queryKey: ['system', 'health'],
    queryFn: () => systemApi.health(),
    refetchInterval: 60 * 1000, // 每分钟检查
  })
}
