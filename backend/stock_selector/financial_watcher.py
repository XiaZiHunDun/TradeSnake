"""
财务观察器 - 负责监控财务预警

财务预警级别：
- HIGH: 立即降级（连续2年亏损、净资产为负等）
- MEDIUM: 15天观察期（净利润同比下降50%等）
- LOW: 监控（应收账款异常等）

设计文档: docs/plans/STOCK_SELECTOR_ARCHITECTURE.md v19.5.3
"""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple, Any

from .enums import PoolTier, FinancialWarningLevel
from .pool_manager import PoolManager
from .types import StockInfo
from . import config

logger = logging.getLogger(__name__)


class FinancialWarning:
    """财务预警"""

    def __init__(self, code: str, name: str, level: FinancialWarningLevel,
                 indicators: Dict[str, Any], description: str):
        self.code = code
        self.name = name
        self.level = level
        self.indicators = indicators
        self.description = description
        self.detected_at = datetime.now()

    def __repr__(self):
        return f"FinancialWarning({self.code}, {self.level.value}, {self.description})"


class FinancialWatcher:
    """财务观察器"""

    def __init__(self, pool_manager: PoolManager):
        self._pm = pool_manager

        # 预警记录 {code: [warnings]}
        self._warning_records: Dict[str, List[FinancialWarning]] = {}

        # 中风险观察期记录 {code: start_date}
        self._medium_probation: Dict[str, date] = {}

    def check_warning(self, code: str, name: str,
                     financial_data: Dict) -> List[FinancialWarning]:
        """
        检查财务预警

        Args:
            code: 股票代码
            name: 股票名称
            financial_data: 财务数据 {
                # 利润相关
                net_profit: 净利润,
                net_profit_yoy: 净利润同比增长,
                continuous_loss_years: 连续亏损年数,

                # 资产相关
                total_assets: 总资产,
                net_assets: 净资产,  # 净资产为负说明资不抵债

                # 负债相关
                debt_ratio: 资产负债率,

                # 流动性相关
                current_ratio: 流动比率,

                # 营收相关
                revenue: 营业收入,
                revenue_yoy: 营收同比增长,

                # 其他
                audit_opinion: 审计意见,  # 0=标准无保留, 1=带强调事项段, etc
            }

        Returns:
            预警列表
        """
        warnings = []

        # 检查高风险预警
        high_warnings = self._check_high_risk(code, name, financial_data)
        warnings.extend(high_warnings)

        # 检查中风险预警
        medium_warnings = self._check_medium_risk(code, name, financial_data)
        warnings.extend(medium_warnings)

        # 检查低风险预警
        low_warnings = self._check_low_risk(code, name, financial_data)
        warnings.extend(low_warnings)

        # 记录预警
        if warnings:
            self._warning_records[code] = warnings

            # 处理中风险预警
            for warning in warnings:
                if warning.level == FinancialWarningLevel.MEDIUM:
                    self._handle_medium_warning(code)

        return warnings

    def _check_high_risk(self, code: str, name: str,
                        data: Dict) -> List[FinancialWarning]:
        """检查高风险预警"""
        warnings = []
        high_config = config.FINANCIAL_WARNING_CONFIG["high"]

        # 连续2年亏损
        continuous_loss_years = data.get("continuous_loss_years", 0)
        if continuous_loss_years >= 2:
            warnings.append(FinancialWarning(
                code=code,
                name=name,
                level=FinancialWarningLevel.HIGH,
                indicators={"continuous_loss_years": continuous_loss_years},
                description=f"连续 {continuous_loss_years} 年亏损",
            ))

        # 净资产为负
        net_assets = data.get("net_assets", 0)
        if net_assets < 0:
            warnings.append(FinancialWarning(
                code=code,
                name=name,
                level=FinancialWarningLevel.HIGH,
                indicators={"net_assets": net_assets},
                description="净资产为负（资不抵债）",
            ))

        # 审计无法表示意见或否定意见
        audit_opinion = data.get("audit_opinion", 0)
        if audit_opinion in [3, 4]:  # 3=无法表示意见, 4=否定意见
            warnings.append(FinancialWarning(
                code=code,
                name=name,
                level=FinancialWarningLevel.HIGH,
                indicators={"audit_opinion": audit_opinion},
                description=f"审计意见异常（code={audit_opinion}）",
            ))

        return warnings

    def _check_medium_risk(self, code: str, name: str,
                          data: Dict) -> List[FinancialWarning]:
        """检查中风险预警"""
        warnings = []
        medium_config = config.FINANCIAL_WARNING_CONFIG["medium"]

        # 净利润同比下降50%
        net_profit_yoy = data.get("net_profit_yoy", 0)
        if net_profit_yoy is not None and net_profit_yoy <= -50:
            warnings.append(FinancialWarning(
                code=code,
                name=name,
                level=FinancialWarningLevel.MEDIUM,
                indicators={"net_profit_yoy": net_profit_yoy},
                description=f"净利润同比下降 {-net_profit_yoy:.1f}%",
            ))

        # 营收同比下降30%
        revenue_yoy = data.get("revenue_yoy", 0)
        if revenue_yoy is not None and revenue_yoy <= -30:
            warnings.append(FinancialWarning(
                code=code,
                name=name,
                level=FinancialWarningLevel.MEDIUM,
                indicators={"revenue_yoy": revenue_yoy},
                description=f"营收同比下降 {-revenue_yoy:.1f}%",
            ))

        # 流动比率<1
        current_ratio = data.get("current_ratio", 0)
        if 0 < current_ratio < 1:
            warnings.append(FinancialWarning(
                code=code,
                name=name,
                level=FinancialWarningLevel.MEDIUM,
                indicators={"current_ratio": current_ratio},
                description=f"流动比率 {current_ratio:.2f} < 1",
            ))

        return warnings

    def _check_low_risk(self, code: str, name: str,
                       data: Dict) -> List[FinancialWarning]:
        """检查低风险预警"""
        warnings = []

        # 应收账款异常增长（假设有相关字段）
        accounts_receivable_growth = data.get("accounts_receivable_growth", 0)
        if accounts_receivable_growth is not None and accounts_receivable_growth > 50:
            warnings.append(FinancialWarning(
                code=code,
                name=name,
                level=FinancialWarningLevel.LOW,
                indicators={"accounts_receivable_growth": accounts_receivable_growth},
                description=f"应收账款增长 {accounts_receivable_growth:.1f}%",
            ))

        # 存货周转下降（假设有相关字段）
        inventory_turnover_change = data.get("inventory_turnover_change", 0)
        if inventory_turnover_change is not None and inventory_turnover_change < -20:
            warnings.append(FinancialWarning(
                code=code,
                name=name,
                level=FinancialWarningLevel.LOW,
                indicators={"inventory_turnover_change": inventory_turnover_change},
                description=f"存货周转下降 {-inventory_turnover_change:.1f}%",
            ))

        # 毛利率下降
        gross_margin_change = data.get("gross_margin_change", 0)
        if gross_margin_change is not None and gross_margin_change < -5:
            warnings.append(FinancialWarning(
                code=code,
                name=name,
                level=FinancialWarningLevel.LOW,
                indicators={"gross_margin_change": gross_margin_change},
                description=f"毛利率下降 {-gross_margin_change:.1f}%",
            ))

        return warnings

    def _handle_medium_warning(self, code: str) -> None:
        """处理中风险预警，开始观察期"""
        if code not in self._medium_probation:
            self._medium_probation[code] = date.today()
            logger.info(f"股票 {code} 进入财务中风险观察期（{config.FINANCIAL_WARNING_CONFIG['medium']['probation_days']}天）")

            # 更新股票信息
            tier = self._pm.get_stock_tier(code)
            if tier:
                info = self._pm.get_stock_info(code, tier)
                if info:
                    info.financial_warning = FinancialWarningLevel.MEDIUM
                    info.warning_start_date = date.today()

    def should_downgrade(self, code: str, tier: PoolTier,
                        financial_data: Dict) -> Tuple[bool, str]:
        """
        判断是否应该因财务问题降级

        Returns:
            (should_downgrade, reason)
        """
        info = self._pm.get_stock_info(code, tier)
        if info is None:
            return False, ""

        # 检查是否有高风险预警
        warnings = self.check_warning(code, info.name, financial_data)
        for warning in warnings:
            if warning.level == FinancialWarningLevel.HIGH:
                return True, f"财务高风险: {warning.description}"

        # 检查中风险观察期
        if code in self._medium_probation:
            start_date = self._medium_probation[code]
            probation_days = config.FINANCIAL_WARNING_CONFIG["medium"]["probation_days"]

            if (date.today() - start_date).days >= probation_days:
                # 观察期结束，仍有中风险则降级
                for warning in warnings:
                    if warning.level == FinancialWarningLevel.MEDIUM:
                        return True, f"财务中风险观察期结束后仍存在问题: {warning.description}"

                # 观察期结束，问题已解决，移除记录
                del self._medium_probation[code]
                info.financial_warning = FinancialWarningLevel.NONE
                info.warning_start_date = None
                logger.info(f"股票 {code} 财务中风险观察期结束，问题已解决")

        return False, ""

    def check_batch(self, stocks_data: List[Dict]) -> Dict[str, List[FinancialWarning]]:
        """
        批量检查财务预警

        Args:
            stocks_data: [{
                code: str,
                name: str,
                financial_data: {...}
            }]

        Returns:
            {code: [warnings]}
        """
        results = {}
        for stock_data in stocks_data:
            code = stock_data.get("code")
            name = stock_data.get("name", "")
            financial_data = stock_data.get("financial_data", {})

            warnings = self.check_warning(code, name, financial_data)
            if warnings:
                results[code] = warnings

        return results

    def get_warning_summary(self) -> Dict[str, int]:
        """获取预警统计"""
        summary = {
            "high": 0,
            "medium": 0,
            "low": 0,
            "total": 0,
        }

        for code, warnings in self._warning_records.items():
            for warning in warnings:
                if warning.level == FinancialWarningLevel.HIGH:
                    summary["high"] += 1
                elif warning.level == FinancialWarningLevel.MEDIUM:
                    summary["medium"] += 1
                elif warning.level == FinancialWarningLevel.LOW:
                    summary["low"] += 1
                summary["total"] += 1

        return summary
