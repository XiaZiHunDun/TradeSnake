"""
事件触发器 - 负责监控市场事件并触发临时池操作

支持的事件类型：
- 涨停/跌停
- 巨量异动
- 高换手率
- 价格异动
- 新闻/公告事件

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any

from .enums import PoolTier, EventType
from .pool_manager import PoolManager
from .types import StockInfo
from . import config

logger = logging.getLogger(__name__)


class TriggerEvent:
    """触发事件"""

    def __init__(self, code: str, name: str, event_type: EventType,
                 trigger_data: Dict[str, Any], reason: str):
        self.code = code
        self.name = name
        self.event_type = event_type
        self.trigger_data = trigger_data
        self.reason = reason
        self.trigger_time = datetime.now()

    def __repr__(self):
        return f"TriggerEvent({self.code}, {self.event_type.value}, {self.reason})"


class EventTrigger:
    """事件触发器"""

    def __init__(self, pool_manager: PoolManager):
        self._pm = pool_manager

        # 事件去重记录 {code: {event_type: last_trigger_time}}
        self._event_records: Dict[str, Dict[EventType, datetime]] = {}

        # 事件回调
        self._callbacks: List[callable] = []

    def register_callback(self, callback: callable) -> None:
        """注册事件回调"""
        self._callbacks.append(callback)

    def check_event(self, code: str, name: str, market_data: Dict) -> Optional[TriggerEvent]:
        """
        检查是否触发事件

        Args:
            code: 股票代码
            name: 股票名称
            market_data: 市场数据 {
                price: 当前价格,
                change_pct: 涨跌幅,
                volume: 成交额,
                turnover_rate: 换手率,
                avg_volume_20d: 20日均成交额,
                ...
            }

        Returns:
            TriggerEvent 如果触发，否则 None
        """
        # 检查是否在黑名单
        if self._pm.is_blacklisted(code):
            return None

        # 检查是否在临时池（避免重复触发）
        current_tier = self._pm.get_stock_tier(code)
        if current_tier == PoolTier.TEMP:
            return None

        # 检查涨停
        event = self._check_limit_up(code, name, market_data)
        if event:
            return event

        # 检查跌停
        event = self._check_limit_down(code, name, market_data)
        if event:
            return event

        # 检查巨量异动
        event = self._check_volume_spike(code, name, market_data)
        if event:
            return event

        # 检查高换手率
        event = self._check_high_turnover(code, name, market_data)
        if event:
            return event

        # 检查价格异动
        event = self._check_price_spike(code, name, market_data)
        if event:
            return event

        return None

    def _check_limit_up(self, code: str, name: str, data: Dict) -> Optional[TriggerEvent]:
        """检查涨停"""
        change_pct = data.get("change_pct", 0)
        threshold = config.EVENT_TRIGGER_CONFIG["limit_up_pct"]

        if change_pct >= threshold:
            if not self._should_trigger(code, EventType.LIMIT_UP):
                logger.debug(f"股票 {code} 涨停事件在去重窗口内，跳过")
                return None

            return TriggerEvent(
                code=code,
                name=name,
                event_type=EventType.LIMIT_UP,
                trigger_data={"change_pct": change_pct, "threshold": threshold},
                reason=f"涨停 {change_pct:.2f}%",
            )
        return None

    def _check_limit_down(self, code: str, name: str, data: Dict) -> Optional[TriggerEvent]:
        """检查跌停"""
        change_pct = data.get("change_pct", 0)
        threshold = config.EVENT_TRIGGER_CONFIG["limit_down_pct"]

        if change_pct <= threshold:
            if not self._should_trigger(code, EventType.LIMIT_DOWN):
                logger.debug(f"股票 {code} 跌停事件在去重窗口内，跳过")
                return None

            return TriggerEvent(
                code=code,
                name=name,
                event_type=EventType.LIMIT_DOWN,
                trigger_data={"change_pct": change_pct, "threshold": threshold},
                reason=f"跌停 {change_pct:.2f}%",
            )
        return None

    def _check_volume_spike(self, code: str, name: str, data: Dict) -> Optional[TriggerEvent]:
        """检查巨量异动"""
        volume = data.get("volume", 0)
        avg_volume_20d = data.get("avg_volume_20d", 0)

        if avg_volume_20d <= 0:
            return None

        ratio = volume / avg_volume_20d
        threshold = config.EVENT_TRIGGER_CONFIG["volume_spike_ratio"]

        if ratio >= threshold:
            if not self._should_trigger(code, EventType.VOLUME_SPIKE):
                return None

            return TriggerEvent(
                code=code,
                name=name,
                event_type=EventType.VOLUME_SPIKE,
                trigger_data={"volume": volume, "avg_volume_20d": avg_volume_20d, "ratio": ratio},
                reason=f"成交额暴增 {ratio:.1f} 倍",
            )
        return None

    def _check_high_turnover(self, code: str, name: str, data: Dict) -> Optional[TriggerEvent]:
        """检查高换手率"""
        turnover_rate = data.get("turnover_rate", 0)
        threshold = config.EVENT_TRIGGER_CONFIG["high_turnover_rate"]

        if turnover_rate >= threshold:
            if not self._should_trigger(code, EventType.HIGH_TURNOVER):
                return None

            return TriggerEvent(
                code=code,
                name=name,
                event_type=EventType.HIGH_TURNOVER,
                trigger_data={"turnover_rate": turnover_rate, "threshold": threshold},
                reason=f"换手率 {turnover_rate:.2f}%",
            )
        return None

    def _check_price_spike(self, code: str, name: str, data: Dict) -> Optional[TriggerEvent]:
        """检查价格异动（短时间内大幅波动）"""
        # 需要结合日内分钟数据，这里简化处理
        # 实际应该检查分钟级别的价格变化
        change_pct = data.get("change_pct", 0)

        # 超过5%但不到涨停阈值的异动
        if 5 <= abs(change_pct) < config.EVENT_TRIGGER_CONFIG["limit_up_pct"]:
            if not self._should_trigger(code, EventType.PRICE_SPIKE):
                return None

            return TriggerEvent(
                code=code,
                name=name,
                event_type=EventType.PRICE_SPIKE,
                trigger_data={"change_pct": change_pct},
                reason=f"价格异动 {change_pct:.2f}%",
            )
        return None

    def _should_trigger(self, code: str, event_type: EventType) -> bool:
        """
        检查是否应该触发（去重）

        Args:
            code: 股票代码
            event_type: 事件类型

        Returns:
            True 如果应该触发，False 如果在去重窗口内
        """
        if code not in self._event_records:
            self._event_records[code] = {}

        last_time = self._event_records[code].get(event_type)
        if last_time is None:
            return True

        # 检查是否在去重窗口内
        dedup_window = timedelta(hours=config.EVENT_TRIGGER_CONFIG["dedup_window_hours"])
        if datetime.now() - last_time < dedup_window:
            return False

        return True

    def _record_event(self, code: str, event_type: EventType) -> None:
        """记录事件触发时间"""
        if code not in self._event_records:
            self._event_records[code] = {}
        self._event_records[code][event_type] = datetime.now()

    def handle_event(self, event: TriggerEvent) -> bool:
        """
        处理触发事件

        Args:
            event: 触发事件

        Returns:
            是否处理成功
        """
        # 记录事件
        self._record_event(event.code, event.event_type)

        # 将股票加入临时池
        success = self._pm.to_temp(
            code=event.code,
            event_type=event.event_type,
            name=event.name,
            reason=event.reason,
        )

        if success:
            logger.info(f"事件触发: {event}")

            # 触发回调
            for callback in self._callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"事件回调执行失败: {e}")

        return success

    def check_batch(self, stocks_data: List[Dict]) -> List[TriggerEvent]:
        """
        批量检查事件

        Args:
            stocks_data: 股票市场数据列表 [{
                code: str,
                name: str,
                price: float,
                change_pct: float,
                volume: float,
                turnover_rate: float,
                avg_volume_20d: float,
            }, ...]

        Returns:
            触发的所有事件列表
        """
        events = []
        for stock_data in stocks_data:
            code = stock_data.get("code")
            name = stock_data.get("name", "")

            event = self.check_event(code, name, stock_data)
            if event:
                self.handle_event(event)
                events.append(event)

        return events

    def clear_old_records(self, hours: int = 48) -> int:
        """
        清理旧的事件记录

        Args:
            hours: 超过多少小时的记录被清理

        Returns:
            清理的记录数
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        count = 0

        for code in list(self._event_records.keys()):
            for event_type in list(self._event_records[code].keys()):
                if self._event_records[code][event_type] < cutoff:
                    del self._event_records[code][event_type]
                    count += 1

            if not self._event_records[code]:
                del self._event_records[code]

        if count > 0:
            logger.debug(f"清理了 {count} 条旧事件记录")

        return count
