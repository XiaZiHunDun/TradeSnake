# 前端模块方案 v2.2.1

> **版本**: v19.9.9 | **状态**: 部分实现 | **基于**: 专家设计方案 1-5 号文档
> **v19.8 更新**: 2026-04-09 完成预测分析模块API集成（涨幅预测、上涨概率、验证报告）

---

## 概述

前端模块是 TradeSnake 系统的用户界面层，负责数据展示、用户交互和操作执行。

---

## 输入输出

### 输入
| 来源 | 数据内容 |
|------|----------|
| backend/api | 各模块数据（战力榜、推荐、账户等） |
| backend/api | WebSocket实时行情推送 |
| 用户交互 | 点击、筛选、搜索、交易操作 |

### 输出
| 输出内容 | 使用者 |
|----------|--------|
| UI界面展示 | 用户 |
| API请求（买入/卖出/刷新等） | backend |
| 用户操作指令 | backend/simulator |

---

## 一、设计目标

### 1.1 问题诊断（当前版本）

当前前端存在以下问题：
- 版本显示混乱，无法确认当前版本
- 页面直接调用 API，缺少模块化封装
- 状态管理分散，难以维护
- 组件复用性低
- 缺少实时数据推送机制
- 缺少专业K线图表
- 大数据量渲染无虚拟滚动

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| 模块化 | 与后端5个核心模块对应 |
| 简洁高效 | 仅做数据展示和交互，不做复杂计算 |
| 可维护 | 统一状态管理，清晰的数据流 |
| 专业金融体验 | 参考 Expert Design 2/3/5 的专业金融UI |
| 性能优先 | 虚拟滚动、WebSocket、Web Workers |

### 1.3 专家设计参考

本方案参考以下专家设计文档：
- **专家设计1**: 基础模块结构（Vue3/React + ECharts + 自选股）
- **专家设计2**: React + TypeScript + Zustand + WebSocket + 虚拟滚动
- **专家设计3**: 专业金融UI（K线工作室，资金风向、7大模块）
- **专家设计4**: Vue3 + Composition API + Web Workers + 预警系统
- **专家设计5**: 完整体系（Ant Design + Tailwind + 组件层级 + 性能优化）

### 1.4 技术选型

| 层级 | 推荐技术 | 说明 |
|------|---------|------|
| **框架** | React 18 + TypeScript | 类型安全、生态成熟 |
| **构建** | Vite | 快速热更新 |
| **图表** | ECharts (辅助图表) | 战力图表、收益曲线 |
| **状态** | Zustand + TanStack Query | 轻量状态 + 服务端缓存 |
| **实时** | WebSocket | 行情推送 |
| **UI** | Ant Design 5 + Tailwind CSS | 业务组件 + 原子化样式 |
| **虚拟滚动** | @tanstack/react-virtual | 大数据量列表 |

---

## 二、模块结构

### 2.1 目录设计

```
frontend/src/
├── modules/                      # 功能模块（按业务划分）
│   ├── market/                    # 市场行情模块
│   │   ├── TopList.jsx           # 战力榜
│   │   ├── MarketDashboard.jsx   # 大盘指数看板
│   │   └── components/           # 市场子组件
│   │
│   ├── stock/                    # 个股详情模块
│   │   ├── StockDetail.jsx       # 个股详情页（仅展示数据，无K线）
│   │   └── components/           # 个股子组件
│   │
│   ├── watchlist/                # 自选股模块
│   │   ├── Watchlist.jsx         # 自选股列表
│   │   ├── WatchlistGroup.jsx    # 分组管理
│   │   └── components/           # 自选股子组件
│   │
│   ├── portfolio/                # 投资组合模块（模拟交易）
│   │   ├── TradingCenter.jsx     # 交易中心
│   │   ├── Portfolio.jsx         # 持仓管理
│   │   ├── Account.jsx           # 账户管理
│   │   └── components/           # 组合子组件
│   │
│   ├── recommender/              # 推荐模块
│   │   ├── Recommend.jsx         # 推荐页面
│   │   ├── SwapSuggest.jsx       # 换股建议
│   │   └── components/          # 推荐子组件
│   │
│   └── backtester/              # 回测模块
│       ├── Backtest.jsx          # 回测页面
│       └── components/           # 回测子组件
│
├── shared/                       # 共享模块
│   ├── components/                # 共享组件
│   │   ├── atoms/                # 原子组件
│   │   │   ├── Button.jsx
│   │   │   ├── Input.jsx
│   │   │   ├── Badge.jsx
│   │   │   └── Tag.jsx
│   │   ├── molecules/            # 分子组件
│   │   │   ├── StockCard.jsx     # 股票卡片
│   │   │   ├── PriceDisplay.jsx  # 价格展示
│   │   │   ├── SearchBar.jsx     # 搜索栏
│   │   │   └── PercentageBar.jsx  # 涨跌幅条
│   │   └── organisms/            # 有机组件
│   │       ├── Header.jsx
│   │       ├── CPChart.jsx       # 战力图表
│   │       └── SortableTable.jsx # 可排序表格
│   │
│   ├── hooks/                    # 共享Hooks
│   │   ├── useApi.js             # API调用（基于TanStack Query）
│   │   ├── useSettings.js        # 设置管理
│   │   ├── useAccount.js         # 账户状态
│   │   ├── useWebSocket.js       # WebSocket连接
│   │   └── useVirtualScroll.js   # 虚拟滚动
│   │
│   ├── stores/                   # Zustand状态管理
│   │   ├── quotesStore.js        # 行情状态
│   │   ├── watchlistStore.js     # 自选股状态
│   │   └── uiStore.js            # UI状态
│   │
│   ├── services/                 # API服务
│   │   ├── api.js                # REST API客户端
│   │   └── websocket.js          # WebSocket客户端
│   │
│   ├── utils/                    # 工具函数
│   │   └── format.js             # 格式化
│   │
│   └── constants/                 # 常量
│       └── theme.js              # 主题配置
│
├── App.jsx                       # 主入口
├── main.jsx                      # React渲染
└── index.css                     # 全局样式
```

### 2.2 与后端模块对应

| 前端模块 | 对应后端模块 | 主要功能 |
|---------|------------|---------|
| `market/*` | `engine/*` | 战力榜、市场行情 |
| `stock/*` | `engine/*` | 个股数据展示（无K线） |
| `watchlist/*` | - | 自选股管理 |
| `portfolio/*` | `simulator/*` | 模拟交易 |
| `recommender/*` | `recommender/*` | 买卖建议 |
| `backtester/*` | `backtester/*` | 回测验证 |

---

## 三、API层与实时数据

### 3.1 REST API客户端（基于TanStack Query）

```typescript
// shared/services/api.ts
import { QueryClient } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,      // 30秒内不重新请求
      cacheTime: 5 * 60 * 1000,  // 缓存5分钟
      retry: 2,
      refetchOnWindowFocus: false
    }
  }
})

const baseUrl = '/api'

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl}${endpoint}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options
  })
  if (!res.ok) throw new Error(`API Error: ${res.status}`)
  return res.json()
}

// API方法
export const api = {
  // 战力相关
  getCPTop: (limit = 200) => request<CPTopResponse>(`/cp/top?limit=${limit}`),
  getStockDetail: (code: string) => request<StockDetail>(`/cp/stock/${code}`),

  // 推荐相关
  getRecommendations: (category: string) => request<Recommendation[]>(`/recommend?category=${category}`),
  getSwapSuggestions: (holdings: Holding[]) => request<SwapSuggestion[]>(
    '/recommend/swap',
    { method: 'POST', body: JSON.stringify({ holdings }) }
  ),

  // 模拟交易
  getAccount: () => request<Account>('/account'),
  getPortfolio: () => request<Portfolio>('/portfolio'),
  buy: (code: string, quantity: number, price?: number) => request<TradeResult>(
    '/trade/buy',
    { method: 'POST', body: JSON.stringify({ code, quantity, price }) }
  ),
  sell: (code: string, quantity: number, price?: number) => request<TradeResult>(
    '/trade/sell',
    { method: 'POST', body: JSON.stringify({ code, quantity, price }) }
  ),

  // 回测
  runBacktest: (params: BacktestParams) => request<BacktestResult>(
    '/backtest',
    { method: 'POST', body: JSON.stringify(params) }
  ),

  // 市场统计
  getMarketStats: () => request<MarketStats>('/stats/market')
}

export { queryClient }
```

### 3.2 WebSocket实时数据（参考专家设计2/3）

```typescript
// shared/services/websocket.ts
type WSMessage =
  | { type: 'quote'; data: Quote }       // 行情快照
  | { type: 'kline'; data: KlineBar }    // K线增量
  | { type: 'trade'; data: Trade }        // 逐笔成交
  | { type: 'depth'; data: DepthData }    // 盘口深度

class WebSocketService {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private subscribers = new Map<string, Set<(data: WSMessage) => void>>()

  connect(url: string = 'ws://localhost:8001/ws') {
    this.ws = new WebSocket(url)
    this.ws.onmessage = (event) => {
      const message: WSMessage = JSON.parse(event.data)
      this.notifySubscribers(message.type, message.data)
    }
    this.ws.onclose = () => this.reconnect()
    this.ws.onerror = () => this.reconnect()
  }

  subscribe(topic: string, callback: (data: WSMessage) => void) {
    if (!this.subscribers.has(topic)) {
      this.subscribers.set(topic, new Set())
    }
    this.subscribers.get(topic)!.add(callback)
    this.ws?.send(JSON.stringify({ action: 'subscribe', topic }))
  }

  unsubscribe(topic: string, callback: (data: WSMessage) => void) {
    this.subscribers.get(topic)?.delete(callback)
    this.ws?.send(JSON.stringify({ action: 'unsubscribe', topic }))
  }

  private notifySubscribers(topic: string, data: unknown) {
    this.subscribers.get(topic)?.forEach(cb => cb(data as WSMessage))
  }

  private reconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      setTimeout(() => {
        this.reconnectAttempts++
        this.connect()
      }, Math.min(1000 * 2 ** this.reconnectAttempts, 30000))
    }
  }
}

export const wsService = new WebSocketService()
```

### 3.3 Zustand状态管理（参考专家设计2/5）

```typescript
// shared/stores/quotesStore.ts
import { create } from 'zustand'

interface Quote {
  code: string
  price: number
  change: number
  changePercent: number
  volume: number
  timestamp: number
}

interface QuotesState {
  quotes: Record<string, Quote>
  updateQuote: (code: string, data: Partial<Quote>) => void
  subscribe: (codes: string[]) => void
}

export const useQuotesStore = create<QuotesState>((set, get) => ({
  quotes: {},

  updateQuote: (code, data) => {
    set(state => ({
      quotes: {
        ...state.quotes,
        [code]: { ...state.quotes[code], ...data, timestamp: Date.now() }
      }
    }))
  },

  subscribe: (codes) => {
    codes.forEach(code => {
      if (!get().quotes[code]) {
        // 初始化订阅
        wsService.subscribe(`quote:${code}`, (msg) => {
          if (msg.type === 'quote') {
            get().updateQuote(code, msg.data)
          }
        })
      }
    })
  }
}))
```

### 3.4 虚拟滚动（参考专家设计2/4）

```typescript
// shared/hooks/useVirtualScroll.ts
import { useVirtualizer } from '@tanstack/react-virtual'

export function useVirtualScroll<T>(items: T[], rowHeight = 48) {
  const parentRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 10  // 预渲染10条
  })

  return { parentRef, virtualizer }
}
```
