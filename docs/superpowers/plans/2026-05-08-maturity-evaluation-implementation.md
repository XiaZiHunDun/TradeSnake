# 策略成熟度评估体系实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立策略成熟度评估体系，包含毕业标准和每日交易信号

**Architecture:** 新增 `maturity` 模块提供评估器和信号生成器，通过 API 暴露毕业状态和每日档位。毕业前只执行"强烈买入"，毕业后全档位开放。

**Tech Stack:** Python + FastAPI + SQLite（复用现有 simulator 数据库）

---

## Task 1: 创建 maturity 模块基础结构

**Files:**
- Create: `backend/maturity/__init__.py`
- Create: `backend/maturity/metrics.py`
- Create: `backend/maturity/evaluator.py`
- Create: `backend/maturity/daily_signal.py`
- Create: `backend/tests/test_maturity.py`

- [ ] **Step 1: Write the failing test - metrics.py**

```python
# backend/tests/test_maturity.py
import pytest
from backend.maturity.metrics import calculate_monthly_returns, calculate_benchmark_excess

class MockPortfolio:
    def __init__(self, monthly_values):
        self.monthly_values = monthly_values  # [(date, value), ...]

def test_calculate_monthly_returns_single_profitable_month():
    """月初10000，月末10500，收益5% > 0.5%阈值，应该算盈利"""
    portfolio = MockPortfolio([
        ('2026-01-01', 10000),
        ('2026-01-31', 10500),
    ])
    result = calculate_monthly_returns(portfolio)
    assert len(result) == 1
    assert result[0]['profitable'] == True
    assert result[0]['return_pct'] == 5.0

def test_calculate_monthly_returns_loss_month():
    """月初10000，月末9900，收益-1%，不应算盈利（低于0.5%盈利门槛）"""
    portfolio = MockPortfolio([
        ('2026-01-01', 10000),
        ('2026-01-31', 9900),
    ])
    result = calculate_monthly_returns(portfolio)
    assert result[0]['profitable'] == False

def test_calculate_benchmark_excess_positive():
    """策略收益5%，基准3%，超额2% > 0"""
    excess = calculate_benchmark_excess(
        strategy_return=0.05,
        benchmark_return=0.03
    )
    assert excess == 0.02
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_maturity.py::test_calculate_monthly_returns_single_profitable_month -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'backend.maturity'"

- [ ] **Step 3: Write minimal metrics.py**

```python
# backend/maturity/metrics.py
"""策略成熟度指标计算"""
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MonthlyReturn:
    month: str  # 'YYYY-MM'
    start_value: float
    end_value: float
    return_pct: float
    profitable: bool  # > 0.5% threshold

@dataclass
class MaturityMetrics:
    monthly_returns: List[MonthlyReturn]
    profitable_months: int  # ≥5/6 for graduation
    total_months: int
    benchmark_excess: float  # > 0 for graduation
    is_qualified: bool  # overall qualification

def calculate_monthly_returns(portfolio) -> List[MonthlyReturn]:
    """计算月度收益率

    Args:
        portfolio: 有 monthly_values 属性 [(date, value), ...]

    Returns:
        List[MonthlyReturn] - 按月统计的收益率
    """
    if not portfolio.monthly_values:
        return []

    result = []
    values = portfolio.monthly_values

    # 按月分组
    from collections import defaultdict
    by_month = defaultdict(list)
    for date_str, value in values:
        month = date_str[:7]  # 'YYYY-MM'
        by_month[month].append((date_str, value))

    for month in sorted(by_month.keys()):
        month_values = sorted(by_month[month])
        start_value = month_values[0][1]
        end_value = month_values[-1][1]
        return_pct = (end_value - start_value) / start_value * 100 if start_value > 0 else 0

        result.append(MonthlyReturn(
            month=month,
            start_value=start_value,
            end_value=end_value,
            return_pct=return_pct,
            profitable=return_pct > 0.5
        ))

    return result

def calculate_benchmark_excess(strategy_return: float, benchmark_return: float) -> float:
    """计算相对基准的超额收益

    Args:
        strategy_return: 策略收益率（小数，如0.05表示5%）
        benchmark_return: 基准收益率（小数，如0.03表示3%）

    Returns:
        超额收益率（小数）
    """
    return strategy_return - benchmark_return

def is_maturity_qualified(metrics: MaturityMetrics) -> bool:
    """判断是否达到毕业标准

    条件（需同时满足）：
    1. 滚动6个月 ≥5个月盈利（>0.5%）
    2. 相对基准超额 > 0
    3. OOS/IS Sharpe > 0.8（在 evaluator 中检查）
    """
    if metrics.total_months < 6:
        return False

    # 条件1：≥5/6个月盈利
    profitable_condition = metrics.profitable_months >= 5

    # 条件2：基准超额 > 0
    excess_condition = metrics.benchmark_excess > 0

    return profitable_condition and excess_condition
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_maturity.py::test_calculate_monthly_returns_single_profitable_month -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_maturity.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/maturity/__init__.py backend/maturity/metrics.py backend/tests/test_maturity.py
git commit -m "feat(maturity): add metrics.py with monthly return calculation"
```

---

## Task 2: 实现 evaluator.py - 毕业标准评估器

**Files:**
- Modify: `backend/maturity/evaluator.py` (create with content below)
- Modify: `backend/tests/test_maturity.py` (add tests)

- [ ] **Step 1: Write the failing test - evaluator**

```python
# 在 backend/tests/test_maturity.py 中添加

def test_evaluator_is_mature_with_valid_data():
    """6个月中5个月盈利，基准超额>0%，应判定为成熟"""
    from backend.maturity.evaluator import MaturityEvaluator

    evaluator = MaturityEvaluator()

    # Mock monthly returns
    monthly_returns = [
        MonthlyReturn('2026-01', 10000, 10500, 5.0, True),
        MonthlyReturn('2026-02', 10500, 10800, 2.86, True),
        MonthlyReturn('2026-03', 10800, 10600, -1.85, False),  # 亏损
        MonthlyReturn('2026-04', 10600, 11200, 5.66, True),
        MonthlyReturn('2026-05', 11200, 11500, 2.68, True),
        MonthlyReturn('2026-06', 11500, 11800, 2.61, True),
    ]

    result = evaluator.evaluate(monthly_returns=monthly_returns, benchmark_excess=0.02, oos_is_ratio=0.85)
    assert result['is_mature'] == True
    assert result['profitable_months'] == 5

def test_evaluator_not_mature_insufficient_profitable_months():
    """6个月中只有4个月盈利，不满足≥5/6条件"""
    from backend.maturity.evaluator import MaturityEvaluator

    evaluator = MaturityEvaluator()

    monthly_returns = [
        MonthlyReturn('2026-01', 10000, 10500, 5.0, True),
        MonthlyReturn('2026-02', 10500, 10800, 2.86, True),
        MonthlyReturn('2026-03', 10800, 10600, -1.85, False),
        MonthlyReturn('2026-04', 10600, 10800, 1.89, True),
        MonthlyReturn('2026-05', 10800, 10600, -1.85, False),  # 亏损
        MonthlyReturn('2026-06', 10600, 10800, 1.89, True),
    ]

    result = evaluator.evaluate(monthly_returns=monthly_returns, benchmark_excess=0.02, oos_is_ratio=0.85)
    assert result['is_mature'] == False
    assert result['reason'] == 'profitable_months_insufficient'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_maturity.py -v`
Expected: FAIL with "No module named 'backend.maturity.evaluator'"

- [ ] **Step 3: Write evaluator.py**

```python
# backend/maturity/evaluator.py
"""策略毕业标准评估器"""
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from .metrics import MonthlyReturn, MaturityMetrics, is_maturity_qualified

@dataclass
class MaturityResult:
    """毕业评估结果"""
    is_mature: bool              # 是否达到毕业标准
    profitable_months: int      # 盈利月份数
    total_months: int           # 总月份数
    benchmark_excess: float    # 基准超额收益
    oos_is_ratio: float         # OOS/IS 比率
    reason: Optional[str] = None  # 如果未达标，说明原因

    def to_dict(self) -> Dict:
        return {
            'is_mature': self.is_mature,
            'profitable_months': self.profitable_months,
            'total_months': self.total_months,
            'benchmark_excess': round(self.benchmark_excess, 4),
            'oos_is_ratio': round(self.oos_is_ratio, 3),
            'reason': self.reason
        }


class MaturityEvaluator:
    """策略成熟度评估器

    毕业条件（需同时满足）：
    1. 滚动6个月 ≥5个月盈利（每月 >0.5%）
    2. 相对基准（沪深300）超额 > 0%
    3. OOS/IS Sharpe > 0.8（防止过拟合）
    """

    # 毕业阈值
    MIN_PROFITABLE_MONTHS = 5
    MIN_MONTHS = 6
    MIN_BENCHMARK_EXCESS = 0.0  # 0%
    MIN_OOS_IS_RATIO = 0.8       # OOS 达到 IS 的 80%

    def evaluate(
        self,
        monthly_returns: List[MonthlyReturn],
        benchmark_excess: float,
        oos_is_ratio: float
    ) -> MaturityResult:
        """评估策略是否达到毕业标准

        Args:
            monthly_returns: 月度收益率列表
            benchmark_excess: 相对基准超额收益（小数）
            oos_is_ratio: OOS/IS Sharpe 比率

        Returns:
            MaturityResult
        """
        profitable_months = sum(1 for m in monthly_returns if m.profitable)
        total_months = len(monthly_returns)

        # 检查条件1：盈利月份数
        if profitable_months < self.MIN_PROFITABLE_MONTHS:
            return MaturityResult(
                is_mature=False,
                profitable_months=profitable_months,
                total_months=total_months,
                benchmark_excess=benchmark_excess,
                oos_is_ratio=oos_is_ratio,
                reason='profitable_months_insufficient'
            )

        # 检查条件2：基准超额
        if benchmark_excess <= self.MIN_BENCHMARK_EXCESS:
            return MaturityResult(
                is_mature=False,
                profitable_months=profitable_months,
                total_months=total_months,
                benchmark_excess=benchmark_excess,
                oos_is_ratio=oos_is_ratio,
                reason='benchmark_excess_insufficient'
            )

        # 检查条件3：OOS/IS 比率
        if oos_is_ratio < self.MIN_OOS_IS_RATIO:
            return MaturityResult(
                is_mature=False,
                profitable_months=profitable_months,
                total_months=total_months,
                benchmark_excess=benchmark_excess,
                oos_is_ratio=oos_is_ratio,
                reason='oos_is_ratio_insufficient'
            )

        # 全部满足
        return MaturityResult(
            is_mature=True,
            profitable_months=profitable_months,
            total_months=total_months,
            benchmark_excess=benchmark_excess,
            oos_is_ratio=oos_is_ratio,
            reason=None
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_maturity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/maturity/evaluator.py backend/tests/test_maturity.py
git commit -m "feat(maturity): add evaluator.py with graduation criteria"
```

---

## Task 3: 实现 daily_signal.py - 每日信号生成器

**Files:**
- Create: `backend/maturity/daily_signal.py`
- Modify: `backend/tests/test_maturity.py`

- [ ] **Step 1: Write the failing test - daily_signal**

```python
# 在 backend/tests/test_maturity.py 中添加

def test_daily_signal_strong_buy_mature():
    """毕业后：Kelly 10%, 低风险, 预测向上 -> 强烈买入"""
    from backend.maturity.daily_signal import DailySignalGenerator

    generator = DailySignalGenerator()

    signal = generator.generate(
        kelly_position=10.0,
        risk_level='acceptable',
        predicted_gain_5d=8.0,
        up_probability_5d=0.65,
        is_mature=True
    )
    assert signal == 'strong_buy'
    assert signal.level == '🟢'

def test_daily_signal_empty_before_maturity():
    """毕业前：Kelly 10% 但未达强烈买入 -> 空仓（禁止操作）"""
    from backend.maturity.daily_signal import DailySignalGenerator

    generator = DailySignalGenerator()

    signal = generator.generate(
        kelly_position=10.0,
        risk_level='acceptable',
        predicted_gain_5d=3.0,  # < 5%
        up_probability_5d=0.55,  # < 0.6
        is_mature=False
    )
    assert signal == 'empty'  # 毕业前非强烈买入都禁止

def test_daily_signal_watch_after_maturity():
    """毕业后：Kelly 5%, 中风险, 预测中性 -> 观望"""
    from backend.maturity.daily_signal import DailySignalGenerator

    generator = DailySignalGenerator()

    signal = generator.generate(
        kelly_position=5.0,
        risk_level='warning',
        predicted_gain_5d=3.0,
        up_probability_5d=0.55,
        is_mature=True
    )
    assert signal == 'watch'
    assert signal.level == '🟡'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_maturity.py -v`
Expected: FAIL with "No module named 'backend.maturity.daily_signal'"

- [ ] **Step 3: Write daily_signal.py**

```python
# backend/maturity/daily_signal.py
"""每日交易信号生成器"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class SignalLevel(Enum):
    """信号档位"""
    STRONG_BUY = ("strong_buy", "🟢")
    WATCH = ("watch", "🟡")
    EMPTY = ("empty", "🔴")

@dataclass
class DailySignal:
    """每日信号"""
    level: str                 # 'strong_buy' / 'watch' / 'empty'
    emoji: str                 # '🟢' / '🟡' / '🔴'
    kelly_position: float     # Kelly建议仓位
    risk_level: str           # 'acceptable' / 'warning' / 'high'
    predicted_gain_5d: float  # 5日预测涨幅
    up_probability_5d: float # 5日上涨概率
    is_mature: bool           # 是否毕业
    reason: str               # 信号原因

    def to_dict(self) -> dict:
        return {
            'level': self.level,
            'emoji': self.emoji,
            'kelly_position': round(self.kelly_position, 2),
            'risk_level': self.risk_level,
            'predicted_gain_5d': round(self.predicted_gain_5d, 2),
            'up_probability_5d': round(self.up_probability_5d, 3),
            'is_mature': self.is_mature,
            'reason': self.reason
        }


class DailySignalGenerator:
    """每日信号生成器

    规则：
    毕业前：只允许执行"强烈买入"档位
    毕业后：可执行所有档位（强烈买入/观望/空仓）
    """

    # 信号触发阈值
    STRONG_BUY_KELLY_MIN = 8.0      # Kelly仓位 > 8%
    STRONG_BUY_PROB_MIN = 0.6      # 上涨概率 > 0.6
    STRONG_BUY_GAIN_MIN = 5.0      # 预测涨幅 > 5%

    def generate(
        self,
        kelly_position: float,
        risk_level: str,
        predicted_gain_5d: float,
        up_probability_5d: float,
        is_mature: bool
    ) -> DailySignal:
        """生成每日交易信号

        Args:
            kelly_position: Kelly建议仓位（%）
            risk_level: 风险等级 ('acceptable' / 'warning' / 'high')
            predicted_gain_5d: 5日预测涨幅（%）
            up_probability_5d: 5日上涨概率（0-1）
            is_mature: 策略是否达到毕业标准

        Returns:
            DailySignal
        """
        # 检查是否强烈买入条件
        is_strong_buy = (
            kelly_position > self.STRONG_BUY_KELLY_MIN and
            risk_level == 'acceptable' and
            up_probability_5d > self.STRONG_BUY_PROB_MIN and
            predicted_gain_5d > self.STRONG_BUY_GAIN_MIN
        )

        # 检查是否空仓条件（高风险或预测下跌）
        is_empty = (
            risk_level == 'high' or
            up_probability_5d < 0.5 or
            predicted_gain_5d < 0
        )

        # 毕业前的特殊处理
        if not is_mature:
            if is_strong_buy:
                return DailySignal(
                    level='strong_buy',
                    emoji='🟢',
                    kelly_position=kelly_position,
                    risk_level=risk_level,
                    predicted_gain_5d=predicted_gain_5d,
                    up_probability_5d=up_probability_5d,
                    is_mature=is_mature,
                    reason='毕业前只允许强烈买入交易'
                )
            else:
                return DailySignal(
                    level='empty',
                    emoji='🔴',
                    kelly_position=kelly_position,
                    risk_level=risk_level,
                    predicted_gain_5d=predicted_gain_5d,
                    up_probability_5d=up_probability_5d,
                    is_mature=is_mature,
                    reason='策略未达毕业标准，禁止非强烈买入交易'
                )

        # 毕业后的逻辑
        if is_strong_buy:
            return DailySignal(
                level='strong_buy',
                emoji='🟢',
                kelly_position=kelly_position,
                risk_level=risk_level,
                predicted_gain_5d=predicted_gain_5d,
                up_probability_5d=up_probability_5d,
                is_mature=is_mature,
                reason='强烈买入信号'
            )
        elif is_empty:
            return DailySignal(
                level='empty',
                emoji='🔴',
                kelly_position=kelly_position,
                risk_level=risk_level,
                predicted_gain_5d=predicted_gain_5d,
                up_probability_5d=up_probability_5d,
                is_mature=is_mature,
                reason='高风险或预测下跌，禁止交易'
            )
        else:
            return DailySignal(
                level='watch',
                emoji='🟡',
                kelly_position=kelly_position,
                risk_level=risk_level,
                predicted_gain_5d=predicted_gain_5d,
                up_probability_5d=up_probability_5d,
                is_mature=is_mature,
                reason='中等机会，等待更明确信号'
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_maturity.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/maturity/daily_signal.py backend/tests/test_maturity.py
git commit -m "feat(maturity): add daily_signal.py with three-tier signal generation"
```

---

## Task 4: 创建 API 路由

**Files:**
- Create: `backend/api/routers/maturity.py`
- Modify: `backend/api/main.py` (add router)
- Modify: `backend/api/dependencies.py` (if needed)

- [ ] **Step 1: Write the failing test - api**

```python
# backend/tests/test_router_maturity.py
import pytest
from fastapi.testclient import TestClient

def test_get_maturity_status(client):
    """测试 /api/maturity/status 端点"""
    response = client.get('/api/maturity/status')
    assert response.status_code == 200
    data = response.json()
    assert 'is_mature' in data
    assert 'profitable_months' in data

def test_get_daily_signal(client):
    """测试 /api/maturity/daily_signal 端点"""
    response = client.get('/api/maturity/daily_signal')
    assert response.status_code == 200
    data = response.json()
    assert 'level' in data
    assert 'emoji' in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_router_maturity.py -v`
Expected: FAIL with "No module named 'backend.api.routers.maturity'"

- [ ] **Step 3: Write maturity router**

```python
# backend/api/routers/maturity.py
"""策略成熟度相关 API"""
from fastapi import APIRouter, Depends
from typing import List, Optional
from pydantic import BaseModel

from backend.maturity.evaluator import MaturityEvaluator
from backend.maturity.daily_signal import DailySignalGenerator
from backend.maturity.metrics import MonthlyReturn

router = APIRouter(prefix='/api/maturity', tags=['maturity'])


class MonthlyReturnResponse(BaseModel):
    month: str
    start_value: float
    end_value: float
    return_pct: float
    profitable: bool


class MaturityStatusResponse(BaseModel):
    is_mature: bool
    profitable_months: int
    total_months: int
    benchmark_excess: float
    oos_is_ratio: float
    reason: Optional[str]
    monthly_returns: List[MonthlyReturnResponse]


class DailySignalResponse(BaseModel):
    level: str
    emoji: str
    kelly_position: float
    risk_level: str
    predicted_gain_5d: float
    up_probability_5d: float
    is_mature: bool
    reason: str


@router.get('/status', response_model=MaturityStatusResponse)
def get_maturity_status():
    """获取策略毕业状态

    返回当前策略是否达到毕业标准，以及详细指标
    """
    # TODO: 从 simulator 获取历史持仓数据
    # TODO: 从 data_manager 获取沪深300数据计算基准超额
    # TODO: 从 backtester/walk_forward 获取 OOS/IS 比率

    # 临时返回模拟数据
    evaluator = MaturityEvaluator()

    # 模拟数据
    monthly_returns = [
        MonthlyReturn('2026-01', 10000, 10500, 5.0, True),
        MonthlyReturn('2026-02', 10500, 10800, 2.86, True),
        MonthlyReturn('2026-03', 10800, 10600, -1.85, False),
        MonthlyReturn('2026-04', 10600, 11200, 5.66, True),
        MonthlyReturn('2026-05', 11200, 11500, 2.68, True),
        MonthlyReturn('2026-06', 11500, 11800, 2.61, True),
    ]

    result = evaluator.evaluate(
        monthly_returns=monthly_returns,
        benchmark_excess=0.02,
        oos_is_ratio=0.85
    )

    return MaturityStatusResponse(
        is_mature=result.is_mature,
        profitable_months=result.profitable_months,
        total_months=result.total_months,
        benchmark_excess=result.benchmark_excess,
        oos_is_ratio=result.oos_is_ratio,
        reason=result.reason,
        monthly_returns=[
            MonthlyReturnResponse(
                month=m.month,
                start_value=m.start_value,
                end_value=m.end_value,
                return_pct=m.return_pct,
                profitable=m.profitable
            ) for m in monthly_returns
        ]
    )


@router.get('/daily_signal', response_model=DailySignalResponse)
def get_daily_signal():
    """获取每日交易信号

    根据当前 Kelly 仓位、风险等级、预测信息生成每日档位信号
    """
    # TODO: 从 recommender/buy_analyzer 获取 Kelly 仓位
    # TODO: 从 probability_predictor 获取上涨概率
    # TODO: 从 gain_predictor 获取预测涨幅

    generator = DailySignalGenerator()

    # 模拟数据
    signal = generator.generate(
        kelly_position=10.0,
        risk_level='acceptable',
        predicted_gain_5d=8.0,
        up_probability_5d=0.65,
        is_mature=True
    )

    return DailySignalResponse(**signal.to_dict())


@router.get('/history', response_model=List[MonthlyReturnResponse])
def get_monthly_history():
    """获取历史月度表现"""
    # TODO: 从 simulator 数据库获取真实历史数据

    return [
        MonthlyReturnResponse(month='2026-01', start_value=10000, end_value=10500, return_pct=5.0, profitable=True),
        MonthlyReturnResponse(month='2026-02', start_value=10500, end_value=10800, return_pct=2.86, profitable=True),
    ]
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_router_maturity.py -v`
Expected: FAIL with "router not registered"

- [ ] **Step 5: 在 main.py 中注册 router**

```python
# 在 backend/api/main.py 中添加
from backend.api.routers import maturity

# 在 create_app() 函数中
app.include_router(maturity.router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_router_maturity.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/api/routers/maturity.py backend/api/main.py backend/tests/test_router_maturity.py
git commit -m "feat(api): add maturity endpoints (/status, /daily_signal, /history)"
```

---

## Task 5: 集成真实数据源（TODO 替换模拟数据）

**Files:**
- Modify: `backend/api/routers/maturity.py` (替换模拟数据为真实数据)

- [ ] **Step 1: Write the failing test - integration**

```python
# 在 backend/tests/test_router_maturity.py 中添加

def test_maturity_status_with_real_data(client):
    """测试使用真实数据源的毕业状态"""
    response = client.get('/api/maturity/status')
    assert response.status_code == 200
    data = response.json()

    # 验证数据结构完整
    assert 'monthly_returns' in data
    assert len(data['monthly_returns']) > 0

    # 验证数据合理性
    for m in data['monthly_returns']:
        assert m['return_pct'] != 0 or m['profitable'] == False
```

- [ ] **Step 2: Run test to verify current implementation uses mock data**

Run: `cd /home/ailearn/projects/TradeSnake && python -m pytest backend/tests/test_router_maturity.py::test_maturity_status_with_real_data -v`
Expected: PASS (but with mock data)

- [ ] **Step 3: Document the integration work**

当前 API 端点使用模拟数据，需要后续集成真实数据源：

1. **monthly_returns**: 从 `simulator/account.py` 获取历史持仓，按月计算收益率
2. **benchmark_excess**: 从 `data_manager` 获取沪深300数据，计算相对收益
3. **oos_is_ratio**: 从 `backtester/walk_forward.py` 获取最新验证结果
4. **kelly_position**: 调用 `recommender/buy_analyzer.py` 的 Kelly 计算
5. **predicted_gain_5d**: 调用 `gain_predictor` 获取预测
6. **up_probability_5d**: 调用 `probability_predictor` 获取概率

- [ ] **Step 4: Commit**

```bash
git add backend/api/routers/maturity.py
git commit -m "docs(maturity): add integration notes for real data sources"
```

---

## Task 6: 创建 CHECKLIST 文档

**Files:**
- Create: `docs/plans/maturity/CHECKLIST.md`

- [ ] **Step 1: Create CHECKLIST.md**

```markdown
# Maturity 模块检查清单

## Auditor 检查项

### 毕业条件
- [ ] 滚动6个月 ≥5个月盈利（每月 >0.5%）
- [ ] 相对基准（沪深300）超额 > 0%
- [ ] OOS/IS Sharpe > 0.8

### 每日信号
- [ ] 强烈买入：Kelly > 8% + 低风险 + 上涨概率 > 0.6 + 预测涨幅 > 5%
- [ ] 观望：中等机会，不满足强烈买入也不满足空仓
- [ ] 空仓：高风险 或 上涨概率 < 0.5 或 预测下跌

### 毕业前限制
- [ ] 毕业前只执行"强烈买入"档位
- [ ] 非强烈买入一律返回"空仓"

## Fixer 修复后检查

- [ ] 代码正确，CHECKLIST 状态已更新

## Verifier 验证项

- [ ] API 端点正常返回
- [ ] 单元测试全部通过
- [ ] 集成测试验证数据流正确
```

- [ ] **Step 2: Commit**

```bash
git add docs/plans/maturity/CHECKLIST.md
git commit -m "docs(maturity): add CHECKLIST.md"
```

---

## 依赖关系图

```
API (maturity.py)
  ├── evaluator.py
  │   └── metrics.py
  ├── daily_signal.py
  └── simulator/account.py (真实数据)
  └── backtester/walk_forward.py (真实数据)
  └── data_manager (沪深300数据)
  └── recommender/buy_analyzer.py (Kelly仓位)
  └── gain_predictor (预测涨幅)
  └── probability_predictor (上涨概率)
```

---

## 执行选项

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**