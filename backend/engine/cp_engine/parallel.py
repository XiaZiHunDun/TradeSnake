"""
并行计算模块 v18.2

提供战力计算的并行化优化：
1. 多进程并行计算股票因子
2. 批量处理的并行归一化
3. 技术指标的并行计算

使用场景：
- 日内多次刷新时，多进程并行计算提升性能
- 大批量股票处理时（200+只）
"""

import os
import multiprocessing as mp
from typing import List, Dict, Callable, Any, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial
import numpy as np

# CPU核心数配置
DEFAULT_WORKERS = max(1, mp.cpu_count() - 1)
BATCH_SIZE = 50  # 每批处理数量


def _calculate_single_stock_factor(args: Tuple) -> Dict[str, float]:
    """
    计算单只股票的因子分数（用于并行计算）

    Args:
        args: (code, name, price, pe, roe, net_profit_growth, revenue_growth,
               change_pct, pb, gross_margin, cashflow, debt_ratio, sector)

    Returns:
        因子分数字典
    """
    (code, name, price, pe, roe, net_profit_growth, revenue_growth,
     change_pct, pb, gross_margin, cashflow, debt_ratio, sector) = args

    try:
        # 成长分
        net_g = max(0, min(300, net_profit_growth))
        rev_g = max(-50, min(100, revenue_growth))
        growth_score = net_g * 0.6 + rev_g * 0.4

        # 价值分
        base_roe = min(max(0, roe), 25)
        pe_score = 0
        if pe > 0:
            if 5 <= pe <= 20:
                pe_score = 10
            elif pe < 5:
                pe_score = 5
            elif 20 < pe <= 30:
                pe_score = 7
            elif 30 < pe <= 50:
                pe_score = 3
            elif pe > 50:
                pe_score = -5

        peg_bonus = 0
        peg = 0
        if pe > 0 and net_profit_growth > 0:
            peg = pe / net_profit_growth
            if peg <= 0.5:
                peg_bonus = 8
            elif peg <= 1:
                peg_bonus = 5
            elif peg <= 2:
                peg_bonus = 0
            else:
                peg_bonus = -5

        pb_score = 0
        if pb > 0:
            if pb <= 1:
                pb_score = 8
            elif pb <= 3:
                pb_score = 5
            elif pb <= 5:
                pb_score = 2
            elif pb > 10:
                pb_score = -3

        value_score = max(0, base_roe + pe_score + peg_bonus + pb_score * 0.3)

        # 质量分
        cf_score = 0
        if cashflow > 0 and roe > 0:
            cf_ratio = cashflow / (roe * 10 + 1)
            if 0.5 <= cf_ratio <= 3:
                cf_score = 15
            elif cf_ratio > 3:
                cf_score = 10
            else:
                cf_score = 5
        elif cashflow <= 0 and roe > 0:
            cf_score = -5

        gm_score = 0
        if gross_margin == 0 and roe > 10:
            gm_score = 8
        elif gross_margin > 30:
            gm_score = 10
        elif gross_margin > 15:
            gm_score = 6

        debt_score = 0
        if debt_ratio > 80:
            debt_score = -8
        elif debt_ratio > 60:
            debt_score = -4
        elif debt_ratio > 50:
            debt_score = 0
        else:
            debt_score = 3

        quality_score = max(0, cf_score + gm_score + debt_score)

        # 动量分（原始）
        momentum_score = max(-10, min(10, change_pct))

        # 风险分数
        risk_factors = []

        # PE风险
        if pe < 0:
            pe_risk = 100
        elif pe > 100:
            pe_risk = 80
        elif pe > 50:
            pe_risk = 50
        elif pe < 5 and pe > 0:
            pe_risk = 30
        else:
            pe_risk = 10
        risk_factors.append(('pe', pe_risk, 0.35))

        # ROE风险
        if roe < 0:
            roe_risk = 100
        elif roe < 5:
            roe_risk = 50
        elif roe < 10:
            roe_risk = 20
        else:
            roe_risk = 5
        risk_factors.append(('roe', roe_risk, 0.25))

        # 成长风险
        if net_profit_growth < -50:
            growth_risk = 100
        elif net_profit_growth < -20:
            growth_risk = 70
        elif net_profit_growth < 0:
            growth_risk = 40
        elif net_profit_growth > 100:
            growth_risk = 30
        else:
            growth_risk = 10
        risk_factors.append(('growth', growth_risk, 0.20))

        # 营收风险
        if revenue_growth < -30:
            rev_risk = 80
        elif revenue_growth < -10:
            rev_risk = 50
        elif revenue_growth < 0:
            rev_risk = 20
        else:
            rev_risk = 5
        risk_factors.append(('revenue', rev_risk, 0.10))

        # 波动风险
        if abs(change_pct) > 8:
            vol_risk = 100
        elif abs(change_pct) > 5:
            vol_risk = 60
        elif abs(change_pct) > 3:
            vol_risk = 30
        else:
            vol_risk = 10
        risk_factors.append(('volatility', vol_risk, 0.10))

        weighted_sum = sum(risk * weight for _, risk, weight in risk_factors)
        max_risk = max(risk for _, risk, _ in risk_factors)
        risk_score = min(100, 0.4 * max_risk + 0.6 * weighted_sum)

        return {
            'code': code,
            'name': name,
            'growth_score': growth_score,
            'value_score': value_score,
            'quality_score': quality_score,
            'momentum_score': momentum_score,
            'risk_score': risk_score,
            'peg': peg,
            'sector': sector,
            'success': True
        }

    except Exception as e:
        return {
            'code': code,
            'name': name,
            'error': str(e),
            'success': False
        }


class ParallelCalculator:
    """
    并行计算管理器 v18.2

    特性：
    - 多进程并行计算股票因子
    - 自动批量分割
    - 进度回调
    - 失败重试机制
    """

    def __init__(self, max_workers: int = None):
        """
        Args:
            max_workers: 最大并行进程数，默认为 CPU核心数-1
        """
        self.max_workers = max_workers or DEFAULT_WORKERS

    def calculate_batch(
        self,
        stocks_data: List[Dict],
        progress_callback: Callable[[int, int], None] = None
    ) -> List[Dict]:
        """
        批量并行计算股票因子

        Args:
            stocks_data: 股票数据列表，每项包含计算所需的字段
            progress_callback: 进度回调函数，签名为 (completed, total)

        Returns:
            计算结果列表
        """
        if not stocks_data:
            return []

        # 转换为元组格式
        args_list = [
            (
                s.get('code', ''),
                s.get('name', ''),
                s.get('price', 0),
                s.get('pe', 0),
                s.get('roe', 0),
                s.get('net_profit_growth', 0),
                s.get('revenue_growth', 0),
                s.get('change_pct', 0),
                s.get('pb', 0),
                s.get('gross_margin', 0),
                s.get('cashflow', 0),
                s.get('debt_ratio', 0),
                s.get('sector', ''),
            )
            for s in stocks_data
        ]

        results = []
        total = len(args_list)
        completed = 0

        # 使用进程池并行计算
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(_calculate_single_stock_factor, args): args[0]
                      for args in args_list}

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1

                if progress_callback and completed % 10 == 0:
                    progress_callback(completed, total)

        # 失败重试
        failed = [r for r in results if not r.get('success', False)]
        if failed:
            # 重试失败的计算
            retry_args = [(f['code'], f['name'], 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, '')
                         for f in failed]
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                retry_futures = {executor.submit(_calculate_single_stock_factor, args): args[0]
                                for args in retry_args}
                for future in as_completed(retry_futures):
                    result = future.result()
                    # 更新原结果
                    for r in results:
                        if r['code'] == result['code']:
                            r.update(result)

        return results

    def parallel_normalize(
        self,
        factor_values: Dict[str, List[float]],
        clip_percentile: float = 0.95
    ) -> Dict[str, List[float]]:
        """
        并行归一化多个因子

        Args:
            factor_values: {因子名: [值列表], ...}
            clip_percentile: 裁剪百分位

        Returns:
            {因子名: [归一化值], ...}
        """
        result = {}

        # 为每个因子创建并行任务
        with ThreadPoolExecutor(max_workers=len(factor_values)) as executor:
            futures = {}
            for factor_name, values in factor_values.items():
                future = executor.submit(
                    self._robust_normalize_parallel,
                    values,
                    clip_percentile
                )
                futures[future] = factor_name

            for future in as_completed(futures):
                factor_name = futures[future]
                result[factor_name] = future.result()

        return result

    @staticmethod
    def _robust_normalize_parallel(
        values: List[float],
        clip_percentile: float = 0.95
    ) -> List[float]:
        """单因子归一化（线程安全）"""
        if not values:
            return []

        arr = np.array(values, dtype=float)

        if len(arr) < 20:
            # 小数据集使用IQR
            q1 = np.percentile(arr, 25)
            q3 = np.percentile(arr, 75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
        else:
            # 大数据集使用百分位裁剪
            lower = np.percentile(arr, (1 - clip_percentile) * 50)
            upper = np.percentile(arr, clip_percentile * 50)

        if upper == lower:
            return [50.0] * len(values)

        clipped = np.clip(arr, lower, upper)
        normalized = ((clipped - lower) / (upper - lower)) * 100

        return normalized.tolist()


class BatchProcessor:
    """
    批处理处理器 v18.2

    用于日内多次刷新时的高效批量处理
    """

    def __init__(self, batch_size: int = BATCH_SIZE):
        """
        Args:
            batch_size: 批处理大小
        """
        self.batch_size = batch_size
        self.calculator = ParallelCalculator()

    def process_stocks(
        self,
        stocks_data: List[Dict],
        update_callback: Callable[[Dict], None] = None
    ) -> List[Dict]:
        """
        批量处理股票数据

        Args:
            stocks_data: 股票数据列表
            update_callback: 每批完成后的回调

        Returns:
            处理结果列表
        """
        results = []
        total = len(stocks_data)

        for i in range(0, total, self.batch_size):
            batch = stocks_data[i:i + self.batch_size]
            batch_results = self.calculator.calculate_batch(batch)

            for result in batch_results:
                if update_callback and result.get('success'):
                    update_callback(result)

            results.extend(batch_results)

        return results


# 全局并行计算器实例
_calculator: Optional[ParallelCalculator] = None


def get_parallel_calculator() -> ParallelCalculator:
    """获取全局并行计算器"""
    global _calculator
    if _calculator is None:
        _calculator = ParallelCalculator()
    return _calculator


def parallel_calculate_batch(
    stocks_data: List[Dict],
    progress_callback: Callable[[int, int], None] = None
) -> List[Dict]:
    """
    并行计算批量股票因子

    Args:
        stocks_data: 股票数据列表
        progress_callback: 进度回调

    Returns:
        计算结果列表
    """
    calculator = get_parallel_calculator()
    return calculator.calculate_batch(stocks_data, progress_callback)
