"""因子归因器 v1.0 - 阶段3：IC分析 + 分组单调性验证"""

from dataclasses import dataclass
from typing import List, Dict, Tuple
from scipy import stats
import numpy as np


@dataclass
class ICResult:
    """IC分析结果"""
    factor_name: str
    ic_mean: float          # IC 均值
    ic_std: float           # IC 标准差
    ir: float               # IR = IC_mean / IC_std
    direction: str          # 'positive' / 'negative' / 'neutral'
    p_value: float          # 统计显著性


@dataclass
class GroupReturnResult:
    """分组收益结果"""
    group: str              # Q1 / Q2 / Q3 / Q4 / Q5
    avg_return: float
    n_samples: int


class FactorAttributor:
    """因子归因器 v1.0

    使用 IC（信息系数）分析 + 分组单调性验证。
    """

    # IC 方向判断阈值：|IC| > 此值认为因子方向明确
    DIRECTION_THRESHOLD = 0.02
    # 高相关性阈值：|相关系数| >= 此值认为因子高度相关
    HIGH_CORR_THRESHOLD = 0.7

    def __init__(self, n_groups: int = 5):
        self.n_groups = n_groups

    def _compute_ic(self, factors, returns):
        """计算两个数组之间的 IC（Spearman 相关系数）"""
        ic, p_value = stats.spearmanr(factors, returns)
        return ic, p_value

    def analyze(
        self,
        factor_data: Dict[str, Dict[str, float]],
        return_data: Dict[str, float],
        factor_names: List[str]
    ) -> Dict:
        """执行因子归因分析

        Args:
            factor_data: {date: {factor_name: value}} 因子数据
            return_data: {date: return_pct} 收益数据
            factor_names: 要分析的因子名称列表

        Returns:
            归因结果字典
        """
        # 1. IC 分析
        ic_results = self._compute_ic_series(factor_data, return_data, factor_names)

        # 2. 分组单调性验证
        group_results = self._compute_group_returns(factor_data, return_data, factor_names)

        # 3. 因子相关性矩阵
        correlation_matrix = self._compute_correlation_matrix(factor_data, factor_names)

        return {
            'ic_analysis': [ic.__dict__ for ic in ic_results],
            'group_returns': {k: [g.__dict__ for g in v] for k, v in group_results.items()},
            'correlation_matrix': correlation_matrix,
            'recommendation': self._generate_recommendation(ic_results, correlation_matrix)
        }

    def _compute_ic_series(
        self,
        factor_data: Dict[str, Dict[str, float]],
        return_data: Dict[str, float],
        factor_names: List[str]
    ) -> List[ICResult]:
        """计算各因子的 IC 序列"""
        results = []

        for factor_name in factor_names:
            factors = []
            returns = []

            for date, factor_values in factor_data.items():
                if date in return_data and factor_name in factor_values:
                    factors.append(factor_values[factor_name])
                    returns.append(return_data[date])

            if len(factors) < 10:
                continue

            # 计算 RankIC（使用 Spearman 相关系数）
            ic, p_value = stats.spearmanr(factors, returns)

            ic_result = ICResult(
                factor_name=factor_name,
                ic_mean=round(ic, 4) if not np.isnan(ic) else 0,
                # NOTE: ic_std 需要多期 IC 观测才能计算（时序滚动窗口）。
                # 当前单次 IC 计算无法提供标准差，IR = IC_mean / IC_std 需要
                # 多次观察才能稳定。此处设为 0.0，真实场景建议用滚动窗口估算。
                ic_std=0.0,
                ir=round(abs(ic) / 0.05, 2) if ic != 0 else 0,  # 简化 IR
                direction='positive' if ic > self.DIRECTION_THRESHOLD else ('negative' if ic < -self.DIRECTION_THRESHOLD else 'neutral'),
                p_value=round(p_value, 4) if not np.isnan(p_value) else 1.0
            )
            results.append(ic_result)

        return results

    def _compute_group_returns(
        self,
        factor_data: Dict[str, Dict[str, float]],
        return_data: Dict[str, float],
        factor_names: List[str]
    ) -> Dict[str, List[GroupReturnResult]]:
        """计算分组收益（验证单调性）"""
        group_results = {}

        for factor_name in factor_names:
            # 收集因子值和收益
            factor_values = []
            return_values = []

            for date, factor_dict in factor_data.items():
                if date in return_data and factor_name in factor_dict:
                    factor_values.append(factor_dict[factor_name])
                    return_values.append(return_data[date])

            if len(factor_values) < self.n_groups * 2:
                continue

            # 分组
            groups = self._divide_into_groups(factor_values, return_values)

            # 计算每组平均收益
            group_returns = []
            for q, (f_vals, r_vals) in groups.items():
                if r_vals:
                    group_returns.append(GroupReturnResult(
                        group=q,
                        avg_return=round(np.mean(r_vals), 4),
                        n_samples=len(r_vals)
                    ))

            group_results[factor_name] = group_returns

        return group_results

    def _divide_into_groups(
        self,
        factor_values: List[float],
        return_values: List[float]
    ) -> Dict[str, Tuple[List[float], List[float]]]:
        """将数据分成 n 组"""
        # 按因子值排序
        sorted_pairs = sorted(zip(factor_values, return_values), key=lambda x: x[0])

        # 分成 n 组
        n = len(sorted_pairs) // self.n_groups
        groups = {}

        for i in range(self.n_groups):
            q_name = f"Q{i + 1}"
            start_idx = i * n
            end_idx = start_idx + n if i < self.n_groups - 1 else len(sorted_pairs)

            q_factors = [p[0] for p in sorted_pairs[start_idx:end_idx]]
            q_returns = [p[1] for p in sorted_pairs[start_idx:end_idx]]

            groups[q_name] = (q_factors, q_returns)

        return groups

    def _check_monotonicity(self, group_returns: List[GroupReturnResult]) -> Dict:
        """检查单调性：Q5 应持续优于 Q1"""
        if len(group_returns) < 3:
            return {'monotonic': False, 'reason': 'insufficient data'}

        returns = [g.avg_return for g in sorted(group_returns, key=lambda x: x.group)]

        # 检查单调递增
        is_monotonic = all(returns[i] <= returns[i+1] for i in range(len(returns)-1))

        return {
            'monotonic': is_monotonic,
            'returns': returns
        }

    def _compute_correlation_matrix(
        self,
        factor_data: Dict[str, Dict[str, float]],
        factor_names: List[str]
    ) -> Dict[str, float]:
        """计算因子相关性矩阵"""
        matrix = {}

        for i, f1 in enumerate(factor_names):
            for f2 in factor_names[i+1:]:
                # 收集共同数据点
                f1_vals = []
                f2_vals = []

                for date, factors in factor_data.items():
                    if f1 in factors and f2 in factors:
                        f1_vals.append(factors[f1])
                        f2_vals.append(factors[f2])

                if len(f1_vals) > 10:
                    corr, _ = stats.pearsonr(f1_vals, f2_vals)
                    matrix[f'{f1}-{f2}'] = round(corr, 3)

        return matrix

    def _generate_recommendation(
        self,
        ic_results: List[ICResult],
        correlation_matrix: Dict[str, float]
    ) -> str:
        """生成优化建议"""
        recommendations = []

        # IC 分析建议
        sorted_by_ir = sorted(ic_results, key=lambda x: x.ir, reverse=True)
        if sorted_by_ir:
            best = sorted_by_ir[0]
            recommendations.append(
                f"{best.factor_name} 因子 IR 最高({best.ir})，建议增加权重"
            )

        # 相关性建议
        for pair, corr in correlation_matrix.items():
            if abs(corr) >= self.HIGH_CORR_THRESHOLD:
                recommendations.append(
                    f"{pair} 高度相关({corr})，可考虑合并"
                )

        return '; '.join(recommendations) if recommendations else '各因子表现正常'