# 任务：实盘风险管理（P4）

> 日期：2026-04-28  
> 类型：Feature Implementation（关键安全网）  
> 设计方：Cursor  
> 执行方：Claude Code  
> 前置任务：P1 完成

---

## For Claude Code

Execute this task continuously. Do not ask the user for routine decisions. Stop only when a stop condition below is met.

**风险管理是保护资金的最后防线，必须写得健壮。宁可少做不可做错。**

---

## Goal

在模拟器（Simulator）中实装 5 项风险管理功能：

1. **自动止损** — 持仓亏损达阈值时强制平仓
2. **尾随止损（Trailing Stop）** — 从持仓最高价回撤一定比例时平仓
3. **组合级回撤熔断** — 组合总净值从峰值回撤超限时降低仓位或清仓
4. **Kelly 仓位实际执行** — Trader 按 Kelly 计算结果自动调整下单数量
5. **市场环境识别** — 简单牛熊判断调整总仓位

---

## Context

### 当前状态

当前模拟器结构：
- `backend/simulator/trader.py` — 交易执行
- `backend/simulator/account.py` — 账户余额
- `backend/simulator/portfolio.py` — 持仓管理
- `backend/risk/risk_control.py` — 风险控制（但目前只有买入限制，无止损）
- `backend/risk/risk_analyzer.py` — 风险分析报告
- `backend/risk/kelly_calculator.py` — Kelly 仓位计算

### 设计原则

1. **所有风险参数写入 `constants.py`** — 不硬编码
2. **风险管理逻辑和交易逻辑分离** — 风险管理判断"该不该卖"，Trader 执行"怎么卖"
3. **日志记录所有风控触发** — 方便事后分析
4. **默认启用但可关闭** — 风控开关在配置中

---

## Scope

Allowed changes:

- `backend/risk/risk_control.py`（核心修改）
- `backend/simulator/trader.py`（集成风控）
- `backend/simulator/portfolio.py`（添加持仓最高价追踪）
- `backend/engine/cp_engine/constants.py`（新增风控常量）
- `backend/risk/kelly_calculator.py`（如需小调整）
- `backend/api/routers/simulator.py`（添加风控配置 API）
- `backend/api/schemas.py`（新增响应模型）
- `backend/tests/` 中新增风控测试

Out of scope:

- 不修改回测引擎的风控（回测已有 stop_loss）
- 不修改前端
- 不修改 CP 引擎

---

## Steps

### Step 1: 新增风控常量

在 `backend/engine/cp_engine/constants.py` 添加：

```python
# 实盘风控参数
RISK_MANAGEMENT = {
    'enabled': True,                    # 总开关
    'stop_loss_pct': -0.07,            # 固定止损 -7%
    'trailing_stop_pct': -0.05,        # 尾随止损：从最高价回撤 5%
    'portfolio_drawdown_limit': -0.15,  # 组合最大回撤 -15%
    'portfolio_drawdown_action': 'reduce',  # 'reduce'(减半仓位) 或 'clear'(清仓)
    'use_kelly_sizing': True,           # 是否使用 Kelly 计算仓位
    'kelly_fraction': 0.5,             # Kelly 系数折扣（半 Kelly，更保守）
    'max_single_position_pct': 0.20,   # 单只股票最大仓位占比 20%
    'market_regime_enabled': True,      # 是否启用市场环境识别
    'market_ma_period': 20,            # 大盘 MA 周期
    'bull_position_pct': 1.0,          # 牛市仓位 100%
    'bear_position_pct': 0.5,          # 熊市仓位 50%
}
```

### Step 2: 增强 Portfolio（追踪持仓最高价）

在 `portfolio.py` 中为每个持仓添加 `peak_price` 字段：

- [ ] 持仓 schema 添加 `peak_price`、`cost_price`
- [ ] 每次更新价格时：`peak_price = max(peak_price, current_price)`
- [ ] 添加方法 `get_positions_with_risk_info()` 返回带止损状态的持仓列表

### Step 3: 实现止损逻辑（risk_control.py）

```python
class RiskManager:
    """实盘风险管理器"""
    
    def __init__(self, config=None):
        from backend.engine.cp_engine.constants import RISK_MANAGEMENT
        self.config = config or RISK_MANAGEMENT
    
    def check_stop_loss(self, position) -> Tuple[bool, str]:
        """检查固定止损
        
        Returns: (should_sell, reason)
        """
        if not self.config['enabled']:
            return False, ""
        
        pnl_pct = (position['current_price'] - position['cost_price']) / position['cost_price']
        if pnl_pct <= self.config['stop_loss_pct']:
            return True, f"固定止损触发: {pnl_pct:.2%} <= {self.config['stop_loss_pct']:.2%}"
        return False, ""
    
    def check_trailing_stop(self, position) -> Tuple[bool, str]:
        """检查尾随止损"""
        if not self.config['enabled']:
            return False, ""
        
        drawdown = (position['current_price'] - position['peak_price']) / position['peak_price']
        if drawdown <= self.config['trailing_stop_pct']:
            return True, f"尾随止损触发: 从最高{position['peak_price']:.2f}回撤{drawdown:.2%}"
        return False, ""
    
    def check_portfolio_drawdown(self, account) -> Tuple[bool, str]:
        """检查组合级回撤"""
        if not self.config['enabled']:
            return False, ""
        
        current_value = account['total_assets']
        peak_value = account.get('peak_assets', current_value)
        drawdown = (current_value - peak_value) / peak_value
        
        if drawdown <= self.config['portfolio_drawdown_limit']:
            action = self.config['portfolio_drawdown_action']
            return True, f"组合回撤熔断: {drawdown:.2%}, 动作: {action}"
        return False, ""
    
    def calculate_kelly_position_size(self, stock_code, account_value, current_price):
        """用 Kelly 公式计算建议仓位"""
        from backend.risk.kelly_calculator import KellyCalculator
        calculator = KellyCalculator()
        kelly_result = calculator.calculate(stock_code)
        
        if kelly_result.get('kelly_position', 0) <= 0:
            return 0
        
        kelly_pct = kelly_result['kelly_position'] * self.config['kelly_fraction']
        kelly_pct = min(kelly_pct, self.config['max_single_position_pct'])
        
        target_value = account_value * kelly_pct
        shares = int(target_value / current_price / 100) * 100
        return max(0, shares)
    
    def detect_market_regime(self) -> str:
        """简单的市场环境识别
        
        基于上证指数 MA20：
        - 指数 > MA20 → 'bull'
        - 指数 < MA20 → 'bear'
        """
        # 从 DuckDB 获取上证指数最近 20 天收盘价
        # 计算 MA20
        # 比较当前价格和 MA20
        ...
```

### Step 4: 集成到 Trader

在 `trader.py` 的买入/卖出流程中集成：

- [ ] 买入前：如果 `use_kelly_sizing=True`，用 Kelly 计算建议手数
- [ ] 买入前：检查市场环境，调整仓位上限
- [ ] 买入前：检查单股仓位不超过 `max_single_position_pct`
- [ ] 每日检查：遍历所有持仓，检查止损和尾随止损
- [ ] 每日检查：检查组合回撤

添加 `check_risk_and_execute()` 方法：

```python
def check_risk_and_execute(self):
    """每日风控检查
    
    自动执行止损、尾随止损、组合熔断
    Returns: list of executed trades
    """
    risk_manager = RiskManager()
    executed = []
    
    # 1. 检查组合回撤
    should_reduce, reason = risk_manager.check_portfolio_drawdown(self.account.get_info())
    if should_reduce:
        # 按比例减仓或清仓
        ...
    
    # 2. 检查每只持仓的止损
    for position in self.portfolio.get_positions():
        should_sell, reason = risk_manager.check_stop_loss(position)
        if not should_sell:
            should_sell, reason = risk_manager.check_trailing_stop(position)
        if should_sell:
            result = self.sell(position['code'], position['shares'], reason=reason)
            executed.append(result)
    
    return executed
```

### Step 5: 添加 API 端点

在 `backend/api/routers/simulator.py` 添加：

```python
@router.post("/api/simulator/risk_check")
async def risk_check():
    """手动触发风控检查"""
    executed = _deps.trader.check_risk_and_execute()
    return {"triggered": len(executed), "trades": executed}

@router.get("/api/simulator/risk_config")
async def get_risk_config():
    """获取当前风控配置"""
    from backend.engine.cp_engine.constants import RISK_MANAGEMENT
    return RISK_MANAGEMENT
```

### Step 6: 测试

- [ ] 创建 `backend/tests/test_risk_manager.py`：
  - 测试固定止损触发
  - 测试尾随止损触发
  - 测试组合回撤熔断
  - 测试 Kelly 仓位计算
  - 测试风控关闭时不触发
  - 测试市场环境识别（mock 数据）
- [ ] 全量回归测试

---

## Verification

```bash
python -m pytest backend/tests/test_risk_manager.py -v
python -m pytest backend/tests/ -v -m "not integration" --ignore=backend/tests/test_routes.py
python -c "from backend.risk.risk_control import RiskManager; print('OK')"
```

---

## Completion Report Format

```markdown
## Summary
- 实装的风控功能列表

## Risk Control Matrix
| 功能 | 回测 | 实盘模拟器 |
|------|------|-----------|
| 止损 | ✅ | ✅ (新增) |
| ... |

## New Tests
- 测试列表

## Verification
- 测试结果

## Configuration
- 默认参数值及其选择依据
```
