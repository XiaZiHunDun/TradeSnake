# 股票筛选模块架构方案 v19.5.5

> 本文档描述 `stock_selector/` 模块的设计方案

---

## 输入输出

### 输入
| 来源 | 数据内容 |
|------|----------|
| data_manager | 股票列表、行情数据、财务数据、指数成分（列表可含全市场；**与本模块主流程一致的批量行情与池化范围见下「产品范围」**） |
| 手动配置 | 白名单/黑名单用户自定义配置 |

**产品范围（与 `PROJECT_OVERVIEW` 一致）**：本模块与战力主算路径配套的 **池分层、流动性排名、批量行情抽样** 以 **沪深主板** 为边界（不含创业板 300、科创板 688、北交所），与 `StockDataFetcher.get_batch_market_data` 一致。指数成分标志仍可用于规则；**不表示**对非主板标的按主板同等能力做批量行情与入池承诺。

### 输出
| 输出内容 | 使用者 |
|----------|--------|
| 股票池分层 (core/active/observe/temp) | engine/recommender/data_manager（各自制定频率策略） |
| 池状态变化通知 | engine/recommender（刷新缓存） |
>
> **版本历史**：
> - v19.5.6: **实现核查**：stock_selector 模块实现与方案一致，无重大问题；确认 market_snapshot、update_strategy、回调机制等均已正确实现
> - v19.5.5: **产品范围显式化**：方案写明仅沪深主板；澄清 data_manager「全量列表」与池/批量行情边界的关系
> - v19.5.4: **与实现对齐**：`market_snapshot` 构建 `market_data`；`initialize` 前注册调度回调；`refresh_pools` 盘后任务触发；池变更 `_emit_pool_tier_changed`；`get_stock_info` 查询接口
> - v19.5.3: 新增数据更新频率策略联动（双向数据流）+ RecommenderCallback 集成
> - v19.5.2: 专家评审完善：准入门槛递进、挤出机制、冲突处理、TTL清理、动态容量
> - v19.5.1: 补充白名单/黑名单、财务预警、历史保留、指数同步兜底
> - v19.5: 初始版本

### 实现同步说明（v19.5.5，2026-04-16）

以下条目描述 **当前仓库行为**，与上文部分伪代码/理想接口可能略有出入时，以本节为准。

| 项 | 实现要点 |
|----|----------|
| **`market_snapshot.py`** | 将 `StockDataFetcher.get_batch_market_data` 等返回的行情行转为 `market_data[code]`（`daily_volume_20d` 万元、`volume_rank`、指数成分标记等）。近 20 日日均成交额优先用 DuckDB `get_avg_daily_amount_20d_bulk`；无 K 线时用当日 `amount` 近似。 |
| **启动时 `financial_data`** | 方案描述"由 data_manager 提供财务数据"；实际启动时传入空 `{}`（`api/main.py` 第561行）。财务数据在 `refresh_pools` 时补充，或由战力计算阶段按需获取。 |
| **启动顺序**（`backend/api/main.py`） | 构建 `market_data` → 注册 `UpdateScheduler` + `StockSelectorCallback`（实现完整 `SelectorCallback`）→ `StockSelector.initialize(...)`，保证 **入池时的 `on_pool_changed` 能到达调度器**。 |
| **`refresh_pools` 触发** | 除业务代码手动调用外，由 **`pool_rebalance_background_task`** 在交易日收盘（`get_trading_status` 为已收盘）后尝试执行，每日最多一次。 |
| **池变更通知** | `initialize` 完成后对各池发送一次 `on_pool_changed(tier, added,[])`；`refresh_pools` 在再平衡后按 tier 计算 `added`/`removed` 并通知；财务预警降级时对旧池/新池分别通知，并调用 `on_stock_downgraded`。 |
| **`get_stock_info(code)`** | `StockSelector` 对外查询当前池中 `StockInfo`（供再平衡任务等组装指数标记）。 |
| **脚本中的「核心池」** | 部分脚本使用 `total_cp > 0` 筛选股票（**不等于** `PoolTier.CORE`），以各脚本 docstring 为准。 |
| **产品范围：仅主板** | 与 `docs/plans/PROJECT_OVERVIEW.md`「产品范围」一节一致；批量 `market_data` 构建依赖主板抽样，非文档笔误。 |

---

## 一、模块定位

### 1.1 职责边界

```
                          ┌─────────────────────────────────────┐
                          │         双向数据流优化               │
data_manager ───────────▶ │ ◀────── 池状态通知 ──────▶          │
  (数据获取)              │       更新频率策略                  │
      ▲                  │                                   │
      │                  │  stock_selector ──────────▶ engine │
      │ 池状态决定         │    (池管理)              (战力分析) │
      │ 更新频率           │           │                      │
      └────────────────── │           ▼                      │
                         │     recommender                     │
                         │      (智能推荐)                     │
                         └─────────────────────────────────────┘
```

**核心职责**：
- 维护股票池的分层结构（核心池、活跃池、观察池、临时池）
- 执行硬性排除和准入过滤
- 管理动态晋级/降级（含冲突处理、挤出机制）
- 处理事件触发（含去重、冷却）
- **⚠️ 新增**：向 data_manager 提供数据更新频率策略

**非职责**：
- 不负责战力计算（由 engine 提供）
- 不负责推荐逻辑（由 recommender 提供）
- **重要**：`stock_selector` 只读数据、不写数据，通过回调通知其他模块

### 1.2 模块价值

| 价值点 | 说明 |
|-------|------|
| **隔离关注点** | 筛选逻辑独立于数据获取和分析计算 |
| **复用性** | 被战力榜、推荐、回测等多个模块调用 |
| **可维护性** | 筛选规则调整不影响数据源和分析引擎 |
| **扩展性** | 便于新增筛选维度或调整分层策略 |

---

## 二、数据流设计

### 2.1 整体数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                         数据输入                                  │
│  data_manager: 全量股票列表、行情数据、财务数据、指数成分         │
│  手动白名单/黑名单: 用户自定义配置                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      第一层：硬性排除                             │
│  ST/退市/次新股(板块差异化)/僵尸股/停牌 + 黑名单                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      第二层：质量准入（底线）                     │
│  市值≥5亿 + 成交额≥1000万 + 财务健康(2/3)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      第三层：分层分类（递进）                     │
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │  核心池   │    │  活跃池   │    │  观察池   │    │  临时池   │  │
│   │ 动态~300 │    │ 动态~500 │    │ 动态~1000│    │  事件驱动  │  │
│   │ ≥5000万  │    │ ≥2000万  │    │ ≥1000万  │    │  TTL:7日  │  │
│   └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      输出：股票池                                │
│  engine: 核心池+活跃池 → 战力计算                               │
│  recommender: 全部池 → 推荐备选                                 │
│  战力榜: 核心池 → 主榜展示                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 盘后批处理流程 vs 盘中实时流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                    盘后批处理（T日收盘后）                          │
├─────────────────────────────────────────────────────────────────────┤
│  1. 数据更新      │ data_manager 提供最新行情+财务数据             │
│  2. ST扫描        │ ⚠️ 早盘竞价前（9:15）已执行过一次，此处复核    │
│  3. 指数同步      │ 调整日前后3天每日全量校验，平时增量             │
│  4. 池再平衡      │ 晋级/降级/挤出（见3.4节）                     │
│  5. 财务预警      │ 仅在财报发布窗口期执行（4/8/10月）             │
│  6. 临时池清理    │ 超期(7日)或已处理则回归原池                    │
│  7. 输出股票池    │ → engine / recommender / 战力榜                │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    盘中实时处理（事件触发）                          │
├─────────────────────────────────────────────────────────────────────┤
│  EventTrigger  ──▶  to_temp()  ──▶  临时池                        │
│        │                                                             │
│        └── 去重窗口期：同一事件24小时内不重复触发                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 ⚠️ 数据更新策略联动（双向数据流）

**核心思想**：股票池状态应反过来指导 data_manager 的数据更新频率策略，实现"按需更新"。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      数据更新频率策略                                    │
│                                                                      │
│  stock_selector              data_manager                              │
│       │                         │                                      │
│       │  维护池状态             │  根据池状态决定更新频率                 │
│       │  (core/active/observe) │                                      │
│       │                         │                                      │
│       │  ┌─────────────────┐   │   ┌─────────────────────────────┐   │
│       └─▶│ 通知更新频率策略  │──▶│   │  核心池 (~300只)            │   │
│           └─────────────────┘   │   │  高频更新：5-15分钟         │   │
│                                 │   ├─────────────────────────────┤   │
│                                 │   │  活跃池 (~500只)            │   │
│                                 │   │  中频更新：30-60分钟        │   │
│                                 │   ├─────────────────────────────┤   │
│                                 │   │  观察池 (~1000只)           │   │
│                                 │   │  低频更新：每日/每周        │   │
│                                 │   └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 更新频率配置

| 池 | 数量 | 盘中更新频率 | 盘后更新频率 | 说明 |
|----|------|--------------|-------------|------|
| **核心池** | ~300只 | **5-15分钟** | 收盘后全量 | 战力榜主力，需实时监控；**计算real_time_score（1分钟K线）** |
| **活跃池** | ~500只 | **30-60分钟** | 收盘后全量 | 推荐备选，中等关注 |
| **观察池** | ~1000只 | **每日/每周** | 收盘后全量 | 潜力观察，低频扫描 |
| **全市场** | 5000+ | **按需** | 按需 | 仅入池时获取基础数据 |

#### 实现接口

```python
class UpdateStrategyProvider:
    """⚠️ 数据更新频率策略提供者

    stock_selector 维护并提供各池的更新频率策略
    data_manager 订阅此策略来决定更新调度
    """

    def get_update_interval(self, tier: PoolTier, market_status: str) -> int:
        """获取指定池的更新间隔（秒）

        Args:
            tier: 股票池层级
            market_status: 市场状态 ('trading'/'closed'/'pre_market')
        """
        intervals = {
            PoolTier.CORE: {
                "trading": 5 * 60,      # 5分钟
                "pre_market": 15 * 60,  # 15分钟
                "closed": 0,             # 收盘后由批处理
            },
            PoolTier.ACTIVE: {
                "trading": 30 * 60,      # 30分钟
                "pre_market": 60 * 60,  # 60分钟
                "closed": 0,
            },
            PoolTier.OBSERVE: {
                "trading": 0,             # 盘中不更新
                "pre_market": 0,
                "closed": 0,             # 收盘后日频
            },
        }
        return intervals[tier][market_status]

    def get_batch_priority(self) -> List[str]:
        """获取批量更新优先级顺序

        用于 data_manager 决定先更新哪些池
        """
        return (
            self.pool_manager.get_pool(PoolTier.CORE) +
            self.pool_manager.get_pool(PoolTier.ACTIVE) +
            self.pool_manager.get_pool(PoolTier.OBSERVE)
        )

    def get_codes_for_update(self, tier: PoolTier) -> List[str]:
        """获取指定池的所有股票代码"""
        return self.pool_manager.get_pool(tier)
```

#### 盘中更新策略示例

```python
class DataManager:
    """data_manager 中的更新调度"""

    def __init__(self, update_strategy: UpdateStrategyProvider):
        self.update_strategy = update_strategy

    def trading_day_update(self):
        """盘中更新调度"""
        # 按优先级顺序更新
        for code in self.update_strategy.get_batch_priority():
            tier = self.update_strategy.get_stock_tier(code)
            interval = self.update_strategy.get_update_interval(
                tier, "trading"
            )

            # 检查是否需要更新
            if self.should_update(code, interval):
                self.update_single_stock(code)

            # 避免请求过快
            time.sleep(0.1)

    def should_update(self, code: str, interval: int) -> bool:
        """判断是否需要更新（基于上次更新时间）"""
        if interval == 0:  # 不需要盘中更新
            return False
        last = self.last_update_time.get(code, 0)
        return (time.time() - last) >= interval
```

#### 通知机制

```python
class StockSelector:
    """stock_selector 中的通知"""

    def notify_pool_change(self, tier: PoolTier, action: str):
        """池变化时通知 data_manager 调整更新策略"""
        for callback in self.callbacks:
            if hasattr(callback, 'on_pool_update_strategy_changed'):
                callback.on_pool_update_strategy_changed(
                    tier=tier,
                    action=action,
                    new_codes=self.pool_manager.get_pool(tier)
                )
```

---

## 三、核心组件

### 3.1 组件概览

```
stock_selector/
├── __init__.py              # 模块导出
├── config.py                # 筛选配置（含动态调整+更新频率）
├── stock_selector.py        # 主筛选器 (Facade)
├── pool_manager.py          # 股票池管理器
├── update_strategy.py       # ⚠️ 数据更新频率策略 🆕
├── filters/
│   ├── __init__.py
│   ├── blacklist.py         # 黑名单过滤
│   ├── manual_list.py       # 手动白名单/黑名单
│   └── admission.py         # 准入条件（递进式）
├── rebalancer.py            # 动态再平衡（含挤出机制）
├── event_trigger.py         # 事件触发器（含去重）
├── index_sync.py            # 指数成分同步
├── financial_watcher.py     # 财务预警（含缓释/恢复）
├── history_keeper.py        # 历史数据保留
└── utils/
    ├── __init__.py
    ├── code_normalizer.py   # 股票代码标准化
    ├── rebalance_date.py    # 指数调整日计算
    └── pool_metrics.py      # 监控指标
```

### 3.2 核心类设计

#### PoolManager

```python
class PoolManager:
    """股票池管理器 - 核心组件"""

    def __init__(self):
        self.core_stocks: Dict[str, StockInfo] = {}      # 核心池
        self.active_stocks: Dict[str, StockInfo] = {}    # 活跃池
        self.observe_stocks: Dict[str, StockInfo] = {}  # 观察池
        self.temp_stocks: Dict[str, TempStockInfo] = {}  # 临时池

    # ─────────────────────────────────────────────
    # 基础操作
    # ─────────────────────────────────────────────

    def get_pool(self, tier: PoolTier) -> List[str]:
        """获取指定层的股票代码列表"""

    def add_stock(self, code: str, tier: PoolTier, reason: str = ""):
        """添加股票到指定池（会检查容量）"""

    def remove_stock(self, code: str, reason: str = ""):
        """从所有池中移除股票"""

    def get_stock_tier(self, code: str) -> Optional[PoolTier]:
        """获取股票所在层"""

    # ─────────────────────────────────────────────
    # 晋级/降级（含冲突处理）
    # ─────────────────────────────────────────────

    def upgrade(self, code: str, reason: str):
        """晋级：观察池 → 活跃池 → 核心池

        ⚠️ 冲突处理原则：
        1. 降级优先于晋级（ST等风险事件先处理）
        2. 容量满时执行末位淘汰
        """

    def downgrade(self, code: str, reason: str):
        """降级：核心池 → 活跃池 → 观察池"""

    def evict_worst(self, tier: PoolTier, reason: str) -> Optional[str]:
        """⚠️ 末位淘汰：找出指定池中战力/成交额最低的股票降级"""

    # ─────────────────────────────────────────────
    # 临时池
    # ─────────────────────────────────────────────

    def to_temp(self, code: str, event_type: str, reason: str):
        """临时池：记录触发事件（含去重检查）"""

    def process_temp(self, code: str, result: str):
        """处理临时池结果并回归原池

        result: 'hold' → 回原池
                'not_hold' → 降一级
                'timeout' → 回观察池
        """

    def cleanup_expired_temp(self):
        """⚠️ 清理超期临时池（TTL机制）"""
```

#### Rebalancer

```python
class Rebalancer:
    """动态再平衡器（含挤出机制）"""

    def should_upgrade(self, code: str) -> Tuple[bool, str]:
        """检查是否应晋级

        晋级条件：
        - 连续5日成交额超过目标池平均水平
        - 近30日涨幅持续超过观察池平均
        - 被纳入沪深300/中证500
        - ⚠️ 需在观察期（10日）内表现稳定
        """

    def should_downgrade(self, code: str) -> Tuple[bool, str]:
        """检查是否应降级

        降级条件：
        - 连续15日成交额低于门槛50%
        - 触发财务预警（高等级立即降级）
        - 被ST/*ST（立即处理）
        - ⚠️ 争议时降级优先
        """

    def execute_rebalance(self):
        """⚠️ 执行每日再平衡（含挤出逻辑）

        流程：
        1. 收集所有待晋级股票（按优先级排序）
        2. 容量检查：满时执行末位淘汰
        3. 批量处理晋级
        4. 执行降级
        """
```

#### EventTrigger

```python
class EventTrigger:
    """事件触发器（含去重冷却）"""

    # ⚠️ 去重窗口期：同一事件24小时内不重复触发
    DEDUP_WINDOW_HOURS = 24

    def check_event(self, code: str, market_data: dict) -> Optional[TriggerEvent]:
        """检查是否触发事件"""

    def should_trigger(self, code: str, event_type: str) -> bool:
        """⚠️ 去重检查：窗口期内不重复触发"""
        last_triggered = self.last_trigger_time.get(code, {})
        last_time = last_triggered.get(event_type)
        if last_time and (now - last_time).hours < DEDUP_WINDOW_HOURS:
            return False
        return True

    def handle_event(self, event: TriggerEvent):
        """处理触发事件"""
```

#### FinancialWatcher

```python
class FinancialWatcher:
    """财务预警监控器（含缓释/恢复机制）"""

    # ⚠️ 梯度处理
    WARNING_ACTIONS = {
        "high": "immediate_downgrade",    # 净利润为负+营收下滑 → 立即降级
        "medium": "probation_15d",         # 资产负债率80-85% → 观察15日
        "low": "monitor_only",             # 资产负债率>80% → 仅监控
    }

    # ⚠️ 恢复机制
    RECOVERY_CONFIG = {
        "check_after_days": 30,           # 30日后检查是否恢复
        "conditions": {
            "negative_profit": "连续2期盈利",
            "revenue_decline": "营收增速回正",
            "high_debt": "资产负债率<75%",
        }
    }

    def check_warning(self, code: str, financial_data: dict) -> List[dict]:
        """检查财务预警（含缓释逻辑）"""

    def should_downgrade(self, code: str, warning: dict) -> Tuple[bool, str]:
        """⚠️ 梯度判断：高级立即，中级观察，低级监控"""
```

### 3.3 代码标准化工具

```python
# utils/code_normalizer.py

def normalize_code(code: str) -> str:
    """⚠️ 股票代码标准化：统一为6位纯数字

    处理：
    - SH600519 → 600519
    - SZ000001 → 000001
    - BJ830799 → 830799
    - 688981   → 688981（已是标准）
    """
    import re
    code = code.strip().upper()
    # 去除前缀
    code = re.sub(r'^(SH|SZ|BJ)', '', code)
    return code
```

### 3.4 指数调整日计算

```python
# utils/rebalance_date.py

def get_next_rebalance_dates(year: int) -> List[date]:
    """⚠️ 动态计算每年6月和12月的指数调整日

    规则：第二个星期五后的第一个交易日
    """
    import calendar
    from datetime import date, timedelta

    def nth_weekday_after(year: int, month: int, n: int, weekday: int) -> date:
        """获取month月第n个weekday之后的第一个交易日"""
        # weekday: 0=周一, 4=周五
        c = calendar.monthcalendar(year, month)
        nth = 0
        for week in c:
            if week[weekday] != 0:
                nth += 1
                if nth == n:
                    d = date(year, month, week[weekday])
                    # 找下一个交易日
                    while d.weekday() >= 5:  # 周六日
                        d += timedelta(days=1)
                    return d
        return None

    return [
        nth_weekday_after(year, 6, 2, 4),   # 6月第二个周五后
        nth_weekday_after(year, 12, 2, 4),  # 12月第二个周五后
    ]
```

---

## 四、数据结构

### 4.1 股票信息

```python
@dataclass
class StockInfo:
    """股票在池中的信息"""
    code: str
    name: str
    tier: PoolTier
    joined_at: datetime
    last_updated: datetime
    upgrade_count: int = 0
    downgrade_count: int = 0
    reason: str = ""

    # 动态指标（用于再平衡）
    avg_volume_20d: float = 0
    change_pct_30d: float = 0
    turnover_rate_20d: float = 0

    # ⚠️ 观察期（晋级后10日内表现监控）
    upgrade_probation_until: datetime = None

    # 财务预警状态
    financial_warning: List[str] = field(default_factory=list)
    warning_probation_until: datetime = None  # ⚠️ 中级预警观察期
    last_financial_check: datetime = None
```

### 4.2 临时股票信息

```python
@dataclass
class TempStockInfo:
    """临时池股票信息"""
    code: str
    name: str
    original_tier: PoolTier
    event_type: str
    triggered_at: datetime
    ttl_at: datetime = None  # ⚠️ TTL: triggered_at + 7个交易日
    analysis_result: Optional[str] = None
    processed: bool = False
```

### 4.3 历史快照

```python
@dataclass
class StockSnapshot:
    """股票历史快照"""
    code: str
    date: str
    tier: PoolTier
    total_cp: float
    rank: int
    reason: str
    # ⚠️ 对曾经进入核心池的股票，永久保留摘要
    ever_in_core: bool = False
```

### 4.4 枚举定义

```python
from enum import Enum

class PoolTier(Enum):
    CORE = "core"
    ACTIVE = "active"
    OBSERVE = "observe"
    TEMP = "temp"

class EventType(Enum):
    LIMIT_UP = "limit_up"
    LIMIT_DOWN = "limit_down"
    VOLUME_SPIKE = "volume_spike"
    NEWS = "news"

class FinancialWarningLevel(Enum):
    HIGH = "high"     # 立即降级
    MEDIUM = "medium" # 观察15日
    LOW = "low"       # 仅监控
```

---

## 五、接口设计

### 5.1 筛选器主接口

```python
class StockSelector:
    """股票筛选器 - Facade接口"""

    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        self.pool_manager = PoolManager()
        self.filter_chain = FilterChain()
        self.rebalancer = Rebalancer()
        self.event_trigger = EventTrigger()
        self.manual_list = ManualListManager()
        self.history_keeper = HistoryKeeper()

    # ─────────────────────────────────────────────
    # 核心接口（只读数据，通过回调通知）
    # ─────────────────────────────────────────────

    def get_pool(self, tier: PoolTier) -> List[str]: ...
    def get_all_analysable_codes(self) -> List[str]: ...
    def should_include(self, code: str) -> Tuple[bool, str]: ...
    def refresh_pools(self): ...  # 盘后批处理

    # ─────────────────────────────────────────────
    # 手动白名单/黑名单
    # ─────────────────────────────────────────────

    def add_whitelist(self, code: str, expire_days: int = 30): ...  # ⚠️ 白名单过期
    def add_blacklist(self, code: str): ...
    def remove_from_whitelist(self, code: str): ...
    def remove_from_blacklist(self, code: str): ...

    # ─────────────────────────────────────────────
    # ⚠️ 循环依赖防护：只读池，不回调
    # ─────────────────────────────────────────────

    def register_callback(self, callback: SelectorCallback):
        """注册回调，selector通过回调通知外部"""
```

### 5.2 回调接口（单向通知，防循环依赖）

```python
class SelectorCallback(Protocol):
    """⚠️ 回调接口：selector通知外部模块，外部不反向调用selector"""

    def on_pool_changed(self, tier: PoolTier, added: List[str], removed: List[str]):
        """池变化时通知（战力榜刷新）"""

    def on_stock_upgraded(self, code: str, from_tier: PoolTier, to_tier: PoolTier):
        """晋级时通知（engine计算战力）"""

    def on_stock_downgraded(self, code: str, from_tier: PoolTier, to_tier: PoolTier):
        """降级时通知（保留历史数据）"""

    def on_event_triggered(self, code: str, event_type: str):
        """事件触发时通知（recommender临时分析）"""
```

### 5.3 与战力榜/推荐系统联动

```python
# 联动原则：
# 1. stock_selector 只读数据，通过回调通知
# 2. engine/recommender 收到通知后自行决定如何处理
# 3. 避免循环依赖：外部模块不回调 stock_selector 的刷新方法

class CPBoard:
    """战力榜联动"""
    def on_pool_changed(self, tier, added, removed):
        if tier == PoolTier.CORE:
            # 核心池变化 → 立即刷新战力榜
            self.refresh_board()
```

---

## 六、配置项

### 6.1 核心配置（含动态调整）

```python
# stock_selector/config.py

# ─────────────────────────────────────────────
# 手动白名单/黑名单
# ─────────────────────────────────────────────
MANUAL_LIST_CONFIG = {
    "whitelist_file": "data/whitelist.json",
    "blacklist_file": "data/blacklist.json",
    "whitelist_expire_days": 30,  # ⚠️ 白名单30日后过期
    "auto_save": True,
}

# ─────────────────────────────────────────────
# 硬性排除
# ─────────────────────────────────────────────
EXCLUDE_CONFIG = {
    "st_stock": True,
    "exclude_asterisk_st_only": False,  # ⚠️ 是否区分ST和*ST
    # ⚠️ 板块差异化次新股保护期
    "new_stock_days": {
        "main": 90,      # 主板
        "chinext": 120,  # 创业板（注册制）
        "star": 120,     # 科创板
        "bj": 180,       # 北交所
    },
    "min_daily_volume": 500,    # 万元，连续20日低于此值
    "suspended_days": 30,
    # ⚠️ 已移除 min_price 规则：价格高低不反映基本面质量
}

# ─────────────────────────────────────────────
# 质量准入（底线）
# ─────────────────────────────────────────────
ADMISSION_CONFIG = {
    "min_market_cap": 5,            # 亿元
    "min_volume_20d": 1000,        # 万元（⚠️ 降为底线1000万）
}

# ─────────────────────────────────────────────
# ⚠️ 分层阈值（递进式，含动态容量）
# ─────────────────────────────────────────────
TIER_CONFIG = {
    "core": {
        # ⚠️ 动态容量：按全市场比例+固定上下限
        "ratio": 0.06,             # 全市场6%
        "min": 250,
        "max": 350,
        "min_volume": 5000,         # 万元（核心池5000万）
        "hs300": True,             # 沪深300直接进
        "volume_rank": 300,
    },
    "active": {
        "ratio": 0.10,
        "min": 400,
        "max": 600,
        "min_volume": 2000,         # 万元（活跃池2000万）
        "zz500": True,
        "zz1000": True,
        "turnover_rank": 20,
    },
    "observe": {
        "ratio": 0.20,
        "min": 800,
        "max": 1200,
        "min_volume": 1000,         # 万元（观察池1000万）
    }
}

# ─────────────────────────────────────────────
# 再平衡
# ─────────────────────────────────────────────
REBALANCE_CONFIG = {
    # ⚠️ 晋级观察期（10日内表现不稳定可快速回退）
    "upgrade_probation_days": 10,
    "quick_revert_trigger": {
        "volume_below_threshold": True,
        "price_drop_pct": -15,
    },
    "downgrade_volume_ratio": 0.5,
    "downgrade_days": 15,
    "upgrade_momentum_days": 5,
}

# ─────────────────────────────────────────────
# ⚠️ 临时池TTL
# ─────────────────────────────────────────────
TEMP_POOL_CONFIG = {
    "max_duration_days": 7,         # 最多停留7个交易日
    "result_handling": {
        "hold": "return_original_tier",
        "not_hold": "downgrade_one_tier",
        "timeout": "return_observe",
    },
    "dedup_window_hours": 24,      # ⚠️ 去重窗口期
}

# ─────────────────────────────────────────────
# 事件触发
# ─────────────────────────────────────────────
EVENT_CONFIG = {
    "limit_up_pct": 9.5,
    "limit_down_pct": -7.0,
    "volume_spike_multiplier": 3.0,
    "turnover_spike_pct": 20,
}

# ─────────────────────────────────────────────
# ⚠️ 财务预警（梯度处理+恢复机制）
# ─────────────────────────────────────────────
FINANCIAL_WARNING_CONFIG = {
    "high": {
        "conditions": ["negative_profit", "revenue_decline_gt_30"],
        "action": "immediate_downgrade",
    },
    "medium": {
        "conditions": ["debt_ratio_80_85"],
        "action": "probation_15d",
        "probation_days": 15,
    },
    "low": {
        "conditions": ["debt_ratio_gt_80"],
        "action": "monitor_only",
    },
    "recovery": {
        "check_after_days": 30,
        "conditions": {...}
    }
}

# ─────────────────────────────────────────────
# 指数同步
# ─────────────────────────────────────────────
INDEX_SYNC_CONFIG = {
    "indices": ["hs300", "zz500", "zz1000"],
    # ⚠️ 动态计算调整日，不再硬编码
    "sync_frequency": {
        "normal": "weekly",           # 平时每周
        "rebalance_window": "daily", # 调整日前后3天每日
    },
    "rebalance_window_days": 3,
    "cache_ttl_hours": 24,
    "fallback_to_cache": True,
    "fallback_to_snapshot": True,
}

# ─────────────────────────────────────────────
# ⚠️ 自适应阈值（可选）
# ─────────────────────────────────────────────
ADAPTIVE_CONFIG = {
    "enabled": False,               # ⚠️ 极端市场时启用
    "adjust_interval_days": 30,
    "volume_percentile": 50,       # 全市场中位数的50%
}

# ─────────────────────────────────────────────
# ⚠️ 数据更新频率策略（反向影响data_manager）
# ─────────────────────────────────────────────
UPDATE_STRATEGY_CONFIG = {
    "enabled": True,
    "market_status_check": "auto",  # "auto" | "manual"

    # 盘中更新间隔（秒）
    "trading_intervals": {
        "core": 5 * 60,       # 核心池：5分钟
        "active": 30 * 60,    # 活跃池：30分钟
        "observe": 0,          # 观察池：盘中不更新
    },

    # 盘前更新间隔（秒）
    "pre_market_intervals": {
        "core": 15 * 60,      # 核心池：15分钟
        "active": 60 * 60,    # 活跃池：60分钟
        "observe": 0,
    },

    # 收盘后更新策略
    "post_close_update": {
        "enabled": True,
        "priority_order": ["core", "active", "observe"],  # 更新顺序
        "batch_delay_seconds": 0.1,  # 批次间延迟（避免请求过快）
    },

    # 特殊时段
    "special_intervals": {
        "limit_up_monitoring": 1 * 60,  # 涨停股票：1分钟监控
        "high_volatility_monitoring": 5 * 60,  # 高波动股票：5分钟监控
    }
}
```

---

## 七、监控指标

```python
# utils/pool_metrics.py

# ⚠️ 监控指标（建议接入监控系统）
MONITOR_METRICS = {
    # 各池数量
    "pool_size": {"core": 0, "active": 0, "observe": 0, "temp": 0},

    # 每日周转率
    "daily_rebalance": {
        "upgrade_count": 0,
        "downgrade_count": 0,
        "evict_count": 0,        # ⚠️ 挤出数量
    },

    # 过滤统计
    "filter_stats": {
        "exclude_st": 0,
        "exclude_new_stock": 0,
        "exclude_volume": 0,
        "admission_pass": 0,
    },

    # 预警统计
    "warning_stats": {
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "downgrade_count": 0,
    },

    # 事件统计
    "event_stats": {
        "limit_up": 0,
        "limit_down": 0,
        "volume_spike": 0,
        "dedup_filtered": 0,     # ⚠️ 去重过滤数量
    },

    # 性能指标
    "perf_stats": {
        "refresh_duration_ms": 0,
        "last_refresh_time": None,
    }
}
```

---

## 八、实现计划

### Phase 1: 基础框架 (1天)
- [ ] 创建目录结构 + 工具类（代码标准化、调整日计算）
- [ ] 实现 `PoolManager` 核心类
- [ ] 实现 `FilterChain`（修正准入门槛递进）
- [ ] 配置化管理

### Phase 2: 核心筛选 (1天)
- [ ] 实现 ST/退市排除（区分ST/*ST）
- [ ] 实现次新股排除（板块差异化）
- [ ] 实现准入条件过滤（1000万底线）
- [ ] 实现三层分级（递进式门槛）

### Phase 3: 动态调整 (1天)
- [ ] 实现 `Rebalancer`（含挤出机制）
- [ ] 实现晋级/降级冲突处理（降级优先）
- [ ] 实现晋级观察期
- [ ] 实现每日再平衡流程

### Phase 4: 财务预警 + 指数同步 (1天)
- [ ] 实现 `FinancialWatcher`（梯度处理+恢复机制）
- [ ] 实现 `IndexSync`（动态计算调整日）
- [ ] 实现 API 失败兜底策略

### Phase 5: ⚠️ 数据更新频率策略 (0.5天)
- [ ] 实现 `UpdateStrategyProvider`（更新频率策略）
- [ ] 实现与 data_manager 的回调通知机制
- [ ] 实现盘中/盘前/盘后差异化更新

### Phase 6: 事件驱动 + TTL (0.5天)
- [ ] 实现 `EventTrigger`（去重窗口期）
- [ ] 实现临时池 TTL 清理机制
- [ ] 实现临时池结果处理

### Phase 7: 白名单过期 + 监控 (0.5天)
- [ ] 实现白名单过期机制
- [ ] 实现监控指标
- [ ] 日志记录

### Phase 8: 联动集成 + 测试 (1天)
- [ ] 实现回调接口（防循环依赖）
- [ ] 与 engine/recommender/data_manager 联动
- [ ] 单元测试 + 集成测试

---

## 九、文件清单

```
backend/stock_selector/
├── __init__.py
├── config.py               # 含动态调整配置+更新频率策略
├── stock_selector.py       # 主筛选器 (Facade)
├── pool_manager.py         # 股票池管理器（含挤出）
├── update_strategy.py      # ⚠️ 数据更新频率策略 🆕
├── filters/
│   ├── __init__.py
│   ├── blacklist.py        # 黑名单过滤
│   ├── manual_list.py      # 白名单/黑名单
│   └── admission.py         # 准入条件
├── rebalancer.py            # 动态再平衡（含冲突处理）
├── event_trigger.py         # 事件触发（含去重）
├── index_sync.py            # 指数同步（含动态日期）
├── financial_watcher.py     # 财务预警（含梯度+恢复）
├── history_keeper.py        # 历史保留
└── utils/
    ├── __init__.py
    ├── code_normalizer.py   # 代码标准化
    ├── rebalance_date.py    # 指数调整日计算
    └── pool_metrics.py      # 监控指标
```

---

## 十、待确认事项

| 事项 | v19.5.1建议 | v19.5.2专家建议 | 最终建议 |
|------|------------|-----------------|---------|
| 核心池数量 | 动态250-350 | 动态比例+上限300 | **动态比例(6%)+max=350** |
| 次新股保护期 | 主板90日 | 板块差异化 | **主板90/创业120/科创120/北交所180** |
| 晋级/降级阈值 | 当前合理 | 增加观察期+回撤保护 | **增加10日观察期** |
| 指数同步频率 | 每日+调整日前 | 平时每周，调整日每日 | **动态计算** |
| 手动白名单 | 持久化JSON | 持久化+30日过期 | **30日过期** |
| 历史数据保留 | 90日 | 核心池永久保留摘要 | **核心池永久** |
| 财务预警降级 | 分级处理 | High自动，Medium确认 | **High自动，Medium15日观察** |
| ST区分 | 统一排除 | 区分ST/*ST | **配置化** |
| 流动性阈值 | 固定2000万 | 自适应（可选） | **默认固定，启用时自适应** |

---

## 附录A: 参考专家评审

| 文档 | 核心贡献 |
|------|---------|
| 评审1 | 次新股板块差异化、动态池容量、梯度处理、监控指标、插件化过滤 |
| 评审2 | 流动性陷阱风险、临时池并发去重、财务预警滞后性、循环依赖防护 |
| 评审3 | **准入倒挂修正、挤出机制、盘中盘后分离、ST实时扫描、指数日期动态计算** |
| 评审4 | **晋级/降级冲突处理（降级优先）、临时池TTL、行业均衡、恢复机制** |
| 评审5 | **财务预警缓释、动态核心池、白名单过期、循环依赖风险** |

## 附录B: 阈值量化依据

| 阈值 | 数值 | 来源依据 |
|------|------|---------|
| 次新股保护期(主板) | 90日 | 专家建议60-120日 |
| 次新股保护期(科创/创业) | 120日 | 专家建议120日 |
| 次新股保护期(北交所) | 180日 | 流动性差异大 |
| 流通市值门槛 | ≥5亿 | 规避"壳"价值 |
| 日均成交额(准入底线) | ≥1000万 | 专家建议1000-2000万 |
| 日均成交额(观察池) | ≥1000万 | 递进式分层 |
| 日均成交额(活跃池) | ≥2000万 | 专家建议 |
| 日均成交额(核心池) | ≥5000万 | 专家建议 |
| 资产负债率预警 | >80% | 专家建议70-80% |
| 营收下滑降级阈值 | >30% | 专家建议20-30% |
| 晋级观察期 | 10日 | 专家建议 |
| 临时池TTL | 7日 | 专家建议 |
| 去重窗口期 | 24小时 | 专家建议 |
