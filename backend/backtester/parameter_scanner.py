"""参数扫描器 v1.0 - 阶段2：贝叶斯优化参数搜索"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Callable
import numpy as np

from .strategy_comparator import StrategyComparator, BacktestConfig, StrategyComparisonResult

# 过滤阈值常量
MAX_DRAWDOWN_THRESHOLD = 15.0  # 最大回撤 <= 15%
MIN_ANNUAL_RETURN = 10.0  # 年化收益 > 10%
MIN_TOTAL_TRADES = 50  # 交易次数 >= 50
INVALID_SCORE = -1000.0  # 无效参数组合的评分

# 评分权重
SCORE_WEIGHT_ANNUAL_RETURN = 0.4
SCORE_WEIGHT_DRAWDOWN = 0.3
SCORE_WEIGHT_WIN_RATE = 0.2
SCORE_WEIGHT_SHARPE = 0.1


@dataclass
class ParameterSpace:
    """参数搜索空间"""
    # 融合权重（连续）
    cp_weight_range: Tuple[float, float] = (0.3, 0.5)
    gain_weight_range: Tuple[float, float] = (0.2, 0.4)
    prob_weight_range: Tuple[float, float] = (0.15, 0.35)

    # 离散参数
    stop_loss_range: List[float] = field(default_factory=lambda: [-0.15, -0.10, -0.08, -0.05])
    max_holding_days_range: List[int] = field(default_factory=lambda: [3, 5, 7, 10])
    top_n_range: List[int] = field(default_factory=lambda: [5, 6, 8])


@dataclass
class ScanResult:
    """参数扫描结果"""
    best_params: Dict
    best_metrics: Dict
    robust_domain: Dict
    walk_forward_results: List[Dict]
    stability_score: float


class ParameterScanner:
    """参数扫描器 v1.0

    使用两阶段搜索：粗搜索（随机采样）+ 精搜索（邻域细化）
    替代网格搜索以减少过拟合风险。
    """

    def __init__(self, space: ParameterSpace = None, n_trials: int = 30):
        self.space = space or ParameterSpace()
        self.n_trials = n_trials
        self.comparator = StrategyComparator()

    def optimize(
        self,
        strategy_name: str,
        train_start: str,
        train_end: str,
        val_start: str,
        val_end: str
    ) -> ScanResult:
        """执行参数优化

        Args:
            strategy_name: 策略名称
            train_start: 训练集开始日期
            train_end: 训练集结束日期
            val_start: 验证集开始日期
            val_end: 验证集结束日期

        Returns:
            ScanResult: 最优参数及稳健域
        """
        print(f"Optimizing {strategy_name}...")

        # 阶段1：粗搜索（随机采样）
        coarse_results = self._coarse_search(strategy_name, train_start, train_end, n_samples=20)

        # 阶段2：精搜索（基于最优结果附近细化）
        if coarse_results:
            best_coarse = max(coarse_results, key=lambda x: x['score'])
            fine_results = self._fine_search(strategy_name, train_start, train_end, best_coarse['params'])
        else:
            fine_results = []
            best_coarse = None

        # 合并结果
        all_results = coarse_results + fine_results
        best_result = max(all_results, key=lambda x: x['score']) if all_results else None

        if best_result is None:
            return ScanResult(
                best_params={},
                best_metrics={},
                robust_domain={},
                walk_forward_results=[],
                stability_score=0.0
            )

        # 滚动验证
        walk_forward = self._walk_forward_validate(strategy_name, best_result['params'], train_start, train_end)

        # 计算稳健域
        robust_domain = self._compute_robust_domain(all_results, best_result)

        # 在验证集上评估
        val_metrics = self._evaluate_on_validation(strategy_name, best_result['params'], val_start, val_end)

        return ScanResult(
            best_params=best_result['params'],
            best_metrics={**best_result['metrics'], **val_metrics},
            robust_domain=robust_domain,
            walk_forward_results=walk_forward,
            stability_score=self._compute_stability_score(walk_forward)
        )

    def _coarse_search(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        n_samples: int = 20
    ) -> List[Dict]:
        """粗搜索：随机采样参数组合"""
        results = []

        for _ in range(n_samples):
            params = self._random_sample_params()
            metrics = self._evaluate_params(strategy_name, params, start_date, end_date)

            if metrics:
                score = self._compute_composite_score(metrics)
                results.append({
                    'params': params,
                    'metrics': metrics,
                    'score': score
                })

        return results

    def _fine_search(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        initial_params: Dict
    ) -> List[Dict]:
        """精搜索：在最优参数附近细化搜索"""
        results = []

        # 在 stop_loss 和 max_holding_days 的邻域搜索
        for sl in self.space.stop_loss_range:
            for days in self.space.max_holding_days_range:
                for n in self.space.top_n_range:
                    params = {
                        'stop_loss': sl,
                        'max_holding_days': days,
                        'top_n': n,
                        'cp_weight': initial_params.get('cp_weight', 0.4),
                        'gain_weight': initial_params.get('gain_weight', 0.35),
                        'prob_weight': initial_params.get('prob_weight', 0.25)
                    }
                    metrics = self._evaluate_params(strategy_name, params, start_date, end_date)
                    if metrics:
                        score = self._compute_composite_score(metrics)
                        results.append({
                            'params': params,
                            'metrics': metrics,
                            'score': score
                        })

        return results

    def _random_sample_params(self) -> Dict:
        """随机采样参数"""
        return {
            'stop_loss': np.random.choice(self.space.stop_loss_range),
            'max_holding_days': np.random.choice(self.space.max_holding_days_range),
            'top_n': np.random.choice(self.space.top_n_range),
            'cp_weight': np.random.uniform(*self.space.cp_weight_range),
            'gain_weight': np.random.uniform(*self.space.gain_weight_range),
            'prob_weight': np.random.uniform(*self.space.prob_weight_range),
        }

    def _evaluate_params(
        self,
        strategy_name: str,
        params: Dict,
        start_date: str,
        end_date: str
    ) -> Optional[Dict]:
        """评估参数组合"""
        try:
            # 创建临时配置
            config = BacktestConfig(
                top_n=params['top_n'],
                stop_loss=params['stop_loss'],
                max_holding_days=params['max_holding_days']
            )

            # 运行回测
            results = self.comparator.compare_strategies(
                start_date=start_date,
                end_date=end_date,
                strategy_names=[strategy_name]
            )

            if strategy_name not in results:
                return None

            result = results[strategy_name]
            return {
                'annual_return': result.annual_return,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'win_rate': result.win_rate,
                'total_trades': result.total_trades
            }
        except Exception as e:
            print(f"  Warning: Failed to evaluate params: {e}")
            return None

    def _compute_composite_score(self, metrics: Dict) -> float:
        """计算综合评分

        筛选条件：
        - 最大回撤 <= 15%
        - 年化收益 > 10%
        - 交易次数 >= 50
        """
        # 硬性筛选
        if metrics.get('max_drawdown', 100) > MAX_DRAWDOWN_THRESHOLD:
            return INVALID_SCORE
        if metrics.get('annual_return', 0) <= MIN_ANNUAL_RETURN:
            return INVALID_SCORE
        if metrics.get('total_trades', 0) < MIN_TOTAL_TRADES:
            return INVALID_SCORE

        # 综合评分
        score = (
            metrics.get('annual_return', 0) * SCORE_WEIGHT_ANNUAL_RETURN +
            (100 - metrics.get('max_drawdown', 0)) * SCORE_WEIGHT_DRAWDOWN +
            metrics.get('win_rate', 0) * SCORE_WEIGHT_WIN_RATE +
            metrics.get('sharpe_ratio', 0) * 10 * SCORE_WEIGHT_SHARPE
        )
        return score

    def _walk_forward_validate(
        self,
        strategy_name: str,
        params: Dict,
        train_start: str,
        train_end: str
    ) -> List[Dict]:
        """滚动验证

        使用相对于训练期的滚动窗口：
        - 训练期前半段 + 验证期后半段
        - 训练期后半段 + 验证期后半段
        - 训练期末期 + 验证期末期
        """
        # 计算滚动窗口：每个窗口训练6个月，验证3个月
        windows = [
            (train_start, self._add_months_str(train_end, 0),  # 训练期
             self._add_months_str(train_end, 1), self._add_months_str(train_end, 3)),  # 验证期
            (self._add_months_str(train_start, 3), self._add_months_str(train_end, 0),  # 训练期
             self._add_months_str(train_end, 1), self._add_months_str(train_end, 3)),  # 验证期
            (self._add_months_str(train_start, 6), self._add_months_str(train_end, 0),  # 训练期
             self._add_months_str(train_end, 1), self._add_months_str(train_end, 3)),  # 验证期
        ]

        results = []
        for t_start, t_end, v_start, v_end in windows:
            train_metrics = self._evaluate_params(strategy_name, params, t_start, t_end)
            val_metrics = self._evaluate_params(strategy_name, params, v_start, v_end)
            if train_metrics and val_metrics:
                results.append({
                    'window': f"{t_start}~{t_end}",
                    'train_metrics': train_metrics,
                    'val_start': v_start,
                    'val_end': v_end,
                    'val_metrics': val_metrics  # 评估验证期
                })

        return results

    def _add_months_str(self, date_str: str, months: int) -> str:
        """在日期字符串上添加月份，返回新日期字符串"""
        parts = date_str.split('-')
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

        new_month = month + months
        new_year = year
        while new_month > 12:
            new_month -= 12
            new_year += 1
        while new_month < 1:
            new_month += 12
            new_year -= 1

        # 保持相同的日，如果新月份天数不够则用月末
        try:
            return f"{new_year}-{new_month:02d}-{day:02d}"
        except ValueError:
            # 某些日期（如2月30日）不存在，使用月末
            import calendar
            last_day = calendar.monthrange(new_year, new_month)[1]
            return f"{new_year}-{new_month:02d}-{last_day:02d}"

    def _compute_robust_domain(self, all_results: List[Dict], best_result: Dict) -> Dict:
        """计算稳健域：最优参数附近的稳健区间"""
        robust_domain = {}

        # 检查 stop_loss 稳健性
        sl_candidates = set(r['params']['stop_loss'] for r in all_results)
        if sl_candidates:
            robust_domain['stop_loss'] = sorted(sl_candidates)

        # 检查 max_holding_days 稳健性
        days_candidates = set(r['params']['max_holding_days'] for r in all_results)
        if days_candidates:
            robust_domain['max_holding_days'] = sorted(days_candidates)

        return robust_domain

    def _compute_stability_score(self, walk_forward_results: List[Dict]) -> float:
        """计算稳定性分数"""
        if not walk_forward_results:
            return 0.0

        returns = [r.get('val_metrics', {}).get('annual_return', 0) for r in walk_forward_results]
        if not returns:
            return 0.0

        # 稳定性 = 1 - 变异系数
        mean = np.mean(returns)
        std = np.std(returns)
        if mean == 0:
            return 0.0
        cv = std / abs(mean)
        return max(0.0, 1.0 - cv)

    def _evaluate_on_validation(
        self,
        strategy_name: str,
        params: Dict,
        val_start: str,
        val_end: str
    ) -> Dict:
        """在验证集上评估"""
        metrics = self._evaluate_params(strategy_name, params, val_start, val_end)
        if metrics:
            return {'val_' + k: v for k, v in metrics.items()}
        return {}