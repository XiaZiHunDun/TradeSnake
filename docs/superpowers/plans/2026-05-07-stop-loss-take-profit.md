# Stop-Loss/Take-Profit 传递到 Simulator 实现方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 将 BuySignal 的 stop_loss/take_profit 传递给 simulator，使持仓管理能在适当时机触发自动止损/止盈。

**Architecture:**
1. BuySignal 已有 stop_loss 和 take_profit 字段
2. Trader.buy() 需要扩展以接收这些参数
3. Portfolio 需要在持仓时记录每只股票的 stop_loss/take_profit
4. Portfolio 需要提供 check_stop_loss() / check_take_profit() 方法供风控调用

---

## Task 1: 在 Portfolio 中添加持仓止损止盈记录

**Files:**
- Modify: `backend/simulator/portfolio.py`

- [ ] **Step 1: 阅读 Portfolio 类，找到持仓数据结构**

约在 line 15-30 定义了 `Position` dataclass

- [ ] **Step 2: 在 Position 中添加 stop_loss 和 take_profit 字段**

找到 `class Position:` 约 line 15，在其中添加：
```python
stop_loss: float = 0.0      # 止损价
take_profit: float = 0.0    # 止盈价
```

- [ ] **Step 3: 在 Portfolio.add_position() 或 buy() 时记录止损止盈**

在 `Portfolio` 类中找到买入相关方法（约 line 50-80 的 `buy()` 方法），修改以支持传入 stop_loss/take_profit：
```python
def buy(self, code: str, price: float, quantity: int,
        stop_loss: float = 0.0, take_profit: float = 0.0) -> None:
    """买入

    Args:
        code: 股票代码
        price: 买入价格
        quantity: 数量
        stop_loss: 止损价
        take_profit: 止盈价
    """
    ...
    position = Position(
        code=code,
        buy_price=price,
        quantity=quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        ...
    )
```

- [ ] **Step 4: 验证修改后 Portfolio 仍可正常导入**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -c "from backend.simulator.portfolio import Portfolio; p = Portfolio(); print('OK')"`

---

## Task 2: 修改 Trader.buy() 支持 stop_loss/take_profit 参数

**Files:**
- Modify: `backend/simulator/trader.py`

- [ ] **Step 1: 阅读 Trader.buy() 方法签名和 Portfolio 调用**

约 line 58-100 定义了 `buy()` 方法

- [ ] **Step 2: 修改 Trader.buy() 签名，添加 stop_loss/take_profit 参数**

在 `def buy(self, code: str, quantity: int, price: float = None, order_type: str = 'market')` 后添加：
```python
def buy(self, code: str, quantity: int, price: float = None,
        order_type: str = 'market',
        stop_loss: float = 0.0, take_profit: float = 0.0) -> Dict:
```

在 `self.portfolio.buy(...)` 调用处，传入 stop_loss 和 take_profit：
```python
self.portfolio.buy(code, exec_price, quantity, stop_loss, take_profit)
```

- [ ] **Step 3: 验证修改后 Trader 仍可正常导入**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -c "from backend.simulator.trader import Trader; t = Trader(); print('OK')"`

---

## Task 3: 在 Portfolio 中添加止损止盈检查方法

**Files:**
- Modify: `backend/simulator/portfolio.py`

- [ ] **Step 1: 在 Portfolio 中添加 check_and_trigger_stops() 方法**

在 Portfolio 类（约 line 150 之后）添加：
```python
def check_and_trigger_stops(self, current_prices: Dict[str, float]) -> List[Tuple[str, str, float]]:
    """检查所有持仓是否触发止损/止盈

    Args:
        current_prices: {code: current_price}

    Returns:
        List of (code, reason, price) 需要卖出的股票
        reason 是 'stop_loss' 或 'take_profit'
    """
    to_sell = []
    for code, position in self._positions.items():
        if position.quantity <= 0:
            continue

        current_price = current_prices.get(code, 0)
        if current_price <= 0:
            continue

        # 检查止损
        if position.stop_loss > 0 and current_price <= position.stop_loss:
            to_sell.append((code, 'stop_loss', current_price))
            continue

        # 检查止盈
        if position.take_profit > 0 and current_price >= position.take_profit:
            to_sell.append((code, 'take_profit', current_price))
            continue

    return to_sell
```

- [ ] **Step 2: 在 Portfolio 中添加 get_position_info() 方法**

添加方法返回持仓详情（包括止损止盈价格）：
```python
def get_position_info(self, code: str) -> Optional[Dict]:
    """获取持仓详情"""
    position = self._positions.get(code)
    if not position or position.quantity <= 0:
        return None

    return {
        'code': position.code,
        'quantity': position.quantity,
        'buy_price': position.buy_price,
        'stop_loss': position.stop_loss,
        'take_profit': position.take_profit,
        'current_value': position.quantity * position.buy_price,  # 需要 current_price 才能计算实际值
    }
```

- [ ] **Step 3: 验证 Portfolio 的止损止盈逻辑**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -c "
from backend.simulator.portfolio import Portfolio
p = Portfolio()
p.buy('000001', 10.0, 100, stop_loss=9.0, take_profit=12.0)
stops = p.check_and_trigger_stops({'000001': 8.5})
print('止损触发:', stops)
stops2 = p.check_and_trigger_stops({'000001': 12.5})
print('止盈触发:', stops2)
"