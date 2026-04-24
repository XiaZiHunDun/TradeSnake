# 前端模块方案 v2.2.1

## 概述

前端模块是 TradeSnake 系统的用户界面层，负责数据展示、用户交互和操作执行。

**版本**: v19.9.9 | **状态**: 部分实现 | **基于**: 专家设计方案 1-5 号文档

> **v19.8 更新**: 2026-04-09 完成预测分析模块API集成（涨幅预测、上涨概率、验证报告）

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
- **专家设计3**: 专业金融UI（K线工作室、资金风向、7大模块）
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
│   ├── services/                # API服务
│   │   ├── api.js                # REST API客户端
│   │   └── websocket.js           # WebSocket客户端
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
```

## 四、页面与布局设计

### 4.1 页面清单

| 页面 | 路由 | 模块 | 功能 |
|------|------|------|------|
| 首页/战力榜 | `/` | market | 展示战力排名，大盘指数看板 |
| 市场行情 | `/market` | market | 股票列表、筛选排序 |
| 个股详情 | `/stock/:code` | stock | 查看股票详细数据 |
| 自选股 | `/watchlist` | watchlist | 自选管理、分组、对比 |
| 模拟交易 | `/portfolio` | portfolio | 持仓、交易、账户 |
| 智能推荐 | `/recommend` | recommender | 买卖建议、换股建议 |
| 回测验证 | `/backtest` | backtester | 策略回测 |
| 设置 | `/settings` | - | 主题、数据刷新频率 |

### 4.2 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  Header (Logo + 大盘速览 + 搜索框)                           │
├────────┬─────────────────────────────────────────────────────┤
│        │                                                      │
│ 侧边栏 │              主内容区                                │
│        │                                                      │
│ · 首页 │   ┌──────────────────────────────────────────┐    │
│ · 行情 │   │                                          │    │
│ · 自选 │   │         战力榜 / 列表 / 详情              │    │
│ · 组合 │   │                                          │    │
│ · 推荐 │   └──────────────────────────────────────────┘    │
│ · 回测 │                                                      │
└────────┴─────────────────────────────────────────────────────┘
```

### 4.3 响应式布局策略

| 场景 | 布局 |
|------|------|
| 桌面端 | 双栏布局（侧边栏 + 主内容） |
| 平板端 | 可折叠侧边栏 + 主内容 |
| 移动端 | 单栏堆叠，底部Tab导航 |

### 4.4 个股详情页（无K线）

个股详情页仅展示关键数据，不包含K线图表：

```
┌─────────────────────────────────────────────┐
│  股票名称 (600036)        [ +自选 ]          │
├─────────────────────────────────────────────┤
│                                             │
│  现价: 45.23  涨跌: +1.25 (+2.84%)         │
│                                             │
│  ──────── 基本面 ────────                    │
│  市盈率(PE): 12.5  │  市净率(PB): 1.8       │
│  总市值: 1.2万亿   │  流通市值: 8000亿       │
│                                             │
│  ──────── 战力数据 ────────                  │
│  战力值: 85.6  │  成长分: 78  │  价值分: 92  │
│  质量分: 88    │  动量分: 75  │  风险系数: 0.3│
│                                             │
│  ──────── 财务摘要 ────────                  │
│  净利润增长率: +15.2%                        │
│  营收增长率: +8.5%                          │
│  ROE: 14.2%                                 │
│                                             │
└─────────────────────────────────────────────┘
```

## 五、组件层级设计（参考专家设计5）

### 5.1 组件分类体系

| 层级 | 说明 | 示例 |
|------|------|------|
| **原子组件 (Atoms)** | 最基础UI单元，无业务逻辑 | Button, Input, Badge, Tag, Switch |
| **分子组件 (Molecules)** | 原子组合，有独立功能单元 | StockCard, PriceDisplay, SearchBar |
| **有机组件 (Organisms)** | 完整业务功能区块 | Header, CPChart, SortableTable |

### 5.2 股票卡片组件

```typescript
// shared/components/molecules/StockCard.tsx
interface StockCardProps {
  stock: {
    code: string
    name: string
    price: number
    change: number
    changePercent: number
    volume?: number
    turnoverRate?: number
  }
  size?: 'small' | 'medium' | 'large'
  onClick?: (code: string) => void
  onAddWatchlist?: (code: string) => void
}

export function StockCard({ stock, size = 'medium', onClick, onAddWatchlist }: StockCardProps) {
  const isUp = stock.change >= 0
  const colorClass = isUp ? 'text-red-500' : 'text-green-500'  // 中国股市配色

  return (
    <div className={`stock-card stock-card--${size}`} onClick={() => onClick?.(stock.code)}>
      <div className="stock-name">{stock.name}</div>
      <div className="stock-code">{stock.code}</div>
      <PriceDisplay price={stock.price} change={stock.change} />
      <div className={`change-percent ${colorClass}`}>
        {isUp ? '+' : ''}{stock.changePercent.toFixed(2)}%
      </div>
      {onAddWatchlist && (
        <button onClick={(e) => { e.stopPropagation(); onAddWatchlist(stock.code) }}>
          +自选
        </button>
      )}
    </div>
  )
}
```

### 5.3 涨跌幅展示组件

```typescript
// shared/components/molecules/PriceDisplay.tsx
interface PriceDisplayProps {
  price: number
  change?: number
  changePercent?: number
  previousPrice?: number
  animated?: boolean  // 价格变化动画
}

export function PriceDisplay({ price, change, changePercent, animated = true }: PriceDisplayProps) {
  const isUp = (change ?? 0) >= 0
  const displayChange = change ?? (price - (previousPrice ?? price))

  return (
    <div className={`price-display ${isUp ? 'price-display--up' : 'price-display--down'}`}>
      <span className="price">{price.toFixed(2)}</span>
      <span className="change">
        {isUp ? '▲' : '▼'} {Math.abs(displayChange).toFixed(2)}
      </span>
      <span className="percent">
        ({isUp ? '+' : ''}{((changePercent ?? 0)).toFixed(2)}%)
      </span>
    </div>
  )
}
```

### 5.4 可排序表格组件

```typescript
// shared/components/organisms/SortableTable.tsx
interface Column<T> {
  key: keyof T
  title: string
  sortable?: boolean
  render?: (value: T[keyof T], row: T) => ReactNode
  width?: number
}

interface SortableTableProps<T> {
  data: T[]
  columns: Column<T>[]
  onRowClick?: (row: T) => void
  virtualized?: boolean  // 大数据量时启用虚拟滚动
}

export function SortableTable<T>({ data, columns, onRowClick, virtualized = true }: SortableTableProps<T>) {
  const [sortKey, setSortKey] = useState<keyof T | null>(null)
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  const sortedData = useMemo(() => {
    if (!sortKey) return data
    return [...data].sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0
      return sortOrder === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortOrder])

  const { parentRef, virtualizer } = useVirtualScroll(sortedData, 48)

  return (
    <div ref={parentRef} className="h-96 overflow-auto">
      <table className="w-full">
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key as string} onClick={() => col.sortable && handleSort(col.key)}>
                {col.title}
                {sortKey === col.key && (sortOrder === 'asc' ? ' ▲' : ' ▼')}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {virtualized ? (
            virtualizer.getVirtualItems().map(virtualRow => {
              const row = sortedData[virtualRow.index]
              return <tr key={virtualRow.key} onClick={() => onRowClick?.(row)}>
                {columns.map(col => (
                  <td key={col.key as string}>{col.render?.(row[col.key], row) ?? row[col.key]}</td>
                ))}
              </tr>
            })
          ) : (
            sortedData.map((row, i) => <tr key={i} onClick={() => onRowClick?.(row)}>
              {columns.map(col => <td key={col.key as string}>{col.render?.(row[col.key], row) ?? row[col.key]}</td>)}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
```

## 六、状态管理方案（参考专家设计2/5）

### 6.1 Zustand Store设计

```typescript
// shared/stores/index.ts
export { useQuotesStore } from './quotesStore'
export { useWatchlistStore } from './watchlistStore'
export { usePortfolioStore } from './portfolioStore'
export { useUIStore } from './uiStore'
```

### 6.2 状态划分

| Store | 管理内容 | 持久化 |
|-------|---------|--------|
| `quotesStore` | 实时行情数据 | 否（内存） |
| `watchlistStore` | 自选股列表、分组 | localStorage |
| `portfolioStore` | 持仓、账户、交易记录 | localStorage |
| `uiStore` | 主题、侧边栏状态、弹窗 | localStorage |

### 6.3 缓存策略

| 数据类型 | 缓存时间 | 说明 |
|---------|---------|------|
| 实时行情 | 5-30秒 | 高频更新，不长时间缓存 |
| K线历史 | 5-30分钟 | 中频更新 |
| 财务数据 | 1小时+ | 低频更新 |
| 自选股/设置 | 永久 | localStorage |

### 6.4 性能优化要点

| 场景 | 策略 |
|------|------|
| K线高频更新 | requestAnimationFrame + 节流100ms |
| 股票列表(3000+) | 虚拟滚动，只渲染可视区域 |
| 指标计算 | Web Worker后台计算 |
| 路由切换 | React.lazy + Suspense懒加载 |
| 数据预加载 | 预加载排名靠前股票详情 |

## 七、主题与UI设计（参考专家设计2/3/5）

### 7.1 专业金融配色方案

```css
/* index.css - CSS Variables */
:root {
  /* 主背景层次 */
  --bg-primary: #0a0e17;      /* 最深背景：主背景 */
  --bg-secondary: #111827;    /* 次背景：卡片底色 */
  --bg-tertiary: #1a2332;     /* 第三层：悬浮面板 */
  --bg-hover: #1f2937;        /* 悬停状态 */

  /* 涨跌色（中国股市惯例：红涨绿跌） */
  --accent-up: #ef4444;       /* 涨：红色 */
  --accent-down: #22c55e;     /* 跌：绿色 */
  --accent-highlight: #3b82f6; /* 高亮：蓝色 */

  /* 文字层次 */
  --text-primary: #f9fafb;    /* 主文字 */
  --text-secondary: #9ca3af;  /* 次文字 */
  --text-muted: #6b7280;      /* 弱化文字 */

  /* 边框 */
  --border: #1f2937;
  --border-light: #374151;

  /* 功能色 */
  --success: #10b981;
  --warning: #f59e0b;
  --error: #ef4444;
  --info: #3b82f6;
}

/* 亮色主题（可选） */
[data-theme="light"] {
  --bg-primary: #ffffff;
  --bg-secondary: #f9fafb;
  --bg-tertiary: #f3f4f6;
  --text-primary: #111827;
  --text-secondary: #6b7280;
  --border: #e5e7eb;
}
```

### 7.2 可访问性

| 要求 | 实现方式 |
|------|---------|
| 语义化标签 | `<header>`, `<main>`, `<aside>`, `<nav>`, `<table>` |
| 键盘导航 | Tab切换焦点，Enter触发操作，方向键导航 |
| 屏幕阅读器 | ARIA标签 + ARIA Live Regions |
| 焦点指示 | 清晰的focus样式 |

### 7.2 字体规范

| 用途 | 字体 | 说明 |
|------|------|------|
| 标题 | Inter, system-ui | 清晰现代 |
| 数据/代码 | JetBrains Mono, monospace | 等宽，数字对齐 |
| 中文正文 | "PingFang SC", "Microsoft YaHei" | 系统无衬线 |

### 7.3 间距系统

| 名称 | 值 | 用途 |
|------|-----|------|
| xs | 4px | 紧凑间距 |
| sm | 8px | 元素内间距 |
| md | 16px | 组件间距 |
| lg | 24px | 模块内间距 |
| xl | 32px | 区块间距 |
| 2xl | 48px | 页面间距 |

### 7.4 交互反馈

| 场景 | 处理方式 |
|------|---------|
| 数据更新 | 价格闪烁动画（背景色渐变） |
| 加载中 | 骨架屏 (Skeleton) |
| 错误 | 错误提示 + 重试按钮 |
| 空状态 | 空状态提示 + 引导操作 |
| 涨跌变化 | 颜色过渡动画 |

## 八、API端点对应

### 8.1 核心API（战力、推荐、交易）

| 前端功能 | API端点 | 方法 | 状态 |
|---------|---------|------|------|
| 战力榜 | `/api/cp/top` | GET | ✅ |
| 单股详情 | `/api/cp/stock/{code}` | GET | ✅ |
| 战力解读 | `/api/cp/explain/{code}` | GET | ✅ |
| 推荐股票 | `/api/cp/recommend` | GET | ✅ |
| 换股建议 | `/api/cp/swap` | GET | ✅ |
| 账户信息 | `/api/account` | GET | ✅ |
| 持仓明细 | `/api/portfolio` | GET | ✅ |
| 买入 | `/api/trade/buy` | POST | ✅ |
| 卖出 | `/api/trade/sell` | POST | ✅ |
| 交易历史 | `/api/trades` | GET | ✅ |
| 用户配置 | `/api/user/profile` | GET/PUT | ✅ |

### 8.2 预测分析API（v19.8 新增）

| 前端功能 | API端点 | 方法 | 状态 |
|---------|---------|------|------|
| 涨幅预测TOP N | `/api/prediction/gain/top` | GET | ✅ 已集成 |
| 单股涨幅预测 | `/api/prediction/gain/{code}` | GET | ✅ 已集成 |
| 上涨概率TOP N | `/api/prediction/probability/top` | GET | ✅ 已集成 |
| 单股上涨概率 | `/api/prediction/probability/{code}` | GET | ✅ 已集成 |

### 8.3 验证报告API（v19.8 新增）

| 前端功能 | API端点 | 方法 | 状态 |
|---------|---------|------|------|
| 综合验证报告 | `/api/verify/report` | GET | ✅ |
| 涨幅预测验证 | `/api/verify/gain_accuracy` | GET | ✅ 已集成 |
| 概率预测验证 | `/api/verify/probability_accuracy` | GET | ✅ 已集成 |
| 换股效果验证 | `/api/verify/swap` | GET | ✅ |
| 战力预测验证 | `/api/verify/cp_accuracy` | GET | ✅ |

### 8.4 回测与风险API

| 前端功能 | API端点 | 方法 | 状态 |
|---------|---------|------|------|
| 回测-简单 | `/api/backtest/simple` | GET | ✅ |
| 回测-对比 | `/api/backtest/compare` | GET | ✅ |
| 回测-基准 | `/api/backtest/benchmark` | GET | ✅ |
| 风险报告 | `/api/risk/report` | GET | ✅ |
| 解套计算 | `/api/risk/break-even/{code}` | GET | ✅ |

### 8.5 历史与系统API

| 前端功能 | API端点 | 方法 | 状态 |
|---------|---------|------|------|
| 战力历史 | `/api/history/{code}` | GET | ✅ |
| 战力变化 | `/api/history/changes` | GET | ✅ |
| 历史榜单 | `/api/history/rankings` | GET | ✅ |
| 健康检查 | `/api/health` | GET | ✅ |
| 数据刷新 | `/api/refresh` | POST | ✅ |
| 快照记录 | `/api/snapshot/record` | POST | ✅ |

## 九、版本管理

### 9.1 版本显示

在页面底部显示版本信息：
```
TradeSnake v2.2 | 后端 v19.8 | 2026-04-08
```

### 9.2 版本同步

```typescript
// shared/constants/version.ts
export const FRONTEND_VERSION = '2.0.0'
export const BACKEND_MIN_VERSION = '19.8.0'

interface VersionInfo {
  frontend: string
  backend: string
  status: 'ok' | 'outdated' | 'unknown'
}

// 版本检查（启动时）
async function checkVersion(): Promise<VersionInfo> {
  try {
    const res = await fetch('/api/health')
    const data = await res.json()
    const backendVersion = data.version || 'unknown'
    const status = compareVersions(backendVersion, BACKEND_MIN_VERSION) >= 0 ? 'ok' : 'outdated'
    return { frontend: FRONTEND_VERSION, backend: backendVersion, status }
  } catch {
    return { frontend: FRONTEND_VERSION, backend: 'unknown', status: 'unknown' }
  }
}
```

## 十、开发规范

### 10.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 组件 | PascalCase | `StockCard.tsx` |
| TypeScript类型 | PascalCase | `StockDetail`, `QuoteData` |
| Hooks | camelCase，use前缀 | `useApi.ts`, `useWebSocket.ts` |
| 工具函数 | camelCase | `formatDate.ts`, `formatCurrency.ts` |
| 样式类 | kebab-case | `stock-card` |
| 常量 | UPPER_SNAKE_CASE | `MAX_RECONNECT_ATTEMPTS` |

### 10.2 代码组织

```
每个模块目录结构：
module/
├── index.ts                # 导出
├── Page.tsx                # 页面组件
├── components/            # 子组件
│   ├── SubComponent1.tsx
│   └── SubComponent2.tsx
├── hooks/                  # 本地hooks
│   └── useLocalHook.ts
└── styles/                 # 本地样式（可选）
    └── page.module.css
```

### 10.3 代码质量

| 要求 | 工具 |
|------|------|
| TypeScript | 严格模式，禁止 `any` |
| 代码格式 | ESLint + Prettier |
| 组件测试 | Vitest + React Testing Library |

### 10.4 开发阶段建议

| 阶段 | 内容 | 周期 | 优先级 |
|------|------|------|--------|
| **Phase 1** | 基础框架 + 项目结构 + API客户端 + 战力榜 | 2周 | P0 |
| **Phase 2** | 个股详情 + 自选股管理 + WebSocket | 2周 | P0 |
| **Phase 3** | 模拟交易（交易中心 + 持仓 + 账户） | 2周 | P1 |
| **Phase 4** | 推荐模块 + 回测模块 | 2周 | P1 |
| **Phase 5** | 性能优化 + 响应式适配 + 筛选排序 | 1周 | P2 |

## 十一、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v2.2.1 | 2026-04-09 | 集成 v19.8 预测分析模块API（涨幅预测、上涨概率、验证报告） |
| v2.2 | 2026-04-08 | 补充预测模块文档框架，状态改为"部分实现" |
| v2.1 | 2026-04-07 | 补充预警系统、画线工具、资金流向可视化、选股器、涨跌色方案、可访问性 |
| v2.0 | 2026-04-07 | 全面升级：TypeScript、WebSocket、K线图、虚拟滚动、Zustand、组件层级体系 |
| v1.0 | 2026-04-07 | 初始方案设计 |

## 十二、相关文档

- [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) - 项目总览
- [ENGINE_ARCHITECTURE.md](./ENGINE_ARCHITECTURE.md) - 分析引擎
- [RECOMMENDER_ARCHITECTURE.md](./RECOMMENDER_ARCHITECTURE.md) - 推荐引擎
- [SIMULATOR_ARCHITECTURE.md](./SIMULATOR_ARCHITECTURE.md) - 模拟炒股
- [BACKTESTER_ARCHITECTURE.md](./BACKTESTER_ARCHITECTURE.md) - 回测验证
- [../references/专家设计/1.md](../references/专家设计/1.md) - 基础模块结构
- [../references/专家设计/2.md](../references/专家设计/2.md) - React + WebSocket专业方案
- [../references/专家设计/3.md](../references/专家设计/3.md) - 专业金融UI设计
- [../references/专家设计/4.md](../references/专家设计/4.md) - Vue3技术实现
- [../references/专家设计/5.md](../references/专家设计/5.md) - 完整体系设计
