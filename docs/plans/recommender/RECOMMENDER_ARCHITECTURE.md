# 智能推荐模块方案 v18.5

## 概述

智能推荐模块是 TradeSnake 系统的决策支持模块，基于战力（CP）评分体系给出股票买卖建议。

---

## 输入输出

### 输入
| 来源 | 数据内容 |
|------|----------|
| engine/cp_engine | StockCP 战力数据（总分、成长分、价值分、动量分、质量分） |
| engine/cp_engine | 风险评估报告（集中度/流动性/市场模式） |
| engine/cp_engine | Kelly仓位计算结果 |
| engine/cp_engine | 技术指标计算值（MA/MACD/RSI等） |
| **engine/gain_predictor** | GainPrediction 涨幅预测（predicted_gain_3d/5d, confidence） |
| **engine/probability_predictor** | ProbabilityPrediction 上涨概率（up_probability_3d/5d, confidence, risk_level） |
| stock_selector | 候选股票池（核心池+活跃池） |
| simulator | 持仓数据（持仓成本、买入日期、盈亏状态） |
| data_manager | cp_history 历史（用于多日动量计算） |

### 输出
| 输出内容 | 使用者 |
|----------|--------|
| 换股建议（from/to/净收益/行动标签） | 用户/前端展示、simulator（执行交易） |
| 买入信号（Kelly仓位、止损止盈、风险等级） | 用户/前端展示、simulator（执行交易） |
| 卖出信号（盈亏状态、行动建议、紧急程度） | 用户/前端展示、simulator（执行交易） |

**版本**: v19.9.9 | **状态**: ✅ 完整（P0全部完成）

**核心定位**：私人工具，直接输出操作建议（推荐、买入、卖出、换股），无需使用委婉表述。

---

## 一、三大操作场景

| 场景 | 说明 | 核心问题 |
|------|------|----------|
| **换股** | 卖出A，买入B | 战力差 vs 交易成本 |
| **纯买入** | 空仓/轻仓直接买入 | Kelly仓位、买入时机、风险评估 |
| **纯卖出** | 持仓止盈/止损卖出 | 盈亏状态、大盘环境、资金去向 |

```
战力数据 → 风险过滤 → 排序筛选 → 换股/买入/卖出 分析 → 建议输出
```

### 1.4 预测融合逻辑（v19.8新增）

推荐引擎融合战力评分与预测引擎结果，优先推荐"战力高+预测好"的股票。

#### 融合策略

| 预测维度 | 融合方式 | 说明 |
|----------|----------|------|
| **涨幅预测** | (predicted_gain_5d / 50) × confidence 加权 | 归一化到0-1，置信度调节 |
| **上涨概率** | up_probability_5d × confidence 加权 | 已是0-1范围，置信度调节 |

#### 融合公式

```
归一化处理：
  cp_norm = total_cp / 100          # 100分制 → 0-1
  gain_norm = predicted_gain_5d / 50  # 50%以上 → 1（上限1.0）
  prob_norm = up_probability_5d      # 已是0-1

综合得分 = 战力权重 × cp_norm + 涨幅权重 × gain_norm × confidence + 上涨概率权重 × prob_norm × confidence
```

**示例**（balanced配置，假设confidence=0.8）：
```
得分 = 0.4 × (total_cp/100) + 0.35 × (gain/50) × 0.8 + 0.25 × prob × 0.8
```

**权重配置**（可调整）：
| 配置项 | 保守 | 平衡 | 激进 |
|--------|------|------|------|
| 战力权重 | 0.5 | 0.4 | 0.3 |
| 涨幅预测权重 | 0.3 | 0.35 | 0.4 |
| 上涨概率权重 | 0.2 | 0.25 | 0.3 |

#### 过滤条件

| 条件 | 说明 |
|------|------|
| predicted_gain_5d < 0 | 过滤预测下跌股票 |
| up_probability_5d < 0.5 | 过滤上涨概率低于50% |
| risk_level = high | 过滤高风险股票 |
| volatility_20d > 40 | 过滤高波动股票 |

---

## 二、模块结构

```
backend/recommender/
├── __init__.py              # 统一导出
├── recommend_engine.py      # 推荐引擎主类
├── filters.py               # 股票过滤器
├── swap_calculator.py        # 换股计算器
├── buy_analyzer.py          # 买入分析器
├── sell_analyzer.py         # 卖出分析器
├── fusion.py                # 预测融合器 v19.8 ⭐新增
└── prompts.py               # 推荐理由生成
```

---

## 三、核心组件详解

### 3.1 RecommendEngine（推荐引擎）

**文件**: `recommend_engine.py`

#### 方法列表

```python
class RecommendEngine:
    # ===== 换股建议 =====
    def get_swap_suggestions(
        holdings: List[Dict],
        all_stocks: List[StockCP],
        principal: float,
        holding_days: int
    ) -> List[SwapSuggestion]:
        """获取换股建议列表"""

    # ===== 纯买入分析 =====
    def get_buy_signals(
        stocks: List[StockCP],
        principal: float,
        risk_preference: str = 'balanced'
    ) -> List[BuySignal]:
        """获取买入信号列表（空仓/轻仓入场）"""

    def analyze_buy_opportunity(
        self,
        stock: StockCP,
        principal: float,
        max_position_pct: float = 20.0
    ) -> BuySignal:
        """分析单只股票的买入价值"""

    # ===== 纯卖出分析 =====
    def get_sell_signals(
        holdings: List[Dict],
        market_mode: str = 'normal'
    ) -> List[SellSignal]:
        """获取持仓卖出信号列表"""

    def analyze_sell_opportunity(
        self,
        holding: Dict,
        market_mode: str = 'normal'
    ) -> SellSignal:
        """分析单只持仓的卖出价值"""
```

---

### 3.2 SwapCalculator（换股计算器）

**文件**: `swap_calculator.py`

#### 换股决策矩阵

| 净收益 | 行动 | 标签 | 颜色 |
|--------|------|------|------|
| > 成本 × 1.5 | **强烈推荐换股** | strong_swap | green |
| > 成本 × 1.0 | **建议换股** | swap | lightgreen |
| > 0 | 谨慎换股 | cautious_swap | yellow |
| > 成本 × (-0.5) | 持有不动 | hold | gray |
| ≤ 成本 × (-0.5) | **别换！** | avoid | red |

#### 强化约束

```python
def should_swap_with_constraints(
    from_stock: StockCP,
    to_stock: StockCP,
    unrealized_pnl_pct: float = 0,   # 持仓亏损幅度
    recent_swap_days: int = 0         # 近N天是否换过
) -> SwapDecision:
    """换股决策（带约束）"""

    # 1. 基础判断
    decision = calculate_swap_decision(from_stock, to_stock)

    # 2. 亏损约束：亏损>20%时提高门槛
    if unrealized_pnl_pct < -20:
        if decision['net_profit'] < decision['cost'] * 2.0:
            decision['action'] = 'hold'
            decision['label'] = '亏损较大，建议持有等待反弹'

    # 3. 换股频率约束：30天内换过则降优先级
    if recent_swap_days < 30:
        if decision['action'] == 'swap':
            decision['priority'] = 'low'

    return decision
```

---

### 3.3 BuyAnalyzer（买入分析器）⭐新增

**文件**: `buy_analyzer.py`

**核心职责**: 分析空仓/轻仓直接买入的机会

#### BuySignal 数据结构

```python
@dataclass
class BuySignal:
    stock: StockCP              # 股票
    kelly_position: float       # Kelly建议仓位比例（%）
    position_amount: float     # 建议买入金额（元）
    shares: int                # 建议买入股数（100整数倍）
    entry_price: float         # 建议买入价
    stop_loss: float           # 止损价（-5%）
    take_profit: float         # 止盈价（+20%）
    risk_level: str            # risk/warning/acceptable
    buy_strength: int          # 买入强度 1-3星
    reasons: List[str]         # 买入理由
    warnings: List[str]        # 风险提示
    breakeven_days: int        # 回本天数
```

#### 买入决策矩阵

| Kelly仓位 | 信号 | 说明 |
|-----------|------|------|
| > 15% | ⭐⭐⭐ 强烈买入 | 胜率和赔率都不错 |
| 8-15% | ⭐⭐ 建议买入 | 条件适中 |
| 3-8% | ⭐ 谨慎买入 | 仓位较小，需控制 |
| < 3% | ⚠️ 不建议买入 | 预期收益太低 |

#### 买入分析流程

```python
def analyze_buy_opportunity(
    stock: StockCP,
    principal: float,
    max_position_pct: float = 20.0
) -> BuySignal:
    """分析买入机会"""

    # 1. 风险检查（ST、涨跌停、停牌、流动性）
    if not is_buyable(stock):
        return BuySignal(signal='blocked', reason='风险检查未通过')

    # 2. Kelly仓位计算
    win_rate = estimate_win_rate(stock)      # 从历史/形态估计
    win_loss_ratio = estimate_win_loss(stock)
    kelly = calculate_kelly(win_rate, win_loss_ratio)
    safe_kelly = kelly * 0.5
    position_pct = min(safe_kelly, max_position_pct)

    position_amount = principal * position_pct
    shares = round_to_lot(position_amount / stock.price)

    # 3. 止损止盈
    stop_loss = stock.price * 0.95        # -5%止损
    take_profit = stock.price * 1.20     # +20%止盈

    # 4. 买入理由
    reasons = generate_buy_reasons(stock)
    warnings = generate_buy_warnings(stock)

    # 5. 回本天数
    breakeven = calculate_breakeven_days(stock, shares, position_amount)

    return BuySignal(
        stock=stock,
        kelly_position=position_pct * 100,
        position_amount=position_amount,
        shares=shares,
        entry_price=stock.price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_level=assess_risk_level(stock),
        buy_strength=calculate_buy_strength(position_pct),
        reasons=reasons,
        warnings=warnings,
        breakeven_days=breakeven
    )
```

---

### 3.4 SellAnalyzer（卖出分析器）⭐新增

**文件**: `sell_analyzer.py`

**核心职责**: 分析持仓卖出的机会（止盈/止损/调仓）

#### SellSignal 数据结构

```python
@dataclass
class SellSignal:
    stock: StockCP              # 股票
    holding_quantity: int      # 持仓数量
    cost_price: float          # 成本价
    current_price: float       # 当前价
    unrealized_pnl: float      # 浮动盈亏（元）
    unrealized_pnl_pct: float  # 盈亏比例（%）
    sell_reason: str           # 卖出原因
    market_mode: str           # 大盘模式
    action: str                # 建议：sell now/wait/don't sell
    action_label: str          # 行动标签
    action_color: str          # 颜色
    next_steps: str            # 后续建议
    urgency: int              # 紧急程度 1-3
```

#### 卖出决策矩阵

| 盈亏状态 | 大盘模式 | 建议 | 标签 |
|---------|---------|------|------|
| 盈利 > 20% | 任意 | **建议止盈** | green |
| 盈利 10-20% | crisis/defensive | **建议止盈** | lightgreen |
| 盈利 10-20% | normal | 可以继续持有 | yellow |
| 盈利 < 10% | normal | 继续持有 | gray |
| 亏损 < -10% | defensive/crisis | **建议止损** | orange |
| 亏损 < -20% | 任意 | **强烈建议止损** | red |
| 亏损 > -10% | normal | 继续持有观察 | gray |

#### 卖出原因类型

```python
SELL_REASONS = {
    'profit_taking': '止盈',           # 盈利达到目标
    'stop_loss': '止损',               # 亏损超过阈值
    'rebalance': '调仓',               # 仓位调整
    'risk_avoid': '风险规避',          # 大盘风险
    'momentum_weakening': '动量减弱',   # 技术面走弱
    'sector_rotation': '板块轮动'      # 行业切换
}
```

#### 卖出分析流程

```python
def analyze_sell_opportunity(
    holding: Dict,
    market_mode: str = 'normal'
) -> SellSignal:
    """分析卖出机会"""

    stock = holding['stock']
    cost_price = holding['cost_price']
    current_price = stock.price
    quantity = holding['quantity']

    # 1. 计算盈亏
    unrealized_pnl = (current_price - cost_price) * quantity
    unrealized_pnl_pct = (current_price - cost_price) / cost_price * 100

    # 2. 判断卖出原因
    sell_reason = determine_sell_reason(unrealized_pnl_pct, market_mode)

    # 3. 决策
    action, urgency = make_sell_decision(unrealized_pnl_pct, market_mode)

    # 4. 后续建议
    if action == 'sell now':
        next_steps = suggest_next_steps(stock, market_mode)

    return SellSignal(
        stock=stock,
        holding_quantity=quantity,
        cost_price=cost_price,
        current_price=current_price,
        unrealized_pnl=unrealized_pnl,
        unrealized_pnl_pct=unrealized_pnl_pct,
        sell_reason=sell_reason,
        market_mode=market_mode,
        action=action,
        action_label=ACTION_LABELS[action],
        action_color=ACTION_COLORS[action],
        next_steps=next_steps,
        urgency=urgency
    )
```

---

### 3.5 StockFilter（股票过滤器）

**文件**: `filters.py`

#### 过滤方法

| 方法 | 说明 | 优先级 |
|------|------|--------|
| `filter_st_stock` | 过滤ST/\*ST/退市股 | P0 |
| `filter_suspended` | 过滤停牌股票 | P0 |
| `filter_limit_up_down` | 过滤涨跌停（涨停不买，跌停不卖） | P0 |
| `filter_by_board` | 按板块过滤 | P0 |
| `filter_by_price_range` | 按价格区间过滤 | P0 |
| `filter_by_pe` | 按PE过滤 | P0 |
| `filter_by_roe` | 按ROE过滤 | P0 |
| `filter_by_risk` | 按风险分数过滤 | P0 |
| `filter_liquidity` | 流动性过滤（日成交额<1000万） | P1 |
| `filter_by_data_quality` | 按数据质量过滤 | P0 |

#### 涨跌停阈值（按板块）

| 板块 | 涨跌停幅度 | 判断阈值 |
|------|-----------|----------|
| 主板 | ±10% | ±9.9% |
| 创业板/科创板 | ±20% | ±19.9% |
| 北交所 | ±30% | ±29.9% |
| ST股 | ±5% | ±4.9% |

---

### 3.6 prompts.py（推荐理由生成）

**文件**: `prompts.py`

#### 买入理由生成

```python
def generate_buy_reasons(stock: StockCP) -> List[str]:
    reasons = []

    if stock.growth_score > 80:
        reasons.append(f"成长分{stock.growth_score:.0f}，市场Top")
    if stock.value_score > 80:
        reasons.append(f"价值分{stock.value_score:.0f}，估值有优势")
    if stock.quality_score > 80:
        reasons.append(f"质量分{stock.quality_score:.0f}，基本面优秀")
    if stock.momentum_score > 70:
        reasons.append(f"动量分{stock.momentum_score:.0f}，趋势向上")

    if stock.roe > 15:
        reasons.append(f"ROE {stock.roe:.1f}%，盈利能力强劲")
    if stock.pe < 20:
        reasons.append(f"PE {stock.pe:.1f}，估值合理")

    return reasons or ["战力综合得分较高"]
```

#### 卖出理由生成

```python
def generate_sell_reasons(holding: Dict, market_mode: str) -> List[str]:
    reasons = []
    pnl_pct = holding['unrealized_pnl_pct']

    if pnl_pct > 20:
        reasons.append(f"盈利{pnl_pct:.1f}%，已达止盈线")
    elif pnl_pct < -20:
        reasons.append(f"亏损{pnl_pct:.1f}%，超过止损线")
    elif pnl_pct < -10:
        reasons.append(f"亏损{pnl_pct:.1f}%，需关注")

    if market_mode == 'crisis':
        reasons.append("大盘危机模式，建议控制风险")
    elif market_mode == 'defensive':
        reasons.append("大盘偏弱，注意风险")

    return reasons
```

---

## 四、风控检查清单

### P0 必须检查

| 检查项 | 说明 | 不通过处理 |
|--------|------|-----------|
| ST股 | 名称包含ST/\*ST/退市 | 不买入 |
| 停牌 | is_suspended=True | 不交易 |
| 涨停 | change_pct >= 9.9%（板块差异化） | 不买入 |
| 跌停 | change_pct <= -9.9%（板块差异化） | 不卖出 |
| 数据质量 | 核心字段缺失过多 | 降低权重或过滤 |

### P1 建议检查

| 检查项 | 说明 | 不通过处理 |
|--------|------|-----------|
| 流动性 | 日成交额<1000万 | 警告 |
| 财报季 | 3-4/8-9月 | 降低权重 |
| 大盘模式 | crisis/defensive | 建议减仓 |

---

## 五、数据模型

### 5.1 换股建议

```python
{
    'from_code': str,
    'from_name': str,
    'from_cp': float,
    'to_code': str,
    'to_name': str,
    'to_cp': float,
    'cp_improvement': float,
    'net_profit': float,
    'trade_cost': float,
    'breakeven_days': int,
    'action': str,
    'action_label': str,
    'action_color': str,
    'prompt': str
}
```

### 5.2 买入信号

```python
{
    'code': str,
    'name': str,
    'total_cp': float,
    'kelly_position': float,
    'position_amount': float,
    'shares': int,
    'entry_price': float,
    'stop_loss': float,
    'take_profit': float,
    'buy_strength': int,
    'reasons': List[str],
    'warnings': List[str],
    'breakeven_days': int,
    'prompt': str
}
```

### 5.3 卖出信号

```python
{
    'code': str,
    'name': str,
    'quantity': int,
    'cost_price': float,
    'current_price': float,
    'unrealized_pnl': float,
    'unrealized_pnl_pct': float,
    'sell_reason': str,
    'market_mode': str,
    'action': str,
    'action_label': str,
    'action_color': str,
    'urgency': int,
    'next_steps': str,
    'prompt': str
}
```

---

## 六、接口契约

### 6.1 ⚠️ 与 stock_selector 和 engine 的联动

```python
from recommender import RecommendEngine
from engine import CPEngine
from stock_selector import StockSelector, PoolTier

stock_selector = StockSelector()
engine = CPEngine()
recommender = RecommendEngine()

# ─────────────────────────────────────────────
# 推荐候选股票池来源
# ─────────────────────────────────────────────
# 从 stock_selector 获取推荐候选池（核心+活跃）
candidate_codes = (
    stock_selector.get_pool(PoolTier.CORE) +
    stock_selector.get_pool(PoolTier.ACTIVE)
)

# 从 engine 获取战力数据
engine.calculate_for_codes(candidate_codes)

# ─────────────────────────────────────────────
# 换股建议
# ─────────────────────────────────────────────
swaps = recommender.get_swap_suggestions(
    holdings=[{'code': '000001', 'stock': engine.get_by_code('000001'), 'quantity': 1000, 'cost_price': 10.0}],
    all_stocks=engine.get_stocks_by_codes(candidate_codes),
    principal=100000,
    holding_days=30
)

# ─────────────────────────────────────────────
# 买入信号
# ─────────────────────────────────────────────
buys = recommender.get_buy_signals(
    stocks=engine.get_top(50),
    principal=100000,
    risk_preference='balanced'
)
```

### 6.2 接收 stock_selector 回调 v18.5

```python
class RecommenderCallback:
    """接收 stock_selector 的池状态变化通知 v18.5"""

    def __init__(self, engine: RecommendEngine):
        self._engine = engine
        self.candidate_pool: List[str] = []      # 推荐候选池
        self.priority_candidates: Set[str] = set()  # 优先候选集
        self.watchlist: Dict[str, List[str]] = {}   # 监控列表 {code: [warnings]}

    def on_pool_changed(self, tier: PoolTier, added: List[str], removed: List[str]):
        """池变化时更新推荐候选池"""
        if tier not in [PoolTier.CORE, PoolTier.ACTIVE]:
            return
        for code in added:
            if code not in self.candidate_pool:
                self.candidate_pool.append(code)
        self.candidate_pool = [c for c in self.candidate_pool if c not in removed]
        for code in removed:
            self.priority_candidates.discard(code)

    def on_stock_upgraded_to_core(self, code: str):
        """股票晋级到核心池 → 优先推荐"""
        self.priority_candidates.add(code)
        if code not in self.candidate_pool:
            self.candidate_pool.append(code)

    def on_financial_warning(self, code: str, warnings: List[str]):
        """财务预警时 → 从推荐移除，加入监控"""
        self.candidate_pool = [c for c in self.candidate_pool if c != code]
        self.priority_candidates.discard(code)
        self.watchlist[code] = warnings

    def get_candidate_pool(self) -> List[str]:
        """获取当前候选池"""
        return self.candidate_pool.copy()

    def get_priority_candidates(self) -> Set[str]:
        """获取优先候选集"""
        return self.priority_candidates.copy()

    def get_watchlist(self) -> Dict[str, List[str]]:
        """获取监控列表"""
        return self.watchlist.copy()
```

# 卖出信号
sells = recommender.get_sell_signals(
    holdings=[{'code': '000001', 'stock': engine.get_by_code('000001'), 'quantity': 1000, 'cost_price': 10.0}],
    market_mode='normal'
)
```

---

## 七、版本规划

### 7.1 当前状态 (v18.5)

- [x] 换股计算器
- [x] 股票过滤器
- [x] 预测融合 RecommenderCallback v19.8 ✅

### 7.2 待实现

**P0 必须**：
- [x] 买入分析器 BuyAnalyzer ✅
- [x] 卖出分析器 SellAnalyzer ✅
- [x] prompts.py 推荐理由生成 ✅
- [x] Kelly仓位集成 ✅

**P1 建议**：
- [x] 流动性过滤 ✅
- [ ] 财报季风险过滤
- [ ] 大盘模式联动

### 7.3 阶段规划

```
v18.2: 基础换股计算器 ✅

v18.5 (当前):
├── P0: BuyAnalyzer 买入分析
├── P0: SellAnalyzer 卖出分析
├── P0: prompts.py 理由生成
└── P0: Kelly仓位计算

v18.x: 完善风控、流动性、财报季
```

---

## 八、版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v18.6 | 2026-04-14 | 补充融合公式：归一化处理(cp/100, gain/50)、置信度乘数×confidence |
| v18.5 | 2026-04-09 | ✅ 预测融合(v19.8)：PredictionFusion实现战力与涨幅/概率预测融合；删除PositionCalculator死代码；BuySignal新增预测字段 |
| v18.4 | 2026-04-07 | ✅ P0全部完成：三大场景设计（换股+纯买入+纯卖出），BuyAnalyzer/SellAnalyzer/Kelly仓位/StockFilter五大过滤器/prompts.py |
| v18.3 | 2026-04-07 | 强化设计：涨跌停过滤、滑点成本、prompts.py |
| v18.2 | 2026-04-07 | 初始版本，基础推荐引擎 + 换股计算 + 过滤器 |

---

## 九、相关文档

- [项目概览](./PROJECT_OVERVIEW.md) - 项目整体介绍
- [分析引擎方案](./ENGINE_ARCHITECTURE.md) - 战力计算模块
- [数据管理方案](./DATA_MANAGER_ARCHITECTURE.md) - 数据获取模块
- [专家评审](../reviews/专家评审/) - 评审文档参考
