"""
涨幅预测器模块

基于技术指标的规则模型预测股票未来N日涨幅：
- 每日收盘后执行一次
- 预测结果存储到 prediction_store（90天）

设计文档：docs/plans/engine/gain_predictor/GAIN_PREDICTOR.md
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, date as date_type
import logging

from .features import calculate_features, GLOBAL_AVG_VOLATILITY
logger = logging.getLogger(__name__)


# 板块涨跌幅限制配置（与 cp_engine/filters.py 保持一致，使用 gem/star/bge/main 命名）
BOARD_LIMIT_CONFIG = {
    'main': 10,      # 主板
    'gem': 20,       # 创业板（300开头）
    'star': 20,      # 科创板（688开头）
    'bge': 30,       # 北交所（4/8开头）
}


@dataclass
class GainPrediction:
    """单只股票涨幅预测"""
    code: str
    name: str
    predicted_gain_3d: float  # 预测3日涨幅%
    predicted_gain_5d: float  # 预测5日涨幅%
    confidence: float  # 置信度 0-1
    confidence_interval_3d: Tuple[float, float]  # 3日置信区间
    confidence_interval_5d: Tuple[float, float]  # 5日置信区间
    features: Dict[str, float]  # 主要特征值
    model_version: str = "rule_v19.8"


@dataclass
class GainPredictionResult:
    """批量涨幅预测结果"""
    predictions: List[GainPrediction]
    calculated_at: str
    data_timestamp: str
    stock_count: int
    distribution: Dict[str, float]  # 预测分布统计
    avg_confidence: float


class GainPredictor:
    """涨幅预测器（ML 优先，规则兜底）"""

    def __init__(self):
        self.model_version = "rule_v19.8"
        self._ml_model = None
        self._ml_checked = False

    def _get_ml_model(self):
        if self._ml_checked:
            return self._ml_model
        self._ml_checked = True
        try:
            from backend.ml.model import StockPredictor
            predictor = StockPredictor()
            if predictor.load("latest"):
                self._ml_model = predictor
                self.model_version = f"lgbm_{predictor.train_date or 'unknown'}"
        except Exception as e:
            logger.warning(f"ML模型加载失败，将使用规则预测: {e}")
        return self._ml_model

    def predict(self, klines_dict: Dict[str, List[Dict]]) -> GainPredictionResult:
        """批量预测股票涨幅

        Args:
            klines_dict: {code: [klines]} 股票代码到K线数据的映射
                        K线按日期升序排列

        Returns:
            GainPredictionResult 批量预测结果
        """
        predictions = []
        total_confidence = 0.0

        for code, klines in klines_dict.items():
            if not klines:
                continue

            name = klines[-1].get('name', klines[-1].get('code', code))
            features = calculate_features(klines)

            pred = self._predict_single(code, name, features, klines)
            if pred:
                predictions.append(pred)
                total_confidence += pred.confidence

        # 排序：按预测5日涨幅降序
        predictions.sort(key=lambda x: x.predicted_gain_5d, reverse=True)

        # 计算分布统计
        distribution = self._calc_distribution(predictions)

        avg_confidence = total_confidence / len(predictions) if predictions else 0.0

        return GainPredictionResult(
            predictions=predictions,
            calculated_at=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            data_timestamp = next((
                self._convert_trade_date(klines[-1].get('trade_date'))
                for klines in klines_dict.values() if klines
            ), datetime.now().strftime("%Y-%m-%d")),
            stock_count=len(predictions),
            distribution=distribution,
            avg_confidence=avg_confidence
        )

    def _predict_single(self, code: str, name: str,
                       features: Dict[str, float],
                       klines: List[Dict]) -> Optional[GainPrediction]:
        """预测单只股票涨幅"""
        if len(klines) < 5:
            return None

        # ========== 综合预测公式 ==========
        # predicted = 动量因子 × 波动率调整 + 趋势加成 + RSI调整 + MACD调整

        # 动量因子
        momentum = (features.get('gain_3d', 0) * 0.4 +
                   features.get('gain_5d', 0) * 0.3 +
                   features.get('gain_10d', 0) * 0.3)

        # 波动率调整
        volatility = features.get('volatility_20d', GLOBAL_AVG_VOLATILITY)
        volatility_factor = min(volatility / 30.0, 1.5)

        # 趋势加成
        ma_position = features.get('ma_position', 1.0)
        trend_bonus = (ma_position - 1.0) * 20 if ma_position > 1 else 0

        # RSI调整（超买超卖修正）
        rsi = features.get('rsi_14', 50)
        rsi_bonus = 0
        if rsi < 30:
            rsi_bonus = (30 - rsi) / 10 * 1.5  # 超卖加成
        elif rsi > 70:
            rsi_bonus = (70 - rsi) / 10 * 1.5  # 超买减成

        # MACD调整（金叉死叉信号）
        macd_cross = features.get('macd_cross', 0)
        macd_bonus = macd_cross * 1.0  # 金叉+1，死叉-1

        # 综合预测
        predicted = (momentum * volatility_factor + trend_bonus +
                     rsi_bonus + macd_bonus)

        # ========== 涨跌停处理 ==========
        predicted = self._apply_limit_adjustment(predicted, klines)

        # ========== 预测3日和5日 ==========
        # 3日预测：主要基于短期动量和RSI
        predicted_gain_3d = (features.get('gain_3d', 0) * 0.6 +
                            rsi_bonus * 0.5 +
                            macd_bonus * 0.3)
        predicted_gain_3d = self._apply_limit_adjustment(predicted_gain_3d, klines)

        # 5日预测：使用综合预测
        predicted_gain_5d = predicted

        # 限制在合理范围内
        predicted_gain_3d = max(-30.0, min(30.0, predicted_gain_3d))
        predicted_gain_5d = max(-50.0, min(50.0, predicted_gain_5d))

        # ========== 置信度计算 ==========
        confidence = min(0.6 + 0.4 * (1 - volatility / 50), 0.95)

        # ========== 置信区间（基于实际预测值计算） ==========
        interval_width_3d = volatility * 0.4 * confidence
        confidence_interval_3d = (
            max(predicted_gain_3d - interval_width_3d, -30.0),
            min(predicted_gain_3d + interval_width_3d, 30.0)
        )
        interval_width_5d = volatility * 0.4 * confidence * 1.5
        confidence_interval_5d = (
            max(predicted_gain_5d - interval_width_5d, -50.0),
            min(predicted_gain_5d + interval_width_5d, 50.0)
        )

        return GainPrediction(
            code=code,
            name=name,
            predicted_gain_3d=round(predicted_gain_3d, 2),
            predicted_gain_5d=round(predicted_gain_5d, 2),
            confidence=round(confidence, 3),
            confidence_interval_3d=tuple(round(x, 2) for x in confidence_interval_3d),
            confidence_interval_5d=tuple(round(x, 2) for x in confidence_interval_5d),
            features={
                'gain_3d': round(float(features.get('gain_3d', 0)), 2),
                'gain_5d': round(float(features.get('gain_5d', 0)), 2),
                'gain_10d': round(float(features.get('gain_10d', 0)), 2),
                'gain_20d': round(float(features.get('gain_20d', 0)), 2),
                'volatility_20d': round(float(features.get('volatility_20d', 0)), 2),
                'atr_14': round(float(features.get('atr_14', 0)), 2),
                'ma_position': round(float(features.get('ma_position', 1.0)), 4),
                'ma10_position': round(float(features.get('ma10_position', 1.0)), 4),
                'rsi_14': round(float(features.get('rsi_14', 50)), 1),
                'macd': round(float(features.get('macd', 0)), 4),
                'macd_signal': round(float(features.get('macd_signal', 0)), 4),
                'macd_cross': float(features.get('macd_cross', 0)),
                'limit_up': float(features.get('limit_up', 0)),
                'limit_down': float(features.get('limit_down', 0)),
                'volume_ratio': round(float(features.get('volume_ratio', 1.0)), 2),
            },
            model_version=self.model_version
        )

    def _apply_limit_adjustment(self, predicted: float, klines: List[Dict]) -> float:
        """应用涨跌停限制调整"""
        if not klines:
            return predicted

        today_change = klines[-1].get('change_pct', 0)
        board_type = self._get_board_type(klines[-1].get('code', ''))
        limit_pct = BOARD_LIMIT_CONFIG.get(board_type, 10)

        # 涨停
        if today_change >= limit_pct - 0.1:
            return float(max(predicted, 5.0))  # 最低5%涨幅

        # 跌停
        if today_change <= -limit_pct + 0.1:
            return float(min(predicted, -3.0))  # 最高-3%跌幅

        # 正常：限制在板块涨跌幅内
        return float(max(-limit_pct, min(limit_pct, predicted)))

    def _get_board_type(self, code: str) -> str:
        """根据代码判断板块类型（与 cp_engine/cp_engine.py board_type 属性一致）"""
        code_clean = code.replace('sz', '').replace('sh', '').lower()
        if code_clean.startswith('688'):
            return 'star'
        elif code_clean.startswith('300'):
            return 'gem'
        elif code_clean.startswith('4') or code_clean.startswith('8'):
            return 'bge'
        else:
            return 'main'

    def _calc_distribution(self, predictions: List[GainPrediction]) -> Dict[str, float]:
        """计算预测分布统计"""
        if not predictions:
            return {}

        gains = [p.predicted_gain_5d for p in predictions]

        return {
            'mean': round(sum(gains) / len(gains), 2),
            'min': round(min(gains), 2),
            'max': round(max(gains), 2),
            'positive_count': sum(1 for g in gains if g > 0),
            'negative_count': sum(1 for g in gains if g < 0),
        }

    def _convert_trade_date(self, trade_date) -> str:
        """将 trade_date 转换为字符串格式"""
        if trade_date is None:
            return datetime.now().strftime("%Y-%m-%d")
        if isinstance(trade_date, str):
            return trade_date
        if isinstance(trade_date, (datetime, date_type)):
            return trade_date.strftime("%Y-%m-%d")
        # pandas Timestamp
        return str(trade_date)

    def to_dict(self, result: GainPredictionResult) -> Dict:
        """转换为字典格式"""
        return {
            'predictions': [
                {
                    'code': p.code,
                    'name': p.name,
                    'predicted_gain_3d': p.predicted_gain_3d,
                    'predicted_gain_5d': p.predicted_gain_5d,
                    'confidence': p.confidence,
                    'confidence_interval_3d': list(p.confidence_interval_3d),
                    'confidence_interval_5d': list(p.confidence_interval_5d),
                    'features': p.features,
                    'model_version': p.model_version,
                }
                for p in result.predictions
            ],
            'calculated_at': result.calculated_at,
            'data_timestamp': result.data_timestamp,
            'stock_count': result.stock_count,
            'distribution': result.distribution,
            'avg_confidence': result.avg_confidence,
        }

    def save_to_store(self, result: GainPredictionResult, date: str = None) -> int:
        """保存预测结果到 prediction_store

        Args:
            result: 预测结果
            date: 日期，默认当天

        Returns:
            保存的股票数量
        """
        from backend.data_manager.prediction_store import get_prediction_store

        if date is None:
            from datetime import datetime
            date = datetime.now().strftime("%Y-%m-%d")

        predictions = [
            {
                'code': p.code,
                'name': p.name,
                'predicted_gain_3d': p.predicted_gain_3d,
                'predicted_gain_5d': p.predicted_gain_5d,
                'confidence': p.confidence,
                'confidence_interval_3d': p.confidence_interval_3d,
                'confidence_interval_5d': p.confidence_interval_5d,
                'features': p.features,
                'model_version': p.model_version,
            }
            for p in result.predictions
        ]

        store = get_prediction_store()
        return store.record_gain_predictions(predictions, date)

    def backtest_historical(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        save_to_store: bool = True
    ) -> Dict:
        """历史回测：基于历史K线数据验证预测准确性

        对指定日期区间内的每个交易日进行预测，并追踪未来N日的实际涨幅，
        以评估规则模型的预测准确性。

        Args:
            codes: 股票代码列表
            start_date: 回测开始日期 (YYYY-MM-DD)
            end_date: 回测结束日期 (YYYY-MM-DD)
            save_to_store: 是否保存每日预测结果到 prediction_store

        Returns:
            回测结果统计，包含以下字段：
            - total_predictions: 总预测次数
            - mean_error: 平均预测误差 (predicted - actual)
            - mean_abs_error: 平均绝对误差
            - accuracy_within_5pct: 预测误差<=5%的比例 (%)
            - accuracy_within_10pct: 预测误差<=10%的比例 (%)
            - top_k_accuracy: 预测涨幅前10%的股票中，实际上涨的比例 (%)
            - cumulative_return: 累计收益率 (%)，假设每日买入预测涨幅前10只
            - sharpe_ratio: 夏普比率
            - errors: 最多10个错误记录

        Prediction Approach:
            1. 滚动窗口：每日使用该日期之前的历史K线（最多60天）计算特征
            2. 特征计算：调用 calculate_features() 提取动量、波动率、趋势、RSI、MACD等指标
            3. 预测生成：应用综合预测公式（动量因子 x 波动率调整 + 趋势加成 + RSI调整 + MACD调整）
            4. 涨跌停处理：根据当日涨跌停状态调整预测值
            5. 实际涨幅对比：5日后获取实际收盘价，计算真实收益率
            6. 统计评估：汇总所有预测-实际对，计算误差统计和高级指标

        Note:
            - 每个交易日只使用该日期之前的数据，避免前视偏差
            - 实际涨幅计算使用复权收盘价
            - TopK准确率和累计收益使用每日预测涨幅前10%的股票
        """
        from backend.data_manager.duckdb_store import get_duckdb_store
        from datetime import datetime, timedelta

        duckdb = get_duckdb_store()
        results = []
        errors = []

        # 遍历每一天
        current_date = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        while current_date <= end:
            date_str = current_date.strftime("%Y-%m-%d")
            date_klines = {}

            for code in codes:
                try:
                    # 获取该日期之前的历史K线（用于计算特征）
                    klines = duckdb.get_klines(
                        code,
                        start_date=start_date,
                        end_date=date_str,
                        limit=60  # 至少60天数据
                    )
                    # P0-1/P0-2: klines is QueryResult, extract data and convert to List[Dict]
                    if klines.success and klines.data is not None and len(klines.data) > 0:
                        df = klines.data
                        # Convert DataFrame to list of dicts, sorted ASC by date (oldest first)
                        klines_list = df.to_dict('records')
                        klines_list.sort(key=lambda x: x.get('trade_date', ''))
                        date_klines[code] = klines_list
                except Exception as e:
                    errors.append(f"{code}@{date_str}: {e}")

            if date_klines:
                # 执行预测
                prediction_result = self.predict(date_klines)

                # 计算实际涨幅（用预测后的N日实际涨幅）
                for pred in prediction_result.predictions:
                    actual_result = self._get_actual_gain(
                        duckdb, pred.code, date_str, 5
                    )
                    if actual_result is not None:
                        results.append({
                            'date': date_str,
                            'code': pred.code,
                            'predicted_gain_5d': pred.predicted_gain_5d,
                            'actual_gain_5d': actual_result,
                            'error': pred.predicted_gain_5d - actual_result,
                            'abs_error': abs(pred.predicted_gain_5d - actual_result),
                        })

                # 保存到 store
                if save_to_store:
                    self.save_to_store(prediction_result, date_str)

            # 下一天
            current_date += timedelta(days=1)

        # 计算统计
        if not results:
            return {'error': 'No valid results', 'details': errors}

        df_len = len(results)
        mean_error = sum(r['error'] for r in results) / df_len
        mean_abs_error = sum(r['abs_error'] for r in results) / df_len
        accuracy_5pct = sum(1 for r in results if r['abs_error'] <= 5) / df_len * 100
        accuracy_10pct = sum(1 for r in results if r['abs_error'] <= 10) / df_len * 100

        # ===== 新增评估指标 =====

        # 1. TopK准确率：预测涨幅前10%的股票，实际上涨的比例
        sorted_by_pred = sorted(results, key=lambda x: x['predicted_gain_5d'], reverse=True)
        top_k_count = max(1, int(df_len * 0.1))  # 前10%
        top_k_actual_winners = sum(1 for r in sorted_by_pred[:top_k_count] if r['actual_gain_5d'] > 0)
        top_k_accuracy = top_k_actual_winners / top_k_count * 100 if top_k_count > 0 else 0

        # 2. 累计收益：假设每天按预测排序买入前10只，持有5天
        daily_returns = []
        for r in results:
            if r['actual_gain_5d'] > 0:
                daily_returns.append(r['actual_gain_5d'] / 100)  # 转为小数
            else:
                daily_returns.append(r['actual_gain_5d'] / 100)
        cumulative_return = (1 + sum(daily_returns) / len(daily_returns)) ** len(daily_returns) - 1 if daily_returns else 0

        # 3. 夏普比率：(平均收益 - 无风险利率) / 收益标准差
        if daily_returns:
            import statistics
            mean_ret = statistics.mean(daily_returns)
            std_ret = statistics.stdev(daily_returns) if len(daily_returns) > 1 else 0
            risk_free_rate = 0.03 / 252  # 年化3%，日化
            sharpe_ratio = (mean_ret - risk_free_rate) / std_ret * (252 ** 0.5) if std_ret > 0 else 0
        else:
            sharpe_ratio = 0

        return {
            'total_predictions': df_len,
            'mean_error': round(mean_error, 2),
            'mean_abs_error': round(mean_abs_error, 2),
            'accuracy_within_5pct': round(accuracy_5pct, 1),
            'accuracy_within_10pct': round(accuracy_10pct, 1),
            # 新增指标
            'top_k_accuracy': round(top_k_accuracy, 1),  # Top10%预测准确率
            'cumulative_return': round(cumulative_return * 100, 2),  # 累计收益率%
            'sharpe_ratio': round(sharpe_ratio, 2),  # 夏普比率
            'errors': errors[:10]  # 最多10个错误
        }

    def _get_actual_gain(
        self,
        duckdb,
        code: str,
        date_str: str,
        days: int
    ) -> Optional[float]:
        """获取指定日期后N日的实际涨幅（使用复权价格）"""
        try:
            klines = duckdb.get_klines(code, start_date=date_str, limit=days + 1)
            # P0-3: DuckDB returns DESC order (newest first), so klines[0]=newest, klines[-1]=oldest
            if klines.success and klines.data is not None and len(klines.data) >= 2:
                klines_list = klines.data.to_dict('records')
                klines_list.sort(key=lambda x: x.get('trade_date', ''))

                # v19.9.11: 使用复权价格计算实际涨幅
                def get_adj_price(k):
                    close = float(k.get('close', 0))
                    adj_factor = float(k.get('adj_factor', 1.0))
                    adj_close = float(k.get('adj_close', 0))
                    if adj_factor > 1 and adj_close == 0:
                        return close * adj_factor
                    elif adj_close > 0:
                        return adj_close
                    return close

                start_price = get_adj_price(klines_list[-1])  # oldest
                end_price = get_adj_price(klines_list[0])     # newest
                if start_price > 0:
                    return (end_price - start_price) / start_price * 100
        except (ValueError, IndexError, ZeroDivisionError):
            pass
        return None


# 全局实例
_predictor: Optional[GainPredictor] = None


def get_gain_predictor() -> GainPredictor:
    """获取 GainPredictor 单例"""
    global _predictor
    if _predictor is None:
        _predictor = GainPredictor()
    return _predictor


def save_predictions_to_store(codes: List[str], data_manager=None, date: str = None) -> int:
    """批量计算并保存涨幅预测（便捷函数）

    Args:
        codes: 股票代码列表
        data_manager: data_manager 实例（可选）
        date: 日期，默认当天

    Returns:
        保存的股票数量
    """
    from datetime import datetime

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # 从 DuckDB 获取 K 线数据
    from backend.data_manager.duckdb_store import get_klines_bulk
    klines_dict_df = get_klines_bulk(codes, days=60)

    # 转换为 List[Dict] 格式（predictor.predict 需要的格式）
    klines_dict: Dict[str, List[Dict]] = {}
    for code, df in klines_dict_df.items():
        if df is not None and not df.empty:
            # DataFrame 按日期升序排列
            df_sorted = df.sort_values('trade_date')
            klines_dict[code] = df_sorted.to_dict('records')

    if not klines_dict:
        return 0

    predictor = get_gain_predictor()
    result = predictor.predict(klines_dict)

    if result and result.predictions:
        return predictor.save_to_store(result, date)
    return 0
