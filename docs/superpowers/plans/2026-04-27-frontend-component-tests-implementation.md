# 任务：前端组件测试

> 日期：2026-04-27  
> 类型：Testing（低风险）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：Router 拆分已完成

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

**原则**：写实际有价值的测试，而不是为了覆盖率凑数。测试应验证组件的关键行为和用户交互，不测试纯样式。

---

## Goal

为前端的核心共享组件和模块页面编写 Vitest + React Testing Library 测试：

- 至少 **4 个共享组件** 测试文件（atoms + molecules）
- 至少 **3 个模块页面** 测试文件（包含 API mock）
- 至少 **1 个 hooks** 测试文件

完成后：`npm run test` 运行全部测试并通过，测试数量 ≥ 20 个 test cases。

---

## Context

### 现有基础设施

- Vitest 已配置：`vitest.config.ts`（jsdom, globals, setupFiles）
- testing-library/react + jest-dom 已安装
- `src/test-setup.ts` 已存在（仅 import jest-dom）
- 当前 0 个测试文件

### 前端架构

```
src/
├── modules/
│   ├── market/TopList.tsx          # 战力榜表格，useCPTop hook
│   ├── stock/StockDetail.tsx       # 个股详情
│   ├── portfolio/Portfolio.tsx     # 模拟账户+持仓+快速交易
│   ├── watchlist/Watchlist.tsx     # 自选股（localStorage）
│   ├── recommend/Recommend.tsx     # 推荐分类+换股建议
│   └── backtest/Backtest.tsx       # 回测表单+结果
├── shared/
│   ├── components/
│   │   ├── atoms/Button.tsx, Input.tsx, Badge.tsx, Tag.tsx
│   │   ├── molecules/StockCard.tsx, SearchBar.tsx, PercentageBar.tsx, PriceDisplay.tsx
│   │   └── organisms/SortableTable.tsx, Header.tsx
│   ├── hooks/useApi.ts            # 20+ TanStack Query hooks
│   └── services/api.ts            # fetch 封装
└── App.tsx
```

### 数据层模式

- 所有 API 调用通过 `shared/services/api.ts` 的 `request<T>()` 函数
- Hooks 在 `shared/hooks/useApi.ts` 中封装 TanStack Query
- 自选股 (`Watchlist`) 用 localStorage，无真实 API 调用
- 模块页面通过 hooks 获取数据，按状态渲染 loading/error/content

---

## Scope

Allowed changes:

- 创建 `frontend/src/**/__tests__/` 或 `frontend/src/**/*.test.tsx` 测试文件
- 修改 `frontend/src/test-setup.ts` 以添加全局 mock 辅助
- 如需要可创建 `frontend/src/__mocks__/` 目录放置 mock 工具

Out of scope:

- 不修改任何现有组件代码（除非发现明确 bug 导致测试无法编写）
- 不修改 `vitest.config.ts`（除非有合理原因如 coverage 配置）
- 不添加新的 npm 依赖（已有的 testing-library 够用）
- 不修改后端任何文件

---

## Autonomy

Claude Code 可以自主决定：

- 测试文件放在 `__tests__/` 还是 `.test.tsx` 命名（推荐与组件同目录的 `.test.tsx`）
- mock 策略：vi.mock 模块级 vs render wrapper（推荐按 React Testing Library 最佳实践）
- 具体测试哪些交互细节（优先测试用户可见行为）
- 是否创建共享的 test utilities / render wrapper

---

## Stop Conditions

- 组件代码中存在严重 bug 使得合理行为无法被测试
- 需要安装额外 npm 包（应该不需要）
- 测试发现后端 API 契约有问题需要修改

---

## Steps

### Step 1: Create Test Utilities

- [ ] 创建 `frontend/src/test-utils.tsx`：
  - 封装一个带 `QueryClientProvider` 和 `MemoryRouter` 的 render wrapper
  - 这样模块页面测试可以正常渲染使用 hooks 和路由的组件
- [ ] 验证：`cd frontend && npx vitest run --passWithNoTests`

```typescript
// 参考模式
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

export function renderWithProviders(ui: React.ReactElement, options?: { route?: string }) {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[options?.route || '/']}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  )
}
```

### Step 2: Atoms Tests

- [ ] 创建 `frontend/src/shared/components/atoms/Button.test.tsx`：
  - 渲染不同 variant
  - 点击触发 onClick
  - disabled 状态不触发 onClick
- [ ] 创建 `frontend/src/shared/components/atoms/Input.test.tsx`：
  - 受控输入更新
  - placeholder 显示
  - type="number" 行为

### Step 3: Molecules Tests

- [ ] 创建 `frontend/src/shared/components/molecules/SearchBar.test.tsx`：
  - 输入文本
  - 提交触发 onSearch
  - 空输入不触发
- [ ] 创建 `frontend/src/shared/components/molecules/StockCard.test.tsx`（如组件接受 props 可测）：
  - 显示股票名称和代码
  - 涨跌颜色正确
  - 点击触发 onClick

### Step 4: Module Pages Tests (with mocked hooks)

关键：使用 `vi.mock('../../shared/hooks/useApi')` mock 整个 hooks 模块。

- [ ] 创建 `frontend/src/modules/market/TopList.test.tsx`：
  - mock `useCPTop` 返回数据 → 渲染表格行
  - mock `useCPTop` 返回 error → 显示错误 + 重试按钮
  - mock `useCPTop` 返回 loading → 显示加载状态
  - 点击筛选按钮切换 all/up/down
- [ ] 创建 `frontend/src/modules/portfolio/Portfolio.test.tsx`：
  - mock account 数据 → 显示总资产、可用资金
  - mock portfolio holdings → 渲染持仓表格
  - 快速交易表单：输入代码+数量，点买入调用 buy mutation
- [ ] 创建 `frontend/src/modules/recommend/Recommend.test.tsx`：
  - mock recommendations → 显示推荐列表
  - 点击分类按钮切换 category
  - mock swap suggestions → 显示换股建议

### Step 5: Hooks Test (optional but valuable)

- [ ] 创建 `frontend/src/shared/hooks/useApi.test.tsx`：
  - 测试 `useCPTop` 调用了正确的 API endpoint
  - 测试 `useBuyTrade` 成功后 invalidate 正确的 query keys
  - 使用 `@tanstack/react-query` 的测试工具（`renderHook` from testing-library）

### Step 6: Run All Tests

- [ ] `cd frontend && npm run test`
- [ ] 确保全部通过
- [ ] 记录测试数量

---

## Verification

```bash
cd frontend

# 运行全部测试
npm run test

# 确认测试数量（期望 >= 20）
npx vitest run --reporter=verbose 2>&1 | tail -5

# 确认构建不受影响
npm run build

# 确认 lint 不报错（测试文件也应通过 lint）
npm run lint
```

---

## Mock 数据参考

为节省探索时间，以下是关键 hook 返回值的结构：

```typescript
// useCPTop 返回
{
  data: {
    data: [
      { code: '600519', name: '贵州茅台', price: 1800, change_pct: 1.5,
        total_cp: 85.3, growth_score: 70, value_score: 80, quality_score: 90,
        momentum_score: 60 },
    ],
    updated_at: '2026-04-27 10:30:00'
  },
  isLoading: false, error: null
}

// useAccount 返回
{
  data: { cash: 15000, total_assets: 25000, total_market_value: 10000,
          total_profit: 500, profit_rate: 2.5 },
  isLoading: false
}

// usePortfolio 返回
{
  data: {
    holdings: [
      { code: '000001', name: '平安银行', quantity: 500, cost_price: 12.5,
        current_price: 13.0, market_value: 6500, profit: 250, profit_rate: 4.0 }
    ]
  }
}

// useRecommendations 返回
{
  data: {
    data: [
      { code: '600036', name: '招商银行', total_cp: 78.5, price: 35.2, change_pct: 0.8 }
    ]
  },
  isLoading: false
}
```

---

## Completion Report Format

```markdown
## Summary
- 创建的测试文件列表
- 总测试数量

## Verification
- `npm run test` 结果
- `npm run build` 结果
- `npm run lint` 结果

## Test Coverage
- 各文件测试点概要

## Remaining Issues
- 未覆盖的组件或已知限制

## Next Task Recommendation
- 后续建议
```
