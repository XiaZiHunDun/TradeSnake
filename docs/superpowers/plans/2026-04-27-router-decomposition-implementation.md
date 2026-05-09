# 任务：Router 拆分实施

> 日期：2026-04-27  
> 类型：Architecture Refactoring（中等风险）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 设计文档：`docs/superpowers/specs/2026-04-27-router-decomposition-design.md`  
> 前置任务：`2026-04-27-ci-fix-and-factbase-sync-implementation.md`（需先完成）

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

**关键原则**：这是一个纯重构任务——所有 API 端点的路径、参数、响应必须与拆分前完全一致。不添加新功能、不改变行为。

---

## Goal

将 `backend/api/router.py`（~1508 行，41 个 endpoint）拆分为 7 个域级子路由文件 + 1 个共享依赖文件，使原始路由文件变为仅 include 子路由的聚合器（< 20 行）。

Acceptance criteria:

- 所有现有测试通过（`test_routes.py` + 全量 backend 测试）
- API 路径零变化
- 无循环导入
- 每个子路由文件职责单一

---

## Context

设计文档 `docs/superpowers/specs/2026-04-27-router-decomposition-design.md` 已定义：

- 目标结构：`backend/api/routers/` + `backend/api/dependencies.py`
- 端点分配：cp / history / simulator / backtest / risk / prediction / system
- 共享依赖方案：模块级单例集中管理

当前全局实例（在 router.py 顶部）：
- `cp_engine`, `recommend_engine`, `_db`, `_account`, `_portfolio`, `_trader`, `_backtest_engine`
- `last_update_time`, `_cp_lock`, `_executor`

Helper 函数（在 router.py 中定义，被多个 endpoint 使用）：
- `_build_stock_response(stock)` → 用于 cp.py
- `get_stock_selector()` → 用于 system.py（refresh）和 cp.py

---

## Scope

Allowed changes:

- `backend/api/router.py` — 精简为聚合文件
- `backend/api/dependencies.py` — 新建
- `backend/api/routers/__init__.py` — 新建
- `backend/api/routers/cp.py` — 新建
- `backend/api/routers/history.py` — 新建
- `backend/api/routers/simulator.py` — 新建
- `backend/api/routers/backtest.py` — 新建
- `backend/api/routers/risk.py` — 新建
- `backend/api/routers/prediction.py` — 新建
- `backend/api/routers/system.py` — 新建
- `backend/api/main.py` — 仅当 lifespan 中引用的变量需改为从 dependencies 导入时

Out of scope:

- 任何端点的路径、参数或响应格式
- `backend/models/schemas.py`
- `backend/tests/test_routes.py`（不应需要修改）
- 前端任何文件
- 任何非 `backend/api/` 的后端模块

---

## Autonomy

Claude Code 可以自主决定：

- 各子路由文件内部的 import 顺序和局部变量命名
- helper 函数放在 `dependencies.py` 还是所属子路由中（推荐：如果只被一个域使用就放该域，被多域使用就放 dependencies）
- 是否在 `__init__.py` 中 re-export（推荐：空 `__init__.py` 即可）
- `main.py` 中 lifespan 引用调整的具体 import 路径

---

## Stop Conditions

- `backend/api/router.py` 有用户未提交改动（先 `git status backend/api/router.py` 检查）
- 拆分后出现循环导入无法解决
- 拆分后测试大面积失败且非本次变更所致
- 需要修改 schemas 或 API 行为才能完成拆分

---

## Steps

### Step 0: Pre-check

- [ ] `git status backend/api/router.py` — 如果显示修改，**停止并报告**
- [ ] `python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short` — 记录基线

### Step 1: Create dependencies.py

- [ ] 创建 `backend/api/dependencies.py`
- [ ] 从 `router.py` 提取所有全局实例：`cp_engine`, `recommend_engine`, `_db` (重命名为 `db`), `_account` (→ `account`), `_portfolio` (→ `portfolio`), `_trader` (→ `trader`), `_backtest_engine` (→ `backtest_engine`), `_executor` (→ `executor`), `last_update_time`, `_cp_lock` (→ `cp_lock`)
- [ ] 迁移 `get_stock_selector()` 函数
- [ ] 迁移 `_build_stock_response()` 辅助函数（或如果只有 cp.py 用就留在 cp.py）
- [ ] 验证导入：`python -c "from backend.api.dependencies import cp_engine; print('OK')"`

### Step 2: Create routers directory

- [ ] `mkdir -p backend/api/routers`
- [ ] 创建空 `backend/api/routers/__init__.py`

### Step 3: Migrate CP routes (cp.py)

- [ ] 创建 `backend/api/routers/cp.py`
- [ ] 迁移端点：`/api/cp/top`, `/api/cp/bottom`, `/api/cp/stock/{code}`, `/api/cp/explain/{code}`, `/api/cp/recommend`, `/api/cp/swap`, `/api/stats/market`
- [ ] 从 dependencies 导入需要的实例
- [ ] 验证：`python -c "from backend.api.routers.cp import router; print('OK')"`

### Step 4: Migrate History routes (history.py)

- [ ] 创建 `backend/api/routers/history.py`
- [ ] 迁移端点：`/api/history/changes`, `/api/history/{code}`, `/api/history/rankings`
- [ ] 验证导入

### Step 5: Migrate Simulator routes (simulator.py)

- [ ] 创建 `backend/api/routers/simulator.py`
- [ ] 迁移端点：`/api/account`, `/api/portfolio`, `/api/trade/buy`, `/api/trade/sell`, `/api/trades`, `/api/user/profile` (GET + PUT)
- [ ] 验证导入

### Step 6: Migrate Backtest routes (backtest.py)

- [ ] 创建 `backend/api/routers/backtest.py`
- [ ] 迁移端点：`/api/backtest/simple`, `/compare`, `/benchmark`, `/full`, `/optimize`, `/status/{task_id}`, `/factor_analysis`
- [ ] 注意：optimize 端点有后台任务管理（`_optimization_tasks` dict），将该 dict 放在此文件或 dependencies 中
- [ ] 验证导入

### Step 7: Migrate Risk routes (risk.py)

- [ ] 创建 `backend/api/routers/risk.py`
- [ ] 迁移端点：`/api/risk/report`, `/api/risk/break-even/{code}`
- [ ] 验证导入

### Step 8: Migrate Prediction routes (prediction.py)

- [ ] 创建 `backend/api/routers/prediction.py`
- [ ] 迁移端点：`/api/prediction/gain/top`, `/probability/top`, `/gain/{code}`, `/probability/{code}`, `/verify/gain_accuracy`, `/verify/probability_accuracy`
- [ ] 验证导入

### Step 9: Migrate System routes (system.py)

- [ ] 创建 `backend/api/routers/system.py`
- [ ] 迁移端点：`/api/health`, `/api/pool/stats`, `/api/refresh`, `/api/refresh/financials`, `/api/snapshot/record`, `/api/verify/report`, `/api/verify/swap`, `/api/verify/cp_accuracy`
- [ ] 注意：refresh 是最复杂的端点，仔细迁移所有依赖引用
- [ ] 验证导入

### Step 10: Rewrite router.py as aggregator

- [ ] 将 `backend/api/router.py` 替换为聚合文件（只 include 7 个子路由）
- [ ] 确保 `main.py` 中 `from backend.api.router import router` 仍正常工作

### Step 11: Update main.py (if needed)

- [ ] 检查 `main.py` 的 lifespan 是否直接引用了原 `router.py` 中的变量
- [ ] 如果是，改为从 `backend.api.dependencies` 导入
- [ ] 验证：`python -c "from backend.api.main import app; print('OK')"`

### Step 12: Full Verification

- [ ] `python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short`
- [ ] `python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py`
- [ ] `python -m pytest backend/data_manager/tests/ -v --tb=short`
- [ ] `wc -l backend/api/router.py` — 期望 < 20 行
- [ ] `wc -l backend/api/routers/*.py` — 查看各文件行数
- [ ] 确认无循环导入：`python -c "from backend.api.main import app; print('FULL IMPORT OK')"`

---

## Verification

```bash
# 核心：路由测试（确保 API 行为不变）
python -m pytest backend/tests/test_routes.py -v -m "not integration" --tb=short

# 后端全量测试
python -m pytest backend/tests/ tests/backtester/ backend/data_manager/tests/ tests/test_simulator.py -v -m "not integration" --ignore=backend/tests/test_routes.py

# 导入验证
python -c "from backend.api.main import app; print('main OK')"
python -c "from backend.api.dependencies import cp_engine, db, trader; print('deps OK')"
python -c "from backend.api.routers.cp import router; print('cp OK')"
python -c "from backend.api.routers.backtest import router; print('backtest OK')"
python -c "from backend.api.routers.system import router; print('system OK')"

# 文件尺寸
wc -l backend/api/router.py backend/api/dependencies.py backend/api/routers/*.py
```

---

## Completion Report Format

```markdown
## Summary
- 创建文件列表
- router.py 最终行数
- 各子路由行数

## Verification
- 路由测试结果
- 全量测试结果
- 导入验证结果

## Architecture
- 最终文件结构

## Remaining Issues
- 任何未解决的问题

## Next Task Recommendation
- 后续建议
```
