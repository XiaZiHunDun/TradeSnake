import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { WatchlistGroup, QuoteUpdate } from '../types'

// UI Store - 管理全局UI状态
interface UIState {
  sidebarCollapsed: boolean
  theme: 'dark' | 'light'
  toggleSidebar: () => void
  toggleTheme: () => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      theme: 'dark',
      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
    }),
    { name: 'ui-store' }
  )
)

// Watchlist Store - 自选股管理
interface WatchlistState {
  groups: WatchlistGroup[]
  selectedGroupId: string | null
  addGroup: (name: string, color?: string) => void
  removeGroup: (id: string) => void
  updateGroup: (id: string, updates: Partial<WatchlistGroup>) => void
  addToGroup: (groupId: string, code: string) => void
  removeFromGroup: (groupId: string, code: string) => void
  selectGroup: (id: string | null) => void
}

export const useWatchlistStore = create<WatchlistState>()(
  persist(
    (set) => ({
      groups: [],
      selectedGroupId: null,
      addGroup: (name, color) =>
        set((s) => ({
          groups: [
            ...s.groups,
            { id: Date.now().toString(), name, codes: [], color },
          ],
        })),
      removeGroup: (id) =>
        set((s) => ({
          groups: s.groups.filter((g) => g.id !== id),
          selectedGroupId: s.selectedGroupId === id ? null : s.selectedGroupId,
        })),
      updateGroup: (id, updates) =>
        set((s) => ({
          groups: s.groups.map((g) => (g.id === id ? { ...g, ...updates } : g)),
        })),
      addToGroup: (groupId, code) =>
        set((s) => ({
          groups: s.groups.map((g) =>
            g.id === groupId && !g.codes.includes(code)
              ? { ...g, codes: [...g.codes, code] }
              : g
          ),
        })),
      removeFromGroup: (groupId, code) =>
        set((s) => ({
          groups: s.groups.map((g) =>
            g.id === groupId ? { ...g, codes: g.codes.filter((c) => c !== code) } : g
          ),
        })),
      selectGroup: (id) => set({ selectedGroupId: id }),
    }),
    { name: 'watchlist-store' }
  )
)

// Quotes Store - 实时行情（内存存储）
interface QuotesState {
  quotes: Record<string, QuoteUpdate>
  updateQuote: (code: string, data: Partial<QuoteUpdate>) => void
  updateQuotes: (updates: Record<string, Partial<QuoteUpdate>>) => void
}

export const useQuotesStore = create<QuotesState>()((set) => ({
  quotes: {},
  updateQuote: (code, data) =>
    set((s) => ({
      quotes: {
        ...s.quotes,
        [code]: { ...s.quotes[code], ...data, timestamp: Date.now() } as QuoteUpdate,
      },
    })),
  updateQuotes: (updates) =>
    set((s) => ({
      quotes: {
        ...s.quotes,
        ...Object.fromEntries(
          Object.entries(updates).map(([code, data]) => [
            code,
            { ...s.quotes[code], ...data, timestamp: Date.now() } as QuoteUpdate,
          ])
        ),
      },
    })),
}))
