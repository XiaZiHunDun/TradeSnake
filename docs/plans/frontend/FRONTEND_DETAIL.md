# 前端模块方案 - 详细设计

> 本文档是前端模块的详细设计部分，对应 `FRONTEND_OVERVIEW.md` 的后续内容。

---

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

---

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

---

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

---

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

### 7.3 字体规范

| 用途 | 字体 | 说明 |
|------|------|------|
| 标题 | Inter, system-ui | 清晰现代 |
| 数据/代码 | JetBrains Mono, monospace | 等宽，数字对齐 |
| 中文正文 | "PingFang SC", "Microsoft YaHei" | 系统无衬线 |

### 7.4 间距系统

| 名称 | 值 | 用途 |
|------|-----|------|
| xs | 4px | 紧凑间距 |
| sm | 8px | 元素内间距 |
| md | 16px | 组件间距 |
| lg | 24px | 模块内间距 |
| xl | 32px | 区块间距 |
| 2xl | 48px | 页面间距 |

### 7.5 交互反馈

| 场景 | 处理方式 |
|------|---------|
| 数据更新 | 价格闪烁动画（背景色渐变） |
| 加载中 | 骨架屏 (Skeleton) |
| 错误 | 错误提示 + 重试按钮 |
| 空状态 | 空状态提示 + 引导操作 |
| 涨跌变化 | 颜色过渡动画 |

---

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

---

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

---

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

---

## 十一、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v2.2.1 | 2026-04-09 | 集成 v19.8 预测分析模块API（涨幅预测、上涨概率、验证报告） |
| v2.2 | 2026-04-08 | 补充预测模块文档框架，状态改为"部分实现" |
| v2.1 | 2026-04-07 | 补充预警系统、画线工具，资金流向可视化、选股器、涨跌色方案、可访问性 |
| v2.0 | 2026-04-07 | 全面升级：TypeScript、WebSocket、K线图、虚拟滚动、Zustand、组件层级体系 |
| v1.0 | 2026-04-07 | 初始方案设计 |

---

## 十二、相关文档

- [项目概览](../PROJECT_OVERVIEW.md) - 项目总览
- [ENGINE_ARCHITECTURE.md](../engine/ENGINE_ARCHITECTURE.md) - 分析引擎
- [RECOMMENDER_ARCHITECTURE.md](../recommender/RECOMMENDER_ARCHITECTURE.md) - 推荐引擎
- [SIMULATOR_ARCHITECTURE.md](../simulator/SIMULATOR_ARCHITECTURE.md) - 模拟炒股
- [BACKTESTER_ARCHITECTURE.md](../backtester/BACKTESTER_ARCHITECTURE.md) - 回测验证
- [专家设计](../../references/专家设计/) - 评审文档参考
