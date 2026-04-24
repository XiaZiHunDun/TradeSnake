"""
准入条件过滤器（递进式门槛）

三层准入门槛（v19.5.3 递进式）：
- 观察池：日均成交额 >= 1000万
- 活跃池：日均成交额 >= 2000万
- 核心池：日均成交额 >= 5000万

附加条件：
- 财务健康（3选2）：净利润为正、营收同比增长>=0、资产负债率<70%
- 指数成分优先

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from typing import List, Dict, Tuple, Optional

from ..enums import PoolTier
from .. import config

logger = logging.getLogger(__name__)


class AdmissionFilter:
    """准入条件过滤器"""

    def __init__(self):
        self._thresholds = {
            PoolTier.OBSERVE: config.ADMISSION_CONFIG["observe"]["min_daily_volume_20d"],
            PoolTier.ACTIVE: config.ADMISSION_CONFIG["active"]["min_daily_volume_20d"],
            PoolTier.CORE: config.ADMISSION_CONFIG["core"]["min_daily_volume_20d"],
        }

        # 财务准入条件
        self._financial_config = {
            "positive_profit": True,      # 净利润为正
            "revenue_growth_gte_0": True,  # 营收同比增长>=0
            "debt_ratio_lt_70": True,      # 资产负债率<70%
        }

    def check_admission(self, stock: Dict, target_tier: PoolTier) -> Tuple[bool, str]:
        """
        检查股票是否满足准入条件

        Args:
            stock: 股票数据 {
                daily_volume_20d: float,  # 近20日日均成交额（万元）
                financial_data: {
                    net_profit: float,  # 净利润
                    revenue_yoy: float,  # 营收同比增长（%）
                    debt_ratio: float,  # 资产负债率（%）
                }
            }
            target_tier: 目标池

        Returns:
            (can_admit, reason)
        """
        code = stock.get("code", "")

        # 1. 成交额门槛检查
        daily_volume = stock.get("daily_volume_20d", 0)
        threshold = self._thresholds.get(target_tier, 1000)

        if daily_volume < threshold:
            return False, f"成交额{daily_volume}万<{threshold}万门槛"

        # 2. 财务健康检查（3选2）
        financial_ok, financial_reason = self._check_financial_health(stock)
        if not financial_ok:
            return False, financial_reason

        # 3. 特殊加成：指数成分（可以直接进入核心/活跃池）
        if target_tier == PoolTier.CORE:
            if stock.get("in_hs300") or stock.get("in_zz500"):
                return True, "指数成分加成（沪深300/中证500）"
        elif target_tier == PoolTier.ACTIVE:
            if stock.get("in_zz1000"):
                return True, "指数成分加成（中证1000）"

        return True, "满足准入条件"

    def _check_financial_health(self, stock: Dict) -> Tuple[bool, str]:
        """
        检查财务健康（3选2）

        Returns:
            (is_healthy, reason)
        """
        financial_data = stock.get("financial_data", {})

        conditions_met = 0

        # 条件1：净利润为正
        net_profit = financial_data.get("net_profit", 0)
        if net_profit > 0:
            conditions_met += 1

        # 条件2：营收同比增长>=0
        revenue_yoy = financial_data.get("revenue_yoy", 0)
        if revenue_yoy >= 0:
            conditions_met += 1

        # 条件3：资产负债率<70%（0表示无负债，是优势）
        debt_ratio = financial_data.get("debt_ratio", 0)
        if debt_ratio < 70:
            conditions_met += 1

        # 3选2通过
        if conditions_met >= 2:
            return True, ""

        # 返回具体原因
        reasons = []
        if net_profit <= 0:
            reasons.append("净利润亏损")
        if revenue_yoy < 0:
            reasons.append(f"营收同比下降{-revenue_yoy:.1f}%")
        if debt_ratio >= 70:
            reasons.append(f"资产负债率{debt_ratio:.1f}%>=70%")

        return False, f"财务不健康({', '.join(reasons)})，仅满足{conditions_met}/3条件"

    def classify_tier(self, stock: Dict) -> Tuple[PoolTier, str]:
        """
        根据准入条件分类股票到合适的池

        Returns:
            (tier, reason)
        """
        code = stock.get("code", "")

        # 指数成分优先
        if stock.get("in_hs300") or stock.get("in_zz500"):
            return PoolTier.CORE, "沪深300或中证500成分"

        if stock.get("in_zz1000"):
            return PoolTier.ACTIVE, "中证1000成分"

        # 成交额判断
        daily_volume = stock.get("daily_volume_20d", 0)

        if daily_volume >= self._thresholds[PoolTier.CORE]:
            return PoolTier.CORE, f"成交额{daily_volume}万>=核心池门槛"
        elif daily_volume >= self._thresholds[PoolTier.ACTIVE]:
            return PoolTier.ACTIVE, f"成交额{daily_volume}万>=活跃池门槛"
        elif daily_volume >= self._thresholds[PoolTier.OBSERVE]:
            return PoolTier.OBSERVE, f"成交额{daily_volume}万>=观察池门槛"
        else:
            return PoolTier.OBSERVE, f"成交额{daily_volume}万<{self._thresholds[PoolTier.OBSERVE]}万，但保留在观察池"

    def filter_by_tier(self, stocks: List[Dict], tier: PoolTier) -> Tuple[List[Dict], List[Dict]]:
        """
        按池过滤股票

        Args:
            stocks: 股票列表
            tier: 目标池

        Returns:
            (admitted_stocks, rejected_stocks)
        """
        admitted = []
        rejected = []

        for stock in stocks:
            can_admit, reason = self.check_admission(stock, tier)
            if can_admit:
                admitted.append(stock)
            else:
                rejected.append({
                    **stock,
                    "reject_reason": reason,
                })

        return admitted, rejected

    def get_threshold(self, tier: PoolTier) -> float:
        """获取指定池的成交额门槛"""
        return self._thresholds.get(tier, 1000)

    def get_all_thresholds(self) -> Dict[str, float]:
        """获取所有池的门槛"""
        return {tier.value: self._thresholds.get(tier, 1000) for tier in PoolTier if tier != PoolTier.TEMP}
