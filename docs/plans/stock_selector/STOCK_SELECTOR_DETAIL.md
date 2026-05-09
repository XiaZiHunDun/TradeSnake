# 股票筛选模块架构方案 - 详细设计

> 本文档是 `stock_selector/` 模块的详细设计部分，对应 `STOCK_SELECTOR_OVERVIEW.md` 的后续内容。

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
