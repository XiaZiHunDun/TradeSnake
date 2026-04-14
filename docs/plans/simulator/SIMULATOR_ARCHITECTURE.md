# 模拟炒股模块方案 v19.7

## 概述

模拟炒股模块是 TradeSnake 系统的交易执行层，模拟真实A股交易规则，支持买入、卖出、持仓管理、账户追踪。

**版本**: v19.7 | **状态**: ✅ 完整（单人模拟版）

---

## 输入输出

### 输入
| 来源 | 数据内容 |
|------|----------|
| data_manager | 实时行情（当前价格、涨跌幅、涨跌停状态） |
| recommender | 交易建议（买入/卖出/换股） |
| 用户操作 | 手动买入/卖出/撤单指令 |
| 内部状态 | 账户信息、持仓信息（内部管理） |

### 输出
| 输出内容 | 使用者 |
|----------|--------|
| 账户摘要（现金、总资产、盈亏） | 用户/前端展示、recommender（生成交易建议） |
| 持仓明细（成本、市值、盈亏） | 用户/前端展示、recommender（生成交易建议） |
| trades（成交记录，含手续费） | 用户/前端展示、backtester（换股效果验证） |
| orders（委托单记录） | 用户/前端展示 |
| holding_snapshots（每日持仓快照） | backtester（验证持仓收益） |

## 版本说明（v19.x专家二审修复）

| 修复项 | 问题 | 修正 |
|--------|------|------|
| 市价单成交价 | ❌按涨跌停价成交导致严重失真 | ✅改为当前最新价 |
| 印花税率 | ❌0.1%已过期 | ✅修正为0.05%（2023年后） |
| check_pending触发 | ❌触发机制不明确 | ✅明确事件驱动/定时轮询/查询触发三种方案 |

## 一、设计背景

本模块定位为**单人模拟炒股工具**，不涉及多用户撮合。核心目的是让用户在无风险环境下验证交易策略，记录交易历史，复盘分析。

**与多人撮合的区别**：
- 无需订单簿匹配（没有其他用户的买卖盘）
- 只需判断"用户订单 vs 市场价格"是否满足成交条件
- 保留委托单记录用于复盘，但不涉及实时撮合

## 二、模块结构

```
simulator/
├── __init__.py           # 模块导出（v19.7）
├── database.py           # SQLite数据库封装（WAL模式）
├── account.py            # 账户管理（含冻结资金、费用计算）
├── portfolio.py          # 持仓管理（FIFO批次 + 除权除息）
├── trader.py             # 交易执行器（市价/限价单 + 成交检查）
├── risk_control.py       # 风控限制（持仓/日买入/次数/涨跌停）
└── stats.py              # 交易统计（盈亏/胜率/回撤）
```

**说明**：委托单管理已集成到 `trader.py` 中（创建/撤销/状态更新）

## 三、核心组件

### 3.1 Database（数据库）

SQLite单例，WAL模式保证并发安全。

**表结构**：

| 表名 | 用途 |
|------|------|
| `account` | 账户信息（现金、初始资金、冻结资金） |
| `holding_batches` | 持仓批次（FIFO） |
| `orders` | 委托单（已提交/已报/成交/已撤/废单） |
| `trades` | 成交明细 |
| `account_flow` | 资金流水 |
| `trade_cooldown` | 交易冷却 |

**索引**：

```sql
CREATE INDEX idx_orders_status ON orders(status, code);
CREATE INDEX idx_orders_created ON orders(created_at);
CREATE INDEX idx_holdings_code ON holding_batches(code, bought_at);
```

### 3.2 Account（账户管理）

**属性**：

| 属性 | 说明 |
|------|------|
| `cash` | 可用资金 |
| `frozen_cash` | 冻结资金（挂单未成交） |
| `initial_cash` | 初始资金（20000元） |
| `total_assets` | 总资产 = 可用资金 + 冻结资金 + 持仓市值 |
| `total_profit` | 总盈亏 = 总资产 - 初始资金 |

**冻结资金计算**：

```python
def calculate_freeze(quantity: int, price: float, is_buy: bool) -> float:
    """买入冻结 = 数量×价格 + 预估佣金 + 预估过户费"""
    amount = quantity * price
    if is_buy:
        commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
        transfer_fee = amount * TRANSFER_FEE_RATE
        return amount + commission + transfer_fee
    return amount
```

### 3.3 Portfolio（持仓管理）

**功能**：
- FIFO批次管理，卖出按买入时间顺序扣减
- 除权除息处理（送股、分红、配股）
- 持仓占比计算

**关键方法**：

```python
class Portfolio:
    def get_holdings() -> List[Dict]      # 获取所有持仓
    def add_holding(code, name, qty, cost_price)  # 买入成交
    def reduce_holding(code, qty) -> bool  # 卖出成交（FIFO）
    def freeze_shares(code, qty)           # 卖出前冻结
    def unfreeze_shares(code, qty)        # 撤单解冻
    def adjust_for_ex_rights(code, bonus_ratio, cash_dividend)  # 除权除息
```

### 3.4 Trader（交易执行器）

**交易规则**：

| 订单类型 | 成交条件 | 说明 |
|---------|---------|------|
| 市价买入 | 立即按当前价格成交 | 涨跌停时无法成交 |
| 市价卖出 | 立即按当前价格成交 | 涨跌停时无法成交 |
| 限价买入 | 市价 ≤ 限价时成交 | 否则挂单等待 |
| 限价卖出 | 市价 ≥ 限价成交 | 否则挂单等待 |

**市价单成交价**（⭐专家指正）：
```python
def get_market_price(code: str, action: str) -> float:
    """市价单按当前最新价成交

    注意：不按涨跌停价成交！
    - 真实A股中，市价单按对手盘最优价成交（非涨跌停价）
    - 单人模拟中，直接按最新价成交最合理
    - 涨停时无法买入，跌停时无法卖出（已由风控拦截）
    """
    stock = get_single_stock_data(code)
    price = stock['price']

    # 涨跌停检查（前置）
    if action == 'buy' and stock.get('is_limit_up'):
        raise OrderError("涨停无法买入")
    if action == 'sell' and stock.get('is_limit_down'):
        raise OrderError("跌停无法卖出")

    # 可选：极小滑点模拟真实冲击成本
    # SLIPPAGE = 0.0001  # 0.01%滑点
    # return price * (1 + SLIPPAGE) if action == 'buy' else price * (1 - SLIPPAGE)
    return price
```

**核心方法**：

```python
class Trader:
    def buy(code: str, quantity: int, price: float = None,
            order_type: str = 'market') -> Dict:
        """买入股票

        市价单：立即成交
        限价单：price=None则用当前价，否则检查市场价≤限价
        """

    def sell(code: str, quantity: int, price: float = None,
             order_type: str = 'market') -> Dict:
        """卖出股票

        市价单：立即成交
        限价单：price=None则用当前价，否则检查市场价≥限价
        """

    def cancel_order(order_id: int) -> Dict:
        """撤销委托单"""

    def get_pending_orders(code: str = None) -> List[Dict]:
        """获取待成交委托"""

    def check_pending_orders(code: str = None):
        """检查限价挂单是否可成交

        触发机制（⭐专家指正，需明确）：
        - 方案A（推荐）：事件驱动 - 行情更新时触发
          # data_manager收到新行情时调用
          def on_price_update(code, new_price):
              trader.check_pending_orders(code)

        - 方案B：定时轮询 - 每隔N秒检查
          # 使用后台线程/定时任务
          def _start_polling(interval_sec=5):
              while self.is_running:
                  self.check_pending_orders()
                  sleep(interval_sec)

        - 方案C（简单）：用户查询时触发
          # get_account / get_portfolio 时顺便检查
          def get_account():
              self.check_pending_orders()
              return self.account.get_summary()
        """
```

### 3.5 Order（委托单管理）

**委托状态**：

| 状态 | 说明 |
|------|------|
| `pending` | 已提交并冻结，等待成交 |
| `filled` | 已成交 |
| `cancelled` | 已撤销 |
| `rejected` | 被拒绝（风控/涨跌停等） |

**委托类型**：
- `market`: 市价单
- `limit`: 限价单

### 3.6 RiskControl（风控限制）

| 规则 | 限制值 |
|------|--------|
| 单股持仓上限 | 30% |
| 单日买入限额 | 80% |
| 单日交易次数 | 10次 |
| 最小买入单位 | 100股 |

```python
class RiskControl:
    @classmethod
    def check_all(cls, action: str, **kwargs) -> Tuple[bool, str]:
        """综合风控检查"""
        # 持仓上限 / 日买入限额 / 交易次数 / 涨跌停 / 流动性
```

### 3.7 Stats（交易统计）

```python
class Stats:
    def get_summary(start_date=None, end_date=None) -> Dict:
        """交易统计"""
        return {
            'total_trades': int,
            'winning_trades': int,
            'losing_trades': int,
            'win_rate': float,
            'total_profit': float,
            'max_drawdown': float,
            'avg_holding_days': float,
        }
```

## 四、交易规则

### 4.1 交易费用（⭐专家指正）

| 费用 | 费率 | 收取 | 说明 |
|------|------|------|------|
| 佣金 | 0.03% | 买卖均收 | 含规费，最低5元 |
| 印花税 | **0.05%** | 仅卖出 | 2023年8月28日后减半征收 |
| 过户费 | 0.001% | 买卖均收 | 沪市深市均收（2022年后统一） |

### 4.2 T+1限制

当天买入的股票不能当天卖出。

```python
def can_sell(code: str, quantity: int) -> Tuple[bool, str]:
    holding = db.get_holding(code)
    total_qty = holding['total_quantity']
    today_bought = db.get_today_bought_quantity(code)
    sellable = total_qty - today_bought
    return quantity <= sellable, f"可卖{sellable}股"
```

### 4.3 涨跌停限制

| 状态 | 买入 | 卖出 |
|------|------|------|
| 涨停 | ❌ | ✅ |
| 跌停 | ✅ | ❌ |

## 五、数据流

### 5.1 市价买入流程

```
Trader.buy(code, qty, order_type='market')
    ↓
1. 风控检查
    ↓
2. 获取当前价格
    ↓
3. 冻结资金（含预估费用）
    ↓
4. 创建成交记录
    ↓
5. 增加持仓批次
    ↓
6. 解冻资金（扣除实际费用）
    ↓
7. 记录资金流水
    ↓
返回成交结果
```

### 5.2 限价买入流程

```
Trader.buy(code, qty, price=X, order_type='limit')
    ↓
1. 风控检查
    ↓
2. 检查是否涨跌停
    ↓
3. 冻结资金（含预估费用）
    ↓
4. 创建pending委托单
    ↓
返回委托单信息

[后续 check_pending_orders]
    ↓
定期检查：current_price ≤ limit_price？
    ↓
是 → 执行成交（同市价买入流程）
    ↓
否 → 继续等待
```

### 5.3 撤单流程

```
Trader.cancel_order(order_id)
    ↓
1. 检查订单状态
    ↓
2. 解冻剩余资金
    ↓
3. 更新订单状态为cancelled
    ↓
4. 记录资金流水
    ↓
返回撤单结果
```

## 六、API端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/account` | 账户摘要 |
| GET | `/api/account/flows` | 资金流水 |
| POST | `/api/account/reset` | 重置账户 |
| GET | `/api/portfolio` | 持仓明细 |
| POST | `/api/orders` | 创建委托 |
| POST | `/api/orders/{id}/cancel` | 撤单 |
| GET | `/api/orders` | 委托历史 |
| GET | `/api/orders/pending` | 待成交委托 |
| GET | `/api/trades` | 成交历史 |
| GET | `/api/stats/summary` | 交易统计 |

## 七、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v19.8 | 2026-04-09 | ✅ 修复导入路径错误（TRADE_COST）、盈亏计算使用FIFO匹配、最大回撤使用快照表计算 |
| v19.7 | 2026-04-08 | ✅ 每日持仓快照记录（holding_snapshots表）、换股效果验证、战力预测准确性分析 |
| v19.1 | 2026-04-07 | ✅ 完整实现：Stats + RiskControl模块、市价单最新价成交、限价单触发机制 |
| v19.0 | 2026-04-07 | 基于单人模拟场景重构：移除订单簿撮合，改为价格对比成交，增加除权除息与统计 |
| v18.6 | 2026-04-07 | 根据专家评审优化：集合竞价/连续竞价、价格笼子、并发安全 |
| v18.5 | 2026-04-07 | 增强：委托单/限价单/撤单/冻结资金 |
| v18.4 | 2026-04-07 | 初始完整实现 |

## 八、相关文档

- [ENGINE_ARCHITECTURE.md](./ENGINE_ARCHITECTURE.md) - 分析引擎
- [RECOMMENDER_ARCHITECTURE.md](./RECOMMENDER_ARCHITECTURE.md) - 推荐引擎
- [DATA_MANAGER_ARCHITECTURE.md](./DATA_MANAGER_ARCHITECTURE.md) - 数据管理
