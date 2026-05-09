# API模块方案 - 概述

## 概述

API模块是 TradeSnake 系统的 HTTP/WebSocket 接口层，基于 FastAPI 构建。

**版本**: v19.9.11（与 main.py 保持一致）| **状态**: ✅ 稳定运行

**核心职责**：
- 聚合所有子路由（战力/推荐/回测/模拟交易/历史/预测/系统管理）
- 管理 FastAPI 生命周期（启动初始化、后台刷新、关闭清理）
- 提供 WebSocket 实时推送能力
- 统一的认证、限流、异常处理

**端口**: http://localhost:8001 | **入口**: `backend/api/main.py`

---

## 输入输出

### 输入
| 来源 | 数据内容 |
|------|----------|
| 前端HTTP | REST API 请求（GET/POST） |
| WebSocket | 实时行情订阅（`/ws/alerts`） |
| 后台调度 | 定时刷新任务（差异化池刷新策略） |
| 外部数据源 | Tushare/akshare/东方财富行情数据 |

### 输出
| 输出内容 | 格式 |
|----------|------|
| JSON响应 | FastAPI Pydantic Response Model |
| WebSocket推送 | JSON文本（ping/pong心跳） |
| 错误响应 | `{"success": false, "error": "...", "detail": "..."}` |

---

## 模块结构

```
backend/api/
├── __init__.py
├── main.py              # FastAPI主入口 + lifespan + 启动初始化
├── router.py            # 路由聚合器（组合7个子路由）
├── dependencies.py       # 依赖注入（cp_engine/db/portfolio/trader）
├── limits.py            # 限流器（slowapi）
├── websocket.py         # WebSocket管理器
└── routers/
    ├── __init__.py
    ├── cp.py             # 战力/推荐/换股
    ├── history.py         # 历史数据
    ├── simulator.py       # 模拟交易（账户/持仓/交易）
    ├── backtest.py        # 回测/优化/因子分析
    ├── risk.py            # 风险分析
    ├── prediction.py      # 预测模型
    └── system.py          # 系统管理
```

---

## 一、核心设计

### 1.1 依赖注入（dependencies.py）

```python
# 核心单例通过 Depends 注入各路由
cp_engine: CPEngine          # 战力引擎（全局唯一）
recommend_engine: RecommendEngine  # 推荐引擎（全局唯一）
db: SimulatorDB              # 模拟交易数据库
account: Account             # 账户
portfolio: Portfolio         # 持仓组合
trader: Trader               # 交易执行器
```

### 1.2 生命周期管理（main.py）

**启动流程**：
1. 初始化 StockSelector（差异化池策略）
2. 注册 UpdateScheduler + StockSelectorCallback
3. 注册 RecommenderCallback
4. 从 SQLite stocks 表快速预加载战力数据
5. 启动后台刷新任务（延迟5秒）
6. 启动股票池再平衡任务

**后台任务**：
| 任务 | 触发条件 | 职责 |
|------|----------|------|
| `background_refresh_task` | 持续运行 | 差异化池刷新（核心池5min/活跃池30min）、收盘后预测保存、K线填充 |
| `pool_rebalance_background_task` | 收盘后触发 | 股票池再平衡（refresh_pools）、池状态持久化 |

**差异化刷新策略**（按 `STOCK_SELECTOR_ARCHITECTURE.md v19.5.3`）：
- 核心池：5分钟刷新间隔
- 活跃池：30分钟刷新间隔
- 观察池：盘中不刷新（仅盘后批处理）

**收盘后任务**（16:00后执行一次）：
1. 涨幅/概率预测计算并保存
2. adj_factor 填充（Tushare → SQLite）
3. K线增量填充（最近7天 → DuckDB）
4. adj_factor 回填（SQLite → DuckDB）

**分钟K线填充**（16:30后，核心池+活跃池，每天轮换50只）

### 1.3 CORS配置

```python
# 支持的源（可通过 CORS_ORIGINS 环境变量配置）
default_origins = [
    "http://localhost:5173",  # 前端开发服务器
    "http://localhost:5174",
]
```

### 1.4 WebSocket

```python
# 端点：/ws/alerts
# 功能：实时行情推送、心跳（ping/pong）
# 管理器：WebSocketManager（connect/disconnect/broadcast）
```

### 1.5 异常处理

```python
# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    # 捕获所有未处理异常，返回500
    # 隐藏 NoneType 等内部错误信息
    return JSONResponse(status_code=500, content={...})
```

### 1.6 限流

使用 `slowapi` 实现请求限流，防止API滥用。

---

## 二、路由聚合（router.py）

```python
from backend.api.routers import cp, history, simulator, backtest, risk, prediction, system

router.include_router(cp.router, tags=["战力/推荐/换股"])
router.include_router(history.router, tags=["历史数据"])
router.include_router(simulator.router, tags=["模拟交易"])
router.include_router(backtest.router, tags=["回测优化"])
router.include_router(risk.router, tags=["风险分析"])
router.include_router(prediction.router, tags=["预测分析"])
router.include_router(system.router, tags=["系统管理"])
```

---

## 三、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v19.9.11 | 2026-04-27 | 从SQLite stocks表加载财务数据用于选股器准入检查 |
| v19.9.9 | 2026-04-26 | 池状态持久化（PoolManager.save_state/load_state）、adj_factor回填到DuckDB |
| v19.9.8 | 2026-04-25 | 收盘后分钟K线填充（差异化池策略，每天50只轮换） |
| v19.9.7 | 2026-04-24 | 收盘后K线增量填充（最近7天）、adj_factor Tushare填充到SQLite |
| v19.9.3 | 2026-04-20 | 差异化池刷新策略、asyncio.Lock保护cp_engine.stocks并发访问 |

---

## 四、相关文档

- [STOCK_SELECTOR_ARCHITECTURE.md](../stock_selector/STOCK_SELECTOR_ARCHITECTURE.md) - 股票池管理
- [ENGINE_ARCHITECTURE.md](../engine/ENGINE_ARCHITECTURE.md) - 分析引擎（含战力/涨幅/概率预测）
- [RECOMMENDER_ARCHITECTURE.md](../recommender/RECOMMENDER_ARCHITECTURE.md) - 智能推荐
- [BACKTESTER_ARCHITECTURE.md](../backtester/BACKTESTER_ARCHITECTURE.md) - 回测验证
- [SIMULATOR_ARCHITECTURE.md](../simulator/SIMULATOR_ARCHITECTURE.md) - 模拟交易
- [DATA_MANAGER_ARCHITECTURE.md](../data_manager/DATA_MANAGER_ARCHITECTURE.md) - 数据管理
