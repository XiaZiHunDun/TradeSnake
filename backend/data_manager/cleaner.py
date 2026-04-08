"""
数据清洗器 - Data Cleaner
=========================
职责：数据校验与清洗，确保数据质量

清洗8步流程：
1. 格式标准化 - 编码、日期、字段名统一
2. 必填字段检查 - code/trade_date/close不能为空
3. 重复数据检测 - 按(code, trade_date)去重
4. 数值范围校验 - 涨跌幅/PE/ROE等范围检查
5. 业务规则校验 - OCLC逻辑、财务勾稽关系
6. 缺失值处理 - 价格前向填充、财务标记null
7. 异常值处理 - ERROR/WARN/INFO三级标记
8. 质量评分 - A/B/C/D四级评级
"""

import math
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


# ==================== 常量定义 ====================

# 异常级别
LEVEL_ERROR = 'ERROR'   # 数据严重异常，标记无效
LEVEL_WARN = 'WARN'    # 数据可能异常，保留但标记
LEVEL_INFO = 'INFO'     # 数据正常，仅做记录

# 质量评分等级
QUALITY_LEVELS = [
    (90, 100, 'A', '优秀'),
    (70, 89, 'B', '良好'),
    (50, 69, 'C', '合格'),
    (0, 49, 'D', '较差'),
]


# ==================== 校验规则配置 ====================

# 行情数据校验规则
REALTIME_VALIDATION_RULES = {
    'change_pct': {'min': -40, 'max': 40, 'description': '涨跌幅(主板±20%,科创±40%)'},
    'volume': {'min': 0, 'description': '成交量>=0'},
    'close': {'min': 0.001, 'description': '收盘价>0'},
    'high': {'min': 0.001, 'description': '最高价>0'},
    'low': {'min': 0.001, 'description': '最低价>0'},
    'open': {'min': 0.001, 'description': '开盘价>0'},
    'pe': {'min': -1000, 'max': 10000, 'description': 'PE合理范围'},
}

# 财务数据校验规则
FINANCIAL_VALIDATION_RULES = {
    'roe': {'min': -100, 'max': 100, 'description': 'ROE范围'},
    'net_profit_growth': {'min': -100, 'max': 500, 'description': '净利润增长'},
    'revenue_growth': {'min': -50, 'max': 200, 'description': '营收增长'},
    'gross_margin': {'min': 0, 'max': 100, 'description': '毛利率'},
    'net_margin': {'min': -100, 'max': 100, 'description': '净利率'},
    'pe_ttm': {'min': -1000, 'max': 10000, 'description': 'PE(TTM)'},
    'pb': {'min': 0.001, 'max': 100, 'description': 'PB'},
}


# ==================== 工具函数 ====================

def normalize_date(value: Any) -> Optional[str]:
    """标准化日期格式"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d')
    if isinstance(value, str):
        # 尝试解析常见格式
        for fmt in ['%Y-%m-%d', '%Y%m%d', '%Y/%m/%d']:
            try:
                return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None


def normalize_code(value: Any) -> Optional[str]:
    """标准化股票代码"""
    if value is None:
        return None
    code = str(value).strip().zfill(6)
    return code if len(code) == 6 else None


def is_valid_trade_date(date_str: str) -> bool:
    """检查是否为有效交易日"""
    if not date_str:
        return False
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        # 简单检查：是否为周末
        return dt.weekday() < 5
    except:
        return False


# ==================== 业务规则校验器 ====================

class BusinessValidator:
    """业务规则校验器"""

    @staticmethod
    def validate_price_logic(data: dict) -> Tuple[dict, List[str]]:
        """验证OHLC价格逻辑"""
        warnings = []

        high = data.get('high', 0)
        low = data.get('low', 0)
        open_price = data.get('open', 0)
        close = data.get('close', 0)

        # 最高价 >= 最低价
        if high < low:
            warnings.append(f"最高价({high})低于最低价({low})")
            # 修正
            data['high'] = max(open_price, close, low)
            data['low'] = min(open_price, close, high)

        # 收盘价在最高最低价之间
        if close > high:
            warnings.append(f"收盘价({close})高于最高价({high})")
            data['close'] = high
        elif close < low:
            warnings.append(f"收盘价({close})低于最低价({low})")
            data['close'] = low

        # 开盘价在最高最低价之间
        if open_price > high:
            warnings.append(f"开盘价({open_price})高于最高价({high})")
            data['open'] = high
        elif open_price < low:
            warnings.append(f"开盘价({open_price})低于最低价({low})")
            data['open'] = low

        return data, warnings

    @staticmethod
    def validate_financial_consistency(data: dict) -> Tuple[dict, List[str]]:
        """验证财务数据勾稽关系"""
        warnings = []

        revenue = data.get('revenue')
        net_margin = data.get('net_margin')
        net_profit = data.get('net_profit')

        # 净利润 ≈ 营收 × 净利率（允许±5%误差）
        if revenue and net_margin is not None and net_profit:
            expected_profit = revenue * net_margin / 100
            if expected_profit != 0:
                error_ratio = abs(net_profit - expected_profit) / abs(expected_profit)
                if error_ratio > 0.05:
                    warnings.append(
                        f"净利润({net_profit})与营收×净利率({expected_profit:.2f})不一致，偏差{error_ratio*100:.1f}%"
                    )

        # 总资产 = 负债 + 所有者权益
        total_assets = data.get('total_assets')
        total_liab = data.get('total_liab')
        equity = data.get('equity')

        if total_assets and total_liab and equity:
            expected = total_liab + equity
            if expected != 0:
                error_ratio = abs(total_assets - expected) / abs(expected)
                if error_ratio > 0.01:
                    warnings.append(
                        f"资产负债表不平衡: 资产({total_assets}), 负债+权益({expected:.2f})"
                    )

        return data, warnings


# ==================== 缺失值处理器 ====================

class MissingValueHandler:
    """缺失值处理器"""

    @staticmethod
    def handle_price(data: dict, prev_data: dict = None) -> dict:
        """
        价格类缺失值处理
        - 前向填充：用昨收价填充
        """
        for field in ['open', 'high', 'low', 'close']:
            if field not in data or data[field] is None:
                if prev_data and prev_data.get('close'):
                    data[field] = prev_data['close']
                else:
                    data[field] = None

        # 涨跌额跟着收盘价一起填充
        if 'change' not in data or data['change'] is None:
            if prev_data and 'close' in prev_data and 'close' in data:
                data['change'] = data['close'] - prev_data['close']

        return data

    @staticmethod
    def handle_financial(data: dict) -> dict:
        """
        财务类缺失值处理
        - 标记null，不填充，保持真实性
        """
        financial_fields = [
            'roe', 'roe_dt', 'roe_yearly',
            'gross_margin', 'net_margin',
            'revenue_growth', 'net_profit_growth',
            'pe', 'pe_ttm', 'pb',
            'current_ratio', 'quick_ratio',
            'debt_ratio', 'cashflow',
        ]

        for field in financial_fields:
            if field in data and (data[field] is None or data[field] == ''):
                data[field] = None  # 保持null

        return data


# ==================== 异常值处理器 ====================

class AnomalyHandler:
    """异常值处理器"""

    def __init__(self):
        self.rules = {
            'realtime': REALTIME_VALIDATION_RULES,
            'financial': FINANCIAL_VALIDATION_RULES,
        }

    def process(self, data: dict, data_type: str) -> Tuple[dict, List[str]]:
        """处理异常值"""
        warnings = []
        errors = []

        rules = self.rules.get(data_type, {})

        for field, rule in rules.items():
            if field not in data:
                continue

            value = data[field]
            if value is None:
                continue

            try:
                val = float(value)

                # 范围检查
                min_val = rule.get('min')
                max_val = rule.get('max')

                if min_val is not None and val < min_val:
                    warnings.append(f"{field}={val} 低于最小值{min_val}")
                    data[f'_{field}_warn'] = True

                if max_val is not None and val > max_val:
                    warnings.append(f"{field}={val} 超过最大值{max_val}")
                    data[f'_{field}_warn'] = True

            except (ValueError, TypeError):
                errors.append(f"{field}={value} 类型错误")

        return data, warnings + errors

    def detect_price_anomaly(self, data: dict, prev_data: dict = None) -> List[str]:
        """检测价格异常（如涨跌停）"""
        warnings = []

        if not prev_data or 'close' not in prev_data:
            return warnings

        prev_close = prev_data.get('close', 0)
        if prev_close <= 0:
            return warnings

        current_close = data.get('close', 0)
        if current_close <= 0:
            return warnings

        change_pct = (current_close - prev_close) / prev_close * 100
        data['change_pct'] = change_pct

        # 主板涨跌超过20%
        if abs(change_pct) > 20:
            warnings.append(f"涨跌幅异常: {change_pct:.2f}%")

        return warnings


# ==================== 质量评分器 ====================

class DataQualityScorer:
    """数据质量评分器"""

    # 评分权重
    WEIGHTS = {
        'completeness': 0.30,   # 字段完整性
        'accuracy': 0.40,       # 数值准确性
        'timeliness': 0.20,    # 时效性
        'consistency': 0.10,   # 一致性
    }

    def calculate_score(self, data: dict) -> dict:
        """计算综合质量评分"""
        scores = {
            'completeness': self._calc_completeness(data),
            'accuracy': self._calc_accuracy(data),
            'timeliness': self._calc_timeliness(data),
            'consistency': self._calc_consistency(data),
        }

        # 加权求和
        total = sum(scores[k] * self.WEIGHTS[k] for k in scores)

        # 确定等级
        level, desc = self._get_level(total)

        return {
            'total': round(total, 1),
            'level': level,
            'description': desc,
            'dimensions': {k: round(v, 1) for k, v in scores.items()},
        }

    def _calc_completeness(self, data: dict) -> float:
        """计算完整性得分"""
        required_fields = ['code', 'close']
        optional_fields = ['open', 'high', 'low', 'volume', 'amount', 'change_pct']

        required_score = sum(1 for f in required_fields if data.get(f) is not None) / len(required_fields)
        optional_score = sum(1 for f in optional_fields if data.get(f) is not None) / len(optional_fields)

        return (required_score * 0.6 + optional_score * 0.4) * 100

    def _calc_accuracy(self, data: dict) -> float:
        """计算准确性得分"""
        error_count = sum(1 for k in data if k.startswith('_') and k.endswith('_error'))
        warning_count = sum(1 for k in data if k.startswith('_') and k.endswith('_warn'))

        base_score = 100
        base_score -= error_count * 20
        base_score -= warning_count * 5

        return max(0, base_score)

    def _calc_timeliness(self, data: dict) -> float:
        """计算时效性得分"""
        updated_at = data.get('_updated_at') or data.get('updated_at')

        if not updated_at:
            return 50

        try:
            if isinstance(updated_at, str):
                updated = datetime.fromisoformat(updated_at)
            else:
                updated = updated_at

            hours_old = (datetime.now() - updated).total_seconds() / 3600

            if hours_old < 1:
                return 100
            elif hours_old < 24:
                return 90
            elif hours_old < 72:
                return 70
            else:
                return max(30, 100 - (hours_old - 72) / 24 * 10)
        except:
            return 50

    def _calc_consistency(self, data: dict) -> float:
        """计算一致性得分"""
        # 简化版本：检查是否有校验警告
        warnings = data.get('__warnings', [])
        return max(0, 100 - len(warnings) * 5)

    def _get_level(self, score: float) -> Tuple[str, str]:
        """根据评分确定等级"""
        for min_score, max_score, level, desc in QUALITY_LEVELS:
            if min_score <= score <= max_score:
                return level, desc
        return 'D', '较差'


# ==================== 数据清洗器 ====================

class DataCleaner:
    """
    数据清洗器 - 核心类

    清洗8步流程：
    1. 格式标准化
    2. 必填字段检查
    3. 重复数据检测（由调用方保证，这里简化）
    4. 数值范围校验
    5. 业务规则校验
    6. 缺失值处理
    7. 异常值处理
    8. 质量评分
    """

    def __init__(self):
        self.business_validator = BusinessValidator()
        self.missing_handler = MissingValueHandler()
        self.anomaly_handler = AnomalyHandler()
        self.quality_scorer = DataQualityScorer()

    def clean(self, raw_data: dict, data_type: str, prev_data: dict = None) -> Tuple[dict, dict]:
        """
        清洗数据主流程

        Args:
            raw_data: 原始数据
            data_type: 数据类型 ('realtime', 'financial', 'daily')
            prev_data: 前一日数据（用于前向填充和异常检测）

        Returns:
            (cleaned_data, quality_report)
        """
        data = raw_data.copy()
        data['__warnings'] = []
        data['__errors'] = []
        data['_updated_at'] = datetime.now().isoformat()

        # 步骤1: 格式标准化
        data = self._normalize_format(data)

        # 步骤2: 必填字段检查
        data, passed = self._validate_required(data)
        if not passed:
            data['__valid'] = False
            return data, {'level': 'D', 'reason': '必填字段缺失', 'total': 0}

        # 步骤4: 数值范围校验
        data, issues = self.anomaly_handler.process(data, data_type)
        data['__warnings'].extend(issues)

        # 步骤5: 业务规则校验
        if data_type == 'realtime':
            data, warnings = self.business_validator.validate_price_logic(data)
            data['__warnings'].extend(warnings)
        elif data_type == 'financial':
            data, warnings = self.business_validator.validate_financial_consistency(data)
            data['__warnings'].extend(warnings)

        # 步骤6: 缺失值处理
        if data_type == 'realtime':
            data = self.missing_handler.handle_price(data, prev_data)
        else:
            data = self.missing_handler.handle_financial(data)

        # 步骤7: 价格异常检测
        if data_type == 'realtime' and prev_data:
            warnings = self.anomaly_handler.detect_price_anomaly(data, prev_data)
            data['__warnings'].extend(warnings)

        # 步骤8: 质量评分
        quality = self.quality_scorer.calculate_score(data)
        quality['warnings'] = data['__warnings']
        data['__quality'] = quality
        data['__valid'] = quality['level'] not in ['D']

        return data, quality

    def _normalize_format(self, data: dict) -> dict:
        """格式标准化"""
        # 日期格式统一
        if 'date' in data and 'trade_date' not in data:
            data['trade_date'] = normalize_date(data.pop('date'))

        # 股票代码标准化
        if 'code' in data:
            data['code'] = normalize_code(data['code'])
        if 'symbol' in data and 'code' not in data:
            data['code'] = normalize_code(data.pop('symbol'))

        return data

    def _validate_required(self, data: dict) -> Tuple[dict, bool]:
        """必填字段检查"""
        # 通用必填
        if not data.get('code'):
            data['__errors'].append('股票代码为空')
            return data, False

        if data.get('close') is None or data['close'] <= 0:
            data['__errors'].append('收盘价无效')
            return data, False

        return data, True


# ==================== 便捷函数 ====================

_cleaner = None


def get_cleaner() -> DataCleaner:
    """获取清洗器单例"""
    global _cleaner
    if _cleaner is None:
        _cleaner = DataCleaner()
    return _cleaner


def clean_data(raw_data: dict, data_type: str, prev_data: dict = None) -> Tuple[dict, dict]:
    """清洗数据的便捷函数"""
    return get_cleaner().clean(raw_data, data_type, prev_data)
