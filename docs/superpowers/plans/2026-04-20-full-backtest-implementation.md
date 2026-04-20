# 完整回测实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现基于历史战力数据的完整回测，支持3个月回测期，核心池约300只股票

**Architecture:**
1. 扩展 `CPHistoryBatchCalculator` 支持历史战力计算（按日期批量计算）
2. 新增 `FullBacktestEngine` 类实现完整回测逻辑
3. 新增 `/api/backtest/full` API 端点
4. 返回实际收益率、夏普比率、最大回撤等指标

**Tech Stack:** Python, FastAPI, DuckDB, SQLite, CPEngine

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/data_manager/filler.py` | 扩展 `CPHistoryBatchCalculator.calculate_historical_cp()` |
| `backend/backtester/full_backtest.py` | 新增 `FullBacktestEngine` 类（独立文件） |
| `backend/models/schemas.py` | 新增 `FullBacktestResponse` 等schema |
| `backend/api/router.py` | 新增 `/api/backtest/full` 端点 |

---

## Task 1: 检查财务历史数据

**Files:**
- Modify: `backend/data_manager/filler.py:2451` (添加get_stats)

**Steps:**

- [ ] **Step 1: 检查 financial_history 表数据量**

```python
# 在 Python REPL 中执行
from backend.data_manager.filler import get_financial_history_filler
filler = get_financial_history_filler()
stats = filler.get_stats()
print(stats)
```

**预期输出**:
```python
{'total_stocks': 3284, 'total_records': 0, 'codes_with_data': 0, 'completed': 0, 'failed': 0}
```

如果 `total_records = 0`，说明需要先填充财务历史数据。

---

## Task 2: 扩展 CPHistoryBatchCalculator 支持历史战力计算

**Files:**
- Modify: `backend/data_manager/filler.py:1709-1940` (在 `CPHistoryBatchCalculator` 类中添加方法)

**Steps:**

- [ ] **Step 1: 添加 `calculate_historical_cp` 方法**

在 `CPHistoryBatchCalculator` 类（line 1709后）中添加：

```python
def calculate_historical_cp(
    self,
    dates: List[str],
    codes: List[str] = None,
    force_recalculate: bool = False
) -> FillResult:
    """
    批量计算历史战力（按指定日期列表）

    Args:
        dates: 要计算的日期列表 (YYYY-MM-DD)
        codes: 股票代码列表，默认核心池
        force_recalculate: 是否强制重新计算（覆盖已有数据）

    Returns:
        FillResult: 计算结果统计
    """
    from datetime import datetime

    result = FillResult()

    # 如果没有指定股票，获取核心池股票
    if codes is None:
        codes = self._get_core_pool_codes()
        print(f"使用核心池: {len(codes)} 只股票")

    total_dates = len(dates)
    print(f"开始计算 {total_dates} 个交易日的战力...")

    for i, date in enumerate(dates):
        try:
            # 检查是否已有该日期的数据
            if not force_recalculate:
                existing = self.cp_store.get_cp_history_by_date(date)
                if len(existing) >= len(codes) * 0.8:  # 已有80%以上数据则跳过
                    print(f"  {date}: 已有数据 ({len(existing)}条)，跳过")
                    continue

            # 获取该日期的战力数据
            stocks_data = self._calculate_cp_for_date(date, codes)
            if stocks_data:
                self.cp_store.record_cp_history(stocks_data, date)
                result.total_records += len(stocks_data)
                result.success += 1
            else:
                result.failed += 1

            if (i + 1) % 10 == 0:
                print(f"  进度: {i+1}/{total_dates}")

        except Exception as e:
            result.failed += 1
            result.errors.append(f"{date}: {str(e)}")
            print(f"  {date}: 错误 - {e}")

    print(f"历史战力计算完成: 成功 {result.success}, 失败 {result.failed}, 记录 {result.total_records}")
    return result

def _get_core_pool_codes(self) -> List[str]:
    """获取核心池股票代码列表"""
    try:
        from backend.stock_selector.stock_selector import get_stock_selector
        selector = get_stock_selector()
        return list(selector.get_pool('CORE'))
    except Exception as e:
        print(f"获取核心池失败: {e}")
        return []

def _calculate_cp_for_date(self, date: str, codes: List[str]) -> List[Dict]:
    """
    计算指定日期的战力数据

    Args:
        date: 日期 (YYYY-MM-DD)
        codes: 股票代码列表

    Returns:
        战力数据列表
    """
    from datetime import datetime, timedelta

    # 获取日期范围内的K线数据（用于计算动量）
    end_dt = datetime.strptime(date, '%Y-%m-%d')
    start_dt = end_dt - timedelta(days=60)  # 往前60天取K线

    stocks_data = []

    for code in codes:
        try:
            # 获取该日期的K线数据
            klines_result = self.duckdb.get_klines(
                code,
                start_date=start_dt.strftime('%Y-%m-%d'),
                end_date=date,
                limit=100
            )

            if not klines_result.success or klines_result.data is None or len(klines_result.data) == 0:
                continue

            klines = klines_result.data.to_dict('records')

            # 获取股票财务数据
            financials = self._get_stock_financials([code])
            if code not in financials:
                continue

            stock_data = financials[code]

            # 使用 CPEngine 创建 StockCP
            stock = self._create_stock_cp(stock_data, klines)
            if stock:
                stock_dict = stock.to_dict()
                stock_dict['rank'] = 0  # 稍后排序
                stocks_data.append(stock_dict)

        except Exception as e:
            continue

    # 排序并设置排名
    stocks_data.sort(key=lambda x: x.get('total_cp', 0), reverse=True)
    for i, stock in enumerate(stocks_data):
        stock['rank'] = i + 1

    return stocks_data
```

- [ ] **Step 2: 运行测试**

```bash
cd /home/ailearn/projects/TradeSnake
python -c "
from backend.data_manager.filler import get_cp_history_calculator
calc = get_cp_history_calculator()

# 测试获取核心池股票
codes = calc._get_core_pool_codes()
print(f'核心池股票数: {len(codes)}')
print(f'示例: {codes[:5]}')
"
```

**预期输出**:
```
核心池股票数: 约300
示例: ['000001', '000002', ...]
```

- [ ] **Step 3: 测试单日战力计算**

```bash
python -c "
from backend.data_manager.filler import get_cp_history_calculator
calc = get_cp_history_calculator()

# 测试计算单日战力
stocks = calc._calculate_cp_for_date('2026-01-15', ['000001', '600000', '600519'])
print(f'计算结果: {len(stocks)} 只')
for s in stocks[:3]:
    print(f\"  {s['code']} {s['name']}: CP={s['total_cp']:.2f}\")
"
```

**预期输出**:
```
计算结果: 3 只
  600519 贵州茅台: CP=XX.XX
  ...
```

- [ ] **Step 4: Commit**

```bash
git add backend/data_manager/filler.py
git commit -m "feat(cp_history): 添加 calculate_historical_cp 方法支持历史战力计算"
```

---

## Task 3: 实现 FullBacktestEngine 类

**Files:**
- Create: `backend/backtester/full_backtest.py`

**Steps:**

- [ ] **Step 1: 创建 FullBacktestEngine 类**

```python
"""
完整回测引擎 - Full Backtest Engine v1.0

基于历史战力数据进行真实收益率回测
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math

from .strategies import Strategy, TopNStrategy, ValueStrategy, GrowthStrategy, MomentumStrategy, QualityStrategy
from .metrics import BacktestResult, Trade


@dataclass
class Position:
    """持仓"""
    code: str
    name: str
    quantity: int = 0
    avg_cost: float = 0.0
    buy_date: str = ''
    holding_days: int = 0


@dataclass
class BacktestTrade:
    """回测交易记录"""
    date: str
    action: str  # 'buy' or 'sell'
    code: str
    name: str
    price: float
    quantity: int
    amount: float
    commission: float
    reason: str = ''


@dataclass
class BacktestStats:
    """回测统计"""
    initial_capital: float
    final_value: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    equity_curve: List[Dict] = field(default_factory=list)
    trades: List[Dict] = field(default_factory=list)


class FullBacktestEngine:
    """完整回测引擎 v1.0"""

    # 交易费用
    COMMISSION_RATE = 0.0003  # 0.03%
    MIN_COMMISSION = 5.0
    STAMP_TAX_RATE = 0.001   # 0.1% (卖出时收取)
    TRANSFER_FEE_RATE = 0.00002  # 0.002%

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
            'quality': QualityStrategy(n=10),
        }

    def run(
        self,
        start_date: str,
        end_date: str,
        strategy_name: str = 'top',
        top_n: int = 10,
        initial_capital: float = 20000.0
    ) -> BacktestStats:
        """
        执行完整回测

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            strategy_name: 策略名称 (top/value/growth/momentum/quality)
            top_n: 持仓数量
            initial_capital: 初始资金

        Returns:
            BacktestStats: 回测统计结果
        """
        # 获取策略
        strategy = self.strategies.get(strategy_name, TopNStrategy(n=top_n))
        if hasattr(strategy, 'n'):
            strategy.n = top_n

        # 获取交易日列表
        trading_dates = self._get_trading_dates(start_date, end_date)
        if len(trading_dates) < 2:
            raise ValueError("交易日数据不足")

        # 初始化状态
        cash = initial_capital
        positions: Dict[str, Position] = {}
        pending_bought: Set[str] = set()
        trades: List[BacktestTrade] = []
        equity_curve: List[Dict] = []

        # 按日期遍历
        for i in range(len(trading_dates) - 1):
            signal_date = trading_dates[i]
            trade_date = trading_dates[i + 1]

            # 获取信号日的战力数据
            cp_data = self._get_cp_at_date(signal_date)
            if not cp_data:
                continue

            # 策略选股
            target_codes = [s['code'] for s in cp_data[:top_n * 2]]  # 取更多候选

            # 检查持仓超时
            for code in list(positions.keys()):
                positions[code].holding_days += 1
                if positions[code].holding_days > 5:  # 最大持仓5天
                    self._execute_sell(positions, cash, trades, code, trade_date, 'max_days')

            # 调仓
            current_codes = set(positions.keys())
            new_codes = set(target_codes[:top_n])

            # 卖出不在新目标中的持仓
            for code in current_codes - new_codes:
                self._execute_sell(positions, cash, trades, code, trade_date, 'rebalance')

            # 买入新目标
            for code in new_codes - current_codes:
                self._execute_buy(positions, cash, trades, pending_bought, code, trade_date)

            # 记录净值
            total_value = cash + sum(
                pos.quantity * self._get_price(code, trade_date)
                for pos in positions.values()
            )
            equity_curve.append({
                'date': trade_date,
                'total_value': total_value,
                'cash': cash,
                'position_value': total_value - cash
            })

            # 清除当日买入记录
            pending_bought.clear()

        # 计算统计
        return self._calculate_stats(
            initial_capital, cash, positions, equity_curve, trades
        )

    def _get_trading_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        result = self.duckdb.query(f"""
            SELECT DISTINCT trade_date
            FROM daily_kline
            WHERE trade_date >= '{start_date}' AND trade_date <= '{end_date}'
            ORDER BY trade_date
        """)
        if result.success:
            return result.data['trade_date'].tolist()
        return []

    def _get_cp_at_date(self, date: str) -> List[Dict]:
        """获取指定日期的战力数据"""
        return self.cp_store.get_cp_history_by_date(date)

    def _get_price(self, code: str, date: str) -> float:
        """获取指定日期的收盘价"""
        result = self.duckdb.get_klines(code, end_date=date, limit=1)
        if result.success and result.data is not None and len(result.data) > 0:
            return float(result.data.iloc[0]['close'])
        return 0.0

    def _execute_buy(self, positions: Dict, cash: float, trades: List,
                     pending_bought: Set, code: str, date: str):
        """执行买入"""
        price = self._get_price(code, date)
        if price <= 0:
            return

        # 获取股票名称
        cp_data = self._get_cp_at_date(date)
        name = next((s['name'] for s in cp_data if s['code'] == code), code)

        # 计算可买入数量（100股整数倍）
        max_qty = int(cash / (price * 1.001)) // 100 * 100
        if max_qty < 100:
            return

        # 计算费用
        gross_amount = price * max_qty
        commission = max(gross_amount * self.COMMISSION_RATE, self.MIN_COMMISSION)
        total_cost = gross_amount + commission

        if total_cost > cash:
            return

        # 执行
        cash -= total_cost
        positions[code] = Position(
            code=code,
            name=name,
            quantity=max_qty,
            avg_cost=price,
            buy_date=date,
            holding_days=0
        )
        pending_bought.add(code)

        trades.append(BacktestTrade(
            date=date,
            action='buy',
            code=code,
            name=name,
            price=price,
            quantity=max_qty,
            amount=gross_amount,
            commission=commission
        ))

    def _execute_sell(self, positions: Dict, cash: float, trades: List,
                     code: str, date: str, reason: str):
        """执行卖出"""
        if code not in positions:
            return

        pos = positions[code]
        price = self._get_price(code, date)
        if price <= 0:
            return

        # 计算费用
        gross_amount = price * pos.quantity
        commission = max(gross_amount * self.COMMISSION_RATE, self.MIN_COMMISSION)
        stamp_tax = gross_amount * self.STAMP_TAX_RATE
        transfer_fee = gross_amount * self.TRANSFER_FEE_RATE
        total_cost = commission + stamp_tax + transfer_fee

        net_amount = gross_amount - total_cost
        cash += net_amount

        trades.append(BacktestTrade(
            date=date,
            action='sell',
            code=code,
            name=pos.name,
            price=price,
            quantity=pos.quantity,
            amount=net_amount,
            commission=total_cost,
            reason=reason
        ))

        del positions[code]

    def _calculate_stats(self, initial_capital: float, final_cash: float,
                        positions: Dict, equity_curve: List[Dict],
                        trades: List[BacktestTrade]) -> BacktestStats:
        """计算回测统计"""
        # 计算最终市值
        final_value = final_cash + sum(
            pos.quantity * self._get_price(pos.code, equity_curve[-1]['date'] if equity_curve else '')
            for pos in positions.values()
        )

        total_return = (final_value - initial_capital) / initial_capital

        # 年化收益率（假设一年250个交易日）
        days = len(equity_curve) if equity_curve else 1
        annualized_return = (1 + total_return) ** (250 / days) - 1

        # 计算夏普比率和最大回撤
        sharpe = 0.0
        max_drawdown = 0.0

        if len(equity_curve) > 1:
            returns = []
            prev_value = equity_curve[0]['total_value']
            for eq in equity_curve[1:]:
                ret = (eq['total_value'] - prev_value) / prev_value
                returns.append(ret)
                prev_value = eq['total_value']

            if returns:
                mean_ret = sum(returns) / len(returns)
                std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / len(returns))
                if std_ret > 0:
                    sharpe = (mean_ret / std_ret) * math.sqrt(250)

            # 最大回撤
            peak = equity_curve[0]['total_value']
            for eq in equity_curve:
                if eq['total_value'] > peak:
                    peak = eq['total_value']
                drawdown = (peak - eq['total_value']) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        # 胜率
        sell_trades = [t for t in trades if t.action == 'sell']
        win_count = 0
        for t in sell_trades:
            if t.amount > 0:  # 简化判断
                win_count += 1
        win_rate = win_count / len(sell_trades) if sell_trades else 0

        return BacktestStats(
            initial_capital=initial_capital,
            final_value=final_value,
            total_return=total_return * 100,
            annualized_return=annualized_return * 100,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown * 100,
            win_rate=win_rate * 100,
            total_trades=len(trades),
            equity_curve=equity_curve,
            trades=[{
                'date': t.date,
                'action': t.action,
                'code': t.code,
                'name': t.name,
                'price': t.price,
                'quantity': t.quantity,
                'amount': t.amount,
                'commission': t.commission,
                'reason': t.reason
            } for t in trades]
        )
```

- [ ] **Step 2: Commit**

```bash
git add backend/backtester/full_backtest.py
git commit -m "feat(backtester): 添加 FullBacktestEngine 完整回测引擎"
```

---

## Task 4: 添加 API 端点和 Schema

**Files:**
- Modify: `backend/models/schemas.py`
- Modify: `backend/api/router.py`

**Steps:**

- [ ] **Step 1: 在 schemas.py 添加新的 Response 模型**

```python
# 在 schemas.py 末尾添加

class BacktestTradeResponse(BaseModel):
    """回测交易记录"""
    date: str
    action: str
    code: str
    name: str
    price: float
    quantity: int
    amount: float
    commission: float
    reason: str = ""

class EquityPointResponse(BaseModel):
    """净值曲线数据点"""
    date: str
    total_value: float
    cash: float
    position_value: float

class FullBacktestResponse(BaseModel):
    """完整回测响应"""
    start_date: str
    end_date: str
    strategy: str
    top_n: int
    initial_capital: float
    final_value: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    equity_curve: List[EquityPointResponse]
    trades: List[BacktestTradeResponse]
```

- [ ] **Step 2: 在 router.py 添加新端点**

在 `backend/api/router.py` 的 backtest 相关端点附近添加：

```python
@router.get("/api/backtest/full", response_model=FullBacktestResponse)
async def full_backtest(
    start_date: str = Query(..., regex="^\\d{4}-\\d{2}-\\d{2}$"),
    end_date: str = Query(..., regex="^\\d{4}-\\d{2}-\\d{2}$"),
    strategy: str = Query("top", pattern="^(top|value|growth|momentum|quality)$"),
    top_n: int = Query(10, ge=1, le=50),
    initial_capital: float = Query(20000, gt=0)
):
    """
    完整回测

    基于历史战力数据进行真实收益率回测，返回：
    - 总收益率
    - 年化收益率
    - 夏普比率
    - 最大回撤
    - 胜率
    - 每日净值曲线
    - 交易记录
    """
    from backend.backtester.full_backtest import FullBacktestEngine

    engine = FullBacktestEngine()
    stats = engine.run(
        start_date=start_date,
        end_date=end_date,
        strategy_name=strategy,
        top_n=top_n,
        initial_capital=initial_capital
    )

    return FullBacktestResponse(
        start_date=start_date,
        end_date=end_date,
        strategy=strategy,
        top_n=top_n,
        initial_capital=stats.initial_capital,
        final_value=stats.final_value,
        total_return=round(stats.total_return, 2),
        annualized_return=round(stats.annualized_return, 2),
        sharpe_ratio=round(stats.sharpe_ratio, 2),
        max_drawdown=round(stats.max_drawdown, 2),
        win_rate=round(stats.win_rate, 2),
        total_trades=stats.total_trades,
        equity_curve=[EquityPointResponse(**eq) for eq in stats.equity_curve],
        trades=[BacktestTradeResponse(**t) for t in stats.trades]
    )
```

- [ ] **Step 3: 测试 API**

```bash
# 启动服务后测试
curl -s --noproxy '*' "http://localhost:8001/api/backtest/full?start_date=2026-01-15&end_date=2026-04-15&strategy=top&top_n=10" | python -m json.tool | head -50
```

**预期输出**:
```json
{
    "start_date": "2026-01-15",
    "end_date": "2026-04-15",
    "strategy": "top",
    "top_n": 10,
    "initial_capital": 20000,
    "final_value": XXXXX,
    "total_return": XX.XX,
    "annualized_return": XX.XX,
    "sharpe_ratio": X.XX,
    "max_drawdown": XX.XX,
    "win_rate": XX.XX,
    "total_trades": XX,
    "equity_curve": [...],
    "trades": [...]
}
```

- [ ] **Step 4: Commit**

```bash
git add backend/models/schemas.py backend/api/router.py
git commit -m "feat(api): 添加 /api/backtest/full 完整回测端点"
```

---

## Task 5: 回填历史战力数据（可选，手动执行）

**Steps:**

- [ ] **Step 1: 执行历史战力回填**

```bash
cd /home/ailearn/projects/TradeSnake
python -c "
from backend.data_manager.filler import get_cp_history_calculator
from datetime import datetime, timedelta

calc = get_cp_history_calculator()

# 生成3个月的交易日列表
end_date = datetime(2026, 4, 17)
start_date = datetime(2026, 1, 15)

# 获取交易日列表（简化处理，使用 DuckDB）
from backend.data_manager.duckdb_store import get_duckdb_store
duckdb = get_duckdb_store()
result = duckdb.query(f\"\"
    SELECT DISTINCT trade_date
    FROM daily_kline
    WHERE trade_date >= '{start_date.strftime('%Y-%m-%d')}'
      AND trade_date <= '{end_date.strftime('%Y-%m-%d')}'
    ORDER BY trade_date
\"\")

dates = result.data['trade_date'].tolist() if result.success else []
print(f'需要计算的日期数: {len(dates)}')

# 执行计算
result = calc.calculate_historical_cp(dates)
print(f'计算完成: {result}')
"
```

---

## 实施检查清单

- [ ] Task 1: 检查财务历史数据
- [ ] Task 2: 扩展 CPHistoryBatchCalculator
- [ ] Task 3: 实现 FullBacktestEngine
- [ ] Task 4: 添加 API 端点
- [ ] Task 5: 回填历史战力数据（可选）
