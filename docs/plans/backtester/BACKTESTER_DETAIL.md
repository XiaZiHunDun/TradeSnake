# 回测验证模块方案 - 详细设计

> **v21重要更新**：当前主引擎为 `FullBacktestEngine`（`full_backtest.py`），旧版 `Backtest` 类（`backtest.py`）已标记为兼容保留。

> 本文档是回测验证模块的详细设计部分，对应 `BACKTESTER_OVERVIEW.md` 的后续内容。

---

## 五、关键实现

### 4.1 历史数据获取

```python
def get_backtest_data(
    codes: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, List[DailyData]]:
    """获取回测所需的历史数据

    需要字段：
    - date: 日期
    - code: 股票代码
    - open/high/low/close: 价格
    - volume: 成交量
    - amount: 成交额
    - change_pct: 涨跌幅%
    - factor: 复权因子（前复权）
    """

def get_historical_factors(
    date: str,
    codes: List[str] = None
) -> Dict[str, StockFactor]:
    """获取指定日期的历史战力因子数据

    数据防护：只返回该日期及之前的历史数据
    不包含任何未来信息

    Args:
        date: 查询日期 (T日)
        codes: 股票代码列表（None=全部）

    Returns:
        {code: StockFactor} 当日战力因子数据
    """
```

**数据防护机制**：
1. 战力因子在每日收盘后计算，只包含T日及之前的数据
2. T日收盘时获取的战力数据，用于生成T+1日的调仓信号
3. 成交按T+1日收盘价，不存在时间穿越

### 4.2 撮合模拟

**成交规则**：
```python
def simulate_trade(trade_date: str, code: str, action: str,
                   price: float, quantity: int,
                   include_fees: bool = False) -> TradeResult:
    """模拟成交

    规则：
    - 按收盘价成交
    - 涨跌停拦截：涨停不买，跌停不卖
    - T+1严格模式：今日买入不可今日卖出
    - 最小交易单位：100股
    """
    # 涨跌停检查
    stock_data = get_stock_data(code, trade_date)
    if stock_data.change_pct >= 9.9 and action == 'buy':
        return TradeResult(success=False, reason='涨停无法买入')
    if stock_data.change_pct <= -9.9 and action == 'sell':
        return TradeResult(success=False, reason='跌停无法卖出')

    # T+1检查
    if strict_t1 and was_bought_today(code, trade_date):
        return TradeResult(success=False, reason='T+1限制，今日不可卖出')
```

**可选成本模型**（当 `include_fees=True`）：
```python
# 买入成本
commission = max(amount * 0.0003, 5)  # 佣金0.03%，最低5元
transfer_fee = amount * 0.00001  # 过户费0.001%
total_cost = amount + commission + transfer_fee

# 卖出成本
commission = max(amount * 0.0003, 5)
stamp_tax = amount * 0.0005  # 印花税0.05%（卖出时）
transfer_fee = amount * 0.00001
total_proceeds = amount - commission - stamp_tax - transfer_fee
```

### 4.3 调仓执行

```python
def rebalance(signal_date: str, current_positions: Dict[str, Position],
              target_codes: List[str], capital: float,
              price_data: Dict[str, DailyData]) -> List[Trade]:
    """执行调仓

    逻辑：
    1. 计算目标持仓与当前持仓的差集
    2. 卖出：不在target_codes中的持仓（按持仓天数最长的先卖）
    3. 买入：用剩余资金买入target_codes中的股票
    4. 检查涨跌停，跳过无法成交的
    5. 资金平均分配，剩余不足100股的留作现金

    Returns:
        List[Trade] 成交记录
    """
```

### 4.4 持仓管理

```python
class Position:
    """持仓"""
    code: str
    name: str
    quantity: int              # 持仓数量
    avg_cost: float           # 平均成本
    buy_date: str            # 买入日期（T日）
    holding_days: int         # 持仓天数（按交易日计算）

class PositionManager:
    """持仓管理器 v19.8

    负责持仓的日常管理：
    - 更新持仓状态
    - 检查最大持仓天数
    - T+1 限制判断
    """
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.pending_bought: Set[str] = set()  # 今日买入的股票

    def add(self, code: str, name: str, quantity: int, price: float, buy_date: str):
        """添加持仓（支持加仓）"""

    def remove(self, code: str) -> Optional[Position]:
        """移除持仓"""

    def update(self, date: str):
        """每日收盘后更新持仓状态"""

    def check_max_holding_days(self, max_days: int) -> List[str]:
        """检查超过最大持仓天数的股票，返回应卖出的列表"""

    def was_bought_today(self, code: str, date: str) -> bool:
        """检查是否今日买入（T+1判断用）"""

    def is_pending(self, code: str) -> bool:
        """检查是否在pending中（T+1限制）"""

    def get_position(self, code: str) -> Optional[Position]:
        """获取持仓"""

    def total_value(self, price_func) -> float:
        """计算持仓总市值"""
```

**持仓天数计算**：
- 买入当日计为第0天（或第1天）
- 超过 `max_position_days` 个交易日收盘后强制卖出
- 例如：`max_position_days=5`，1月1日买入，1月8日（≥5个交易日）强制卖出

---

## 六、配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `initial_capital` | 20000 | 初始资金 |
| `max_positions` | 10 | 最大持仓数 |
| `max_position_days` | 5 | 最大持仓天数（交易日） |
| `include_fees` | False | 是否计入手续费 |
| `strict_t1` | False | 是否启用T+1严格模式 |
| `benchmark` | None | 基准代码，如'000300.SH' |
| `commission_rate` | 0.0003 | 佣金率 |
| `min_commission` | 5 | 最低佣金（元） |
| `stamp_tax_rate` | 0.0005 | 印花税率（卖出，0.05%） |
| `transfer_fee_rate` | 0.00001 | 过户费率 |
| `min_trade_unit` | 100 | 最小交易单位（1手） |
| `price_model` | 'close' | 成交价模型：close/next_open/vwap |
| `cash_reserve_ratio` | 0.05 | 现金预留比例（避免资金不足） |

---

## 七、使用示例

### 7.1 FullBacktestEngine（主引擎 - 推荐）

```python
from backend.backtester.full_backtest import FullBacktestEngine

# 创建回测引擎
engine = FullBacktestEngine()

# 执行回测（使用默认TOP10策略）
result = engine.run(
    start_date='2024-01-01',
    end_date='2024-12-31',
    strategy_name='top',       # top/value/growth/momentum/rising_cp/hybrid/recommendation
    top_n=10,                  # 持仓数量
    initial_capital=20000,     # 初始资金
    stop_loss_pct=-0.07,     # 止损阈值 -7%（v21标准）
    max_holding_days=5,        # 最大持仓天数
    market_filter_pct=-2.0,   # 大盘跌幅超-2%时减半持仓
)

# 输出结果
print(f"总收益率: {result.total_return:.2f}%")
print(f"年化收益率: {result.annualized_return:.2f}%")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2f}%")
print(f"交易胜率: {result.win_rate:.2f}%")
print(f"总交易次数: {result.total_trades}")
```

### 7.2 RecommendationStrategy（推荐策略 - 使用 recommender 选股）

```python
from backend.backtester.full_backtest import FullBacktestEngine

# 创建回测引擎
engine = FullBacktestEngine()

# 使用推荐策略回测（复用 BuyAnalyzer.get_buy_signals() 完整选股逻辑）
result = engine.run_recommendation(
    start_date='2024-01-01',
    end_date='2024-12-31',
    strategy_name='recommendation',  # 使用推荐策略
    principal=1000000.0,               # 本金（元）
    risk_preference='balanced'        # 风险偏好：conservative/balanced/aggressive
)

# 输出结果
print(f"总收益率: {result.total_return:.2f}%")
print(f"年化收益率: {result.annualized_return:.2f}%")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2f}%")
```

**RecommendationStrategy 特点**：
- 复用 `BuyAnalyzer.get_buy_signals()` 的完整选股逻辑
- 包含 ST/涨跌停/停牌 过滤
- 使用 Kelly 仓位计算
- 融入预测数据（GainPrediction + ProbabilityPrediction）
- 与实盘选股逻辑一致，回测结果更能反映实盘表现

**注意**：
- 需要 `prediction_store` 中有历史预测数据
- 如果某只股票没有预测数据，`BuyAnalyzer` 会使用默认参数计算

### 7.3 Backtest（旧版引擎 - 兼容保留）

```python
from backend.backtester import Backtest, TopNStrategy, generate_report

# 定义策略：持仓战力榜TOP 10，最大持仓5天
strategy = TopNStrategy(n=10, max_days=5)

# 执行回测
bt = Backtest()
result = bt.run(
    strategy=strategy,
    start_date='2024-01-01',
    end_date='2024-12-31',
    initial_capital=20000,
    stock_list=None,          # 使用全部股票
    include_fees=True,        # 计入手续费
    strict_t1=False,          # 默认简化模式（忽略T+1）
    benchmark='000300.SH'    # 对比沪深300
)

# 输出结果
print(f"总收益率: {result.total_return:.2f}%")
print(f"年化收益率: {result.annual_return:.2f}%")
print(f"基准收益率: {result.benchmark_return:.2f}%")
print(f"超额收益: {result.excess_return:.2f}%")
print(f"夏普比率: {result.sharpe_ratio:.2f}")
print(f"卡玛比率: {result.calmar_ratio:.2f}")
print(f"最大回撤: {result.max_drawdown:.2f}%")
print(f"最大连盈: {result.max_consecutive_win}天")
print(f"最大连亏: {result.max_consecutive_loss}天")
print(f"交易胜率: {result.win_rate:.2f}%")
print(f"盈亏比: {result.profit_loss_ratio:.2f}")

# 生成报告
report = generate_report(result)
print(report)
```

### 七.2 策略有效性判断

回测结果需要结合基准对比来判断策略是否有效。核心判断依据：

**超额收益（excess_return）**：

| 超额收益 | 判断 | 说明 |
|----------|------|------|
| > 0 | ✅ 策略有效 | 跑赢了基准 |
| ≈ 0 | ⚠️ 无明显优势 | 与基准相当，不如直接买指数 |
| < 0 | ❌ 策略无效 | 跑输了基准 |

**参考判断标准**：

| 指标 | 优秀 | 良好 | 一般 | 较差 |
|------|------|------|------|------|
| 超额收益 | > 10% | 5-10% | 0-5% | < 0% |
| 夏普比率 | > 1.5 | 1.0-1.5 | 0.5-1.0 | < 0.5 |
| 卡玛比率 | > 2.0 | 1.0-2.0 | 0.5-1.0 | < 0.5 |
| 最大回撤 | < 10% | 10-20% | 20-30% | > 30% |
| 交易胜率 | > 60% | 50-60% | 40-50% | < 40% |

**回测结论解读示例**：

```markdown
## 回测结论

策略：战力TOP10选股（持仓10只，最大持仓5天）
回测期：2024-01-01 ~ 2024-12-31

| 指标 | 策略 | 沪深300 | 判断 |
|------|------|---------|------|
| 总收益率 | 25.3% | 15.2% | ✅ |
| 年化收益率 | 25.3% | 15.2% | ✅ |
| 最大回撤 | -8.5% | -12.3% | ✅ |
| 夏普比率 | 1.8 | 0.9 | ✅ |

**结论**：战力选股策略全年跑赢沪深300约10个百分点，
夏普比率接近2倍，表明策略在风险调整后收益明显优于基准。
超额收益稳定，值得实盘验证。
```

---

## 八、API集成状态

### 8.1 当前状态

✅ **已清理遗留代码**（v19.3.1）

已删除无用文件和目录：
- `api/routes.py` (78KB, 2214行) - 遗留，从未被使用
- `core/` 整个目录 - 已完全清理，包含：
  - `core/backtest.py` - 旧版回测
  - `core/risk_analyzer.py` - 旧版风险分析
  - `core/alert_engine.py` - 无用模块
  - `core/cp_engine.py` - 已迁移到 engine/
  - `core/history.py` - 已迁移到 engine/
  - `core/database.py` - 已迁移到 simulator/
  - `core/refresh_strategy.py` - 已迁移到 engine/
  - `core/trading_time.py` - 已迁移到 engine/
  - `core/migrate_to_sqlite.py` - 迁移到 scripts/

当前 `api/` 结构：
| 文件 | 状态 |
|------|------|
| `api/router.py` | ✅ 实际被使用 |
| `api/main.py` | ✅ 入口文件 |

当前 `backend/` 模块结构：
| 目录 | 版本 | 说明 |
|------|------|------|
| `data_manager/` | v18.3 | 数据管理 |
| `stock_selector/` | v19.5.2 | 股票筛选 |
| `engine/` | v19.7 | 分析引擎 |
| `recommender/` | v18.4 | 智能推荐 |
| `simulator/` | v19.7 | 模拟炒股 |
| `backtester/` | v19.7 | 回测验证 |

### 8.2 后续工作

**TODO**: 将 backtester 模块接入 `api/router.py`

### 8.3 待完善功能 (TODO)

| 功能 | 优先级 | 说明 |
|------|--------|------|
| **成交价模型扩展** | 中 | 目前仅支持 close 收盘价成交；方案设计支持 next_open/vwap，需外部需求驱动 |
| **基准数据获取** | 中 | 方案设计支持沪深300基准对比，目前返回 None；需数据源支持 |
| **预测分数融合** | 低 | 方案设计回测中可融合涨幅/概率预测；目前仅用CP分数，预测分数在 verification.py 单独验证 |
| **price_history 迁移** | 高 | 回测器当前使用 SQLite price_history 表；方案已记录应迁移到 DuckDB daily_kline |

> 注：上述功能在"一、实现差异说明"章节已有记录，此处汇总为 TODO 便于跟踪

---

## 九、输入输出验证 (2026-04-16)

### 输入验证

| 来源 | 方案描述 | 实际实现 | 状态 |
|------|----------|----------|------|
| data_manager.cp_history | 历史战力数据 | FullBacktestEngine 从 cp_history_store 读取 | ✅ |
| data_manager.prediction_store | 历史预测结果 | verification.py:340-344,450-454 正确读取 | ✅ |
| data_manager | 历史行情数据 | FullBacktestEngine 从 DuckDB daily_kline 读取 | ✅ |
| simulator | holding_snapshots | verification.py:119 正确读取 | ✅ |
| simulator | trades | verification.py:119 正确读取 | ✅ |

> **注意**：`backtest.py` 的旧版实现存在数据源问题（从 simulator.database 读取），已被 `FullBacktestEngine` 替代。

### 输出验证

| 输出内容 | 方案描述 | 实际实现 | 状态 |
|----------|----------|----------|------|
| BacktestStats | 回测绩效结果 | FullBacktestEngine 返回 BacktestStats 对象 | ✅ |
| 换股验证报告 | 胜率/平均收益 | verification.py:100-179 verify_swap_effectiveness() | ✅ |
| CP预测准确性 | 高战力组跑赢概率 | verification.py:211-317 verify_cp_prediction_accuracy() | ✅ |
| 涨幅预测准确性 | 预测偏差/TOPK准确率 | verification.py:319-427 verify_gain_prediction_accuracy() | ✅ |
| 概率预测准确性 | 概率校准度 | verification.py:429-554 verify_probability_prediction_accuracy() | ✅ |
| 回测报告存档 | backtest_reports.db | verification.py:732-768 save_verification_report() | ✅ |

### 模块对接检查

| 对接项 | 方向 | 实现方式 | 状态 |
|--------|------|----------|------|
| cp_history读取 | data_manager → backtester | FullBacktestEngine 从 cp_history_store 读取 | ✅ |
| DuckDB读取 | data_manager → backtester | FullBacktestEngine 从 DuckDB daily_kline 读取 | ✅ |
| prediction_store读取 | data_manager → backtester | verification.py 正确导入 data_manager.prediction_store | ✅ |
| holding_snapshots读取 | simulator → backtester | verification.py 通过 db.get_holding_snapshots() 读取 | ✅ |
| trades读取 | simulator → backtester | verification.py 通过 db.get_trades() 读取 | ✅ |

**✅ 已修复 (v19.9.2)**：backtester 的 `_default_get_trading_dates()` 和 `_default_get_stock_factors()` 现从 `data_manager.cp_history_store` 读取，与战力刷新保持一致。同时修复 `cp_history_store` 表结构，添加 `change_pct` 列用于回测涨跌停判断。

**✅ v21主引擎升级**：FullBacktestEngine 使用 DuckDB 作为主数据源，cp_history_store 作为战力数据源，数据流更清晰。

```python
# v21推荐：使用 FullBacktestEngine 接入 api/router.py
from backend.backtester.full_backtest import FullBacktestEngine

@router.get("/api/backtest/new")
async def new_backtest(...):
    engine = FullBacktestEngine()
    result = engine.run(...)
    return result
```

---

## 十、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v21 | 2026-05-06 | ✅ FullBacktestEngine 升级为主引擎，支持止损/风控/滑点/大盘过滤；新增 alpha_analyzer, benchmark, cost_model, factor_attributor, parameter_scanner, risk_controller, walk_forward, strategy_comparator |
| v19.9.2 | 2026-04-17 | ✅ 修复backtester从data_manager.cp_history_store读取战力数据 |
| v19.9.1 | 2026-04-14 | 补充"实现差异说明"章节：记录未完成的5项功能（成交价模型、现金预留、止损触发、基准获取、预测分数融合） |
| v19.9 | 2026-04-09 | ✅ 明确回测器数据来源，price_history为历史遗留表，计划迁移到DuckDB |
| v19.8 | 2026-04-09 | ✅ 实现 PositionManager 类、BacktestReportStore、回测报告存档功能 |
| v19.7 | 2026-04-08 | ✅ cp_history迁移到data_manager统一管理（SQLite WAL模式） |
| v19.4 | 2026-04-08 | ✅ 回测报告存档（backtest_reports）方案完成：SQLite存储、1年保留、100条上限 |
| v19.3.1 | 2026-04-07 | ✅ 清理整个 core/ 目录，迁移有用模块到对应位置 |
| v19.3 | 2026-04-07 | ✅ 修复最大回撤计算错误、新增净值曲线、补充策略有效性判断标准 |
| v19.2 | 2026-04-07 | ✅ P0修复：胜率/盈亏比改按交易次数、涨跌停拦截、T+1模式 |
| v19.1 | 2026-04-07 | 初始方案设计 |

---

## 十一、相关文档

- [ENGINE_ARCHITECTURE.md](../engine/ENGINE_ARCHITECTURE.md) - 分析引擎
- [RECOMMENDER_ARCHITECTURE.md](../recommender/RECOMMENDER_ARCHITECTURE.md) - 推荐引擎
- [SIMULATOR_ARCHITECTURE.md](../simulator/SIMULATOR_ARCHITECTURE.md) - 模拟炒股
- [DATA_MANAGER_ARCHITECTURE.md](../data_manager/DATA_MANAGER_ARCHITECTURE.md) - 数据管理
