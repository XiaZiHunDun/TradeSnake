# API模块方案

> 本文档是API模块的入口索引，实际内容拆分到以下两个文件中：

## 文档结构

| 文件 | 内容 | 行数 |
|------|------|------|
| [API_OVERVIEW.md](./API_OVERVIEW.md) | 概述、输入输出、模块结构、核心设计（依赖注入/后台任务/CORS/异常处理） | ~350 |
| [API_DETAIL.md](./API_DETAIL.md) | 路由详情（7个子路由）、API端点总表、数据模型、版本历史 | ~280 |

## 内容速览

### API_OVERVIEW.md
- **概述**：FastAPI入口（8001端口）、7个子路由聚合（战力/历史/模拟/回测/风险/预测/系统）
- **输入输出**：输入（WebSocket/前端HTTP/后台调度），输出（JSON响应/实时推送）
- **模块结构**：main.py(主入口+生命周期) + router.py(路由聚合) + dependencies.py(依赖注入) + limits.py(限流) + websocket.py(WebSocket管理) + routers/(7个子路由)
- **核心设计**：依赖注入(cp_engine/recommend_engine/db/portfolio/trader)、后台任务(background_refresh_task+pool_rebalance_background_task)、差异化池刷新(核心池5min/活跃池30min)、CORS配置、WebSocket推送、全局异常处理器

### API_DETAIL.md
- **路由详情**：7个子路由（cp/history/simulator/backtest/risk/prediction/system）完整端点清单
- **API端点总表**：27个端点（战力8个/回测8个/历史3个/模拟5个/预测3个/系统3个）
- **数据模型**：AccountResponse/HoldingDetail/PortfolioResponse/CPListResponse/SingleStockResponse/SwapSuggestion/BuySignal/SellSignal等
- **版本历史**：v19.9.3~v19.9.11 共5个版本

---

## 模块说明

API模块是 TradeSnake 系统的 HTTP/WebSocket 接口层，负责：
- 聚合所有子路由（战力、推荐、回测、模拟交易、历史、预测、系统管理）
- 管理 FastAPI 生命周期（启动初始化、后台刷新、关闭清理）
- 提供 WebSocket 实时推送能力
- 统一的认证、限流、异常处理

**版本**: v19.9.11 | **状态**: ✅ 稳定运行

**端口**: http://localhost:8001

---

## 目录结构

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
