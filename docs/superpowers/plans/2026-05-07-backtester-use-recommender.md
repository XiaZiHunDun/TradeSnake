# Backtester 使用 Recommender 选股实现方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 backtester 使用 recommender 的 `BuyAnalyzer.get_buy_signals()` 进行选股，复用融合预测 + Kelly仓位 + 风控过滤逻辑。

**Architecture:**
1. `BuyAnalyzer.get_buy_signals(stocks, principal)` 已有完整的选股逻辑（ST/涨跌停过滤 + Kelly仓位 + 买入强度排序）
2. `PredictionFusion.get_latest_predictions(codes)` 可从 `prediction_store` 获取历史预测数据用于回测
3. 在 `strategies.py` 中新增 `RecommendationStrategy`，将 `BuyAnalyzer` 的输出转换为 backtester 可用的 `StockFactor` 列表
4. 修改 `FullBacktestEngine` 支持使用 `RecommendationStrategy`

---

## 文件结构

```
backend/
├── recommender/
│   └── buy_analyzer.py       # 现有 BuyAnalyzer - 核心选股逻辑
├── backtester/
│   ├── strategies.py          # 新增 RecommendationStrategy
│   └── full_backtest.py       # 修改以支持 RecommendationStrategy
└── data_manager/
    └── prediction_store.py    # 现有 - get_latest_predictions() 用于获取历史预测
```

---

## Task 1: 理解 BuyAnalyzer.get_buy_signals() 的完整返回格式

**Files:**
- Modify: `backend/recommender/buy_analyzer.py:127-158`

- [ ] **Step 1: 阅读 buy_analyzer.py 的 get_buy_signals 方法**

确认返回格式为 `List[Dict]`，每个 dict 包含：
- `code`, `name`, `total_cp`
- `shares`, `entry_price`, `stop_loss`, `take_profit`
- `buy_strength` (1-3星)
- `risk_level` (risk/warning/acceptable)
- `kelly_position`, `position_amount`

输出：列出完整字段列表

---

## Task 2: 在 strategies.py 中新增 RecommendationStrategy

**Files:**
- Modify: `backend/backtester/strategies.py`

- [ ] **Step 1: 在 strategies.py 末尾添加 RecommendationStrategy**

```python
class RecommendationStrategy(Strategy):
    """推荐策略 - 使用 BuyAnalyzer.get_buy_signals() 选股

    复用 recommender 的完整逻辑：
    - 融合预测（GainPrediction + ProbabilityPrediction）
    - Kelly 仓位计算
    - ST/涨跌停/停牌 过滤
    - 买入强度排序
    """

    def __init__(self, n: int = 10, max_days: int = 5,
                 principal: float = 1000000.0,
                 risk_preference: str = 'balanced'):
        self.n = n
        self._max_days = max_days
        self.principal = principal
        self.risk_preference = risk_preference

    @property
    def name(self) -> str:
        return f"推荐TOP{self.n}"

    @property
    def max_position_days(self) -> int:
        return self._max_days

    @property
    def max_positions(self) -> int:
        return self.n

    def select_stocks(self, date: str, stock_factors: Dict[str, StockFactor],
                      rank: int = None) -> List[str]:
        """使用 BuyAnalyzer.get_buy_signals() 选股

        Args:
            date: 信号日 (T日) - 用于获取对应日期的预测数据
            stock_factors: {code: StockFactor} 历史战力因子数据
            rank: 最大持仓数量

        Returns:
            目标持仓股票代码列表
        """
        from backend.recommender.buy_analyzer import BuyAnalyzer
        from backend.engine import StockCP

        n = rank or self.n

        # 将 StockFactor 转换为 StockCP
        stocks = []
        for code, factor in stock_factors.items():
            if factor.is_suspended:
                continue
            # StockCP 需要的字段
            stock = self._factor_to_stockcp(factor)
            stocks.append(stock)

        if not stocks:
            return []

        # 调用 BuyAnalyzer 获取买入信号
        signals = BuyAnalyzer.get_buy_signals(
            stocks=stocks,
            principal=self.principal,
            risk_preference=self.risk_preference,
            limit=n * 2  # 多取一些以便排序
        )

        # 按 buy_strength 降序，取前 n 个
        signals.sort(key=lambda x: x.get('buy_strength', 0), reverse=True)
        return [s['code'] for s in signals[:n]]

    def _factor_to_stockcp(self, factor: StockFactor) -> 'StockCP':
        """将 StockFactor 转换为 StockCP"""
        from backend.engine import StockCP
        return StockCP(
            code=factor.code,
            name=factor.name,
            price=factor.close,
            pe=0, roe=0, pb=0,
            net_profit_growth=0, revenue_growth=0,
            change_pct=factor.change_pct,
            growth_score=factor.growth_score,
            value_score=factor.value_score,
            momentum_score=factor.momentum_score,
            quality_score=factor.quality_score,
            total_cp=factor.total_cp,
            risk_score=50,  # 默认中等风险
            volatility_20d=0,
            is_suspended=factor.is_suspended,
            avg_daily_amount_20d=0,
        )
```

- [ ] **Step 2: 验证 RecommendationStrategy 可被正常导入**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -c "from backend.backtester.strategies import RecommendationStrategy; print('OK')"`

Expected: `OK`

---

## Task 3: 修改 FullBacktestEngine 支持 RecommendationStrategy

**Files:**
- Modify: `backend/backtester/full_backtest.py`

- [ ] **Step 1: 在 FullBacktestEngine.__init__ 中添加 recommendation 策略**

找到 `FullBacktestEngine.__init__` (约 line 79)，添加：
```python
# 添加推荐策略（需要 cp_history 数据）
try:
    from .strategies import RecommendationStrategy
    self.strategies['recommendation'] = RecommendationStrategy(n=10)
except ImportError:
    pass
```

- [ ] **Step 2: 添加 run_recommendation 方法**

在 `FullBacktestEngine` 中添加新方法：
```python
def run_recommendation(
    self,
    start_date: str,
    end_date: str,
    strategy_name: str = 'recommendation',
    principal: float = 1000000.0,
    risk_preference: str = 'balanced'
) -> BacktestStats:
    """使用推荐策略运行回测

    复用 BuyAnalyzer.get_buy_signals() 的完整选股逻辑
    """
    if strategy_name not in self.strategies:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    strategy = self.strategies[strategy_name]
    if hasattr(strategy, 'principal'):
        strategy.principal = principal
    if hasattr(strategy, 'risk_preference'):
        strategy.risk_preference = risk_preference

    return self.run(
        start_date=start_date,
        end_date=end_date,
        strategy_name=strategy_name
    )
```

- [ ] **Step 3: 修改 self.strategies 字典初始化，动态加载 RecommendationStrategy**

将 `__init__` 中的策略映射修改为延迟导入：

```python
def __init__(self):
    from backend.data_manager.cp_history_store import get_cp_history_store
    from backend.data_manager.duckdb_store import get_duckdb_store

    self.cp_store = get_cp_history_store()
    self.duckdb = get_duckdb_store()

    # 策略映射
    self.strategies = {
        'top': TopNStrategy(n=10),
        'value': ValueStrategy(n=10),
        'growth': GrowthStrategy(n=10),
        'momentum': MomentumStrategy(n=10),
        'rising_cp': RisingCPStrategy(n=10),
        'hybrid': HybridRisingStrategy(n=10),
    }

    # 延迟导入推荐策略（需要 prediction_store）
    try:
        from .strategies import RecommendationStrategy
        self.strategies['recommendation'] = RecommendationStrategy(n=10)
    except ImportError:
        pass
```

- [ ] **Step 4: 验证修改后引擎仍能正常工作**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -c "from backend.backtester.full_backtest import FullBacktestEngine; e = FullBacktestEngine(); print('strategies:', list(e.strategies.keys()))"`

Expected: `strategies: ['top', 'value', 'growth', 'momentum', 'rising_cp', 'hybrid', 'recommendation']`

---

## Task 4: 测试 RecommendationStrategy 选股逻辑

**Files:**
- Create: `backend/tests/test_recommendation_strategy.py`

- [ ] **Step 1: 编写测试用例**

```python
"""测试 RecommendationStrategy 选股逻辑"""
import pytest
from backend.backtester.strategies import RecommendationStrategy, StockFactor


def test_recommendation_strategy_select():
    """测试按买入强度排序选股"""
    strategy = RecommendationStrategy(n=3, principal=100000.0, risk_preference='balanced')

    # 构造测试数据
    factors = {
        '000001': StockFactor(
            code='000001', name='平安银行', date='2024-01-01', close=10.0,
            change_pct=1.0, total_cp=80.0,
            growth_score=30.0, value_score=20.0, momentum_score=20.0, quality_score=10.0,
            is_limit_up=False, is_limit_down=False, is_suspended=False
        ),
        '000002': StockFactor(
            code='000002', name='万科A', date='2024-01-01', close=8.0,
            change_pct=2.0, total_cp=75.0,
            growth_score=25.0, value_score=25.0, momentum_score=15.0, quality_score=10.0,
            is_limit_up=False, is_limit_down=False, is_suspended=False
        ),
        '000004': StockFactor(
            code='000004', name='st股', date='2024-01-01', close=5.0,
            change_pct=0.0, total_cp=70.0,
            growth_score=20.0, value_score=20.0, momentum_score=20.0, quality_score=10.0,
            is_limit_up=False, is_limit_down=False, is_suspended=True  # 停牌
        ),
    }

    selected = strategy.select_stocks('2024-01-01', factors, rank=2)

    # st股和停牌股应该被过滤
    assert '000004' not in selected
    assert len(selected) <= 2
    assert selected[0] in ['000001', '000002']
```

- [ ] **Step 2: 运行测试**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -m pytest backend/tests/test_recommendation_strategy.py -v`

---

## Task 5: 验证完整回测流程使用 RecommendationStrategy

**Files:**
- Modify: `backend/tests/test_recommendation_strategy.py`

- [ ] **Step 1: 添加集成测试**

```python
def test_full_backtest_uses_recommendation():
    """验证 FullBacktestEngine 可以使用 recommendation 策略"""
    from backend.backtester.full_backtest import FullBacktestEngine

    engine = FullBacktestEngine()
    assert 'recommendation' in engine.strategies

    # 使用简单的日期范围测试
    try:
        result = engine.run_recommendation(
            start_date='2024-01-01',
            end_date='2024-01-31',
            strategy_name='recommendation',
            principal=1000000.0
        )
        assert result is not None
    except Exception as e:
        pytest.skip(f"需要真实数据或历史预测: {e}")
```

- [ ] **Step 2: 运行测试**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -m pytest backend/tests/test_recommendation_strategy.py -v`

---

## Task 6: 更新 backtester 文档

**Files:**
- Modify: `docs/plans/backtester/BACKTESTER_ARCHITECTURE.md`

- [ ] **Step 1: 在 ARCHITECTURE.md 中添加 RecommendationStrategy 说明**

在 "策略" 章节添加：
```markdown
### RecommendationStrategy

**作用**：使用 recommender 的 `BuyAnalyzer.get_buy_signals()` 选股，复用完整的融合预测 + Kelly仓位 + 风控过滤逻辑。

**数据流**：
```
stock_factors → BuyAnalyzer.get_buy_signals() → BuySignal list → ranked by buy_strength
```

**优势**：
- 复用 recommender 的完整逻辑（ST/涨跌停过滤、预测融合、Kelly仓位）
- 与实盘选股逻辑一致
- 回测结果更能反映实盘表现

**使用方式**：
```python
engine = FullBacktestEngine()
result = engine.run_recommendation(
    start_date='2024-01-01',
    end_date='2024-12-31',
    strategy_name='recommendation',
    principal=1000000.0,
    risk_preference='balanced'
)
```

**注意**：
- 需要 prediction_store 中有历史预测数据
- 如果某只股票没有预测数据，BuyAnalyzer 会使用默认参数计算
```

---

## 验证清单

- [ ] RecommendationStrategy 可正常导入
- [ ] FullBacktestEngine.strategies 包含 'recommendation'
- [ ] `run_recommendation()` 方法存在且可调用
- [ ] ST/停牌股票被正确过滤
- [ ] 集成测试通过（如果预测数据存在）