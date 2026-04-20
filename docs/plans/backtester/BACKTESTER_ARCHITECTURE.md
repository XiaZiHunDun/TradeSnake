# 回测验证模块方案 v19.9

> **v19.9更新**：明确回测器数据来源，price_history为历史遗留表，计划迁移到DuckDB

## 概述

回测验证模块是 TradeSnake 系统的策略验证层，包含两个子组件：

| 子组件 | 文件 | 定位 |
|--------|------|------|
| **回测引擎** | `backtest.py` | 基于历史数据模拟交易，评估策略绩效 |
| **策略验证** | `verification.py` | 基于simulator真实持仓验证换股效果、战力预测准确性 |

**版本**: v19.9 | **状态**: ✅ 方案确定

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
| DuckDB | `daily_kline` | **主要数据源** | ✅ 推荐使用 |
| SQLite | `price_history` | 回测器当前使用 | ⚠️ **历史遗留表，计划迁移到DuckDB** |

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
├── __init__.py           # 模块导出
├── backtest.py           # 回测引擎核心（基于历史数据的回测模拟）
│                        # 包含 PositionManager (v19.8新增)
├── verification.py       # 策略验证（换股效果验证、战力预测准确性）
│                        # 包含 BacktestReportStore (v19.8新增)
├── strategies.py          # 策略定义
├── metrics.py           # 绩效指标计算
└── reports.py           # 回测报告生成
```

---

## 四、核心组件

### 3.1 Backtest（回测引擎）

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
- **T+1严格模式**：`strict_t1=True` 时，今日买入的股票不能今日卖出

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
| CustomStrategy | 自定义策略 | 用户传入选股函数 |

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
    profit_loss_ratio: float  # 盈亏比
    avg_holding_days: float   # 平均持仓天数

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
stamp_tax = amount * 0.0005  # 印花税0.05%
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
| `stamp_tax_rate` | 0.0005 | 印花税率（卖出） |
| `transfer_fee_rate` | 0.00001 | 过户费率 |
| `min_trade_unit` | 100 | 最小交易单位（1手） |
| `price_model` | 'close' | 成交价模型：close/next_open/vwap |
| `cash_reserve_ratio` | 0.05 | 现金预留比例（避免资金不足） |

---

## 七、使用示例

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

### 六.1 策略有效性判断

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

### 7.1 当前状态

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

### 7.2 后续工作

**TODO**: 将 backtester 模块接入 `api/router.py`

### 7.3 待完善功能 (TODO)

| 功能 | 优先级 | 说明 |
|------|--------|------|
| **成交价模型扩展** | 中 | 目前仅支持 close 收盘价成交；方案设计支持 next_open/vwap，需外部需求驱动 |
| **基准数据获取** | 中 | 方案设计支持沪深300基准对比，目前返回 None；需数据源支持 |
| **预测分数融合** | 低 | 方案设计回测中可融合涨幅/概率预测；目前仅用CP分数，预测分数在 verification.py 单独验证 |
| **price_history 迁移** | 高 | 回测器当前使用 SQLite price_history 表；方案已记录应迁移到 DuckDB daily_kline |

> 注：上述功能在"一、实现差异说明"章节已有记录，此处汇总为 TODO 便于跟踪

## 七.y 输入输出验证 (2026-04-16)

### 输入验证

| 来源 | 方案描述 | 实际实现 | 状态 |
|------|----------|----------|------|
| data_manager.cp_history | 历史战力数据 | backtest.py:609-618 从 simulator.database 读取 | ⚠️ |
| data_manager.prediction_store | 历史预测结果 | verification.py:340-344,450-454 正确读取 | ✅ |
| data_manager | 历史行情数据 | backtest.py:661-675 从 SQLite price_history 读取 | ⚠️ |
| simulator | holding_snapshots | verification.py:119 正确读取 | ✅ |
| simulator | trades | verification.py:119 正确读取 | ✅ |

### 输出验证

| 输出内容 | 方案描述 | 实际实现 | 状态 |
|----------|----------|----------|------|
| BacktestResult | 回测绩效结果 | backtest.py 返回 BacktestResult 对象 | ✅ |
| 换股验证报告 | 胜率/平均收益 | verification.py:100-179 verify_swap_effectiveness() | ✅ |
| CP预测准确性 | 高战力组跑赢概率 | verification.py:211-317 verify_cp_prediction_accuracy() | ✅ |
| 涨幅预测准确性 | 预测偏差/TOPK准确率 | verification.py:319-427 verify_gain_prediction_accuracy() | ✅ |
| 概率预测准确性 | 概率校准度 | verification.py:429-554 verify_probability_prediction_accuracy() | ✅ |
| 回测报告存档 | backtest_reports.db | verification.py:732-768 save_verification_report() | ✅ |

### 模块对接检查

| 对接项 | 方向 | 实现方式 | 状态 |
|--------|------|----------|------|
| cp_history读取 | data_manager → backtester | backtester 从 simulator.database 读取，而非 data_manager/cp_history_store | ⚠️ |
| prediction_store读取 | data_manager → backtester | verification.py 正确导入 data_manager.prediction_store | ✅ |
| holding_snapshots读取 | simulator → backtester | verification.py 通过 db.get_holding_snapshots() 读取 | ✅ |
| trades读取 | simulator → backtester | verification.py 通过 db.get_trades() 读取 | ✅ |

**问题**：backtest.py 的 `_default_get_trading_dates()` 和 `_default_get_stock_factors()` 从 `simulator.database` 读取 cp_history，但战力数据实际由 `data_manager/cp_history_store` 管理。

**✅ 已修复 (v19.9.2)**：backtester 的 `_default_get_trading_dates()` 和 `_default_get_stock_factors()` 现从 `data_manager.cp_history_store` 读取，与战力刷新保持一致。同时修复 `cp_history_store` 表结构，添加 `change_pct` 列用于回测涨跌停判断。

**建议**：回测器应支持从 data_manager 获取数据，或确保两个数据源同步。

```python
# 目标：使用新的 backtester 模块接入 api/router.py
from backend.backtester import Backtest, TopNStrategy, generate_report

@router.get("/api/backtest/new")
async def new_backtest(...):
    bt = Backtest()
    result = bt.run(...)
    return generate_report(result)
```

---

## 九、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
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

## 十、相关文档

- [ENGINE_ARCHITECTURE.md](./ENGINE_ARCHITECTURE.md) - 分析引擎
- [RECOMMENDER_ARCHITECTURE.md](./RECOMMENDER_ARCHITECTURE.md) - 推荐引擎
- [SIMULATOR_ARCHITECTURE.md](./SIMULATOR_ARCHITECTURE.md) - 模拟炒股
- [DATA_MANAGER_ARCHITECTURE.md](./DATA_MANAGER_ARCHITECTURE.md) - 数据管理
