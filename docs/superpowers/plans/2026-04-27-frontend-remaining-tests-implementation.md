# 任务：前端补测 StockDetail / Watchlist / Backtest

> 日期：2026-04-27  
> 类型：Testing（低风险）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：API 类型一致性修复完成后执行（类型对齐后 mock 数据更准确）

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

---

## Goal

为剩余 3 个未覆盖的模块页面编写测试，加上 Layout 和 SortableTable 的共享组件测试。

完成后：前端测试文件从 9 个增到 ≥ 14 个，总 test cases 从 36 个增到 ≥ 56 个。

---

## Context

### 已有测试

```
✅ atoms/Button.test.tsx (7)
✅ atoms/Input.test.tsx (6)
✅ molecules/SearchBar.test.tsx (4)
✅ molecules/StockCard.test.tsx (5)
✅ modules/market/TopList.test.tsx (4)
✅ modules/portfolio/Portfolio.test.tsx (4)
✅ modules/recommend/Recommend.test.tsx (4)
✅ hooks/useApi.test.tsx (3)
```

### 需要新增

```
❌ modules/stock/StockDetail.test.tsx
❌ modules/watchlist/Watchlist.test.tsx
❌ modules/backtest/Backtest.test.tsx
❌ shared/components/organisms/SortableTable.test.tsx
❌ shared/components/Layout.test.tsx
```

### 模块特点

- **StockDetail**: 使用 `useStockDetail(code)` hook，展示单股详情（价格、战力分解、风险、财务数据）。依赖 `useParams()` 获取 code。
- **Watchlist**: 纯本地 localStorage 操作（`useWatchlistGroups` + `useSaveWatchlistGroups`），不调用后端 API。包含分组管理、添加/删除股票。
- **Backtest**: 表单输入（start_date, end_date, holding_days, top_n）+ `useBacktest()` mutation。展示回测结果。
- **SortableTable**: 接受 `data`, `columns`, `onRowClick` 等 props，支持排序列点击。是最重要的共享组件。
- **Layout**: 容器组件，包含 Header + Sidebar + Outlet。依赖 zustand store (`useUIStore`)。

---

## Scope

Allowed changes:

- 创建上述 5 个测试文件
- 可修改 `test-utils.tsx` 添加辅助
- 可修改 `test-setup.ts` 添加 localStorage mock 等

Out of scope:

- 不修改任何组件代码
- 不修改已有测试文件（除非它们因类型修复需要更新 mock 数据）

---

## Steps

### Step 1: SortableTable.test.tsx（≥ 5 cases）

- [ ] 渲染表头（columns title 显示）
- [ ] 渲染数据行
- [ ] 点击行触发 onRowClick
- [ ] 点击 sortable 列头切换排序
- [ ] 空数据显示 emptyMessage

### Step 2: StockDetail.test.tsx（≥ 5 cases）

- [ ] mock `useParams` 返回 code
- [ ] mock `useStockDetail` 返回数据 → 显示股票名称和战力
- [ ] loading 状态
- [ ] error 状态
- [ ] 显示各因子分数

### Step 3: Watchlist.test.tsx（≥ 5 cases）

- [ ] mock localStorage 为空 → 显示"暂无分组"
- [ ] mock 有分组数据 → 渲染分组列表
- [ ] 创建新分组
- [ ] 删除分组
- [ ] 添加股票到分组（如界面支持）

### Step 4: Backtest.test.tsx（≥ 4 cases）

- [ ] 渲染表单（日期、持仓天数、top_n 输入）
- [ ] 提交表单调用 backtest mutation
- [ ] 显示回测结果
- [ ] 参数验证（空日期不提交）

### Step 5: Layout.test.tsx（≥ 3 cases）

- [ ] 渲染 Header 和 Sidebar
- [ ] Outlet 区域渲染子路由内容
- [ ] 搜索回调传递

### Step 6: Verification

- [ ] `npm run test` — 全部通过
- [ ] `npm run typecheck`
- [ ] `npm run lint`

---

## Verification

```bash
cd frontend
npm run test
npm run typecheck
npm run lint
```

---

## Completion Report Format

```markdown
## Summary
- 新增测试文件和数量
- 总前端测试数量

## Verification
- npm run test 结果

## Remaining Gaps
- 还有哪些组件/功能未覆盖
```
