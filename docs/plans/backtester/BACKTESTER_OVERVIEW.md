# 回测验证模块方案 v21

> **v21重要更新**：当前主引擎为 `FullBacktestEngine`（`full_backtest.py`），旧版 `Backtest` 类（`backtest.py`）已标记为兼容保留。

> **v19.9历史更新**：明确回测器数据来源，price_history为历史遗留表，计划迁移到DuckDB

**版本**: v21 | **状态**: ✅ 方案确定

---

## 输入输出

### 输入
| 来源 | 数据内容 |
|------|----------|
| data_manager | cp_history（历史战力数据，用于历史战力评分） |
| data_manager | prediction_store（历史预测结果，用于验证预测准确性） |
| data_manager | 历史行情数据（收盘价、成交量、涨跌幅） |
| simulator | holding_snapshots（每日持仓快照，用于验证） |
| simulator | trades（交易记录，用于换股效果验证） |

**历史行情数据来源说明**：

| 存储 | 表名 | 用途 | 状态 |
|------|------|------|------|
| DuckDB | `daily_kline` | **主要数据源 ✅** | 已迁移完成 |
| SQLite | `price_history` | 回测器历史使用 | ⚠️ 旧数据源，DuckDB 已包含相同时间段 |

> 注意：`price_history` 是历史遗留表，回测器当前仍使用它。DuckDB `daily_kline` 已覆盖相同时间段，**计划迁移回测器到DuckDB**。

### 输出
| 输出内容 | 使用者 |
|----------|--------|
| BacktestResult（总收益率、夏普比率、最大回撤等） | 用户/前端展示 |
| 换股验证报告（换股胜率、平均收益） | 用户/前端展示 |
| CP预测准确性报告（高战力组跑赢市场概率） | 用户/前端展示 |
| 涨幅预测准确性报告（预测偏差、TopK准确率） | 用户/前端展示 |
| 概率预测准确性报告（概率校准度） | 用户/前端展示 |
| 回测报告存档 | 文件系统存储（data/backtest_reports.db，1年/100条） |

---

## 回测声明（必读）

本回测模块存在以下**简化假设**，结论仅供参考，不构成投资建议：

| 假设 | 说明 | 影响 |
|------|------|------|
| **不分股模式（默认）** | 卖出后可立即买入 | 忽略T+1限制，收益可能偏高 |
| **可选T+1严格模式** | `strict_t1=True`时启用 | 更贴近实盘 |
| **固定成交价** | 按收盘价模拟成交 | 无法模拟盘中波动 |
| **固定股票池** | 使用当前股票池 | 不含已退市股票（幸存者偏差） |
| **可选手续费** | `include_fees=True`时计入 | 收益率更精确 |

**如需更精确模拟，可开启 `include_fees=True` 和 `strict_t1=True`**

---

## 一、实现差异说明

以下功能在设计文档中有描述，但**当前实现未完成**：

| 功能 | 设计文档描述 | 当前实现 | 说明 |
|------|-------------|----------|------|
| **成交价模型** | 支持 close/next_open/vwap 三种 | 仅支持 close | 回测按收盘价成交是简化，暂无需求实现其他模型 |
| **基准数据获取** | `benchmark='000300.SH'` 获取沪深300数据 | 返回None，需外部提供 | 基准对比功能需外部提供数据源 |
| **预测分数融合** | 回测中可融合涨幅/概率预测 | 仅使用CP分数 | 预测分数在verification.py单独验证，未融入回测选股 |

> **注意**：止损止盈逻辑属于 recommender 模块（buy_analyzer/sell_analyzer），不属于 backtester 职责范围。backtester 仅记录交易原因字段。

---

## 二、设计背景

本模块定位为**战力驱动的选股回测工具**，核心目的是：

1. 验证"战力选股"策略的有效性
2. 评估策略的收益率、风险、最大回撤等指标
3. 辅助用户优化持仓数量、换仓频率等参数

**与模拟炒肉的区分**：

| 模块 | 定位 | T+1 | 手续费 | 适用场景 |
|------|------|-----|--------|----------|
| 模拟炒股 | 实盘模拟 | ✅ 严格 | ✅ 精确 | 真实交易练习 |
| 回测模块 | 策略验证 | 可选 | 可选 | 快速验证想法 |

---

## 三、模块结构

```
backtester/
├── __init__.py              # 模块导出
├── full_backtest.py         # FullBacktestEngine 主回测引擎（v21主引擎）
├── backtest.py              # Backtest 旧版回测引擎（兼容保留）
├── verification.py          # 策略验证（换股效果验证、战力预测准确性）
│                           # 包含 BacktestReportStore (v19.8新增)
├── strategies.py            # 策略定义
│                           # 新增: RisingCPStrategy, HybridRisingStrategy, MultiFactorStrategy
├── metrics.py              # 绩效指标计算
├── reports.py              # 回测报告生成
├── alpha_analyzer.py       # Alpha因子验证分析器（IC、分组回测、信号衰减）
├── benchmark.py            # 基准数据获取（沪深300、等权组合）
├── cost_model.py           # 交易成本模型（佣金、印花税、过户费、滑点）
├── factor_attributor.py    # 因子归因器（IC分析 + 分组单调性验证）
├── parameter_scanner.py    # 参数扫描器（贝叶斯优化参数搜索）
├── risk_controller.py      # 风控控制器（止损、仓位限制、大盘过滤）
├── walk_forward.py         # Walk-Forward滚动窗口回测
└── strategy_comparator.py  # 策略对比器（多策略绩效对比）
```

### 新增文件说明

| 文件 | 作用 | 核心类/函数 |
|------|------|-------------|
| `alpha_analyzer.py` | Alpha因子验证分析 | `AlphaAnalyzer` - IC分析、分组回测、信号衰减 |
| `benchmark.py` | 基准数据获取 | `BenchmarkProvider` - 沪深300/等权基准收益 |
| `cost_model.py` | 交易成本计算 | `CostModel` - 佣金/印花税/过户费/滑点 |
| `factor_attributor.py` | 因子归因分析 | `FactorAttributor` - IC分析、分组单调性验证 |
| `parameter_scanner.py` | 参数优化搜索 | `ParameterScanner` - 两阶段参数搜索 |
| `risk_controller.py` | 风控机制 | `RiskController` - 止损、大盘过滤、仓位限制 |
| `walk_forward.py` | Walk-Forward回测 | `WalkForwardBacktester` - 滚动窗口验证 |
| `strategy_comparator.py` | 策略对比 | `StrategyComparator` - 多策略绩效对比 |

---

## 四、核心组件

### 3.1 FullBacktestEngine（主回测引擎）

> **v21主引擎**：基于战力数据进行完整回测，支持止损、风控、仓位管理

**核心方法**：
```python
class FullBacktestEngine:
    def run(
        self,
        start_date: str,              # 开始日期 YYYY-MM-DD
        end_date: str,                # 结束日期 YYYY-MM-DD
        strategy_name: str = 'top',   # 策略名称 (top/value/growth/momentum)
        top_n: int = 10,              # 持仓数量
        initial_capital: float = 20000.0,  # 初始资金
        weight_config: Dict = None,   # 战力权重配置（如需自定义）
        stop_loss_pct: float = -0.07, # 止损阈值 -7%（v21标准）
        max_holding_days: int = 5,    # 最大持仓天数
        market_filter_pct: float = -2.0  # 大盘过滤阈值
    ) -> BacktestStats
```

**回测流程**：
```
T日收盘：
    1. 获取T日战力数据
    2. 执行策略 select_stocks(T日战力) → 目标持仓列表
    3. 对比当前持仓与目标持仓
    4. 生成调仓信号（仅当列表变化时）

T+1日收盘：
    5. 按T+1日收盘价执行成交
    6. 涨跌停股票无法成交（跳过）
    7. 更新持仓状态
    8. 记录每日净值
```

**关键规则**：
- **信号日→成交日分离**：避免时间穿越，T日收盘信号，T+1日成交
- **涨跌停拦截**：
  - 涨幅 >= 9.9% 的股票：取消买入
  - 跌幅 <= -9.9% 的股票：取消卖出
- **仅当持仓变化时调仓**：避免无意义的手续费
- **止损机制**：`stop_loss_pct` 亏损超过阈值立即卖出
- **大盘过滤**：`market_filter_pct` 大盘跌幅超过阈值时减半持仓

**返回 BacktestStats**：
```python
@dataclass
class BacktestStats:
    initial_capital: float
    final_value: float
    total_return: float           # 总收益率%
    annualized_return: float      # 年化收益率%
    sharpe_ratio: float           # 夏普比率
    max_drawdown: float           # 最大回撤%
    win_rate: float               # 交易胜率%
    total_trades: int            # 总交易次数
    equity_curve: List[Dict]     # 净值曲线
    trades: List[Dict]            # 交易明细
    completed_pnls: List[float]  # 已平仓盈亏列表
```

---

### 3.1.2 Backtest（旧版回测引擎 - 兼容保留）

> **兼容保留**：旧版 `Backtest` 类仅用于向后兼容，新代码请使用 `FullBacktestEngine`

**核心方法**：
```python
class Backtest:
    def run(
        strategy: Strategy,
        start_date: str,           # 开始日期 YYYY-MM-DD
        end_date: str,             # 结束日期 YYYY-MM-DD
        initial_capital: float,    # 初始资金
        stock_list: List[str] = None,  # 股票池（None=全部）
        include_fees: bool = False,     # 是否计入手续费
        strict_t1: bool = False,        # 是否启用T+1严格模式
        benchmark: str = None,          # 基准代码，如 '000300.SH'（沪深300）
    ) -> BacktestResult
```

**与 FullBacktestEngine 的差异**：

| 特性 | FullBacktestEngine（主引擎） | Backtest（旧版） |
|------|------------------------------|------------------|
| 止损机制 | ✅ 支持（stop_loss_pct） | ❌ 不支持 |
| 大盘过滤 | ✅ 支持（market_filter_pct） | ❌ 不支持 |
| 滑点模型 | ✅ 支持（0.1%滑点） | ❌ 不支持 |
| 多因子权重 | ✅ 支持（weight_config） | ❌ 不支持 |
| DuckDB数据源 | ✅ 主数据源 | ⚠️ SQLite price_history |

---

### 3.2 Strategy（策略定义）

**策略基类**：
```python
class Strategy(ABC):
    @abstractmethod
    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int) -> List[str]:
        """根据日期和股票因子数据返回应持仓的股票代码

        Args:
            date: 信号日 (T日)
            stock_factors: {code: StockFactor} 历史战力因子数据
            rank: 最大持仓数量

        Returns:
            目标持仓股票代码列表
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    def max_position_days(self) -> int:
        """最大持仓天数（交易日），默认5天"""
        return 5

    @property
    def max_positions(self) -> int:
        """最大持仓数量，默认10只"""
        return 10
```

**StockFactor 数据结构**：
```python
@dataclass
class StockFactor:
    code: str
    name: str
    date: str                      # 日期
    close: float                  # 收盘价
    change_pct: float             # 涨跌幅%
    total_cp: float               # 战力总分
    growth_score: float           # 成长分
    value_score: float            # 价值分
    momentum_score: float          # 动量分
    quality_score: float          # 质量分
    is_limit_up: bool             # 是否涨停
    is_limit_down: bool           # 是否跌停
    is_suspended: bool            # 是否停牌
```

**预定义策略**：

| 策略 | 说明 | 实现 |
|------|------|------|
| TopNStrategy | 持仓战力榜TOP N | 按total_cp排序取TOP N |
| ValueStrategy | 价值型策略 | 按value_score排序取TOP N |
| GrowthStrategy | 成长型策略 | 按growth_score排序取TOP N |
| MomentumStrategy | 动量策略 | 按momentum_score排序取TOP N |
| MultiFactorStrategy | 多因子融合 | 因子加权综合评分 |
| RisingCPStrategy | 战力提升策略 | 持有战力提升的股票 |
| HybridRisingStrategy | 混合策略 | 战力+成长双维度 |
| LowVolatilityStrategy | 低波动策略 | 波动率低且动量正向 |
| HighDividendStrategy | 高股息策略 | 股息率高且价值低估 |
| ValueGrowthBalancedStrategy | 价值成长平衡 | 价值+成长均衡配置 |
| RecommendationStrategy | 推荐策略 | 复用BuyAnalyzer选股逻辑 |
| CustomStrategy | 自定义策略 | 用户传入选股函数 |

> v21 新增：RisingCPStrategy, HybridRisingStrategy, LowVolatilityStrategy, HighDividendStrategy, ValueGrowthBalancedStrategy, RecommendationStrategy

---

### 3.3 Metrics（绩效指标）

**计算指标**：

| 类别 | 指标 | 说明 | 计算方式 |
|------|------|------|----------|
| 收益 | **总收益率** | 整体收益 | (最终净值 - 1) × 100% |
| 收益 | **年化收益率** | 年化收益 | (1 + 总收益)^(250/交易日) - 1 |
| 收益 | **基准收益率** | 对比基准收益 | (基准最终 - 基准初始) / 基准初始 |
| 收益 | **超额收益** | 相对基准超额 | 总收益率 - 基准收益率 |
| 风险 | **最大回撤** | 最大跌幅 | max(peak - 谷值) / peak × 100% |
| 风险 | **年化波动率** | 收益波动率 | 日收益标准差 × √250 × 100（百分比值） |
| 风险 | **最大连续亏损天数** | 最长连续亏损 | max(连续亏损天数) |
| 风险 | **最大连续盈利天数** | 最长连续盈利 | max(连续盈利天数) |
| 综合 | **夏普比率** | 风险调整收益 | (年化收益 - 无风险利率) / 年化波动率 |
| 综合 | **卡玛比率** | 收益/回撤比 | 年化收益 / 最大回撤 |
| 交易 | **交易胜率** | 盈利交易占比 | 盈利交易次数 / 总交易次数 |
| 交易 | **盈亏比** | 平均盈/亏 | 平均盈利金额 / 平均亏损金额 |
| 交易 | **平均持仓天数** | 平均持仓时长 | 总持仓天数 / 交易次数 |
| 交易 | **总交易次数** | 买入+卖出总笔数 | - |
| 交易 | **盈利次数** | 盈利交易笔数 | - |
| 交易 | **亏损次数** | 亏损交易笔数 | - |

**指标计算说明**：

```python
# 夏普比率（含无风险利率）
risk_free_rate = 0.03  # 3%年化
sharpe = (annual_return - risk_free_rate) / volatility

# 交易胜率（按交易次数，非天数）
winning_trades = sum(1 for t in trades if t.profit > 0)
total_trades = len(trades)
win_rate = winning_trades / total_trades if total_trades > 0 else 0

# 盈亏比（按交易金额）
avg_profit = sum(t.profit for t in trades if t.profit > 0) / winning_trades
avg_loss = abs(sum(t.profit for t in trades if t.profit < 0) / losing_trades)
profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
```

**净值序列**：
```python
{
    'dates': ['2024-01-01', '2024-01-02', ...],
    'values': [1.0, 1.02, 0.98, ...],
    'benchmark': [1.0, 1.01, 0.99, ...],  # 可选
    'positions': [{'code': '000001', 'quantity': 100}, ...]
}
```

---

### 3.4 Reports（报告生成）

**回测报告结构**：
```python
class BacktestResult:
    strategy_name: str           # 策略名称
    start_date: str             # 开始日期
    end_date: str               # 结束日期
    initial_capital: float      # 初始资金
    final_capital: float        # 最终资金

    # 绩效指标
    total_return: float         # 总收益率%
    annual_return: float        # 年化收益率%
    benchmark_return: float     # 基准收益率%
    excess_return: float        # 超额收益率%
    sharpe_ratio: float         # 夏普比率
    calmar_ratio: float         # 卡玛比率
    max_drawdown: float         # 最大回撤%
    volatility: float           # 年化波动率%
    max_consecutive_win: int   # 最大连续盈利天数
    max_consecutive_loss: int  # 最大连续亏损天数

    # 交易指标
    total_trades: int          # 总交易次数
    winning_trades: int        # 盈利次数
    losing_trades: int         # 亏损次数
    win_rate: float            # 交易胜率%
    profit_loss_ratio: float   # 盈亏比
    avg_holding_days: float    # 平均持仓天数

    # 交易记录
    trades: List[Trade]        # 交易明细

    # 净值曲线
    equity_curve: Dict         # 日期→总资产
    net_value_curve: Dict      # 日期→净值（总资产/初始资金）

    # 持仓记录
    positions_history: List[Dict]  # 每日持仓
```

**Trade 数据结构**：
```python
@dataclass
class Trade:
    signal_date: str           # 信号日
    trade_date: str           # 成交日
    code: str                  # 股票代码
    name: str                  # 股票名称
    action: Literal['buy', 'sell']
    price: float              # 成交价
    quantity: int              # 成交数量
    amount: float              # 成交金额
    commission: float          # 佣金
    stamp_tax: float          # 印花税（卖出时）
    transfer_fee: float       # 过户费
    profit: float             # 盈亏（卖出时）
    reason: str               # 原因：'rebalance'/'stop_loss'/'max_days'
```

**报告生成方法**：
```python
def generate_report(result: BacktestResult) -> str:
    """生成Markdown格式回测报告"""

def save_report(result: BacktestResult, path: str):
    """保存报告到文件"""
```

### 3.5 Verification（策略验证）

**文件**: `verification.py`

**核心职责**: 基于simulator的真实持仓和交易数据，验证策略效果

**功能**:
| 方法 | 说明 |
|------|------|
| `verify_swap_effectiveness()` | 验证换股效果：卖出后持有到现在是否盈利 |
| `verify_cp_prediction_accuracy()` | 验证战力预测：高战力股票是否跑赢市场 |
| `verify_prediction_accuracy()` | 验证涨幅/概率预测准确性（v19.8新增） |
| `get_verification_report()` | 生成综合验证报告 |
| `get_swap_summary()` | 获取换股验证汇总统计 |

**数据来源**:
```python
# 从simulator获取真实交易数据
trades = db.get_trades(limit=1000)  # 所有卖出交易
holding_snapshots = db.get_holding_snapshots()  # 每日持仓快照

# 从data_manager获取cp_history
cp_store = get_cp_history_store()
cp_history = cp_store.get_cp_history(code, days=30)  # 卖出时的战力

# 从data_manager获取prediction_store（v19.8新增）
prediction_store = get_prediction_store()
predictions = prediction_store.get_predictions(code, days=30)  # 卖出时的预测
```

**验证指标**:
| 指标 | 说明 | 数据来源 |
|------|------|----------|
| 换股胜率 | 卖出后盈利的比例 | simulator/trades |
| 换股平均收益 | 卖出价 vs 当前价的变化 | simulator/trades |
| 高战力组跑赢概率 | 高战力股票跑赢市场的比例 | cp_history |
| 涨幅预测偏差 | predicted_gain vs 实际涨幅 | prediction_store |
| 概率预测校准度 | up_probability vs 实际上涨比例 | prediction_store |

**输出到 backtest_reports.db**:
```python
def save_verification_report(report: Dict, report_type: str = 'general') -> str:
    """保存验证报告到SQLite（backtest_reports.db）

    保留策略: 1年或100条，超限自动删除最旧记录
    """
    store = get_report_store()
    return store.save_verification_report(report, report_type)

def save_backtest_report(result: BacktestResult, content: str = None) -> str:
    """保存回测报告到SQLite"""
    store = get_report_store()
    return store.save_backtest_report(result, content)
```
