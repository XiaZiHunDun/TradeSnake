# API模块方案 - 详细设计

> 本文档是API模块的详细路由和端点文档，对应 `API_OVERVIEW.md` 的后续内容。

---

## 一、路由详情

### 1.1 CP路由（routers/cp.py）

**标签**: 战力/推荐/换股

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/cp/list` | GET | 获取战力排行榜 |
| `/api/cp/stock/{code}` | GET | 获取单只股票战力详情 |
| `/api/cp/top` | GET | 获取战力TOP N |
| `/api/cp/explain/{code}` | GET | 战力分数解释 |
| `/api/cp/market_stats` | GET | 市场统计 |
| `/api/swap/suggestions` | GET | 换股建议 |
| `/api/recommend/buy` | GET | 买入信号 |
| `/api/recommend/sell` | GET | 卖出信号 |

**核心响应模型**：
- `CPListResponse`: 战力列表（分页）
- `SingleStockResponse`: 单只股票完整战力数据
- `SwapSuggestion`: 换股建议（from/to/净收益/行动标签）
- `RecommendResponse`: 买入/卖出信号

### 1.2 History路由（routers/history.py）

**标签**: 历史数据

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/history/kline/{code}` | GET | 获取K线数据 |
| `/api/history/cp/{code}` | GET | 获取历史战力 |
| `/api/history/portfolio` | GET | 获取历史持仓 |

### 1.3 Simulator路由（routers/simulator.py）

**标签**: 模拟交易

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/account` | GET | 获取账户信息 |
| `/api/portfolio` | GET | 获取持仓明细 |
| `/api/trades` | GET | 获取交易历史 |
| `/api/trade/buy` | POST | 买入股票 |
| `/api/trade/sell` | POST | 卖出股票 |
| `/api/user/profile` | GET | 获取用户配置 |
| `/api/simulator/risk_check` | POST | 手动触发风控检查 |
| `/api/simulator/risk_config` | GET | 获取风控配置 |
| `/api/simulator/market_regime` | GET | 获取市场环境 |
| `/api/simulator/kelly/{code}` | GET | 获取Kelly建议手数 |

**核心响应模型**：
- `AccountResponse`: 账户（cash/总资产/盈亏/收益率）
- `PortfolioResponse`: 持仓明细列表
- `TradeRequest`: 交易请求（code/action/price/quantity）
- `TradeResponse`: 交易结果

### 1.4 Backtest路由（routers/backtest.py）

**标签**: 回测优化

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/backtest/simple` | GET | 简单回测 |
| `/api/backtest/compare` | GET | 对比回测 |
| `/api/backtest/benchmark` | GET | 基准回测 |
| `/api/backtest/full` | GET | 完整回测（response_model: FullBacktestResponse） |
| `/api/backtest/trades/{task_id}` | GET | 回测交易明细 |
| `/api/backtest/equity/{task_id}` | GET | 净值曲线 |
| `/api/backtest/optimize` | POST | 异步参数优化 |
| `/api/backtest/optimize/{task_id}` | GET | 优化任务状态 |

**核心响应模型**：
- `FullBacktestResponse`: 完整回测结果（总收益率/夏普比率/最大回撤/交易明细）
- `BacktestTradeResponse`: 单笔交易记录
- `EquityPointResponse`: 净值数据点

### 1.5 Risk路由（routers/risk.py）

**标签**: 风险分析

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/risk/portfolio` | GET | 组合风险分析 |
| `/api/risk/stock/{code}` | GET | 单只股票风险 |
| `/api/risk/alerts` | GET | 风险预警 |

### 1.6 Prediction路由（routers/prediction.py）

**标签**: 预测分析

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/prediction/gain/top` | GET | 涨幅预测TOP N |
| `/api/prediction/probability/top` | GET | 上涨概率预测TOP N |
| `/api/prediction/history/{code}` | GET | 预测历史 |

**核心响应模型**：
- `GainPredictionResponse`: 涨幅预测（predicted_gain_3d/5d/confidence）
- `ProbabilityPredictionResponse`: 上涨概率（up_probability_3d/5d/confidence/risk_level）

### 1.7 System路由（routers/system.py）

**标签**: 系统管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/system/health` | GET | 健康检查 |
| `/api/system/stats` | GET | 系统统计 |
| `/api/system/config` | GET | 系统配置 |

---

## 二、API端点总表

| 端点 | 方法 | 标签 | 响应模型 |
|------|------|------|----------|
| `/api/cp/top` | GET | 战力/推荐/换股 | List[SingleStockResponse] |
| `/api/cp/bottom` | GET | 战力/推荐/换股 | List[SingleStockResponse] | 避雷榜 |
| `/api/cp/stock/{code}` | GET | 战力/推荐/换股 | SingleStockResponse |
| `/api/cp/explain/{code}` | GET | 战力/推荐/换股 | CPExplanationResponse |
| `/api/stats/market` | GET | 战力/推荐/换股 | MarketStatsResponse |
| `/api/cp/recommend` | GET | 战力/推荐/换股 | RecommendResponse | 含fusion参数 |
| `/api/cp/swap` | GET | 战力/推荐/换股 | List[SwapSuggestion] |
| `/api/history/kline/{code}` | GET | 历史数据 | KlineResponse |
| `/api/history/cp/{code}` | GET | 历史数据 | CPHistoryResponse |
| `/api/history/portfolio` | GET | 历史数据 | PortfolioHistoryResponse |
| `/api/account` | GET | 模拟交易 | AccountResponse |
| `/api/portfolio` | GET | 模拟交易 | PortfolioResponse |
| `/api/trades` | GET | 模拟交易 | TradeHistoryResponse |
| `/api/trade/buy` | POST | 模拟交易 | TradeResponse |
| `/api/trade/sell` | POST | 模拟交易 | TradeResponse |
| `/api/user/profile` | GET/PUT | 模拟交易 | UserProfileResponse |
| `/api/backtest/simple` | GET | 回测优化 | BacktestSimpleResponse |
| `/api/backtest/compare` | GET | 回测优化 | BacktestCompareResponse |
| `/api/backtest/benchmark` | GET | 回测优化 | BacktestBenchmarkResponse |
| `/api/backtest/full` | GET | 回测优化 | FullBacktestResponse |
| `/api/backtest/trades/{task_id}` | GET | 回测优化 | List[BacktestTradeResponse] |
| `/api/backtest/equity/{task_id}` | GET | 回测优化 | List[EquityPointResponse] |
| `/api/backtest/optimize` | POST | 回测优化 | OptimizationTaskResponse |
| `/api/backtest/optimize/{task_id}` | GET | 回测优化 | OptimizationStatusResponse |
| `/api/risk/portfolio` | GET | 风险分析 | PortfolioRiskResponse |
| `/api/risk/stock/{code}` | GET | 风险分析 | StockRiskResponse |
| `/api/risk/alerts` | GET | 风险分析 | RiskAlertsResponse |
| `/api/prediction/gain/top` | GET | 预测分析 | GainPredictionResponse |
| `/api/prediction/probability/top` | GET | 预测分析 | ProbabilityPredictionResponse |
| `/api/prediction/history/{code}` | GET | 预测分析 | PredictionHistoryResponse |
| `/api/system/health` | GET | 系统管理 | HealthResponse |
| `/api/system/stats` | GET | 系统管理 | SystemStatsResponse |
| `/api/system/config` | GET | 系统管理 | SystemConfigResponse |

---

## 三、关键数据模型

### 账户与持仓

```python
class AccountResponse(BaseModel):
    cash: float                    # 可用资金
    initial_cash: float           # 初始资金
    total_market_value: float     # 持仓总市值
    total_assets: float           # 总资产
    total_profit: float           # 总盈亏
    profit_rate: float            # 收益率%

class HoldingDetail(BaseModel):
    code: str
    name: str
    quantity: int
    cost_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
```

### 战力与推荐

```python
class SingleStockResponse(BaseModel):
    code: str; name: str; price: float
    total_cp: float; growth_score: float; value_score: float
    quality_score: float; momentum_score: float; risk_score: float
    pe: float; roe: float; pb: float
    # ... 完整战力数据

class SwapSuggestion(BaseModel):
    from_code: str; from_name: str; from_cp: float
    to_code: str; to_name: str; to_cp: float
    cp_improvement: float; net_profit: float
    action: str; action_label: str; action_color: str

class BuySignal(BaseModel):
    code: str; name: str; total_cp: float
    kelly_position: float; position_amount: float; shares: int
    entry_price: float; stop_loss: float; take_profit: float
    buy_strength: int; reasons: List[str]; warnings: List[str]

class SellSignal(BaseModel):
    code: str; name: str; quantity: int
    cost_price: float; current_price: float
    unrealized_pnl: float; unrealized_pnl_pct: float
    action: str; action_label: str; urgency: int
```

### 回测

```python
class FullBacktestResponse(BaseModel):
    total_return: float; annual_return: float
    sharpe_ratio: float; calmar_ratio: float
    max_drawdown: float; win_rate: float
    total_trades: int; trades: List[BacktestTrade]

class EquityPointResponse(BaseModel):
    date: str; value: float; benchmark: Optional[float]
```

---

## 四、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v19.9.11 | 2026-04-27 | 从SQLite stocks表加载财务数据用于选股器准入检查 |
| v19.9.9 | 2026-04-26 | 池状态持久化、adj_factor回填到DuckDB |
| v19.9.8 | 2026-04-25 | 收盘后分钟K线填充（差异化池策略，每天50只轮换） |
| v19.9.7 | 2026-04-24 | 收盘后K线增量填充、adj_factor Tushare填充到SQLite |
| v19.9.3 | 2026-04-20 | 差异化池刷新策略、asyncio.Lock保护cp_engine.stocks并发访问 |
