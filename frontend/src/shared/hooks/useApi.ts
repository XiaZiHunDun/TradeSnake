import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { cpApi, recommendApi, tradeApi, backtestApi, watchlistApi } from '../services/api'
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
