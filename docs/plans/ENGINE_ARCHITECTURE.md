# 分析引擎模块方案 v19.7

## 概述

分析引擎模块是 TradeSnake 系统的核心计算模块，负责股票战力计算、风险评估、历史追踪。

**版本**: v19.7 | **状态**: ✅ 完整（P0+P1+P2全部完成）

**与推荐引擎对接**：为推荐引擎提供战力数据、风险评估、Kelly公式、技术指标等核心能力，支持换股、纯买入、纯卖出三大场景。

**核心流程**: `原始数据 → 战力计算 → 风险评估 → 历史记录`

---

## 输入输出

### 输入

| 来源 | 数据内容 |
|------|----------|
| data_manager | 股票综合数据（行情+财务） |
| data_manager | 历史日K线（用于多日动量计算） |
| data_manager | 分钟K线（核心池，用于 real_time_score） |
| stock_selector | 股票池分层（core/active/observe，每日变更） |

> **说明**：engine 向 stock_selector 查询池分层，自主制定分析计算频率策略（如核心池5分钟计算、活跃池30分钟计算）。外部数据获取频率由 data_manager 管理。

### 输出

| 输出内容 | 使用者 |
|----------|--------|
| StockCP（战力数据） | recommender（推荐） |
| 风险评估报告 | recommender/simulator |
| Kelly仓位计算结果 | recommender（买入分析） |
| 技术指标计算值 | recommender（买入/卖出分析） |
| cp_history历史数据 | data_manager（统一存储管理） |

---

## 一、模块结构

```
backend/engine/
├── __init__.py              # 统一导出
├── cp_engine.py             # 战力计算核心
├── risk_analyzer.py         # 风险评估器
├── history.py               # 战力历史记录（SQLite WAL）
├── constants.py             # 常量配置
├── indicators.py            # 技术指标（MA/MACD/RSI） v18.2
├── cache.py                # 因子级缓存（LRU+TTL） v18.2
├── parallel.py             # 并行计算（多进程） v18.2
├── refresh_strategy.py      # 刷新策略
└── trading_time.py         # 交易时间判断
```

---

## 二、核心组件详解

### 2.1 CPEngine（战力计算引擎）

**文件**: `cp_engine.py`

**核心类**:

| 类 | 说明 |
|---|---|
| `StockCP` | 单只股票战力数据（dataclass） |
| `CashCP` | 现金战力计算 |
| `TradeDecision` | 换股决策引擎 v15 |
| `CPEngine` | 战力计算引擎主类 |
| `DataValidator` | 数据校验器（ST/*ST过滤） v18.2 |
| `KellyCalculator` | Kelly公式仓位计算器 v18.2 |
| `TechnicalIndicators` | 技术指标计算器 v18.2 |
| `FactorCache` | 因子级缓存管理器 v18.2 |
| `ParallelCalculator` | 并行计算管理器 v18.2 |

#### StockCP（单只股票战力数据）

**字段**:
```python
@dataclass
class StockCP:
    # 基础数据
    code: str           # 股票代码
    name: str           # 股票名称
    price: float        # 当前价格
    pe: float           # 市盈率
    roe: float          # 净资产收益率
    net_profit_growth: float  # 净利润增长率
    revenue_growth: float     # 营收增长率
    change_pct: float         # 当日涨跌幅

    # 扩展指标
    pb: float = 0              # 市净率
    gross_margin: float = 0    # 毛利率
    revenue: float = 0         # 营业收入
    cashflow: float = 0        # 现金流
    debt_ratio: float = 0      # 资产负债率
    current_ratio: float = 0   # 流动比率
    interest_coverage: float = 0  # 利息保障倍数
    deducted_net_profit: float = 0  # 扣非净利润
    volume: float = 0          # 成交量
    amount: float = 0          # 成交额
    dividend_yield: float = 0   # 股息率
    market_cap: float = 0      # 总市值
    high: float = 0            # 最高价
    low: float = 0             # 最低价
    sector: str = ''           # 所属行业

    # 计算得分
    growth_score: float = 0    # 成长分
    value_score: float = 0    # 价值分
    momentum_score: float = 0  # 动量分
    quality_score: float = 0   # 质量分
    real_time_score: float = 0  # 实时分（v19.6，仅核心池）
    total_cp: float = 0       # 总战力

    # 风险
    risk_score: float = 0      # 风险分数
    peg: float = 0             # PEG估值

    # 元数据
    data_quality: str = 'low'  # 数据质量
```

**属性**:
```python
stock.board_type      # 'main'/'gem'/'star'/'bge'
stock.board_name      # '主板'/'创业板'/'科创板'/'北交所'
stock.can_trade_newbie  # 新手是否可交易
stock.trade_requirement  # 交易门槛说明
stock.sector          # 所属行业（如 '银行'、'房地产'）
```

#### CashCP（现金战力）

**公式**: 现金战力 = 本金 × (年化无风险利率 / 365) × 持有天数

**示例**: 10万现金持有30天 = 100000 × (0.02 / 365) × 30 = 164.38 战力损失

**基准**: 现金CP基准 = 50（中等水平，代表"零增长"基准）

**判断逻辑**:
```python
CashCP.should_hold_cash(stock_cp, stock_change_pct)
# 返回 (是否持有现金, 原因)
```

#### TradeDecision（换股决策引擎 v15）

**核心公式**:
```
换股净收益 = (B战力 - A战力) × 本金 × 持有天数 - 交易成本
```

**方法**:
```python
TradeDecision.should_swap(cp_a, cp_b, principal=100000, holding_days=30)
# 返回换股建议（含成本分解、净收益、建议等级）

TradeDecision.calculate_trade_cost(principal)
# 返回完整交易成本（含佣金、印花税、过户费）

TradeDecision.get_cp_threshold(principal, holding_days, threshold=0)
# 计算需要最小战力差才能达到指定收益率
```

**决策等级**:
| 等级 | 条件 | 标签 |
|---|---|---|
| strong_buy | 净收益 > 成本 × 1.2 | 强烈建议换股 |
| buy | 净收益 > 成本 × 0 | 谨慎换股 |
| hold | 净收益 > 成本 × (-0.5) | 持有不动 |
| danger | 净收益 ≤ 成本 × (-0.5) | 别换！ |

#### CPEngine（主引擎）

**方法**:
```python
engine = CPEngine()
engine.add_stock(stock: StockCP)      # 添加股票（自动去重）
engine.calculate_all() -> List[StockCP]  # 计算所有股票战力
engine.get_top(n=50, board=None) -> List[StockCP]  # 获取TOP N
engine.get_bottom(n=10, board=None) -> List[StockCP]  # 获取BOTTOM N
engine.get_by_code(code) -> Optional[StockCP]  # 根据代码获取
engine.to_dataframe() -> pd.DataFrame  # 转换为DataFrame
```

---

### 2.2 RiskAnalyzer（风险评估器）

**文件**: `risk_analyzer.py`

**风险评估方法**:

| 方法 | 功能 |
|---|---|
| `get_market_cp(stocks)` | 计算市场整体CP（简单平均） |
| `assess_concentration_risk(holdings)` | 评估仓位集中度 |
| `assess_industry_concentration_risk(holdings)` | 评估行业集中度 |
| `assess_liquidity_risk(holdings, avg_volume)` | 评估流动性风险 |
| `assess_market_risk(market_cp, holdings)` | 评估市场系统性风险 |
| `get_market_mode(market_cp, market_change_pct)` | 判断市场模式（正常/防御/危机） |
| `get_cash_recommendation(mode)` | 根据市场模式给出仓位建议 |
| `is_earnings_season(dt)` | 检查是否在财报发布期 |
| `check_trade_cooldown(db, code)` | 检查股票交易冷却状态 |
| `assess_small_account_risk(capital, trade_amount)` | 评估小额账户风险 |
| `calculate_break_even(cost_price, current_price)` | 计算解套所需涨幅 |
| `find_industry_peers(code, sector, all_stocks)` | 找同行业替代股票 |
| `generate_risk_report(db, holdings, all_stocks, market_cp, capital)` | 生成综合风险报告 |

**集中度阈值**:
```python
CONCENTRATION_THRESHOLDS = {
    'high': 70,    # 高风险
    'medium': 50,  # 中等风险
    'low': 30      # 低风险
}
```

**市场模式判断**:

```python
class MarketMode:
    """市场模式 - 用于判断大盘整体走势，决定仓位策略"""

    NORMAL = 'normal'           # 正常模式
    DEFENSIVE = 'defensive'     # 防御模式（市场低迷）
    CRISIS = 'crisis'         # 危机模式（大盘暴跌）

    @classmethod
    def get_market_mode(cls, market_cp: float, market_change_pct: float = None) -> str:
        """判断当前市场模式

        Args:
            market_cp: 市场整体CP（所有股票CP的简单平均）
            market_change_pct: 市场当日涨跌幅（可选）

        Returns:
            市场模式: 'normal' / 'defensive' / 'crisis'
        """
        # 危机模式：市场CP < 35 或 当日跌幅 > 3%
        if market_cp < 35:
            return cls.CRISIS
        if market_change_pct is not None and market_change_pct < -3:
            return cls.CRISIS

        # 防御模式：市场CP < 45 或 当日跌幅 > 1.5%
        if market_cp < 45:
            return cls.DEFENSIVE
        if market_change_pct is not None and market_change_pct < -1.5:
            return cls.DEFENSIVE

        return cls.NORMAL

    @classmethod
    def get_cash_recommendation(cls, mode: str) -> dict:
        """根据市场模式给出仓位建议（仅提示，不自动执行）

        Args:
            mode: 市场模式

        Returns:
            仓位建议，包含:
            - cash_ratio: 建议现金比例 (0.0 ~ 1.0)
            - action: 操作建议文字
            - reason: 原因说明
        """
        recommendations = {
            cls.CRISIS: {
                'cash_ratio': 1.0,
                'action': '全部换成现金',
                'reason': '市场CP极低或大盘暴跌，建议清仓观望'
            },
            cls.DEFENSIVE: {
                'cash_ratio': 0.7,
                'action': '建议高比例现金',
                'reason': '市场CP偏低或出现下跌，建议谨慎操作'
            },
            cls.NORMAL: {
                'cash_ratio': 0.0,
                'action': '正常操作',
                'reason': '市场整体正常，可以正常置换'
            }
        }
        return recommendations.get(mode, recommendations[cls.NORMAL])

    @classmethod
    def get_market_warning(cls, mode: str) -> str:
        """获取市场警告信息"""
        if mode == cls.CRISIS:
            return "⚠️ 危机模式：市场处于暴跌状态，建议全部换成现金"
        elif mode == cls.DEFENSIVE:
            return "⚡ 防御模式：市场偏弱，建议保持高比例现金"
        return "✅ 市场正常，可进行常规置换操作"
```

**财报发布月份**: [4, 7, 10]

---

### 2.3 History（战力历史记录）

**文件**: `history.py`

**历史数据存储**: SQLite `cp_history` 表（保留2年）

> ⚠️ **v18.2更新**: 已从JSON迁移到SQLite（WAL模式），解决并发写入损坏问题

**函数**:

| 函数 | 功能 |
|---|---|
| `save_history(stocks, date)` | 保存当日战力数据 |
| `load_history(days=7)` | 加载最近N天历史 |
| `get_stock_history(code, days=7)` | 获取指定股票历史战力 |
| `calc_momentum_nd(code, days=5)` | 计算N日动量 |
| `get_momentum_3d(code)` | 计算3日动量 |
| `get_momentum_5d(code)` | 计算5日动量 |
| `get_cp_changes(days=7)` | 获取战力变化显著的股票 |
| `get_historical_rankings(days=30, limit=10)` | 获取历史TOP10榜单 |
| `get_ranking_changes(days=30)` | 获取榜单排名变化 |

---

### 2.4 Constants（常量配置）

**文件**: `constants.py`

#### 战力公式权重 v14

```python
WEIGHTS = {
    'growth': 0.30,      # 成长分
    'value': 0.25,       # 价值分
    'quality': 0.20,     # 质量分
    'momentum': 0.10,    # 动量分 v18.2 (从0.15下调)
    'risk_penalty': 0.10  # 风险惩罚
}
```

#### A股交易费用

```python
TRADE_COST = {
    'commission': 0.0003,    # 券商佣金：万分之三
    'stamp_tax': 0.0005,     # 印花税：万分之五，仅卖出
    'transfer_fee': 0.00001, # 过户费：十万分之一，仅沪市
    'min_commission': 5.0,   # 最低佣金：5元/笔
}
```

#### 其他常量

```python
CASH_CP_BASELINE = 50       # 现金CP基准
RISK_FREE_RATE = 0.02       # 无风险利率
EARNINGS_SEASON_MONTHS = [4, 7, 10]  # 财报发布月份
SMALL_ACCOUNT_THRESHOLD = 5000  # 小额账户阈值
MIN_MEANINGFUL_TRADE = 50000     # 最小有意义交易量
```

---

### 2.5 Refresh Strategy（刷新策略）

**文件**: `refresh_strategy.py`

**函数**:
```python
get_refresh_interval() -> int  # 获取刷新间隔（秒）
# 交易时间: 60秒 / 盘前盘后: 300秒 / 收盘后: 3600秒

get_market_phase() -> str      # 获取当前市场阶段
# pre_open / morning_open / morning / late_morning / noon_break
# afternoon / market_close / after_hours / closed
```

---

### 2.6 Trading Time（交易时间）

**文件**: `trading_time.py`

**交易时间**:
- 上午: 09:30 - 11:30
- 下午: 13:00 - 15:00
- 周六周日休市

**函数**:
```python
is_trading_time() -> bool      # 判断当前是否为交易时间
get_trading_status() -> dict   # 获取详细交易状态
```

---

### 2.7 KellyCalculator（Kelly公式仓位管理） v18.2

**文件**: `risk_analyzer.py`

**核心公式**: `f* = p - (1-p)/b`
- f* = 最佳下注比例
- p = 获胜概率
- b = 盈亏比

**主要方法**:
```python
calculate_kelly_fraction(win_rate, win_loss_ratio) -> float  # 计算Kelly比例
get_position_recommendation(trades, win_rate, ...) -> Dict  # 获取仓位推荐
assess_trade_kelly(from_cp, to_cp, holding_days, ...) -> Dict  # 换股Kelly评估
```

**仓位推荐模式**: conservative (1/4 Kelly) / balanced (半Kelly) / aggressive (3/4 Kelly)

---

### 2.8 TechnicalIndicators（技术指标） v18.2

**文件**: `indicators.py`

**支持指标**:
- MA: 移动平均线（5/10/20/60日）
- MACD: 指数平滑异同移动平均线
- RSI: 相对强弱指数

**主要方法**:
```python
calculate_ma(prices, period) -> float           # 计算MA
calculate_macd(prices) -> Dict                   # 计算MACD
calculate_rsi(prices, period=14) -> float      # 计算RSI
get_technical_signal(prices) -> Dict           # 综合技术信号
```

**信号判断**: bullish / bearish / neutral

---

### 2.9 FactorCache（因子级缓存） v18.2

**文件**: `cache.py`

**特性**:
- LRU 淘汰策略
- TTL 过期机制（默认5分钟）
- 最大500只股票缓存

**主要方法**:
```python
get(code) -> StockFactorCache     # 获取缓存
set(code, cache) -> None          # 设置缓存
get_batch(codes) -> Tuple         # 批量获取
invalidate(code=None) -> None     # 使缓存失效
get_stats() -> Dict               # 缓存统计
```

---

### 2.10 ParallelCalculator（并行计算） v18.2

**文件**: `parallel.py`

**特性**:
- 多进程并行计算（ProcessPoolExecutor）
- 自动批量分割
- 失败重试机制

**主要方法**:
```python
calculate_batch(stocks_data, progress_callback) -> List[Dict]  # 批量并行计算
parallel_normalize(factor_values) -> Dict                     # 并行归一化
```

---

## 三、战力计算详解

### 3.1 分数计算

**成长分**:
```
net_g = max(0, min(300, 净利润增长率))
rev_g = max(-50, min(100, 营收增长率))
growth_score = net_g × 0.6 + rev_g × 0.4
```

**价值分**:
```
base_roe = min(max(0, ROE), 25)
pe_score = 根据PE区间给分 (5~20为佳)
peg_bonus = 根据PEG值给分 (≤1为佳)
pb_score = 根据PB值给分 (≤3为佳)
value_score = max(0, base_roe + pe_score + peg_bonus + pb_score × 0.3)
```

**质量分**:
```
cf_score = 现金流/ROE综合评分
gm_score = 毛利率评分 (>30%为佳)
debt_score = 资产负债率评分 (<60%为佳)
quality_score = max(0, cf_score + gm_score + debt_score)
```

**动量分**:
```
momentum_score = max(-10, min(10, 当日涨跌幅))
```

**实时分（real_time_score）** v19.6:
```
# 基于1分钟K线的实时因子，仅核心池计算
# 数据来源：DuckDB minute_kline 表
# 仅在盘中（9:30-15:00）计算

kline_ma5_change = (MA5 - MA5_开盘) / MA5_开盘 × 100
kline_ma15_change = (MA15 - MA15_开盘) / MA15_开盘 × 100
volume_ratio = 当前成交量 / MA5成交量

real_time_score = (
    kline_ma5_change × 0.5 +
    kline_ma15_change × 0.3 +
    (volume_ratio - 1) × 10 × 0.2
)
```

> **说明**：real_time_score权重2%，用于反馈市场分钟级实时变化，与日频动量分（momentum_score）职责分离。

### 3.2 总战力计算

```python
# 归一化到0-100
norm_growth = ((growth - min_growth) / (max_growth - min_growth)) × 100
norm_value = ((value - min_value) / (max_value - min_value)) × 100
norm_momentum = ((momentum - min_momentum) / (max_momentum - min_momentum)) × 100
norm_quality = max(10, quality_score)  # 最低基准10
norm_real_time = max(-10, min(10, real_time_score))  # 实时因子（仅核心池）

# 加权求和
base_cp = (
    norm_growth × 0.30 +
    norm_value × 0.25 +
    norm_quality × 0.20 +
    norm_momentum × 0.08 +    # 日频动量（降低）
    norm_real_time × 0.02     # 实时因子（新增，仅核心池）
)

# 风险调整
risk_factor = 1 - (risk_score / 100) × 0.10
total_cp = max(0, base_cp × risk_factor)
```

> **v19.6更新**：新增real_time_score（实时因子），权重2%，仅核心池计算，用于反馈1分钟K线的市场实时变化。

### 3.3 风险分数计算

```python
risk = 0

# PE风险
if pe < 0: risk += 30
elif pe > 100: risk += 20
elif pe > 50: risk += 10
elif pe < 5: risk += 5

# ROE风险
if roe < 0: risk += 25
elif roe < 5: risk += 10

# 增长风险
if net_profit_growth < -50: risk += 15
elif net_profit_growth < 0: risk += 5

# 营收风险
if revenue_growth < -30: risk += 10

# 波动风险
if |change_pct| > 8: risk += 15
elif |change_pct| > 5: risk += 8

risk_score = min(100, risk)
```

---

## 四、数据流

### 4.1 战力计算流程

```
原始数据 (akshare/东方财富)
         ↓
  create_stock_from_raw()
         ↓
     StockCP.__post_init__()
         ↓
    calculate_scores() 计算各因子分
         ↓
    calculate_risk() 计算风险分
         ↓
     CPEngine.calculate_all()
         ↓
    归一化 + 加权 + 风险调整
         ↓
    total_cp 输出
```

### 4.2 换股决策流程

```
持仓股票A (cp_a) + 候选股票B (cp_b)
         ↓
  TradeDecision.should_swap()
         ↓
  计算战力差 × 本金 × 持有天数
         ↓
  减去完整交易成本
         ↓
  根据阈值判断决策等级
         ↓
  返回 swap/hold/avoid 建议
```

---

## 五、数据输入输出接口

### 5.1 引擎与数据管理的边界

```
┌─────────────────────────────────────────────────────────┐
│                   data_manager                          │
│  (负责数据获取、缓存、清洗)                              │
└─────────────────────┬───────────────────────────────────┘
                      │
         原始数据 (Dict) / StockCP 对象
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                   stock_selector                         │
│  (负责股票池分层、维护更新策略) ⚠️ v19.5 新增           │
└─────────────────────┬───────────────────────────────────┘
                      │
              股票池列表 (core/active/observe)
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                     engine                               │
│  (负责战力计算、风险评估、历史追踪)                        │
└─────────────────────┬───────────────────────────────────┘
                      │
         StockCP List / 风险报告 / 历史数据
```

### 5.2 ⚠️ 与 stock_selector 的联动

**核心池 + 活跃池** → 战力计算 → 战力榜展示

```python
class CPEngine:
    def __init__(self, stock_selector: StockSelector):
        self.stock_selector = stock_selector

    def calculate_all(self):
        # 从 stock_selector 获取应分析的股票池
        codes = (
            self.stock_selector.get_pool(PoolTier.CORE) +
            self.stock_selector.get_pool(PoolTier.ACTIVE)
        )

        # 只对这 ~800 只股票计算战力
        for code in codes:
            self.calculate_cp(code)

    def on_stock_upgraded(self, code: str):
        """收到 stock_selector 晋级通知时，重新计算该股票战力"""
        self.calculate_cp(code)
```

### 5.2 输入数据格式

**格式A: 原始数据字典 (来自 data_manager)**
```python
raw_stock = {
    'code': '000001',
    'name': '平安银行',
    'price': 12.5,
    'pe': 8.5,
    'roe': 12.3,
    'net_profit_growth': 15.2,
    'revenue_growth': 8.5,
    'change_pct': 1.2,
    'pb': 0.9,
    'gross_margin': 30.5,
    'revenue': 10000000000,
    'cashflow': 500000000,
    'debt_ratio': 45.0,
    'sector': '银行',
    # ... 其他字段
}
```

**格式B: StockCP 对象 (引擎内部流转)**
```python
stock = StockCP(
    code='000001',
    name='平安银行',
    price=12.5,
    pe=8.5,
    roe=12.3,
    net_profit_growth=15.2,
    revenue_growth=8.5,
    change_pct=1.2,
    # ... 自动计算 scores 和 total_cp
)
```

### 5.3 引擎输入接口

```python
class CPEngine:
    def calculate_from_raw(raw_stocks: List[Dict]) -> List[StockCP]:
        """从原始数据字典直接计算战力

        内部流程: 字典验证 → 字段映射 → StockCP创建 → 战力计算
        """

    def calculate_from_stocks(stocks: List[StockCP]) -> List[StockCP]:
        """从已创建的StockCP对象计算（跳过数据转换）

        适用于: 缓存命中后直接计算、跨引擎共享StockCP对象
        """

    def add_stock(stock: StockCP) -> None:
        """添加单只股票（自动去重）"""
```

### 5.4 数据校验接口

```python
class DataValidator:
    @staticmethod
    def validate(raw: Dict) -> ValidationResult:
        """校验输入数据

        返回:
            ValidationResult(is_valid, cleaned_data, errors)
        """

    @staticmethod
    def validate_field(name: str, value: Any, field_type: type) -> Any:
        """校验并转换单个字段

        示例:
            validate_field('pe', '8.5', float) -> 8.5
            validate_field('pe', 'N/A', float) -> 0.0
            validate_field('roe', None, float) -> 0.0
        """
```

**校验规则**:
| 字段 | 类型 | 校验规则 | 默认值 |
|------|------|---------|--------|
| code | str | 非空，6位数字 | 报错 |
| name | str | 非空 | 报错 |
| price | float | > 0 | 报错 |
| pe | float | >= 0 或 None | 0.0 |
| roe | float | -100 ~ 100 或 None | 0.0 |
| change_pct | float | -50 ~ 50 或 None | 0.0 |

---

## 六、因子扩展机制

### 6.1 因子注册表设计

```python
@dataclass
class FactorConfig:
    name: str              # 因子名称 (如 'growth', 'value')
    weight: float          # 权重 (如 0.30)
    calculator: Callable    # 计算函数
    normalizer: Callable    # 归一化函数
    enabled: bool = True    # 是否启用

class FactorRegistry:
    """因子注册表 - 支持动态添加/禁用因子"""

    _factors: Dict[str, FactorConfig] = {}

    @classmethod
    def register(cls, config: FactorConfig):
        """注册新因子"""

    @classmethod
    def get(cls, name: str) -> FactorConfig:
        """获取因子配置"""

    @classmethod
    def list_enabled(cls) -> List[FactorConfig]:
        """获取所有启用的因子"""

    @classmethod
    def disable(cls, name: str):
        """禁用因子（用于A/B测试）"""
```

### 6.2 内置因子

```python
# 因子定义示例
factors = [
    FactorConfig(
        name='growth',
        weight=0.30,
        calculator=lambda s: s.net_profit_growth * 0.6 + s.revenue_growth * 0.4,
        normalizer=lambda values: min_max_normalize(values, 0, 100)
    ),
    FactorConfig(
        name='value',
        weight=0.25,
        calculator=lambda s: calculate_value_score(s),
        normalizer=lambda values: min_max_normalize(values, 0, 100)
    ),
    # 未来可添加:
    # FactorConfig(name='tech_macd', weight=0.10, calculator=calculate_macd, ...)
    # FactorConfig(name='momentum_5d', weight=0.05, calculator=calculate_momentum, ...)
]
```

### 6.3 未来扩展方向

| 阶段 | 因子类型 | 示例 | 权重建议 |
|------|---------|------|---------|
| v20 | 技术指标因子 | MACD/RSI/MA组合 | 0.10 |
| v20 | 资金流因子 | 北向资金/主力净流入 | 0.05 |
| v21 | 情绪因子 | 龙虎榜/舆情评分 | 0.05 |

---

## 七、接口契约

### 7.1 与 data_manager 的契约

**标准调用流程**:
```python
from data_manager import get_stock_data_api
from engine import CPEngine

# 1. 从数据管理模块获取原始数据
raw_stocks = get_stock_data_api(limit=200)

# 2. 交给分析引擎计算战力
engine = CPEngine()
stocks = engine.calculate_from_stocks([
    create_stock_from_raw(**raw) for raw in raw_stocks
])
results = engine.calculate_all()

# 3. 获取战力榜单
top50 = engine.get_top(50, board='main')
```

**数据管理模块返回的完整字段** (`get_full_stock_data()`):

| 字段 | 类型 | 说明 | 引擎需求 |
|------|------|------|---------|
| `code` | str | 6位股票代码 | ✅ 必需 |
| `name` | str | 股票名称 | ✅ 必需 |
| `price` | float | 当前价 | ✅ 必需 |
| `yesterday` | float | 昨收价 | - |
| `open` | float | 开盘价 | - |
| `high` | float | 最高价 | ✅ |
| `low` | float | 最低价 | ✅ |
| `volume` | float | 成交量 | ✅ |
| `amount` | float | 成交额 | ✅ |
| `pe` | float | 市盈率 | ✅ 必需 |
| `pb` | float | 市净率 | ✅ |
| `change_pct` | float | 当日涨跌幅 | ✅ 必需 |
| `market_cap` | float | 总市值 | ✅ |
| `roe` | float | 净资产收益率 | ✅ 必需 |
| `net_profit_growth` | float | 净利润增长率 | ✅ 必需 |
| `revenue_growth` | float | 营收增长率 | ✅ 必需 |
| `gross_margin` | float | 毛利率 | ✅ |
| `revenue` | float | 营业收入 | ✅ |
| `cashflow` | float | 现金流 | ✅ |
| `debt_ratio` | float | 资产负债率 | ✅ |
| `dividend_yield` | float | 股息率 | ✅ |
| `data_quality` | str | 数据质量标记 | ✅ |
| `data_source` | str | 数据来源 | - |

**✅ 已对接字段（v18.2完成）**:

| 字段 | 说明 | 状态 |
|------|------|---------|
| `sector` | 所属行业（如'银行'、'房地产'） | ✅ 已实现 |
| `current_ratio` | 流动比率 | ✅ 已有 |
| `interest_coverage` | 利息保障倍数 | ✅ 已有 |
| `deducted_net_profit` | 扣非净利润 | ✅ 已有 |

**引擎保证的输出**:
```python
# StockCP.to_dict() 输出的完整字段
{
    'code': str,
    'total_cp': float,     # 0-100 总战力
    'growth_score': float,
    'value_score': float,
    'quality_score': float,
    'momentum_score': float,
    'risk_score': float,   # 0-100 风险分数
    # ... 全部原始字段（含sector）
}
```

**数据质量标记** (`data_quality`):
```python
'high'    # PE/ROE/增长数据完整
'medium'  # 部分财务数据完整
'low'     # 仅行情数据
```

**字段校验规则**:
```python
# 引擎对关键字段的校验
REQUIRED_FIELDS = ['code', 'name', 'price', 'pe', 'roe', 'net_profit_growth', 'revenue_growth', 'change_pct']

# 数值范围校验
VALIDATION_RULES = {
    'price': {'min': 0, 'max': 10000},
    'pe': {'min': 0, 'max': 1000, 'default': 0},
    'roe': {'min': -100, 'max': 100, 'default': 0},
    'change_pct': {'min': -50, 'max': 50, 'default': 0},
}
```

### 7.2 与 recommender 的契约

**推荐模块需要从引擎获取的数据**:

```python
# 推荐引擎的标准调用流程
from engine import CPEngine, StockCP, KellyCalculator

# 1. 创建并计算引擎
engine = CPEngine()
for stock in raw_stocks:
    engine.add_stock(stock)
results = engine.calculate_all()

# 2. 获取战力榜单
top_stocks = engine.get_top(50, board='main')

# 3. 获取单股详情（含涨跌停状态）
stock = engine.get_by_code('000001')
is_limit_up = stock.is_limit_up    # 是否涨停
is_limit_down = stock.is_limit_down  # 是否跌停
price_limit_pct = stock.price_limit_pct  # 涨跌停限制（10%/20%）

# 4. Kelly仓位计算
kelly = KellyCalculator.calculate_kelly_fraction(win_rate=0.55, win_loss_ratio=1.5)
safe_position = KellyCalculator.get_safe_position_pct(kelly, mode='balanced')
```

**引擎保证输出给recommender的字段**:

```python
StockCP 关键属性（recommender层需要）:
├── total_cp           # 总战力（排序依据）
├── growth_score       # 成长分
├── value_score        # 价值分
├── quality_score      # 质量分
├── momentum_score     # 动量分
├── risk_score         # 风险分
├── sector             # 所属行业（用于行业分散度分析）
├── is_limit_up        # 是否涨停（recommender需过滤）
├── is_limit_down      # 是否跌停（recommender需过滤）
├── price_limit_pct   # 涨跌停限制（10%/20%/30%）
├── can_trade_newbie   # 新手可交易
├── data_quality       # 数据质量（低质量降权）
├── is_st              # 是否ST股
├── is_suspended        # 是否停牌（v18.4新增）
├── avg_daily_amount_20d  # 20日均成交额（v18.4新增）
├── turnover_rate      # 换手率（v18.4新增）
└── volatility_20d     # 20日波动率（v18.4新增）
```

#### 7.2.1 三大场景支持

引擎为推荐引擎的三大操作场景提供支撑：

**换股场景**：
```python
# 引擎提供：战力计算、风险评估、交易成本计算
stock_a = engine.get_by_code('000001')
stock_b = engine.get_by_code('600036')
cp_diff = stock_b.total_cp - stock_a.total_cp
```

**纯买入场景**：
```python
# 引擎提供：Kelly仓位、技术指标信号
kelly = KellyCalculator.calculate_kelly_fraction(win_rate, win_loss_ratio)
indicators = TechnicalIndicators.get_technical_signal(prices)
```

**纯卖出场景**：
```python
# 引擎提供：大盘模式判断、风险评估
mode = RiskAnalyzer.get_market_mode(market_cp, market_change_pct)
risk_report = RiskAnalyzer.generate_risk_report(...)
```

### 7.3 与 simulator 的契约

**RiskAnalyzer 依赖的持仓数据格式**:
```python
# simulator 应提供的数据格式
holding = {
    'code': str,           # 股票代码
    'name': str,           # 股票名称
    'quantity': int,       # 持股数量
    'cost_price': float,   # 成本价
    'cost_total': float,   # 总成本
    'current_price': float,  # 当前价
    'value_total': float,   # 当前市值
    'profit': float,       # 盈亏金额
    'profit_pct': float,   # 盈亏比例
    'cp': float,           # 战力值
    'sector': str,         # 所属行业
}
```

### 7.4 与 database 的契约

**check_trade_cooldown 需要的表结构**:
```sql
CREATE TABLE trade_records (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    name TEXT,
    action TEXT NOT NULL,      -- 'buy' / 'sell'
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    amount REAL NOT NULL,
    commission REAL,
    trade_date TEXT NOT NULL,
    batch_id TEXT NOT NULL,    -- 用于T+1追踪
    created_at TEXT
);

CREATE INDEX idx_trade_code ON trade_records(code);
CREATE INDEX idx_trade_batch ON trade_records(batch_id);
```

### 7.5 状态管理策略

| 设计选择 | 适用场景 | 实现方式 |
|---------|---------|---------|
| 无状态 | 简单请求/响应 | 每次新建实例 |
| 单例模式 | 共享配置/缓存 | `get_engine()` 单例 |
| 依赖注入 | 可测试/可替换 | 通过构造函数传入 |

**推荐**: 无状态设计 + `get_engine()` 工厂函数

```python
# 推荐用法
def get_engine() -> CPEngine:
    """获取引擎实例（无状态，每次调用新建）"""
    return CPEngine()

# 或带缓存的单例
_engine_instance = None
def get_engine_cached() -> CPEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = CPEngine()
    return _engine_instance
```

---

## 八、便捷函数

```python
from engine import CPEngine, StockCP, CashCP, TradeDecision, RiskAnalyzer
from engine import create_stock_from_raw, WEIGHTS, TRADE_COST

# 创建股票战力对象
stock = create_stock_from_raw(
    code='000001', name='平安银行', price=12.5,
    pe=8.5, roe=12.3, net_profit_growth=15.2,
    revenue_growth=8.5, change_pct=1.2,
    sector='银行'
)

# 计算战力
engine = CPEngine()
engine.add_stock(stock)
results = engine.calculate_all()

# 获取TOP10
top10 = engine.get_top(10, board='main')

# 现金战力判断
should_hold = CashCP.should_hold_cash(45, -3.5)

# 换股决策
decision = TradeDecision.should_swap(60, 75, 100000, 30)

# 风险评估
risk_report = RiskAnalyzer.generate_risk_report(db, holdings, all_stocks, market_cp, capital)
```

---

## 九、专家评审反馈与增强建议

> 本节对照5份专家评审报告，整理核心问题与改进建议。
>
> **专家评审来源**: `docs/reviews/专家评审/1.md` ~ `5.md`

---

### 9.1 P0 必须修复（影响正确性）✅ 已完成

#### 9.1.1 归一化分数漂移问题 ✅ 已修复 (v18.2)

**问题**: 动态 `min/max` 归一化导致基本面没变但战力暴跌。

**已实现方案 - 百分位数截断**:
```python
@staticmethod
def _robust_normalize(values: List[float], clip_percentile: float = 0.95) -> List[float]:
    """
    稳健归一化 - 使用百分位裁剪避免极值干扰

    1. 用指定百分位（如95%）计算裁剪边界
    2. 超出边界的值被裁剪到边界值
    3. 在裁剪后的范围内进行min-max归一化
    """
    arr = np.array(values, dtype=float)
    lower = np.percentile(arr, (1 - clip_percentile) * 50)
    upper = np.percentile(arr, clip_percentile * 50)
    clipped = np.clip(arr, lower, upper)
    if upper == lower:
        return [50.0] * len(values)
    normalized = ((clipped - lower) / (upper - lower)) * 100
    return normalized.tolist()
```

#### 9.1.2 ST/*ST股未过滤 ✅ 已修复 (v18.2)

**问题**: ST股会污染归一化基准，且推荐ST股会造成实际亏损。

**已实现方案**:
```python
class DataValidator:
    ST_PREFIXES = ('ST', '*ST', 'SST', 'S*ST', 'S', 'SS', 'SSD', 'SSR')

    @classmethod
    def is_st_stock(cls, name: str) -> bool:
        if not name:
            return False
        name_upper = name.upper().strip()
        return name_upper.startswith(cls.ST_PREFIXES)
            )
```

#### 9.1.3 JSON存储风险 ✅ 已修复 (v18.2)

**问题**: `cp_history.json` 并发写入可能损坏，30天数据全丢。

**已实现方案**: 迁移到 SQLite（WAL模式，支持并发写入）

```python
# history.py v18.2
def _get_db() -> Optional[Database]:
    """获取数据库实例"""
    from core.database import Database
    return Database()

def save_history(stocks: List[Dict], date: str = None) -> bool:
    """优先使用SQLite存储，降级到JSON"""
    db = _get_db()
    if db is not None:
        db.record_cp_history(stocks, date)
        return True
    return _save_history_json(stocks, date)
```

**SQLite表结构**（已有索引优化）:
```sql
CREATE TABLE cp_history (
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    total_cp REAL DEFAULT 0,
    growth_score REAL DEFAULT 0,
    ...
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (code, recorded_at)
);
CREATE INDEX idx_cp_history_date ON cp_history(recorded_at);
CREATE INDEX idx_cp_history_code ON cp_history(code);
```

#### 9.1.4 幸存者偏差 ⚠️ 3/5专家提及

**问题**: 回测池只包含当前存活股票，会高估策略收益。

**修复方案**: 回测数据源需包含已退市股票，可从 akshare 历史日线获取。

---

### 9.2 P1 强烈建议（提升专业度）

#### 9.2.1 动量分权重过高 ⚠️ 4/5专家提及

**问题**: 当日涨跌幅归一化后，涨停股永远得100分，跌停股永远得0分。

**修复方案**:
1. 降低动量分权重到 5-8%
2. 或改为**多日动量**（5日/20日）替代当日涨跌幅
3. 增加波动率惩罚

```python
# 建议：将动量分改为多日动量组合
momentum_score = (
    history.calc_momentum_5d(code) * 0.6 +
    change_pct * 0.4
)
```

#### 9.2.2 交易成本精度不足 ✅ 已修复 (v18.2)

**问题**: 缺少最低佣金5元、沪/深过户费差异。

**已实现方案**:
```python
def calculate_trade_cost(cls, principal: float, board_from: str = 'main', board_to: str = 'main') -> dict:
    """计算完整换股的总成本 v18.2

    - 过户费仅沪市收取（双向）
    - 印花税仅卖出时收取
    - 佣金最低5元/笔
    """
    # 券商佣金（双向）
    sell_commission = max(principal * TRADE_COST['commission'], TRADE_COST['min_commission'])
    buy_commission = max(principal * TRADE_COST['commission'], TRADE_COST['min_commission'])

    # 印花税（仅卖出）
    sell_stamp = principal * TRADE_COST['stamp_tax']

    # 过户费（仅沪市双向）
    is_shanghai_from = board_from in ('main', 'star')
    is_shanghai_to = board_to in ('main', 'star')
    sell_transfer = principal * TRADE_COST['transfer_fee'] if is_shanghai_from else 0
    buy_transfer = principal * TRADE_COST['transfer_fee'] if is_shanghai_to else 0
    ...
```

**Recommender层需实现（含滑点成本）**:
```python
# recommender层负责的滑点模型
def calculate_trade_cost_with_slippage(price, quantity, side):
    """滑点模型（简化版）
    - 小单（<10万）：0.02% 滑点
    - 中单（10-50万）：0.05% 滑点 + 冲击成本
    - 大单（>50万）：0.10% 滑点 + 显著冲击成本
    """
    slippage = estimate_slippage(price, quantity)
    impact = estimate_market_impact(quantity) if needs_impact else 0
    return base_cost + slippage + impact
```

#### 9.2.3 风险分数线性叠加问题 ✅ 已修复 (v18.2)

**问题**: 多项风险累加可能溢出100，且PE<0和ROE<0高度相关重复惩罚。

**已实现方案**:
```python
def calculate_risk(self):
    # 风险因子及权重
    risk_factors = []
    risk_factors.append(('pe', pe_risk, 0.35))
    risk_factors.append(('roe', roe_risk, 0.25))
    risk_factors.append(('growth', growth_risk, 0.20))
    risk_factors.append(('revenue', rev_risk, 0.10))
    risk_factors.append(('volatility', vol_risk, 0.10))

    # 最终风险 = 0.4 * 最大风险 + 0.6 * 加权平均
    self.risk_score = min(100, 0.4 * max_risk + 0.6 * weighted_sum)
```

#### 9.2.4 动量分权重过高 ✅ 已修复 (v18.2)

**问题**: 当日涨跌幅归一化后，涨停股永远得100分，跌停股永远得0分。

**已实现方案**:
1. 动量权重从 15% 降到 10%
2. 新增 `apply_multi_day_momentum()` 方法，组合多日动量（60%）+ 当日动量（40%）
3. **波动率调整动量分**：高波动日子的涨跌幅信号可靠性下降，适当降低权重

```python
# 波动率调整逻辑 v18.2
if daily_range > 8%:   volatility_factor = 0.3  # 极端波动
elif daily_range > 5%: volatility_factor = 0.5  # 高波动
elif daily_range > 3%: volatility_factor = 0.7  # 正常偏高
elif daily_range < 1%: volatility_factor = 1.2  # 低波动（信号更可靠）
```

**效果示例**:
| 股票 | 涨跌幅 | 波动率 | 调整后动量 |
|------|--------|--------|-----------|
| 低波动上涨 | +2% | 0.8% | 100 (增强) |
| 高波动上涨 | +2% | 5.0% | 70 (折扣) |
| 低波动下跌 | -2% | 0.8% | 0 (正确反映) |

#### 9.2.5 行业相对PE风险评估 ✅ 已修复 (v18.2)

**问题**: PE风险不考虑行业差异，银行PE=8可能高估，AI股PE=100可能低估。

**已实现方案**:
```python
def _calculate_industry_pe_averages(self) -> Dict[str, float]:
    """从当前股票池计算各行业的PE中位数"""
    # 需至少3只股票才计算行业中位数

def _apply_industry_pe_adjustment(self):
    """根据PE与行业中位数的比率调整风险"""
    pe_ratio = stock.pe / industry_median_pe
    if pe_ratio > 2.5: adjustment = +25  # 显著高于行业
    elif pe_ratio < 0.5: adjustment = -10  # 价值洼地
```

#### 9.2.6 财报日历不完整 ⚠️ 1/5专家提及
```python
EARNINGS_CALENDAR = {
    'annual_report': [3, 4],    # 年报（与一季报重叠）
    'q1_report': [4],          # 一季报
    'half_year_report': [8],   # 半年报
    'q3_report': [10],         # 三季报
}
```

---

### 9.3 技术指标层（待增强）

| 专家建议 | 我们的现状 | 优先级 |
|---------|-----------|--------|
| TA-Lib (150+技术指标) | ❌ 未使用 | 高 |
| MA/EMA 均线系统 | ❌ 未实现 | 高 |
| MACD/KDJ/RSI 震荡指标 | ❌ 未实现 | 中 |
| BOLL 布林带 | ❌ 未实现 | 中 |

**双轨制架构建议**（专家1提出）:
```
┌─────────────────────────────────────┐
│           ScoreBlender (融合层)      │
│    基本面战力(80%) + 技术面(20%)     │
└────────────────┬────────────────────┘
                 │
    ┌────────────┴────────────┐
    ▼                         ▼
┌─────────┐            ┌─────────────┐
│ CPEngine │            │ TechEngine  │
│(基本面)  │            │ (技术指标)   │
└─────────┘            └─────────────┘
```

---

### 9.4 回测引擎（待完善）

| 专家建议 | 我们的现状 | 优先级 |
|---------|-----------|--------|
| 事件驱动回测 | ⚠️ 在backtester模块但未完善 | 高 |
| 向量化回测 (VectorBT) | ❌ 未实现 | 中 |
| 幸存者偏差防范 | ❌ 未实现 | 高 |

**统一过滤接口建议**（专家3提出）:
```python
class StockFilter:
    @staticmethod
    def apply(stock, context, mode='realtime'):
        """统一过滤逻辑，回测和实盘共用"""
        if mode == 'backtest':
            historical_status = context.get_historical_status(stock.code, context.date)
            if historical_status == 'delisted':
                return FilterResult(excluded=True, reason='已退市')
        # ...
```

---

### 9.5 风险控制 ✅ 部分完成 (v18.2)

| 专家建议 | 我们的现状 | 优先级 |
|---------|-----------|--------|
| ST股/*ST股过滤 | ✅ DataValidator拦截 | 高 |
| 涨跌停检测 | ✅ StockCP.is_limit_up/is_limit_down | 中 |
| 凯利公式仓位管理 | ✅ KellyCalculator实现 | 中 |
| 流动性检查 (日均成交额) | ⚠️ 标记在risk_report中，未强制过滤 | 中 |

**Engine层已提供（recommender层需使用）**:
```python
# engine层提供的基础能力
stock.is_limit_up    # 是否涨停
stock.is_limit_down  # 是否跌停
stock.price_limit_pct  # 涨跌停限制（10%/20%/30%）
```

**Recommender层需实现**:
```python
# recommender层负责过滤
def filter_limit_up_down(stocks):
    """涨停不买，跌停不卖"""
    return [s for s in stocks if not (s.is_limit_up or s.is_limit_down)]
```

**已实现方案**:
```python
# 涨跌停检测 v18.2
@property
def price_limit_pct(self) -> float:
    limits = {'main': 10.0, 'gem': 20.0, 'star': 20.0, 'bge': 30.0}
    return limits.get(self.board_type, 10.0)

@property
def is_limit_up(self) -> bool:
    return abs(self.change_pct - self.price_limit_pct) < 0.5

@property
def is_limit_down(self) -> bool:
    return abs(self.change_pct + self.price_limit_pct) < 0.5
```

---

### 9.6 性能优化（待关注）

| 专家建议 | 我们的现状 | 优先级 |
|---------|-----------|--------|
| 向量化计算 (避免循环) | ⚠️ 部分使用 Pandas | 中 |
| Numba JIT 加速 | ❌ 未使用 | 中 |
| 多进程并行 (全市场扫描) | ❌ 未实现 | 低 |
| Redis 缓存 | ⚠️ 仅用内存+JSON | 低 |

---

### 9.7 实施建议

**当前定位**: 个人工具，非专业量化平台

**推荐优先级**:
1. **P0 必须**: 归一化稳定性、ST股过滤、JSON→DuckDB迁移
2. **P1 强烈建议**: 动量分改进、交易成本精度、风险分数优化
3. **P2 可选增强**: 技术指标引入、凯利公式仓位管理

**阶段规划**:
```
v18.2 (本周) ✅ 已完成
├── ✅ P0: 稳健归一化函数（防分数漂移，百分位裁剪+IQR小数据集）
├── ✅ P0: ST/*ST股过滤（DataValidator拦截）
├── ✅ P0: JSON → SQLite迁移（历史数据，支持WAL并发）
├── ✅ P1: 动量分改进（权重15%→10%，波动率调整）
├── ✅ P1: 交易成本精度（沪/深过户费区分，最低佣金）
├── ✅ P1: 风险分数优化（加权评估替代线性叠加）
└── ✅ P1: 行业相对PE风险评估

v18.2 (本周)
├── ✅ P2: Kelly公式仓位管理
├── ✅ P2: 技术指标集成（MA/MACD/RSI，基于pandas实现）
├── ✅ P2: 因子级缓存（LRU + TTL淘汰策略）
└── ✅ P2: 并行计算优化（多进程批量处理）

v19.0 ⏳ (待规划)
└── 新功能开发，待需求明确后规划

v20+ ⏳ (远期规划)
└── 因子增强方向：技术指标因子(MA/MACD/RSI)、资金流因子、情绪因子等
    详见「6.3 未来扩展方向」
```

---

### 9.8 专家评审总结

| 评分项 | 评分 | 说明 |
|--------|------|------|
| 架构设计 | ⭐⭐⭐⭐⭐ | 模块化清晰，契约明确 |
| 投资逻辑 | ⭐⭐⭐⭐⭐ | 战力体系原创，五维模型合理 |
| 数值稳定性 | ⭐⭐⭐⭐⭐ | 归一化有分数漂移风险 ✅ 已修复 |
| 回测质量 | ⭐⭐⭐ | 幸存者偏差未处理 |
| 风险控制 | ⭐⭐⭐⭐ | 基础风险有，动态风控改善 ✅ |

**综合评级**: A（优秀，v18.2已修复P0和P1核心问题）

---

### 9.9 大盘危机应对机制（新增）

**背景**: 当大盘所有股票都在跌时（如2024年春节期间的市场暴跌），需要有明确的机制判断是否应该全部换成现金。

**设计原则**:
- **仅提示，不自动执行**: 用户决策权在自己手中
- **简单平均**: 市场CP取所有股票CP的简单平均（等权重）

**市场模式判断**:

| 模式 | 触发条件 | 建议现金比例 | 说明 |
|------|---------|-------------|------|
| `crisis` | 市场CP < 35 **或** 跌幅 < -3% | 100% | 大盘暴跌，清仓观望 |
| `defensive` | 市场CP < 45 **或** 跌幅 < -1.5% | 70% | 市场低迷，谨慎操作 |
| `normal` | 其他情况 | 0% | 正常置换 |

**接口示例**:
```python
from engine import RiskAnalyzer

# 获取市场模式
mode = RiskAnalyzer.get_market_mode(market_cp=38, market_change_pct=-2.5)
# -> 'defensive'

# 获取仓位建议
recommendation = RiskAnalyzer.get_cash_recommendation(mode)
# -> {'cash_ratio': 0.7, 'action': '建议高比例现金', 'reason': '...'}

# 获取警告信息
warning = RiskAnalyzer.get_market_warning(mode)
# -> "⚡ 防御模式：市场偏弱，建议保持高比例现金"
```

**在风险报告中的体现**:
```python
def generate_risk_report(...):
    # ... 其他评估 ...

    # 新增：市场模式判断
    mode = RiskAnalyzer.get_market_mode(market_cp, market_change_pct)
    recommendation = RiskAnalyzer.get_cash_recommendation(mode)

    report['market_mode'] = {
        'mode': mode,
        'warning': RiskAnalyzer.get_market_warning(mode),
        'cash_recommendation': recommendation
    }

    if mode == 'crisis':
        report['warnings'].append('市场处于危机模式，建议清仓')
    elif mode == 'defensive':
        report['suggestions'].append('市场偏弱，建议保持高比例现金')

    return report
```

---

## 十、版本历史

| 版本 | 日期 | 更新 |
|---|---|---|
| v19.7 | 2026-04-08 | ✅ cp_history迁移到data_manager统一管理（SQLite WAL模式） |
| v19.6 | 2026-04-08 | 新增real_time_score实时因子（权重2%），基于1分钟K线计算MA5/MA15变化+成交量异动，仅核心池计算 |
| v18.5 | 2026-04-07 | ⚠️ 新增与stock_selector联动：基于池分层(core/active/observe)确定分析范围，只对核心池+活跃池计算战力 |
| v18.4 | 2026-04-07 | 同步recommender三大场景支持：新增is_suspended/avg_daily_amount_20d/turnover_rate/volatility_20d字段，完善与BuyAnalyzer/SellAnalyzer/换股场景的接口对接 |
| v18.3 | 2026-04-07 | 新增与recommender模块接口契约（StockCP关键属性说明）、recommender相关评审项（涨跌停过滤、滑点成本、财报季风险） |
| v18.2 | 2026-04-07 | P0+P1全部完成，P2全部完成：稳健归一化（含小数据集IQR）、ST过滤、JSON→SQLite、沪/深过户费区分、风险分数优化、动量分改进（波动率调整+多日动量集成）、sector字段对接、行业相对PE风险评估、涨跌停检测、**Kelly公式仓位管理**、**技术指标集成（MA/MACD/RSI）**、**因子级缓存（LRU+TTL）**、**并行计算优化（多进程批量处理）** |
| v18.1.8 | 2026-04-06 | 完善与数据管理模块的接口契约，明确标准调用流程 |
| v18.1.7 | 2026-04-06 | 新增大盘危机应对机制（MarketMode市场模式判断） |
| v18.1.6 | 2026-04-06 | 新增专家评审反馈章节，整理P0/P1优先级问题 |
| v18.1.6 | 2026-04-06 | 完善模块架构文档，新增数据接口、因子扩展、接口契约 |
| v15 | 2026-04-05 | 换股决策引擎重构 |
| v14 | 2026-04-05 | 战力公式权重调整 |

**v19.0+**: 待规划，功能需求明确后补充 |

---

## 十一、相关文档

- [项目概览](./PROJECT_OVERVIEW.md) - 项目整体介绍
- [数据管理模块方案](./DATA_MANAGER_ARCHITECTURE.md) - 数据获取模块
- [智能推荐模块方案](./RECOMMENDER_ARCHITECTURE.md) - 推荐引擎模块
- [专家评审](../reviews/专家评审/) - 评审文档参考
