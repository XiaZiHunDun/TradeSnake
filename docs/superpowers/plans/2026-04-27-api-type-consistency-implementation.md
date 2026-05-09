# 任务：前后端 API 类型一致性修复

> 日期：2026-04-27  
> 类型：Bug Fix + Type Safety（中等风险）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：前端组件测试已完成

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

**注意**：本任务只修改前端类型定义和 API 调用层。不修改后端 schemas.py（那是正确的事实源）。

---

## Goal

修复 `frontend/src/shared/types/index.ts` 和 `api.ts` 中与后端 `schemas.py` 不一致的类型定义，消除运行时隐患。

Acceptance criteria:

- 前端类型定义与后端 Pydantic schema 字段一一对应
- `npm run typecheck` 通过
- `npm run build` 通过
- `npm run test` 通过（已有测试不因类型改动而失败）

---

## Context

### 已发现的类型不匹配（按严重程度排序）

#### BUG 级别：TradeResult 定义错误

后端 `TradeResponse`（schemas.py 315-326）：
```python
class TradeResponse(BaseModel):
    success: bool
    action: str          # buy/sell
    code: str
    name: str
    quantity: int
    price: float
    total_amount: float
    cost_detail: TradeCostBreakdown
    cash_after: float
    message: str
```

前端 `TradeResult`（types/index.ts 176-184）：
```typescript
export interface TradeResult {
  success: boolean
  message: string
  trade_id?: string    // ❌ 后端没有此字段
  price?: number       // ❌ 后端是必填
  shares?: number      // ❌ 后端用 quantity
  amount?: number      // ❌ 后端用 total_amount
  commission?: number  // ❌ 后端用 cost_detail 对象
}
```

前端已有 `TradeExecutionDetail`（144-155）几乎正确匹配后端，但 `api.ts` 中 `buy()` 和 `sell()` 返回的是 `TradeResult` 而非 `TradeExecutionDetail`。

**修复方案**：删除旧 `TradeResult`，让 `tradeApi.buy/sell` 返回 `TradeExecutionDetail`（或将其重命名为 `TradeResult`）。

---

#### MISMATCH 级别：MarketStats 字段完全不同

后端 `MarketStatsResponse`（133-143）：
```python
total_stocks, avg_cp, high_cp_count, mid_cp_count, low_cp_count,
avg_change, rising_stocks, falling_stocks, unchanged_stocks
```

前端 `MarketStats`（231-240）：
```typescript
total_stocks, up_count, down_count, flat_count,
limit_up_count, limit_down_count, total_amount, market_capitalization
```

前端完全错误。如果前端某处使用了 `MarketStats`，运行时取值全是 undefined。

**修复方案**：重写 `MarketStats` 匹配后端。

---

#### MISSING 级别：StockCP 缺少融合推荐字段

后端 `StockCPData` 有但前端 `StockCP` 缺少：
- `kelly_position: number`
- `predicted_gain_5d: number`
- `up_probability_5d: number`
- `prediction_confidence: number`
- `fused_score: number`
- `net_benefit_hint: string`
- `roe: number`（前端 StockDetail 有，但 StockCP 没有）
- `net_profit_growth: number`（同上）
- `revenue_growth: number`（同上）
- `peg: number`

**修复方案**：在 `StockCP` 中补全为 optional 字段。

---

#### LOOSE 级别：BacktestResult 太松散

前端：
```typescript
export interface BacktestResult {
  total_return?: number
  annual_return?: number  // ❌ 后端是 annualized_return
  ...
  [key: string]: unknown  // 完全放弃类型检查
}
```

后端 `FullBacktestResponse` 有严格定义（包含 equity_curve, trades 等）。

**修复方案**：精确定义 `BacktestResult` 匹配后端（但保留 `[key: string]: unknown` 因为 simple/compare 回测的响应没有 response_model）。

---

#### MINOR 级别：杂项

- `CPTopResponse` 缺少 `error?: string` 字段
- `HealthResponse.status` 后端可能返回 `"ok"` 不是 `"healthy"`（待确认实际值）
- 前端 `StockCP` 的别名字段（`change`, `changePercent`, `growth_cp` 等）是死代码，可删除

---

## Scope

Allowed changes:

- `frontend/src/shared/types/index.ts` — 修改类型定义
- `frontend/src/shared/services/api.ts` — 修改返回类型
- `frontend/src/shared/hooks/useApi.ts` — 如需适配类型变化
- `frontend/src/modules/**/*.tsx` — 如类型改名导致编译错误
- 前端测试文件 — 如 mock 数据结构需更新

Out of scope:

- `backend/models/schemas.py`（后端是正确的事实源）
- 后端任何文件
- 不改变 UI 行为（只改类型，不改渲染逻辑）

---

## Autonomy

Claude Code 可以自主决定：

- 是删除 `TradeResult` 还是重命名 `TradeExecutionDetail` 为 `TradeResult`
- 前端别名字段（`change`, `changePercent` 等）是删除还是保留为 deprecated
- `BacktestResult` 是精确化还是保持松散（简单回测 API 无 response_model）

---

## Stop Conditions

- 修改类型后发现大量组件代码依赖旧字段（如 `TradeResult.shares`），需要业务逻辑变更
- 前端实际使用了后端不存在的 API 字段（意味着后端需要补字段，超出本任务范围）

---

## Steps

### Step 1: Fix TradeResult

- [ ] 删除旧 `TradeResult` interface
- [ ] 将 `TradeExecutionDetail` 重命名为 `TradeResult`（或保留两者取合理的那个）
- [ ] 更新 `api.ts` 中 `tradeApi.buy()` 和 `sell()` 的返回类型
- [ ] 检查所有引用 `TradeResult` 的组件，确保字段访问正确
- [ ] `npm run typecheck`

### Step 2: Fix MarketStats

- [ ] 重写 `MarketStats` interface 匹配后端 `MarketStatsResponse`：
```typescript
export interface MarketStatsResponse {
  total_stocks: number
  avg_cp: number
  high_cp_count: number
  mid_cp_count: number
  low_cp_count: number
  avg_change: number
  rising_stocks: number
  falling_stocks: number
  unchanged_stocks: number
}
```
- [ ] 检查前端是否有组件使用旧的 `MarketStats`，更新引用
- [ ] `npm run typecheck`

### Step 3: Add missing StockCP fields

- [ ] 在 `StockCP` 中补全 optional 字段：
```typescript
// 融合推荐字段 (v19.9.5)
kelly_position?: number
predicted_gain_5d?: number
up_probability_5d?: number
prediction_confidence?: number
fused_score?: number
net_benefit_hint?: string
// 财务（已在 StockDetail 中，StockCP 也应有）
roe?: number
net_profit_growth?: number
revenue_growth?: number
peg?: number
```
- [ ] `npm run typecheck`

### Step 4: Tighten BacktestResult

- [ ] 为 `FullBacktestResponse` 创建精确类型（匹配后端）
- [ ] 保持 `BacktestResult` 作为 simple/compare 回测的松散类型（或合并）
- [ ] 修复 `annual_return` → `annualized_return` 命名
- [ ] `npm run typecheck`

### Step 5: Minor fixes

- [ ] `CPTopResponse` 添加 `error?: string`
- [ ] 清理或标注死代码别名字段（`change`, `changePercent`, `growth_cp` 等）
- [ ] `npm run typecheck`

### Step 6: Full verification

- [ ] `npm run typecheck`
- [ ] `npm run build`
- [ ] `npm run test`
- [ ] `npm run lint`

---

## Verification

```bash
cd frontend
npm run typecheck
npm run build
npm run test
npm run lint
```

---

## Completion Report Format

```markdown
## Summary
- 修复的类型不匹配列表
- 影响的文件

## Verification
- typecheck / build / test / lint 结果

## Type Changes
- 删除/新增/修改的 interface 列表

## Remaining Issues
- 后端无 response_model 的 endpoint（如 /api/backtest/simple）类型仍为推断

## Next Task Recommendation
```
