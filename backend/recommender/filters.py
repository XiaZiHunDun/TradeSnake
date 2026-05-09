"""
股票过滤器 - Stock Filters v18.4
=================================

提供多级风险过滤：
- ST股过滤
- 停牌过滤
- 涨跌停过滤
- 流动性过滤
- 数据质量过滤
"""

from typing import List, Dict


class StockFilter:
    """股票过滤器 v18.4"""

    # 涨跌停阈值（按板块，与 cp_engine 保持一致）
    LIMIT_THRESHOLDS = {
        'main': 9.9,      # 主板 ±9.9%
        'gem': 19.9,     # 创业板 ±19.9%
        'star': 19.9,    # 科创板 ±19.9%
        'bge': 29.9,     # 北交所 ±29.9%
        'st': 4.9,       # ST股特殊处理 ±4.9%
    }

    # 流动性最低阈值（日成交额，元）
    MIN_DAILY_AMOUNT = 10000000  # 1000万

    @staticmethod
    def filter_st_stock(stocks: List) -> List:
        """过滤ST/*ST/退市风险股票 v18.4

        识别规则（双重保障）：
        1. 股票名称包含 ST/*ST/SST/S*ST/S/SS/SSD/SSR/退 等前缀（与 cp_engine ST_PREFIXES 一致）
        2. engine返回的 is_st 标记
        """
        result = []
        for s in stocks:
            # 使用StockCP的is_st属性
            if getattr(s, 'is_st', False):
                continue
            # 备用：名称检查（与 cp_engine DataValidator.ST_PREFIXES 保持一致）
            name = getattr(s, 'name', '')
            st_patterns = ['ST', '*ST', 'SST', 'S*ST', 'S', 'SS', 'SSD', 'SSR', '退']
            if any(prefix in name.upper() for prefix in st_patterns):
                continue
            result.append(s)
        return result

    @staticmethod
    def filter_suspended(stocks: List) -> List:
        """过滤停牌股票 v18.4"""
        return [s for s in stocks if not getattr(s, 'is_suspended', False)]

    @staticmethod
    def filter_limit_up_down(stocks: List) -> List:
        """过滤涨跌停股票 v18.4

        规则：
        - 涨停不买（但可以卖）
        - 跌停不卖（但可以买）
        - 按板块差异化阈值
        """
        result = []
        for s in stocks:
            board_type = getattr(s, 'board_type', 'main')

            # 获取涨跌停阈值
            if getattr(s, 'is_st', False):
                threshold = 4.9  # ST股5%
            else:
                threshold = StockFilter.LIMIT_THRESHOLDS.get(board_type, 9.9)

            change_pct = getattr(s, 'change_pct', 0)

            # 涨停不买
            if change_pct >= threshold:
                continue

            result.append(s)
        return result

    @staticmethod
    def filter_liquidity(stocks: List, min_amount: float = None) -> List:
        """流动性过滤 v18.4

        Args:
            stocks: 股票列表
            min_amount: 最低日成交额，默认1000万
        """
        if min_amount is None:
            min_amount = StockFilter.MIN_DAILY_AMOUNT

        return [
            s for s in stocks
            if getattr(s, 'avg_daily_amount_20d', 0) >= min_amount
        ]

    @staticmethod
    def filter_by_board(stocks: List, boards: List[str]) -> List:
        """按板块过滤"""
        if not boards:
            return stocks
        return [s for s in stocks if getattr(s, 'board_type', '') in boards]

    @staticmethod
    def filter_by_price_range(stocks: List, min_price: float = 0, max_price: float = float('inf')) -> List:
        """按价格区间过滤"""
        return [s for s in stocks if min_price <= getattr(s, 'price', 0) <= max_price]

    @staticmethod
    def filter_by_pe(stocks: List, min_pe: float = 0, max_pe: float = 100) -> List:
        """按PE过滤"""
        return [s for s in stocks if min_pe <= getattr(s, 'pe', 0) <= max_pe]

    @staticmethod
    def filter_by_roe(stocks: List, min_roe: float = 0) -> List:
        """按ROE过滤"""
        return [s for s in stocks if getattr(s, 'roe', 0) >= min_roe]

    @staticmethod
    def filter_by_cp(stocks: List, min_cp: float = 0) -> List:
        """按战力过滤"""
        return [s for s in stocks if getattr(s, 'total_cp', 0) >= min_cp]

    @staticmethod
    def filter_by_risk(stocks: List, max_risk: float = 100) -> List:
        """按风险过滤"""
        return [s for s in stocks if getattr(s, 'risk_score', 100) <= max_risk]

    @staticmethod
    def filter_tradeable(stocks: List, for_newbie: bool = True) -> List:
        """过滤可交易股票"""
        if for_newbie:
            return [s for s in stocks if getattr(s, 'can_trade_newbie', False)]
        return stocks

    @staticmethod
    def filter_by_data_quality(stocks: List, min_quality: str = 'medium') -> List:
        """按数据质量过滤"""
        quality_order = {'low': 0, 'medium': 1, 'high': 2}
        min_level = quality_order.get(min_quality, 0)
        return [
            s for s in stocks
            if quality_order.get(getattr(s, 'data_quality', 'low'), 0) >= min_level
        ]

    @classmethod
    def apply_all_filters(cls, stocks: List, context: Dict = None) -> List:
        """应用完整过滤链 v18.4

        Args:
            stocks: 股票列表
            context: 过滤上下文，包含风险偏好等

        Returns:
            过滤后的股票列表
        """
        if context is None:
            context = {}

        risk_preference = context.get('risk_preference', 'balanced')

        result = stocks

        # P0 必须过滤
        filters = [
            ('st', cls.filter_st_stock),
            ('suspended', cls.filter_suspended),
            ('limit', cls.filter_limit_up_down),
            ('data_quality', cls.filter_by_data_quality),
        ]

        for name, func in filters:
            original_count = len(result)
            result = func(result)
            if len(result) != original_count:
                print(f"  过滤[{name}]: {original_count} -> {len(result)}")

        # P1 建议过滤
        if risk_preference != 'aggressive':
            # 流动性过滤（激进型不过滤）
            original_count = len(result)
            result = cls.filter_liquidity(result)
            if len(result) != original_count:
                print(f"  过滤[liquidity]: {original_count} -> {len(result)}")

        return result
