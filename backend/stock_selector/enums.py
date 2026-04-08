"""
枚举类型定义
"""

from enum import Enum


class PoolTier(Enum):
    """股票池层级"""
    CORE = "core"       # 核心池 ~300只
    ACTIVE = "active"   # 活跃池 ~500只
    OBSERVE = "observe"  # 观察池 ~1000只
    TEMP = "temp"       # 临时池 事件驱动

    @property
    def target_size(self) -> int:
        """目标数量"""
        sizes = {
            PoolTier.CORE: 300,
            PoolTier.ACTIVE: 500,
            PoolTier.OBSERVE: 1000,
            PoolTier.TEMP: 50,  # 临时池容量上限
        }
        return sizes.get(self, 0)

    @property
    def update_interval(self) -> int:
        """更新间隔（秒）"""
        intervals = {
            PoolTier.CORE: 300,      # 5分钟
            PoolTier.ACTIVE: 3600,   # 1小时
            PoolTier.OBSERVE: 21600, # 6小时
            PoolTier.TEMP: 60,       # 1分钟（事件驱动）
        }
        return intervals.get(self, 3600)


class EventType(Enum):
    """事件类型"""
    LIMIT_UP = "limit_up"           # 涨停
    LIMIT_DOWN = "limit_down"       # 跌停
    VOLUME_SPIKE = "volume_spike"   # 巨量异动
    HIGH_TURNOVER = "high_turnover" # 高换手率
    PRICE_SPIKE = "price_spike"    # 价格异动
    NEWS_EVENT = "news_event"       # 新闻/公告事件


class FinancialWarningLevel(Enum):
    """财务预警级别"""
    NONE = "none"           # 无问题
    LOW = "low"             # 低风险：监控
    MEDIUM = "medium"       # 中风险：15天观察期
    HIGH = "high"           # 高风险：立即降级

    @property
    def action(self) -> str:
        """建议动作"""
        actions = {
            FinancialWarningLevel.NONE: "无需动作",
            FinancialWarningLevel.LOW: "加入监控列表",
            FinancialWarningLevel.MEDIUM: "进入15天观察期",
            FinancialWarningLevel.HIGH: "立即从当前池降级",
        }
        return actions.get(self, "未知")


class RebalanceAction(Enum):
    """再平衡动作"""
    ADD = "add"
    REMOVE = "remove"
    UPGRADE = "upgrade"
    DOWNGRADE = "downgrade"
    EVICT = "evict"
