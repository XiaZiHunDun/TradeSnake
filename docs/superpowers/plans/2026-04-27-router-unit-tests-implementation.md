# 任务：后端子路由独立单元测试

> 日期：2026-04-27  
> 类型：Testing（低风险）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：Router 拆分已完成

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

---

## Goal

为 7 个域级子路由创建独立的单元测试文件，每个文件测试该域的 endpoint 行为（正常响应 + 异常处理）。

与现有 `test_routes.py`（集成级别 TestClient 测试）不同，这些测试聚焦于：
- 单个 endpoint 函数的逻辑分支
- Mock 依赖后的隔离测试
- 边界条件和错误处理

完成后：新增 ≥ 35 个 test cases，所有通过。

---

## Context

### 当前测试结构

```
backend/tests/
├── conftest.py
├── test_routes.py         # 集成测试（TestClient + mock lifespan）
├── test_cp_engine.py      # 引擎单测
├── test_history.py        # 历史模块单测
├── test_fusion.py         # 融合推荐单测
└── test_prediction_engines.py  # 预测引擎单测
```

### 新增文件

```
backend/tests/
├── test_router_cp.py           # NEW
├── test_router_history.py      # NEW
├── test_router_simulator.py    # NEW
├── test_router_backtest.py     # NEW
├── test_router_risk.py         # NEW
├── test_router_prediction.py   # NEW
└── test_router_system.py       # NEW
```

### 子路由位置

```
backend/api/routers/
├── cp.py           # 7 个 endpoint
├── history.py      # 3 个 endpoint
├── simulator.py    # 7 个 endpoint
├── backtest.py     # 7 个 endpoint
├── risk.py         # 2 个 endpoint
├── prediction.py   # 6 个 endpoint
└── system.py       # 8 个 endpoint
```

### 测试模式

使用 `httpx.AsyncClient` + `app` 的方式或直接 `TestClient(app)`。由于当前 `test_routes.py` 已经用了 `TestClient + mock lifespan`，新测试可以：

**方案 A（推荐）**：直接 import endpoint 函数并调用（纯函数测试 + mock 依赖）  
**方案 B**：类似 test_routes.py 的 TestClient 但更聚焦

推荐 **方案 A**，因为它更轻量、隔离度更高、不需要 lifespan 的复杂 mock。

```python
# 示例：测试 cp.py 的 get_cp_top
from unittest.mock import patch, MagicMock
import pytest

@pytest.fixture
def mock_cp_engine():
    """Mock cp_engine with sample data"""
    with patch('backend.api.routers.cp.cp_engine') as mock:
        mock.stocks = [...]  # 构造 StockCP 对象
        yield mock

class TestCPTop:
    async def test_returns_sorted_by_cp(self, mock_cp_engine):
        from backend.api.routers.cp import get_cp_top
        result = await get_cp_top(limit=10)
        assert result.total <= 10
        # 验证排序

    async def test_empty_stocks(self, mock_cp_engine):
        mock_cp_engine.stocks = []
        from backend.api.routers.cp import get_cp_top
        result = await get_cp_top(limit=10)
        assert result.total == 0
```

---

## Scope

Allowed changes:

- 创建 `backend/tests/test_router_*.py` 文件（7 个）
- 如需要可修改 `backend/tests/conftest.py` 添加共享 fixtures

Out of scope:

- 不修改任何路由代码
- 不修改现有 `test_routes.py`
- 不修改 `dependencies.py`

---

## Autonomy

Claude Code 可以自主决定：

- 方案 A 或 B（推荐 A，即直接调用 endpoint 函数）
- 每个路由测试的具体 case 数量（只要总数 ≥ 35）
- fixture 的封装方式
- 是否使用 `pytest-asyncio` 或同步调用

---

## Stop Conditions

- 发现子路由函数无法单独调用（过度耦合于 FastAPI 框架）—— 改用 TestClient 方式
- 需要修改路由代码才能使其可测

---

## Steps

### Step 1: Setup

- [ ] 确认 `pytest-asyncio` 是否已安装（如果用方案 A 的 async 函数）
- [ ] 在 `conftest.py` 中添加通用 mock fixtures（如 mock_cp_engine, mock_db 等）

### Step 2: test_router_cp.py（≥ 7 cases）

测试端点：`get_cp_top`, `get_cp_bottom`, `get_cp_stock`, `get_cp_explain`, `get_recommend`, `get_swap`, `get_market_stats`

关键测试点：
- top/bottom 排序方向
- stock not found → HTTPException
- recommend 不同 category
- swap 无持仓时行为
- market stats 空引擎时

### Step 3: test_router_history.py（≥ 3 cases）

- changes 返回格式
- stock history 代码不存在
- rankings 参数验证

### Step 4: test_router_simulator.py（≥ 7 cases）

- account 正常返回
- portfolio 有/无持仓
- buy 成功/失败（余额不足、代码无效）
- sell 成功/失败（无持仓）
- user profile GET/PUT

### Step 5: test_router_backtest.py（≥ 5 cases）

- simple backtest 参数传递
- full backtest 正常/空结果
- optimize 创建任务+状态查询
- factor_analysis

### Step 6: test_router_risk.py（≥ 3 cases）

- risk report 正常
- break-even 计算
- break-even 代码不存在

### Step 7: test_router_prediction.py（≥ 5 cases）

- gain/probability top 正常
- gain/probability 单股
- verify accuracy

### Step 8: test_router_system.py（≥ 5 cases）

- health 正常
- pool stats
- refresh 主流程（mock）
- snapshot record

### Step 9: Full Verification

- [ ] `python -m pytest backend/tests/test_router_*.py -v --tb=short`
- [ ] `python -m pytest backend/tests/ -v -m "not integration" --tb=short`
- [ ] 确认不影响既有测试

---

## Verification

```bash
# 新测试
python -m pytest backend/tests/test_router_*.py -v --tb=short

# 全量（含旧测试）
python -m pytest backend/tests/ -v -m "not integration" --tb=short

# 确认总数
python -m pytest backend/tests/ -v -m "not integration" --tb=short 2>&1 | grep "passed"
```

---

## Completion Report Format

```markdown
## Summary
- 创建的文件和测试数量

## Verification
- 各文件测试结果
- 全量测试结果

## Test Coverage by Router
| Router | Test Cases | Key Behaviors Tested |
|--------|-----------|---------------------|
| cp.py  | N         | ...                 |
| ...    | ...       | ...                 |

## Remaining Issues

## Next Task Recommendation
```
