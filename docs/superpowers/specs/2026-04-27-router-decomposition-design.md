# Router 拆分设计

> 日期：2026-04-27  
> 类型：Architecture Refactoring  
> 设计方：Cursor  
> 状态：待执行

---

## 一、问题

`backend/api/router.py` 当前 1508 行，包含 41 个 endpoint，混合了 8 个不同业务域：

- 战力计算与推荐（CP/Recommend/Swap）
- 历史数据查询（History）
- 模拟交易（Account/Portfolio/Trade/User）
- 回测与优化（Backtest/Optimize/Factor）
- 风险分析（Risk）
- 预测模型（Prediction）
- 系统运维（Health/Pool/Refresh/Snapshot）
- 验证与诊断（Verify）

问题：

1. **可读性差**：新功能不知道加在哪里
2. **测试困难**：无法针对单一域做 mock 测试
3. **循环导入风险**：已出现 `get_stock_selector()` 的 lazy import hack
4. **变更冲突**：多人/多任务同时修改同一文件

---

## 二、目标

将 `router.py` 拆分为多个域级子路由文件，保持：

- API 路径完全不变（零破坏性变更）
- 每个子路由文件职责单一、可独立测试
- 共享依赖统一管理，消除 lazy import hack
- 拆分后 `test_routes.py` 无需修改即可通过

---

## 三、拆分方案

### 3.1 新目录结构

```
backend/api/
├── main.py              # 不变（lifespan, app 创建, 中间件）
├── router.py            # 变为"聚合路由"——只 include 子路由
├── dependencies.py      # 新建：共享实例与依赖注入
└── routers/             # 新建：域级子路由
    ├── __init__.py
    ├── cp.py            # 战力 + 推荐 + 换股
    ├── history.py       # 历史数据
    ├── simulator.py     # 模拟交易 + 用户
    ├── backtest.py      # 回测 + 优化 + 因子分析
    ├── risk.py          # 风险分析
    ├── prediction.py    # 预测模型 + 验证
    └── system.py        # 健康 + 池 + 刷新 + 快照 + 诊断验证
```

### 3.2 端点分配

| 子路由 | 端点 | 行数估计 |
|--------|------|----------|
| `cp.py` | `/api/cp/top`, `/bottom`, `/stock/{code}`, `/explain/{code}`, `/api/cp/recommend`, `/api/cp/swap`, `/api/stats/market` | ~220 行 |
| `history.py` | `/api/history/changes`, `/{code}`, `/rankings` | ~30 行 |
| `simulator.py` | `/api/account`, `/portfolio`, `/trade/buy`, `/trade/sell`, `/trades`, `/user/profile` | ~180 行 |
| `backtest.py` | `/api/backtest/simple`, `/compare`, `/benchmark`, `/full`, `/optimize`, `/status/{task_id}`, `/factor_analysis` | ~350 行 |
| `risk.py` | `/api/risk/report`, `/break-even/{code}` | ~50 行 |
| `prediction.py` | `/api/prediction/gain/top`, `/probability/top`, `/gain/{code}`, `/probability/{code}`, `/verify/gain_accuracy`, `/verify/probability_accuracy` | ~260 行 |
| `system.py` | `/api/health`, `/pool/stats`, `/refresh`, `/refresh/financials`, `/snapshot/record`, `/verify/report`, `/verify/swap`, `/verify/cp_accuracy` | ~300 行 |

### 3.3 共享依赖管理 (`dependencies.py`)

当前 `router.py` 顶部有多个模块级全局实例：

```python
cp_engine = CPEngine()
recommend_engine = RecommendEngine()
_db = get_db()
_account = Account()
_portfolio = Portfolio()
_trader = Trader()
_backtest_engine = BacktestEngine()
last_update_time = None
_cp_lock = asyncio.Lock()
```

设计方案：`dependencies.py` 用模块级单例 + getter 函数封装这些全局状态。

```python
# backend/api/dependencies.py
"""共享依赖 — 所有子路由从此处获取引擎实例"""
import asyncio
from concurrent.futures import ThreadPoolExecutor

from backend.engine.cp_engine import CPEngine
from backend.recommender.recommend_engine import RecommendEngine
from backend.simulator.database import get_db
from backend.simulator.account import Account
from backend.simulator.portfolio import Portfolio
from backend.simulator.trader import Trader
from backend.backtester.backtest import BacktestEngine

cp_engine = CPEngine()
recommend_engine = RecommendEngine()
db = get_db()
account = Account()
portfolio = Portfolio()
trader = Trader()
backtest_engine = BacktestEngine()

executor = ThreadPoolExecutor(max_workers=2)
cp_lock = asyncio.Lock()
last_update_time: str | None = None


def get_stock_selector():
    """获取 StockSelector 单例（延迟导入避免循环）"""
    from backend.api.main import get_stock_selector as _get
    return _get()
```

### 3.4 聚合路由 (`router.py` 新内容)

```python
# backend/api/router.py
"""API 路由聚合"""
from fastapi import APIRouter
from backend.api.routers import cp, history, simulator, backtest, risk, prediction, system

router = APIRouter()
router.include_router(cp.router)
router.include_router(history.router)
router.include_router(simulator.router)
router.include_router(backtest.router)
router.include_router(risk.router)
router.include_router(prediction.router)
router.include_router(system.router)
```

### 3.5 子路由内部模式

每个子路由文件的结构：

```python
# backend/api/routers/cp.py
from fastapi import APIRouter, HTTPException, Query
from backend.api.dependencies import cp_engine, recommend_engine, ...
from backend.models.schemas import CPListResponse, ...

router = APIRouter()

@router.get("/api/cp/top", response_model=CPListResponse)
async def get_cp_top(...):
    ...
```

---

## 四、风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| API 路径变化 | 不使用 `prefix` 参数，每个端点保持完整路径 |
| 共享状态不一致 | 集中到 `dependencies.py`，子路由只引用不创建 |
| 测试破坏 | 拆分后 `test_routes.py` 测试的是 `app`（包含所有子路由），无需修改 |
| `main.py` 中的 lifespan 仍需引用 `cp_engine` | lifespan 从 `dependencies` 导入，不改 main 逻辑 |
| 用户 `router.py` 可能有未提交改动 | 执行前先 `git stash` 或确认无未提交改动 |

---

## 五、不在本次范围

- 不改变任何 API 路径或行为
- 不引入 FastAPI Depends() 依赖注入（当前用模块级单例即可，未来可升级）
- 不重构 `main.py` 的 lifespan（保持现状）
- 不拆分 `schemas.py`（一个 schemas 文件目前可接受）
- 不添加新测试（复用现有 `test_routes.py` 验证）

---

## 六、验证标准

```bash
# 1. 所有路由测试通过
python -m pytest backend/tests/test_routes.py -v -m "not integration"

# 2. 后端可启动
python -c "from backend.api.main import app; print('OK')"

# 3. 无循环导入
python -c "from backend.api.routers.cp import router; print('cp OK')"
python -c "from backend.api.routers.simulator import router; print('simulator OK')"
python -c "from backend.api.routers.backtest import router; print('backtest OK')"

# 4. 原 router.py 行数验证（应大幅缩减）
wc -l backend/api/router.py  # 期望 < 20 行

# 5. 全量后端测试
python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py
python -m pytest backend/tests/test_routes.py -v -m "not integration"
```

---

## 七、执行建议

此设计对应的实施任务应确保：

1. 先确认 `backend/api/router.py` 无用户未提交改动
2. 创建 `dependencies.py` 和 `routers/` 目录
3. 逐个域迁移端点代码，每迁移一个域后运行测试
4. 最后将 `router.py` 精简为聚合文件
5. 全量验证
