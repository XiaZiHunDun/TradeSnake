"""
预警引擎 - TradeSnake v17.2+v18.x

功能：
- 持仓战力变化预警
- 风险等级变化预警
- 换股信号预警
- 新机会预警
- 预警去重 + 冷却机制
- 动态阈值调整
"""

import asyncio
import time
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

try:
    from backend.core.database import get_db
except ImportError:
    from core.database import get_db


# 预警规则配置
WARN_RULES = {
    'cp_drop': {
        'threshold': 15,       # 战力单日下降超过15分
        'level': 'warning',
        'cooldown_hours': 24,
    },
    'cp_drop_danger': {
        'threshold': 25,       # 战力单日下降超过25分
        'level': 'danger',
        'cooldown_hours': 24,
    },
    'cp_trend_drop': {
        'threshold_days': 5,   # 连续5天
        'threshold_drop': 10, # 累计下降10分
        'level': 'warning',
        'cooldown_hours': 48,
    },
    'risk_level_up': {
        'level': 'warning',
        'cooldown_hours': 24,
    },
    'swap_signal': {
        'cp_diff_threshold': 15,  # 目标股战力比当前高15分以上
        'level': 'info',
        'cooldown_hours': 24,
    },
    'new_opportunity': {
        'cp_threshold': 80,
        'rank_change': 10,
        'level': 'info',
        'cooldown_hours': 12,
    }
}

# 预警过期配置
ALERT_EXPIRE_DAYS = 7
ALERT_KEEP_MAX = 100
READ_ALERT_EXPIRE_DAYS = 3


@dataclass
class Alert:
    """预警数据模型"""
    alert_type: str
    code: str
    name: str
    level: str  # warning/danger/info
    title: str
    message: str
    cp_before: float = 0
    cp_after: float = 0
    suggestion: str = ""
    id: int = 0
    is_read: bool = False
    created_at: str = ""
    expires_at: str = ""


class AlertDeduplicator:
    """预警去重器：防止预警风暴"""

    def __init__(self):
        self.recent_alerts = {}  # {alert_key: timestamp}

    def should_generate(self, alert_type: str, code: str, level: str) -> Tuple[bool, Optional[str]]:
        """
        检查是否应该生成预警

        返回: (should_generate, reason_if_not)
        """
        key = f"{alert_type}:{code}:{level}"

        if key in self.recent_alerts:
            last_time = self.recent_alerts[key]
            cooldown = self._get_cooldown(alert_type) * 3600  # 转换为秒

            elapsed = time.time() - last_time
            if elapsed < cooldown:
                remaining = int(cooldown - elapsed)
                return False, f"冷却中，{remaining // 3600}h{(remaining % 3600) // 60}m后可再次预警"

        self.recent_alerts[key] = time.time()
        return True, None

    def _get_cooldown(self, alert_type: str) -> int:
        """获取各类型预警的冷却时间（小时）"""
        cooldowns = {
            'cp_drop': 24,
            'cp_drop_danger': 24,
            'cp_trend_drop': 48,
            'swap_signal': 24,
            'new_opportunity': 12,
            'risk_level_up': 24,
        }
        return cooldowns.get(alert_type, 24)

    def cleanup_old_entries(self, max_age_hours: int = 48):
        """清理过期的去重记录"""
        now = time.time()
        expired_keys = [
            k for k, v in self.recent_alerts.items()
            if now - v > max_age_hours * 3600
        ]
        for k in expired_keys:
            del self.recent_alerts[k]


class AlertEngine:
    """预警引擎"""

    def __init__(self):
        self.db = get_db()
        self.dedup = AlertDeduplicator()
        self._init_default_config()

    def _init_default_config(self):
        """初始化默认预警配置"""
        for rule_type, config in WARN_RULES.items():
            existing = self.db.get_alert_config(rule_type)
            if not existing:
                self.db.set_alert_config(
                    rule_type=rule_type,
                    threshold=config.get('threshold', config.get('threshold_drop', 0)),
                    cooldown_hours=config.get('cooldown_hours', 24)
                )

    def get_dynamic_threshold(self, rule_type: str = 'cp_drop', lookback_days: int = 30) -> Dict:
        """
        基于历史波动率计算动态阈值

        算法：threshold = max(最小阈值, 均值 + k倍标准差)
        - 保守市场：k=1.0，更容易触发预警
        - 正常市场：k=1.5
        - 波动市场：k=2.0，更难触发预警
        """
        # 获取最近N天的战力变化数据
        changes = []
        for days in range(1, lookback_days + 1):
            date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            history = self.db.get_cp_changes(days=days)
            for h in history:
                if h.get('change', 0) > 0:  # 只统计下跌
                    changes.append(h['change'])

        if len(changes) < 10:
            # 数据不足，使用静态默认值
            return {'threshold': WARN_RULES.get(rule_type, {}).get('threshold', 15), 'is_dynamic': False}

        changes_arr = np.array(changes)
        mean_change = np.mean(changes_arr)
        std_change = np.std(changes_arr)

        # 根据标准差系数计算动态阈值
        k = 1.5  # 1.5倍标准差
        base_threshold = WARN_RULES.get(rule_type, {}).get('threshold', 15)
        dynamic_threshold = max(base_threshold, mean_change + k * std_change)

        return {
            'threshold': round(dynamic_threshold, 1),
            'mean': round(mean_change, 2),
            'std': round(std_change, 2),
            'is_dynamic': True,
            'sample_size': len(changes)
        }

    def check_cp_drop(self, code: str, name: str, current_cp: float, previous_cp: float, use_dynamic: bool = True) -> Optional[Alert]:
        """检查战力下降预警"""
        if previous_cp <= 0 or current_cp <= 0:
            return None

        drop = previous_cp - current_cp

        # 获取阈值（动态或静态）
        if use_dynamic:
            dynamic_info = self.get_dynamic_threshold('cp_drop')
            threshold = dynamic_info['threshold']
        else:
            config = WARN_RULES.get('cp_drop', {})
            config_db = self.db.get_alert_config('cp_drop')
            threshold = config_db.get('threshold', config.get('threshold', 15)) if config_db else config.get('threshold', 15)

        if drop >= threshold:
            # 检查去重
            should_gen, reason = self.dedup.should_generate('cp_drop', code, 'warning')
            if not should_gen:
                return None

            level = 'danger' if drop >= 25 else 'warning'

            return Alert(
                alert_type='cp_drop',
                code=code,
                name=name,
                level=level,
                title=f"{name}战力下降{int(drop)}分",
                message=f"战力从{previous_cp:.1f}下降至{current_cp:.1f}，跌幅{(drop/previous_cp)*100:.1f}%",
                cp_before=previous_cp,
                cp_after=current_cp,
                suggestion="建议关注，若持续下跌考虑换股",
                expires_at=(datetime.now() + timedelta(days=ALERT_EXPIRE_DAYS)).isoformat()
            )

        return None

    def check_cp_trend_drop(self, code: str, name: str, cp_history: List[Dict]) -> Optional[Alert]:
        """检查连续下跌趋势预警"""
        if len(cp_history) < 5:
            return None

        # 检查最近5天是否连续下跌
        recent = cp_history[:5]
        drops = []
        for i in range(len(recent) - 1):
            if recent[i]['total_cp'] > recent[i+1]['total_cp'] > 0:
                drops.append(recent[i]['total_cp'] - recent[i+1]['total_cp'])

        if len(drops) >= 4:  # 至少4天在跌
            total_drop = sum(drops)
            if total_drop >= 10:
                # 检查去重
                should_gen, reason = self.dedup.should_generate('cp_trend_drop', code, 'warning')
                if not should_gen:
                    return None

                return Alert(
                    alert_type='cp_trend_drop',
                    code=code,
                    name=name,
                    level='warning',
                    title=f"{name}连续下跌趋势",
                    message=f"最近5天下跌{len(drops)}天，累计下降{total_drop:.1f}分",
                    cp_before=recent[0]['total_cp'],
                    cp_after=recent[-1]['total_cp'],
                    suggestion="注意风险，建议检查基本面变化",
                    expires_at=(datetime.now() + timedelta(days=ALERT_EXPIRE_DAYS)).isoformat()
                )

        return None

    def check_risk_level_change(self, code: str, name: str, old_level: str, new_level: str) -> Optional[Alert]:
        """检查风险等级变化"""
        if old_level == new_level:
            return None

        level_map = {'较低': 1, '中等': 2, '高风险': 3}
        old_score = level_map.get(old_level, 0)
        new_score = level_map.get(new_level, 0)

        if new_score > old_score:
            # 检查去重
            should_gen, reason = self.dedup.should_generate('risk_level_up', code, 'warning')
            if not should_gen:
                return None

            return Alert(
                alert_type='risk_level_up',
                code=code,
                name=name,
                level='warning',
                title=f"{name}风险等级上升",
                message=f"风险等级从「{old_level}」变为「{new_level}」",
                suggestion="建议关注，风险偏好降低时可考虑换股",
                expires_at=(datetime.now() + timedelta(days=ALERT_EXPIRE_DAYS)).isoformat()
            )

        return None

    def check_swap_signal(self, code: str, name: str, current_cp: float, better_cp: float, better_code: str, better_name: str) -> Optional[Alert]:
        """检查换股信号"""
        if better_cp <= current_cp:
            return None

        diff = better_cp - current_cp
        if diff < 15:  # 阈值15分
            return None

        # 检查去重
        should_gen, reason = self.dedup.should_generate('swap_signal', code, 'info')
        if not should_gen:
            return None

        return Alert(
            alert_type='swap_signal',
            code=code,
            name=name,
            level='info',
            title=f"换股信号：{name} → {better_name}",
            message=f"当前战力{current_cp:.1f}，{better_name}战力{better_cp:.1f}，差{diff:.1f}分",
            cp_before=current_cp,
            cp_after=better_cp,
            suggestion=f"考虑从{name}换到{better_name}",
            expires_at=(datetime.now() + timedelta(days=ALERT_EXPIRE_DAYS)).isoformat()
        )

    def check_new_opportunity(self, code: str, name: str, cp: float, rank: int, previous_rank: int) -> Optional[Alert]:
        """检查新股机会"""
        if cp < 80:
            return None

        rank_change = previous_rank - rank  # 正数表示排名上升
        if rank_change < 10:
            return None

        # 检查去重
        should_gen, reason = self.dedup.should_generate('new_opportunity', code, 'info')
        if not should_gen:
            return None

        return Alert(
            alert_type='new_opportunity',
            code=code,
            name=name,
            level='info',
            title=f"新机会：{name}战力突破{cp:.0f}分",
            message=f"战力榜排名从第{previous_rank}位上升至第{rank}位",
            cp_before=previous_rank,
            cp_after=cp,
            suggestion="建议加入自选关注",
            expires_at=(datetime.now() + timedelta(days=ALERT_EXPIRE_DAYS)).isoformat()
        )

    def generate_all_alerts(self, holdings: List[Dict] = None, all_stocks: List[Dict] = None) -> List[Alert]:
        """检查所有预警类型并生成预警"""
        alerts = []

        # 如果没有提供持仓数据，从数据库获取
        if holdings is None:
            # TODO: 从持仓管理模块获取
            holdings = []

        # 获取战力变化
        cp_changes = self.db.get_cp_changes(days=7)

        for change in cp_changes:
            code = change['code']
            name = change['name']
            old_cp = change.get('old_cp', 0)
            new_cp = change.get('new_cp', 0)
            change_val = change.get('change', 0)

            # 检查战力下降
            if change_val > 0:  # 下降为正
                alert = self.check_cp_drop(code, name, new_cp, old_cp)
                if alert:
                    alerts.append(alert)

            # 检查连续下跌
            history = self.db.get_cp_history(code, days=7)
            if history:
                alert = self.check_cp_trend_drop(code, name, history)
                if alert:
                    alerts.append(alert)

        return alerts

    def save_alert(self, alert: Alert) -> int:
        """保存预警到数据库"""
        alert_id = self.db.create_alert({
            'code': alert.code,
            'name': alert.name,
            'alert_type': alert.alert_type,
            'level': alert.level,
            'title': alert.title,
            'message': alert.message,
            'cp_before': alert.cp_before,
            'cp_after': alert.cp_after,
            'expires_at': alert.expires_at
        })

        # WebSocket广播（v18.x）
        try:
            from backend.api.websocket import broadcast_alert
            asyncio.create_task(broadcast_alert({
                'id': alert_id,
                'type': alert.alert_type,
                'code': alert.code,
                'name': alert.name,
                'level': alert.level,
                'title': alert.title,
                'message': alert.message,
                'created_at': datetime.now().isoformat()
            }))
        except Exception as e:
            print(f"WebSocket广播失败: {e}")

        return alert_id

    def get_alerts(self, unread_only: bool = False, limit: int = 50) -> List[Dict]:
        """获取预警列表"""
        return self.db.get_alerts(unread_only=unread_only, limit=limit)

    def get_alert_summary(self) -> Dict:
        """获取预警汇总"""
        return self.db.get_alert_summary()

    def mark_read(self, alert_ids: List[int] = None, all: bool = False):
        """标记预警已读"""
        if all:
            # 标记所有未读为已读
            alerts = self.db.get_alerts(unread_only=True, limit=1000)
            for alert in alerts:
                self.db.mark_alert_read(alert['id'])
        elif alert_ids:
            for alert_id in alert_ids:
                self.db.mark_alert_read(alert_id)

    def cleanup_expired_alerts(self):
        """清理过期预警"""
        # SQLite不支持复杂的日期运算，在查询时过滤
        pass


# 全局预警引擎实例
_alert_engine = None


def get_alert_engine() -> AlertEngine:
    """获取预警引擎单例"""
    global _alert_engine
    if _alert_engine is None:
        _alert_engine = AlertEngine()
    return _alert_engine
