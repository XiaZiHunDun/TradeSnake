"""
预警引擎单元测试 - TradeSnake Alert Engine Tests
"""

import pytest
import sys
import os
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.alert_engine import (
    AlertDeduplicator,
    Alert,
    WARN_RULES,
    ALERT_EXPIRE_DAYS
)


class TestAlertDeduplicator:
    """测试预警去重器"""

    def setup_method(self):
        """每个测试方法前设置"""
        self.dedup = AlertDeduplicator()

    def test_should_generate_new_alert(self):
        """测试新预警应该生成"""
        should_gen, reason = self.dedup.should_generate('cp_drop', '600519', 'warning')
        assert should_gen is True
        assert reason is None

    def test_should_not_generate_duplicate_within_cooldown(self):
        """测试冷却期内不应重复生成预警"""
        # 第一次生成
        self.dedup.should_generate('cp_drop', '600519', 'warning')

        # 立即再次生成应该被拒绝
        should_gen, reason = self.dedup.should_generate('cp_drop', '600519', 'warning')
        assert should_gen is False
        assert '冷却中' in reason

    def test_should_generate_after_cooldown(self):
        """测试冷却期后应重新生成"""
        # 第一次生成
        self.dedup.should_generate('cp_drop', '600519', 'warning')

        # 模拟时间流逝（直接修改时间戳）
        self.dedup.recent_alerts['cp_drop:600519:warning'] = time.time() - 25 * 3600  # 25小时后

        should_gen, reason = self.dedup.should_generate('cp_drop', '600519', 'warning')
        assert should_gen is True

    def test_different_code_not_affected(self):
        """测试不同股票代码不受去重影响"""
        # 600519 生成预警
        self.dedup.should_generate('cp_drop', '600519', 'warning')

        # 000858 同一类型应该可以生成
        should_gen, reason = self.dedup.should_generate('cp_drop', '000858', 'warning')
        assert should_gen is True

    def test_different_level_not_affected(self):
        """测试不同预警级别不受去重影响"""
        # warning 级别生成
        self.dedup.should_generate('cp_drop', '600519', 'warning')

        # danger 级别同一股票应该可以生成
        should_gen, reason = self.dedup.should_generate('cp_drop', '600519', 'danger')
        assert should_gen is True

    def test_different_type_not_affected(self):
        """测试不同预警类型不受去重影响"""
        # cp_drop 类型生成
        self.dedup.should_generate('cp_drop', '600519', 'warning')

        # cp_trend_drop 类型同一股票应该可以生成
        should_gen, reason = self.dedup.should_generate('cp_trend_drop', '600519', 'warning')
        assert should_gen is True

    def test_cleanup_old_entries(self):
        """测试清理过期条目"""
        # 添加旧条目
        self.dedup.recent_alerts['cp_drop:600519:warning'] = time.time() - 50 * 3600  # 50小时前

        # 清理
        self.dedup.cleanup_old_entries(max_age_hours=48)

        # 旧条目应该被删除
        assert 'cp_drop:600519:warning' not in self.dedup.recent_alerts

    def test_get_cooldown_returns_correct_hours(self):
        """测试各预警类型的冷却时间"""
        assert self.dedup._get_cooldown('cp_drop') == 24
        assert self.dedup._get_cooldown('cp_drop_danger') == 24
        assert self.dedup._get_cooldown('cp_trend_drop') == 48
        assert self.dedup._get_cooldown('swap_signal') == 24
        assert self.dedup._get_cooldown('new_opportunity') == 12
        assert self.dedup._get_cooldown('unknown_type') == 24  # 默认值


class TestAlert:
    """测试预警数据模型"""

    def test_alert_creation(self):
        """测试创建预警"""
        alert = Alert(
            alert_type='cp_drop',
            code='600519',
            name='贵州茅台',
            level='warning',
            title='战力下降10分',
            message='战力从80.0下降至70.0'
        )

        assert alert.alert_type == 'cp_drop'
        assert alert.code == '600519'
        assert alert.name == '贵州茅台'
        assert alert.level == 'warning'
        assert alert.is_read is False

    def test_alert_default_values(self):
        """测试预警默认值"""
        alert = Alert(
            alert_type='cp_drop',
            code='600519',
            name='贵州茅台',
            level='warning',
            title='test',
            message='test'
        )

        assert alert.cp_before == 0
        assert alert.cp_after == 0
        assert alert.suggestion == ""
        assert alert.is_read is False
        assert alert.created_at == ""


class TestWarnRules:
    """测试预警规则配置"""

    def test_cp_drop_rule_config(self):
        """测试战力下降规则配置"""
        rule = WARN_RULES['cp_drop']
        assert rule['threshold'] == 15
        assert rule['level'] == 'warning'
        assert rule['cooldown_hours'] == 24

    def test_cp_drop_danger_rule_config(self):
        """测试危险战力下降规则配置"""
        rule = WARN_RULES['cp_drop_danger']
        assert rule['threshold'] == 25
        assert rule['level'] == 'danger'
        assert rule['cooldown_hours'] == 24

    def test_swap_signal_rule_config(self):
        """测试换股信号规则配置"""
        rule = WARN_RULES['swap_signal']
        assert rule['cp_diff_threshold'] == 15
        assert rule['level'] == 'info'
        assert rule['cooldown_hours'] == 24

    def test_new_opportunity_rule_config(self):
        """测试新机会规则配置"""
        rule = WARN_RULES['new_opportunity']
        assert rule['cp_threshold'] == 80
        assert rule['rank_change'] == 10
        assert rule['level'] == 'info'
        assert rule['cooldown_hours'] == 12

    def test_all_rule_types_exist(self):
        """测试所有规则类型都存在"""
        expected_types = [
            'cp_drop', 'cp_drop_danger', 'cp_trend_drop',
            'risk_level_up', 'swap_signal', 'new_opportunity'
        ]
        for rule_type in expected_types:
            assert rule_type in WARN_RULES


class TestAlertEngineCooldownLogic:
    """测试预警引擎冷却逻辑"""

    def test_cooldown_calculation(self):
        """测试冷却时间计算"""
        dedup = AlertDeduplicator()

        # cp_drop 冷却24小时
        key = 'cp_drop:600519:warning'
        dedup.recent_alerts[key] = time.time()

        # 1小时后检查
        dedup.recent_alerts[key] = time.time() - 1 * 3600
        should_gen, reason = dedup.should_generate('cp_drop', '600519', 'warning')
        assert should_gen is False
        assert '冷却中' in reason
        assert 'h' in reason  # 包含小时部分

        # 25小时后检查
        dedup.recent_alerts[key] = time.time() - 25 * 3600
        should_gen, reason = dedup.should_generate('cp_drop', '600519', 'warning')
        assert should_gen is True

    def test_cp_trend_drop_longer_cooldown(self):
        """测试连续下跌使用更长冷却时间"""
        dedup = AlertDeduplicator()

        # cp_trend_drop 冷却48小时
        key = 'cp_trend_drop:600519:warning'
        dedup.recent_alerts[key] = time.time() - 24 * 3600  # 24小时前

        should_gen, reason = dedup.should_generate('cp_trend_drop', '600519', 'warning')
        assert should_gen is False  # 还在冷却中

        # 49小时后
        dedup.recent_alerts[key] = time.time() - 49 * 3600
        should_gen, reason = dedup.should_generate('cp_trend_drop', '600519', 'warning')
        assert should_gen is True

    def test_new_opportunity_shorter_cooldown(self):
        """测试新机会使用较短冷却时间"""
        dedup = AlertDeduplicator()

        # new_opportunity 冷却12小时
        key = 'new_opportunity:600519:info'
        dedup.recent_alerts[key] = time.time() - 10 * 3600  # 10小时前

        should_gen, reason = dedup.should_generate('new_opportunity', '600519', 'info')
        assert should_gen is False  # 还在冷却中

        # 13小时后
        dedup.recent_alerts[key] = time.time() - 13 * 3600
        should_gen, reason = dedup.should_generate('new_opportunity', '600519', 'info')
        assert should_gen is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])