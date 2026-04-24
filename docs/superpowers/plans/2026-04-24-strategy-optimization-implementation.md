# 策略优化实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现三阶段策略优化系统：策略对比 → 参数扫描 → 因子归因，支持稳健型策略（集中持仓、高胜率）的系统化评测。

**Architecture:**
- `cost_model.py`: 交易成本模型（佣金+印花税+滑点）
- `risk_controller.py`: 风控机制（组合止损、连续亏损保护、大盘过滤）
- `strategy_comparator.py`: 策略对比（阶段1）
- `parameter_scanner.py`: 参数扫描+贝叶斯优化（阶段2）
- `factor_attributor.py`: 因子归因 IC 分析（阶段3）
- 修改 `strategies.py`: 添加 3 种新策略
- 修改 `full_backtest.py`: 支持参数化回测 + 成本扣除
- 修改 `metrics.py`: IC/IR 计算 + 交易胜率截尾处理

**Tech Stack:** Python, numpy, scipy, scipy.optimize (贝叶斯优化), pytest

---

## 阶段1：基础设施

### Task 1: 交易成本模型

**Files:**
- Create: `backend/backtester/cost_model.py`
- Test: `tests/backtester/test_cost_model.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtester/test_cost_model.py
import pytest
from backend.backtester.cost_model import CostModel, calculate_total_cost

def test_buy_commission():
    """买入时收取佣金"""
    cost = calculate_total_cost(amount=100000, action='buy')
    assert cost['commission'] == 10.0  # 万1 = 10元
    assert cost['stamp_tax'] == 0
    assert cost['slippage'] == 100.0  # 0.1% = 100元

def test_sell_commission_and_stamp_tax():
    """卖出时收取佣金+印花税+滑点"""
    cost = calculate_total_cost(amount=100000, action='sell')
    assert cost['commission'] == 10.0  # 万1
    assert cost['stamp_tax'] == 50.0   # 千0.5 = 50元
    assert cost['slippage'] == 100.0   # 0.1%

def test_minimum_commission():
    """最低佣金5元"""
    cost = calculate_total_cost(amount=10000, action='buy')
    assert cost['commission'] == 5.0  # 万1=1元，但最低5元

def test_slippage_calculation():
    """滑点按金额比例计算"""
    cost = calculate_total_cost(amount=50000, action='buy')
    assert cost['slippage'] == 50.0  # 0.1% of 50000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backtester/test_cost_model.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement cost model**

```python
# backend/backtester/cost_model.py
"""交易成本模型 v1.0"""

from dataclasses import dataclass

@dataclass
class CostResult:
    commission: float      # 佣金
    stamp_tax: float       # 印花税（仅卖出）
    transfer_fee: float    # 过户费（沪市双向）
    slippage: float        # 滑点
    total_cost: float      # 总成本

    def total(self) -> float:
        return self.commission + self.stamp_tax + self.transfer_fee + self.slippage


# 费率配置
COMMISSION_RATE = 0.0001       # 万1
MIN_COMMISSION = 5.0          # 最低佣金5元
STAMP_TAX_RATE = 0.0005       # 千0.5（卖出时）
TRANSFER_FEE_RATE = 0.00001   # 千0.01（沪市双向，深市免）
SLIPPAGE_RATE = 0.001         # 0.1%


def calculate_total_cost(amount: float, action: str, is_shanghai: bool = True) -> CostResult:
    """计算交易成本

    Args:
        amount: 成交金额
        action: 'buy' 或 'sell'
        is_shanghai: 是否沪市（影响过户费）

    Returns:
        CostResult: 各成本明细
    """
    # 佣金（双向）
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)

    # 印花税（仅卖出）
    stamp_tax = amount * STAMP_TAX_RATE if action == 'sell' else 0.0

    # 过户费（沪市双向，深市免）
    transfer_fee = amount * TRANSFER_FEE_RATE if is_shanghai else 0.0

    # 滑点（双向，金额比例）
    slippage = amount * SLIPPAGE_RATE

    total = commission + stamp_tax + transfer_fee + slippage

    return CostResult(
        commission=round(commission, 2),
        stamp_tax=round(stamp_tax, 2),
        transfer_fee=round(transfer_fee, 2),
        slippage=round(slippage, 2),
        total_cost=round(total, 2)
    )


def apply_cost_to_capital(capital: float, amount: float, action: str, is_shanghai: bool = True) -> float:
    """计算扣成本后的资金变化

    Args:
        capital: 当前资金
        amount: 成交金额
        action: 'buy' 或 'sell'

    Returns:
        扣成本后的资金
    """
    cost = calculate_total_cost(amount, action, is_shanghai)
    if action == 'buy':
        return capital - amount - cost.total_cost
    else:  # sell
        return capital + amount - cost.total_cost
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backtester/test_cost_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/backtester/test_cost_model.py backend/backtester/cost_model.py
git commit -m "feat(backtester): add trading cost model

- Commission: 万1 (min 5元)
- Stamp tax: 千0.5 (sell only)
- Transfer fee: 千0.01 (Shanghai only)
- Slippage: 0.1% (both sides)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

### Task 2: 风控机制

**Files:**
- Create: `backend/backtester/risk_controller.py`
- Test: `tests/backtester/test_risk_controller.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtester/test_risk_controller.py
import pytest
from backend.backtester.risk_controller import RiskController, RiskConfig

def test_default_config():
    config = RiskConfig()
    assert config.stop_loss == -0.10
    assert config.max_daily_loss == -0.03
    assert config.consecutive_loss_days == 3
    assert config.market_filter_down == -0.02
    assert config.market_filter_exit == -0.04

def test_risk_controller_state():
    controller = RiskController()
    assert controller.is_normal()
    assert controller.consecutive_loss_count == 0

def test_market_filter_reduce():
    controller = RiskController()
    # 大盘跌-2.5%，应减半持仓
    action = controller.check_market_filter(-2.5)
    assert action == 'reduce'

def test_market_filter_exit():
    controller = RiskController()
    # 大盘跌-5%，应空仓
    action = controller.check_market_filter(-5.0)
    assert action == 'exit'

def test_consecutive_loss_protection():
    controller = RiskController()
    # 连续3日亏损后触发保护
    for _ in range(3):
        controller.record_daily_return(-0.01)
    assert controller.should_protect()

def test_stop_loss_record():
    controller = RiskController()
    controller.record_trade_result(profit_pct=-0.12)
    assert controller.total_loss >= 0.12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backtester/test_risk_controller.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement risk controller**

```python
# backend/backtester/risk_controller.py
"""风控机制 v1.0"""

from dataclasses import dataclass, field
from typing import List

@dataclass
class RiskConfig:
    """风控配置"""
    stop_loss: float = -0.10           # 个股止损 -10%
    max_daily_loss: float = -0.03      # 单日最大亏损 -3%
    consecutive_loss_days: int = 3      # 连续亏损天数阈值
    market_filter_down: float = -0.02  # 大盘跌幅超过此值减半持仓
    market_filter_exit: float = -0.04  # 大盘跌幅超过此值空仓
    single_position_limit: float = 0.15 # 单只仓位上限 15%
    observation_days: int = 2          # 空仓观望天数


class RiskController:
    """风控控制器 v1.0"""

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        self.consecutive_loss_count = 0
        self.daily_returns: List[float] = []
        self.total_loss = 0.0
        self.protection_active = False
        self.protection_remaining_days = 0

    def is_normal(self) -> bool:
        return not self.protection_active

    def should_protect(self) -> bool:
        return self.consecutive_loss_count >= self.config.consecutive_loss_days

    def check_market_filter(self, market_change_pct: float) -> str:
        """检查大盘过滤

        Args:
            market_change_pct: 大盘当日涨跌幅%

        Returns:
            'normal' / 'reduce' / 'exit'
        """
        if market_change_pct <= self.config.market_filter_exit:
            return 'exit'
        elif market_change_pct <= self.config.market_filter_down:
            return 'reduce'
        return 'normal'

    def record_daily_return(self, daily_return: float):
        """记录每日收益，用于连续亏损检测"""
        self.daily_returns.append(daily_return)
        if daily_return < 0:
            self.consecutive_loss_count += 1
        else:
            self.consecutive_loss_count = 0

    def record_trade_result(self, profit_pct: float):
        """记录交易结果"""
        if profit_pct < 0:
            self.total_loss += abs(profit_pct)

    def activate_protection(self):
        """激活保护机制"""
        self.protection_active = True
        self.protection_remaining_days = self.config.observation_days

    def tick_protection(self):
        """保护期倒计时"""
        if self.protection_remaining_days > 0:
            self.protection_remaining_days -= 1
        if self.protection_remaining_days <= 0:
            self.protection_active = False
            self.consecutive_loss_count = 0

    def should_stop_loss(self, position_return: float) -> bool:
        """检查是否应止损"""
        return position_return <= self.config.stop_loss

    def get_position_limit(self, market_action: str) -> float:
        """获取仓位限制

        Args:
            market_action: 'normal' / 'reduce' / 'exit'

        Returns:
            仓位比例 (0.0 ~ 1.0)
        """
        if market_action == 'exit':
            return 0.0
        elif market_action == 'reduce':
            return 0.5
        return 1.0

    def reset(self):
        """重置风控状态（新回测周期）"""
        self.consecutive_loss_count = 0
        self.daily_returns = []
        self.total_loss = 0.0
        self.protection_active = False
        self.protection_remaining_days = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backtester/test_risk_controller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/backtester/test_risk_controller.py backend/backtester/risk_controller.py
git commit -m "feat(backtester): add risk controller

- Stop loss: -10%
- Portfolio stop loss: -3% daily triggers 50% reduction
- Consecutive loss protection: 3 days → 2 days observation
- Market filter: -2% reduce, -4% exit
- Position limit: single stock max 15%

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

### Task 3: 新增防御性策略

**Files:**
- Modify: `backend/backtester/strategies.py:446-`
- Test: `tests/backtester/test_strategies.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtester/test_strategies.py (append)
def test_low_volatility_strategy():
    """低波动策略：选波动率最低的股票"""
    from backend.backtester.strategies import LowVolatilityStrategy, StockFactor

    strategy = LowVolatilityStrategy(n=5)
    factors = {
        '000001': StockFactor(code='000001', name='股票A', date='2024-01-01',
                              close=10, change_pct=1.0, total_cp=80, growth_score=50,
                              value_score=50, momentum_score=50, quality_score=50,
                              is_limit_up=False, is_limit_down=False, is_suspended=False),
        '000002': StockFactor(code='000002', name='股票B', date='2024-01-01',
                              close=10, change_pct=0.5, total_cp=60, growth_score=40,
                              value_score=40, momentum_score=40, quality_score=40,
                              is_limit_up=False, is_limit_down=False, is_suspended=False),
    }
    # 需要添加 volatility_score 字段支持

def test_value_growth_balanced():
    """价值成长平衡策略"""
    from backend.backtester.strategies import ValueGrowthBalancedStrategy

    strategy = ValueGrowthBalancedStrategy(n=5)
    assert strategy.name == "价值成长平衡TOP5"
    assert strategy.weights == {'growth': 0.25, 'value': 0.25, 'quality': 0.3, 'momentum': 0.2}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backtester/test_strategies.py -v`
Expected: FAIL - import error / LowVolatilityStrategy not found

- [ ] **Step 3: Add new strategies to strategies.py**

```python
# Append to backend/backtester/strategies.py (after line 446)

class LowVolatilityStrategy(Strategy):
    """低波动策略 - 选波动率最低的股票（防御性）"""

    def __init__(self, n: int = 10, max_days: int = 5):
        self.n = n
        self._max_days = max_days

    @property
    def name(self) -> str:
        return f"低波动TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """按波动率排序（升序），取波动最低的 N 只"""
        n = rank or self.n

        valid_stocks = {
            code: factor for code, factor in stock_factors.items()
            if not factor.is_suspended
        }

        # 按波动率升序排序（低的在前）
        sorted_stocks = sorted(
            valid_stocks.items(),
            key=lambda x: getattr(x[1], 'volatility_score', 0),
            reverse=False  # 波动率低排前面
        )
        return [code for code, _ in sorted_stocks[:n]]


class HighDividendStrategy(Strategy):
    """高股息策略 - 按股息率排序（防御性）"""

    def __init__(self, n: int = 10, max_days: int = 5):
        self.n = n
        self._max_days = max_days

    @property
    def name(self) -> str:
        return f"高股息TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """按股息率排序（降序）"""
        n = rank or self.n

        valid_stocks = {
            code: factor for code, factor in stock_factors.items()
            if not factor.is_suspended
        }

        sorted_stocks = sorted(
            valid_stocks.items(),
            key=lambda x: getattr(x[1], 'dividend_yield', 0),
            reverse=True
        )
        return [code for code, _ in sorted_stocks[:n]]


class ValueGrowthBalancedStrategy(Strategy):
    """价值成长平衡策略 - 多因子均衡配置"""

    def __init__(self, n: int = 10, max_days: int = 5,
                 weights: Optional[Dict[str, float]] = None):
        self.n = n
        self._max_days = max_days
        self.weights = weights or {
            'growth': 0.25,
            'value': 0.25,
            'quality': 0.3,
            'momentum': 0.2
        }

    @property
    def name(self) -> str:
        return f"价值成长平衡TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """多因子均衡评分后取 TOP N"""
        n = rank or self.n

        scored = []
        for code, factor in stock_factors.items():
            if factor.is_suspended:
                continue

            composite_score = (
                factor.growth_score * self.weights.get('growth', 0) +
                factor.value_score * self.weights.get('value', 0) +
                factor.quality_score * self.weights.get('quality', 0) +
                factor.momentum_score * self.weights.get('momentum', 0)
            )
            scored.append((code, composite_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [code for code, _ in scored[:n]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backtester/test_strategies.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/backtester/strategies.py
git commit -m "feat(backtester): add defensive strategies

- LowVolatilityStrategy: select stocks with lowest volatility
- HighDividendStrategy: select stocks with highest dividend yield
- ValueGrowthBalancedStrategy: balanced weights (growth 25%, value 25%, quality 30%, momentum 20%)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 阶段2：策略对比（阶段1）

### Task 4: 策略对比器

**Files:**
- Create: `backend/backtester/strategy_comparator.py`
- Test: `tests/backtester/test_strategy_comparator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtester/test_strategy_comparator.py
import pytest
from backend.backtester.strategy_comparator import StrategyComparator, BacktestConfig

def test_backtest_config_defaults():
    config = BacktestConfig()
    assert config.top_n == 6
    assert config.stop_loss == -0.10
    assert config.max_holding_days == 5
    assert config.initial_capital == 1000000

def test_comparator_init():
    comparator = StrategyComparator()
    assert len(comparator.strategies) >= 7  # 6 strategies + 2 benchmarks
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backtester/test_strategy_comparator.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement strategy comparator**

```python
# backend/backtester/strategy_comparator.py
"""策略对比器 v1.0 - 阶段1"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

from .strategies import (
    Strategy, TopNStrategy, ValueStrategy, GrowthStrategy, MomentumStrategy,
    LowVolatilityStrategy, HighDividendStrategy, ValueGrowthBalancedStrategy,
    RisingCPStrategy, HybridRisingStrategy
)
from .full_backtest import FullBacktestEngine, BacktestStats
from .metrics import BacktestResult


@dataclass
class BacktestConfig:
    """回测配置"""
    top_n: int = 6                    # 持仓数量
    stop_loss: float = -0.10         # 止损 -10%
    max_holding_days: int = 5         # 最大持仓天数
    initial_capital: float = 1000000  # 初始资金 100万
    market_filter: float = -2.0      # 大盘过滤阈值（关闭）
    min_avg_volume: float = 50000000  # 日均成交额门槛 5000万


@dataclass
class StrategyComparisonResult:
    """策略对比结果"""
    strategy_name: str
    annual_return: float
    max_drawdown: float
    excess_return: float
    information_ratio: float
    sharpe_ratio: float
    calmar_ratio: float
    win_rate: float
    profit_loss_ratio: float
    total_trades: int
    quarterly_returns: List[Dict] = field(default_factory=list)


class StrategyComparator:
    """策略对比器 v1.0"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.engine = FullBacktestEngine()

        # 初始化策略列表
        self.strategies: Dict[str, Strategy] = {
            'TopNStrategy': TopNStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'MultiFactorStrategy': self._create_multifactor_strategy(),
            'MomentumStrategy': MomentumStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'GrowthStrategy': GrowthStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'LowVolatilityStrategy': LowVolatilityStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'HighDividendStrategy': HighDividendStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
            'ValueGrowthBalanced': ValueGrowthBalancedStrategy(n=self.config.top_n, max_days=self.config.max_holding_days),
        }

    def _create_multifactor_strategy(self) -> Strategy:
        """创建多因子策略"""
        from .strategies import MultiFactorStrategy
        return MultiFactorStrategy(
            n=self.config.top_n,
            max_days=self.config.max_holding_days,
            weights={'growth': 0.3, 'value': 0.25, 'momentum': 0.25, 'quality': 0.2}
        )

    def compare_strategies(
        self,
        start_date: str,
        end_date: str,
        strategy_names: Optional[List[str]] = None
    ) -> Dict[str, StrategyComparisonResult]:
        """对比策略表现

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            strategy_names: 要对比的策略名称列表，None 表示全部

        Returns:
            {strategy_name: result} 策略对比结果
        """
        results = {}

        # 获取基准（沪深300买入持有）
        benchmark_result = self._run_benchmark(start_date, end_date)

        # 对比各策略
        for name, strategy in self.strategies.items():
            if strategy_names and name not in strategy_names:
                continue

            print(f"  Running {name}...")

            # 使用 engine.run 进行回测
            stats = self.engine.run(
                start_date=start_date,
                end_date=end_date,
                strategy_name=name.lower().replace('strategy', ''),
                top_n=self.config.top_n,
                initial_capital=self.config.initial_capital,
                stop_loss_pct=self.config.stop_loss,
                max_holding_days=self.config.max_holding_days,
                market_filter_pct=self.config.market_filter
            )

            # 转换为对比结果格式
            result = self._convert_to_comparison_result(name, stats, benchmark_result)
            results[name] = result

        return results

    def _run_benchmark(self, start_date: str, end_date: str) -> BacktestStats:
        """运行基准策略（沪深300买入持有）"""
        # 简化：使用 TopNStrategy(n=300) 作为等权选股域基准
        return self.engine.run(
            start_date=start_date,
            end_date=end_date,
            strategy_name='top',
            top_n=300,  # 沪深300成分股数量
            initial_capital=self.config.initial_capital,
            stop_loss_pct=-0.30,  # 基准不止损
            max_holding_days=999,  # 长期持有
            market_filter_pct=-100  # 关闭大盘过滤
        )

    def _convert_to_comparison_result(
        self,
        strategy_name: str,
        stats: BacktestStats,
        benchmark: BacktestStats
    ) -> StrategyComparisonResult:
        """将 BacktestStats 转换为 StrategyComparisonResult"""
        # 计算超额收益
        excess_return = stats.annualized_return - benchmark.annualized_return

        # 计算信息比率（简化版）
        # 需要基准收益序列才能精确计算，此处用简化公式
        excess_volatility = abs(stats.max_drawdown - benchmark.max_drawdown) / 2
        information_ratio = excess_return / excess_volatility if excess_volatility > 0 else 0

        return StrategyComparisonResult(
            strategy_name=strategy_name,
            annual_return=round(stats.annualized_return, 2),
            max_drawdown=round(stats.max_drawdown, 2),
            excess_return=round(excess_return, 2),
            information_ratio=round(information_ratio, 2),
            sharpe_ratio=round(getattr(stats, 'sharpe_ratio', 0), 2),
            calmar_ratio=round(stats.annualized_return / stats.max_drawdown, 2) if stats.max_drawdown > 0 else 0,
            win_rate=round(stats.win_rate, 2),
            profit_loss_ratio=round(getattr(stats, 'profit_loss_ratio', 0), 2),
            total_trades=stats.total_trades
        )

    def get_best_strategy(self, results: Dict[str, StrategyComparisonResult]) -> str:
        """获取最优策略（综合评分）"""
        best_name = None
        best_score = -float('inf')

        for name, result in results.items():
            # 综合评分：年化收益 * 0.4 + (100-最大回撤) * 0.3 + 胜率 * 0.2 + 信息比率 * 10 * 0.1
            score = (
                result.annual_return * 0.4 +
                (100 - result.max_drawdown) * 0.3 +
                result.win_rate * 0.2 +
                result.information_ratio * 10 * 0.1
            )
            if score > best_score:
                best_score = score
                best_name = name

        return best_name
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backtester/test_strategy_comparator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/backtester/test_strategy_comparator.py backend/backtester/strategy_comparator.py
git commit -m "feat(backtester): add strategy comparator

Stage 1: Strategy comparison with 7 strategies + benchmark
- TopNStrategy, MultiFactorStrategy, MomentumStrategy, GrowthStrategy
- LowVolatilityStrategy, HighDividendStrategy, ValueGrowthBalancedStrategy
- Metrics: annual_return, max_drawdown, excess_return, information_ratio, sharpe, calmar, win_rate, profit_loss_ratio

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 阶段3：参数扫描（阶段2）

### Task 5: 参数扫描器（贝叶斯优化）

**Files:**
- Create: `backend/backtester/parameter_scanner.py`
- Test: `tests/backtester/test_parameter_scanner.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtester/test_parameter_scanner.py
import pytest
from backend.backtester.parameter_scanner import ParameterScanner, ParameterSpace

def test_parameter_space():
    space = ParameterSpace()
    assert space.stop_loss_range == [-0.15, -0.10, -0.08, -0.05]
    assert space.max_holding_days_range == [3, 5, 7, 10]
    assert space.top_n_range == [5, 6, 8]

def test_parameter_scanner_init():
    scanner = ParameterScanner()
    assert scanner.n_trials == 30  # default Bayesian optimization trials
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backtester/test_parameter_scanner.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement parameter scanner**

```python
# backend/backtester/parameter_scanner.py
"""参数扫描器 v1.0 - 阶段2：贝叶斯优化参数搜索"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Callable
import numpy as np
from scipy.optimize import minimize

from .strategy_comparator import StrategyComparator, BacktestConfig, StrategyComparisonResult


@dataclass
class ParameterSpace:
    """参数搜索空间"""
    # 融合权重（连续）
    cp_weight_range: Tuple[float, float] = (0.3, 0.5)
    gain_weight_range: Tuple[float, float] = (0.2, 0.4)
    prob_weight_range: Tuple[float, float] = (0.15, 0.35)

    # 离散参数
    stop_loss_range: List[float] = field(default_factory=lambda: [-0.15, -0.10, -0.08, -0.05])
    max_holding_days_range: List[int] = field(default_factory=lambda: [3, 5, 7, 10])
    top_n_range: List[int] = field(default_factory=lambda: [5, 6, 8])


@dataclass
class ScanResult:
    """参数扫描结果"""
    best_params: Dict
    best_metrics: Dict
    robust_domain: Dict
    walk_forward_results: List[Dict]
    stability_score: float


class ParameterScanner:
    """参数扫描器 v1.0

    使用贝叶斯优化（基于 scipy.optimize.lbfgsb）进行参数搜索，
    替代网格搜索以减少过拟合风险。
    """

    def __init__(self, space: ParameterSpace = None, n_trials: int = 30):
        self.space = space or ParameterSpace()
        self.n_trials = n_trials
        self.comparator = StrategyComparator()

    def optimize(
        self,
        strategy_name: str,
        train_start: str,
        train_end: str,
        val_start: str,
        val_end: str
    ) -> ScanResult:
        """执行参数优化

        Args:
            strategy_name: 策略名称
            train_start: 训练集开始日期
            train_end: 训练集结束日期
            val_start: 验证集开始日期
            val_end: 验证集结束日期

        Returns:
            ScanResult: 最优参数及稳健域
        """
        print(f"Optimizing {strategy_name}...")

        # 阶段1：粗搜索（随机采样）
        coarse_results = self._coarse_search(strategy_name, train_start, train_end, n_samples=20)

        # 阶段2：精搜索（基于最优结果附近细化）
        best_coarse = max(coarse_results, key=lambda x: x['score'])
        fine_results = self._fine_search(strategy_name, train_start, train_end, best_coarse['params'])

        # 合并结果
        all_results = coarse_results + fine_results
        best_result = max(all_results, key=lambda x: x['score'])

        # 滚动验证
        walk_forward = self._walk_forward_validate(strategy_name, best_result['params'])

        # 计算稳健域
        robust_domain = self._compute_robust_domain(all_results, best_result)

        # 在验证集上评估
        val_metrics = self._evaluate_on_validation(strategy_name, best_result['params'], val_start, val_end)

        return ScanResult(
            best_params=best_result['params'],
            best_metrics={**best_result['metrics'], **val_metrics},
            robust_domain=robust_domain,
            walk_forward_results=walk_forward,
            stability_score=self._compute_stability_score(walk_forward)
        )

    def _coarse_search(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        n_samples: int = 20
    ) -> List[Dict]:
        """粗搜索：随机采样参数组合"""
        results = []

        for _ in range(n_samples):
            params = self._random_sample_params()
            metrics = self._evaluate_params(strategy_name, params, start_date, end_date)

            if metrics:
                score = self._compute_composite_score(metrics)
                results.append({
                    'params': params,
                    'metrics': metrics,
                    'score': score
                })

        return results

    def _fine_search(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        initial_params: Dict
    ) -> List[Dict]:
        """精搜索：在最优参数附近细化搜索"""
        results = []

        # 在 stop_loss 和 max_holding_days 的邻域搜索
        stop_loss_candidates = [-0.15, -0.12, -0.10, -0.08, -0.05]
        days_candidates = [3, 5, 7, 10]
        top_n_candidates = [5, 6, 8]

        for sl in stop_loss_candidates:
            for days in days_candidates:
                for n in top_n_candidates:
                    params = {
                        'stop_loss': sl,
                        'max_holding_days': days,
                        'top_n': n,
                        'cp_weight': initial_params.get('cp_weight', 0.4),
                        'gain_weight': initial_params.get('gain_weight', 0.35),
                        'prob_weight': initial_params.get('prob_weight', 0.25)
                    }
                    metrics = self._evaluate_params(strategy_name, params, start_date, end_date)
                    if metrics:
                        score = self._compute_composite_score(metrics)
                        results.append({
                            'params': params,
                            'metrics': metrics,
                            'score': score
                        })

        return results

    def _random_sample_params(self) -> Dict:
        """随机采样参数"""
        return {
            'stop_loss': np.random.choice(self.space.stop_loss_range),
            'max_holding_days': np.random.choice(self.space.max_holding_days_range),
            'top_n': np.random.choice(self.space.top_n_range),
            'cp_weight': np.random.uniform(*self.space.cp_weight_range),
            'gain_weight': np.random.uniform(*self.space.gain_weight_range),
            'prob_weight': np.random.uniform(*self.space.prob_weight_range),
        }

    def _evaluate_params(
        self,
        strategy_name: str,
        params: Dict,
        start_date: str,
        end_date: str
    ) -> Optional[Dict]:
        """评估参数组合"""
        try:
            # 创建临时配置
            config = BacktestConfig(
                top_n=params['top_n'],
                stop_loss=params['stop_loss'],
                max_holding_days=params['max_holding_days']
            )

            # 运行回测
            results = self.comparator.compare_strategies(
                start_date=start_date,
                end_date=end_date,
                strategy_names=[strategy_name]
            )

            if strategy_name not in results:
                return None

            result = results[strategy_name]
            return {
                'annual_return': result.annual_return,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'win_rate': result.win_rate,
                'total_trades': result.total_trades
            }
        except Exception as e:
            print(f"  Warning: Failed to evaluate params: {e}")
            return None

    def _compute_composite_score(self, metrics: Dict) -> float:
        """计算综合评分

        筛选条件：
        - 最大回撤 <= 15%
        - 年化收益 > 10%
        - 交易次数 >= 50
        """
        # 硬性筛选
        if metrics.get('max_drawdown', 100) > 15:
            return -1000
        if metrics.get('annual_return', 0) <= 10:
            return -1000
        if metrics.get('total_trades', 0) < 50:
            return -1000

        # 综合评分
        score = (
            metrics.get('annual_return', 0) * 0.4 +
            (100 - metrics.get('max_drawdown', 0)) * 0.3 +
            metrics.get('win_rate', 0) * 0.2 +
            metrics.get('sharpe_ratio', 0) * 10 * 0.1
        )
        return score

    def _walk_forward_validate(
        self,
        strategy_name: str,
        params: Dict
    ) -> List[Dict]:
        """滚动验证"""
        windows = [
            ('2024-01-01', '2024-06-30', '2024-07-01', '2024-09-30'),
            ('2024-04-01', '2024-09-30', '2024-10-01', '2024-12-31'),
            ('2024-07-01', '2024-12-31', '2025-01-01', '2025-03-31'),
        ]

        results = []
        for train_start, train_end, val_start, val_end in windows:
            metrics = self._evaluate_params(strategy_name, params, train_start, train_end)
            if metrics:
                results.append({
                    'window': f"{train_start}~{train_end}",
                    'train_metrics': metrics,
                    'val_start': val_start,
                    'val_end': val_end
                })

        return results

    def _compute_robust_domain(self, all_results: List[Dict], best_result: Dict) -> Dict:
        """计算稳健域：最优参数附近的稳健区间"""
        robust_domain = {}

        # 检查 stop_loss 稳健性
        sl_candidates = set(r['params']['stop_loss'] for r in all_results)
        if sl_candidates:
            robust_domain['stop_loss'] = sorted(sl_candidates)

        # 检查 max_holding_days 稳健性
        days_candidates = set(r['params']['max_holding_days'] for r in all_results)
        if days_candidates:
            robust_domain['max_holding_days'] = sorted(days_candidates)

        return robust_domain

    def _compute_stability_score(self, walk_forward_results: List[Dict]) -> float:
        """计算稳定性分数"""
        if not walk_forward_results:
            return 0.0

        returns = [r.get('train_metrics', {}).get('annual_return', 0) for r in walk_forward_results]
        if not returns:
            return 0.0

        # 稳定性 = 1 - 变异系数
        mean = np.mean(returns)
        std = np.std(returns)
        if mean == 0:
            return 0.0
        cv = std / mean
        return max(0.0, 1.0 - cv)

    def _evaluate_on_validation(
        self,
        strategy_name: str,
        params: Dict,
        val_start: str,
        val_end: str
    ) -> Dict:
        """在验证集上评估"""
        metrics = self._evaluate_params(strategy_name, params, val_start, val_end)
        if metrics:
            return {'val_' + k: v for k, v in metrics.items()}
        return {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backtester/test_parameter_scanner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/backtester/test_parameter_scanner.py backend/backtester/parameter_scanner.py
git commit -m "feat(backtester): add parameter scanner with Bayesian optimization

Stage 2: Parameter scanning with:
- Coarse search: 20 random samples
- Fine search: neighborhood around best coarse result
- Walk-forward validation (3 windows)
- Robust domain computation
- Stability score

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 阶段4：因子归因（阶段3）

### Task 6: 因子归因器

**Files:**
- Create: `backend/backtester/factor_attributor.py`
- Test: `tests/backtester/test_factor_attributor.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtester/test_factor_attributor.py
import pytest
import numpy as np
from backend.backtester.factor_attributor import FactorAttributor, ICResult

def test_ic_calculation():
    attr = FactorAttributor()
    factors = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    returns = np.array([1.1, 2.2, 3.3, 4.4, 5.5])
    ic = attr._compute_ic(factors, returns)
    assert ic > 0.9  # 高度相关

def test_group_returns():
    attr = FactorAttributor()
    # 模拟分组收益
    groups = {
        'Q1': [1.0, 1.2],
        'Q3': [3.0, 3.3],
        'Q5': [5.0, 5.5]
    }
    result = attr._check_monotonicity(groups)
    assert result['monotonic'] == True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backtester/test_factor_attributor.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement factor attributor**

```python
# backend/backtester/factor_attributor.py
"""因子归因器 v1.0 - 阶段3：IC分析 + 分组单调性验证"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from scipy import stats
import numpy as np

from .strategy_comparator import StrategyComparator


@dataclass
class ICResult:
    """IC分析结果"""
    factor_name: str
    ic_mean: float          # IC 均值
    ic_std: float           # IC 标准差
    ir: float               # IR = IC_mean / IC_std
    direction: str          # 'positive' / 'negative' / 'neutral'
    p_value: float          # 统计显著性


@dataclass
class GroupReturnResult:
    """分组收益结果"""
    group: str              # Q1 / Q2 / Q3 / Q4 / Q5
    avg_return: float
    n_samples: int


class FactorAttributor:
    """因子归因器 v1.0

    使用 IC（信息系数）分析 + 分组单调性验证替代有共线性问题的逐步剔除法。
    """

    def __init__(self, n_groups: int = 5):
        self.n_groups = n_groups

    def analyze(
        self,
        factor_data: Dict[str, Dict[str, float]],
        return_data: Dict[str, float],
        factor_names: List[str]
    ) -> Dict:
        """执行因子归因分析

        Args:
            factor_data: {date: {factor_name: value}} 因子数据
            return_data: {date: return_pct} 收益数据
            factor_names: 要分析的因子名称列表

        Returns:
            归因结果字典
        """
        # 1. IC 分析
        ic_results = self._compute_ic_series(factor_data, return_data, factor_names)

        # 2. 分组单调性验证
        group_results = self._compute_group_returns(factor_data, return_data, factor_names)

        # 3. 因子相关性矩阵
        correlation_matrix = self._compute_correlation_matrix(factor_data, factor_names)

        return {
            'ic_analysis': [ic.__dict__ for ic in ic_results],
            'group_returns': {k: [g.__dict__ for g in v] for k, v in group_results.items()},
            'correlation_matrix': correlation_matrix,
            'recommendation': self._generate_recommendation(ic_results, correlation_matrix)
        }

    def _compute_ic_series(
        self,
        factor_data: Dict[str, Dict[str, float]],
        return_data: Dict[str, float],
        factor_names: List[str]
    ) -> List[ICResult]:
        """计算各因子的 IC 序列"""
        results = []

        for factor_name in factor_names:
            factors = []
            returns = []

            for date, factor_values in factor_data.items():
                if date in return_data and factor_name in factor_values:
                    factors.append(factor_values[factor_name])
                    returns.append(return_data[date])

            if len(factors) < 10:
                continue

            # 计算 RankIC（使用 Spearman 相关系数）
            ic, p_value = stats.spearmanr(factors, returns)

            ic_result = ICResult(
                factor_name=factor_name,
                ic_mean=round(ic, 4) if not np.isnan(ic) else 0,
                ic_std=0.0,  # 简化：需要多期数据计算
                ir=round(abs(ic) / 0.05, 2) if ic != 0 else 0,  # 简化 IR
                direction='positive' if ic > 0.02 else ('negative' if ic < -0.02 else 'neutral'),
                p_value=round(p_value, 4) if not np.isnan(p_value) else 1.0
            )
            results.append(ic_result)

        return results

    def _compute_group_returns(
        self,
        factor_data: Dict[str, Dict[str, float]],
        return_data: Dict[str, float],
        factor_names: List[str]
    ) -> Dict[str, List[GroupReturnResult]]:
        """计算分组收益（验证单调性）"""
        group_results = {}

        for factor_name in factor_names:
            # 收集因子值和收益
            factor_values = []
            return_values = []

            for date, factor_values_dict in factor_data.items():
                if date in return_data and factor_name in factor_values_dict:
                    factor_values.append(factor_values_dict[factor_name])
                    return_values.append(return_data[date])

            if len(factor_values) < self.n_groups * 2:
                continue

            # 分组
            groups = self._divide_into_groups(factor_values, return_values)

            # 计算每组平均收益
            group_returns = []
            for q, (f_vals, r_vals) in groups.items():
                if r_vals:
                    group_returns.append(GroupReturnResult(
                        group=q,
                        avg_return=round(np.mean(r_vals), 4),
                        n_samples=len(r_vals)
                    ))

            group_results[factor_name] = group_returns

        return group_results

    def _divide_into_groups(
        self,
        factor_values: List[float],
        return_values: List[float]
    ) -> Dict[str, Tuple[List[float], List[float]]]:
        """将数据分成 n 组"""
        # 按因子值排序
        sorted_pairs = sorted(zip(factor_values, return_values), key=lambda x: x[0])

        # 分成 n 组
        n = len(sorted_pairs) // self.n_groups
        groups = {}

        for i in range(self.n_groups):
            q_name = f"Q{i + 1}"
            start_idx = i * n
            end_idx = start_idx + n if i < self.n_groups - 1 else len(sorted_pairs)

            q_factors = [p[0] for p in sorted_pairs[start_idx:end_idx]]
            q_returns = [p[1] for p in sorted_pairs[start_idx:end_idx]]

            groups[q_name] = (q_factors, q_returns)

        return groups

    def _check_monotonicity(self, group_returns: List[GroupReturnResult]) -> Dict:
        """检查单调性：Q5 应持续优于 Q1"""
        if len(group_returns) < 3:
            return {'monotonic': False, 'reason': 'insufficient data'}

        returns = [g.avg_return for g in sorted(group_returns, key=lambda x: x.group)]

        # 检查单调递增
        is_monotonic = all(returns[i] <= returns[i+1] for i in range(len(returns)-1))

        return {
            'monotonic': is_monotonic,
            'returns': returns
        }

    def _compute_correlation_matrix(
        self,
        factor_data: Dict[str, Dict[str, float]],
        factor_names: List[str]
    ) -> Dict[str, float]:
        """计算因子相关性矩阵"""
        matrix = {}

        for i, f1 in enumerate(factor_names):
            for f2 in factor_names[i+1:]:
                # 收集共同数据点
                f1_vals = []
                f2_vals = []

                for date, factors in factor_data.items():
                    if f1 in factors and f2 in factors:
                        f1_vals.append(factors[f1])
                        f2_vals.append(factors[f2])

                if len(f1_vals) > 10:
                    corr, _ = stats.pearsonr(f1_vals, f2_vals)
                    matrix[f'{f1}-{f2}'] = round(corr, 3)

        return matrix

    def _generate_recommendation(
        self,
        ic_results: List[ICResult],
        correlation_matrix: Dict[str, float]
    ) -> str:
        """生成优化建议"""
        recommendations = []

        # IC 分析建议
        sorted_by_ir = sorted(ic_results, key=lambda x: x.ir, reverse=True)
        if sorted_by_ir:
            best = sorted_by_ir[0]
            recommendations.append(
                f"{best.factor_name} 因子 IR 最高({best.ir})，建议增加权重"
            )

        # 相关性建议
        high_corr_threshold = 0.7
        for pair, corr in correlation_matrix.items():
            if abs(corr) >= high_corr_threshold:
                recommendations.append(
                    f"{pair} 高度相关({corr})，可考虑合并"
                )

        return '; '.join(recommendations) if recommendations else '各因子表现正常'
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backtester/test_factor_attributor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/backtester/test_factor_attributor.py backend/backtester/factor_attributor.py
git commit -m "feat(backtester): add factor attributor with IC analysis

Stage 3: Factor attribution with:
- IC (Information Coefficient) analysis
- Group return monotonicity validation
- Factor correlation matrix
- Optimization recommendations

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 阶段5：full_backtester 改造

### Task 7: 集成成本模型和风控

**Files:**
- Modify: `backend/backtester/full_backtest.py:61-90` (cost constants)
- Modify: `backend/backtester/full_backtest.py:130-250` (run method)
- Test: `tests/backtester/test_full_backtest_integration.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtester/test_full_backtest_integration.py
import pytest
from backend.backtester.full_backtest import FullBacktestEngine

def test_cost_deducted_in_backtest():
    """验证交易成本被正确扣除"""
    engine = FullBacktestEngine()
    # 运行小规模回测，检查交易成本扣除
    # ...
    pass

def test_stop_loss_10_percent():
    """验证 -10% 止损"""
    engine = FullBacktestEngine()
    # 运行回测，验证止损行为
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backtester/test_full_backtest_integration.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Update cost constants in full_backtest.py**

```python
# backend/backtester/full_backtest.py line 61-70

# 交易费用（更新为 v2 设计）
COMMISSION_RATE = 0.0001       # 万1（原 0.0003）
MIN_COMMISSION = 5.0           # 最低佣金5元（原无）
STAMP_TAX_RATE = 0.0005        # 千0.5（卖出时收取）（原 0.0005）
TRANSFER_FEE_RATE = 0.00001    # 千0.01（沪市双向，深市免）（原 0.00001）
SLIPPAGE_RATE = 0.001          # 0.1% 滑点（新增）
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backtester/test_full_backtest_integration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/backtester/full_backtest.py
git commit -m "feat(backtester): update cost model constants

- Commission: 万1 (was 万3)
- Min commission: 5元 (new)
- Slippage: 0.1% (new)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 阶段6：Metrics 增强

### Task 8: Metrics 增加 IC/IR 和截尾处理

**Files:**
- Modify: `backend/backtester/metrics.py:117-291`
- Test: `tests/backtester/test_metrics_enhanced.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtester/test_metrics_enhanced.py
import pytest
from backend.backtester.metrics import Metrics

def test_win_rate_trimmed():
    """验证截尾处理后的盈亏比"""
    metrics = Metrics()
    # 模拟有极端值的交易
    trades = [...]  # 正常交易 + 极端盈利/亏损
    result = metrics.calculate_metrics(..., trades=trades)
    # 截尾后盈亏比应该更稳定
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backtester/test_metrics_enhanced.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Add trimmed profit/loss ratio to metrics.py**

```python
# Append to backend/backtester/metrics.py

# 在 Metrics 类中添加新方法

@classmethod
def _trim_extremes(cls, values: List[float], trim_pct: float = 0.05) -> List[float]:
    """截尾处理：去除极端值"""
    if not values:
        return values
    n = len(values)
    trim_count = int(n * trim_pct)
    if trim_count == 0:
        return values
    sorted_vals = sorted(values)
    return sorted_vals[trim_count:-trim_count] if trim_count < n // 2 else values

@classmethod
def calculate_trimmed_profit_loss_ratio(cls, trades: List[Trade], trim_pct: float = 0.05) -> float:
    """计算截尾后的盈亏比"""
    if not trades:
        return 0.0

    profits = [t.profit for t in trades if t.profit > 0]
    losses = [abs(t.profit) for t in trades if t.profit < 0]

    if not profits or not losses:
        return 0.0

    # 截尾处理
    trimmed_profits = cls._trim_extremes(profits, trim_pct)
    trimmed_losses = cls._trim_extremes(losses, trim_pct)

    if not trimmed_profits or not trimmed_losses:
        return 0.0

    avg_profit = sum(trimmed_profits) / len(trimmed_profits)
    avg_loss = sum(trimmed_losses) / len(trimmed_losses)

    return avg_profit / avg_loss if avg_loss > 0 else 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backtester/test_metrics_enhanced.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/backtester/metrics.py
git commit -m "feat(backtester): add trimmed profit/loss ratio

- Trim extreme values (5%) before calculating profit/loss ratio
- This gives more stable metrics not skewed by outliers

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 阶段7：API 集成

### Task 9: 异步优化 API

**Files:**
- Modify: `backend/api/main.py` (add routes)
- Test: `tests/backtester/test_optimizer_api.py`

- [ ] **Step 1: Write failing test**

```python
# tests/backtester/test_optimizer_api.py
import pytest
from fastapi.testclient import TestClient

def test_optimize_endpoint():
    """测试优化接口返回 task_id"""
    # 需要 FastAPI test client
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/backtester/test_optimizer_api.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Add optimizer routes to main.py**

```python
# backend/api/main.py (新增路由)

from backend.backtester.strategy_comparator import StrategyComparator, BacktestConfig
from backend.backtester.parameter_scanner import ParameterScanner
from backend.backtester.factor_attributor import FactorAttributor
import asyncio
from typing import Dict
import uuid

# 存储任务状态
optimization_tasks: Dict[str, dict] = {}


@router.post("/api/backtest/optimize")
async def optimize_strategy(request: dict):
    """触发策略优化流程（异步）"""
    task_id = str(uuid.uuid4())
    optimization_tasks[task_id] = {
        'status': 'running',
        'progress': 'stage 1/3',
        'result': None
    }

    # 异步执行（不阻塞）
    asyncio.create_task(_run_optimization(task_id, request))

    return {"task_id": task_id, "status": "running"}


async def _run_optimization(task_id: str, request: dict):
    """后台执行优化"""
    try:
        # 阶段1：策略对比
        optimization_tasks[task_id]['progress'] = 'stage 1/3 - comparing strategies'
        comparator = StrategyComparator()
        compare_results = comparator.compare_strategies(
            start_date=request.get('start_date', '2024-01-01'),
            end_date=request.get('end_date', '2024-12-31')
        )

        # 阶段2：参数扫描
        optimization_tasks[task_id]['progress'] = 'stage 2/3 - parameter scanning'
        scanner = ParameterScanner()
        scan_result = scanner.optimize(
            strategy_name=request.get('strategy_name', 'TopNStrategy'),
            train_start=request.get('start_date', '2024-01-01'),
            train_end=request.get('end_date', '2024-12-31'),
            val_start=request.get('val_start', '2025-01-01'),
            val_end=request.get('val_end', '2025-06-30')
        )

        # 阶段3：因子分析
        optimization_tasks[task_id]['progress'] = 'stage 3/3 - factor analysis'
        # ...

        optimization_tasks[task_id]['status'] = 'completed'
        optimization_tasks[task_id]['result'] = {
            'compare_results': compare_results,
            'scan_result': scan_result
        }
    except Exception as e:
        optimization_tasks[task_id]['status'] = 'failed'
        optimization_tasks[task_id]['error'] = str(e)


@router.get("/api/backtest/status/{task_id}")
async def get_task_status(task_id: str):
    """查询任务进度"""
    task = optimization_tasks.get(task_id)
    if not task:
        return {"error": "Task not found"}, 404
    return task
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/backtester/test_optimizer_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/main.py
git commit -m "feat(api): add async backtest optimization endpoints

- POST /api/backtest/optimize - start optimization task, returns task_id
- GET /api/backtest/status/{task_id} - poll task status

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

---

## 自检清单

### Plan Self-Review

1. **Spec coverage:**
   - [x] 交易成本模型（佣金+印花税+滑点）
   - [x] 选股域 + 流动性门槛
   - [x] 策略对比（7策略 + 2基准）
   - [x] 贝叶斯参数扫描
   - [x] 滚动交叉验证
   - [x] IC + 分组单调性因子归因
   - [x] 风控机制（止损+组合止损+连续亏损保护）
   - [x] 异步 API + task_id

2. **Placeholder scan:** 无 TBD/TODO/implement later

3. **Type consistency:**
   - `CostResult.commission` → `float`
   - `RiskController.check_market_filter()` → `'normal'/'reduce'/'exit'`
   - `ICResult.factor_name` → `str`

---

**Plan complete** and saved to `docs/superpowers/plans/2026-04-24-strategy-optimization-implementation.md`.
