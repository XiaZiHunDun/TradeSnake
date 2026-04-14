"""
预测融合模块测试 - Test Fusion v19.8
"""

import pytest
from unittest.mock import Mock, MagicMock

from backend.recommender.fusion import PredictionFusion, FusionResult
from backend.engine import StockCP
from backend.engine.gain_predictor import GainPrediction
from backend.engine.probability_predictor import ProbabilityPrediction


class TestPredictionFusion:
    """测试 PredictionFusion 融合器"""

    def _create_mock_stock(self, code='000001', total_cp=75.0, risk_score=40):
        """创建模拟股票战力数据"""
        stock = Mock(spec=StockCP)
        stock.code = code
        stock.name = f'股票{code}'
        stock.total_cp = total_cp
        stock.risk_score = risk_score
        stock.volatility_20d = 25.0
        return stock

    def _create_mock_gain_pred(self, code='000001', predicted_gain_5d=5.0, confidence=0.7):
        """创建模拟涨幅预测"""
        return GainPrediction(
            code=code,
            name=f'股票{code}',
            predicted_gain_3d=2.5,
            predicted_gain_5d=predicted_gain_5d,
            confidence=confidence,
            confidence_interval_3d=(-5, 10),
            confidence_interval_5d=(-10, 20),
            features={'gain_3d': 3.0, 'gain_5d': 5.0, 'volatility_20d': 25.0, 'rsi_14': 55},
            model_version='rule_v19.8'
        )

    def _create_mock_prob_pred(self, code='000001', up_probability_5d=0.65, confidence=0.7):
        """创建模拟上涨概率预测"""
        return ProbabilityPrediction(
            code=code,
            name=f'股票{code}',
            up_probability_3d=0.6,
            up_probability_5d=up_probability_5d,
            confidence=confidence,
            risk_level='medium',
            features={'gain_3d': 3.0, 'volatility_20d': 25.0, 'rsi_14': 55},
            model_version='rule_v19.8'
        )

    def test_fuse_single_stock_with_all_predictions(self):
        """测试融合单只股票（同时有涨幅和概率预测）"""
        stock = self._create_mock_stock('000001', total_cp=80.0)
        gain_pred = self._create_mock_gain_pred('000001', predicted_gain_5d=8.0, confidence=0.75)
        prob_pred = self._create_mock_prob_pred('000001', up_probability_5d=0.7, confidence=0.75)

        result = PredictionFusion.fuse(stock, gain_pred, prob_pred, 'balanced')

        assert isinstance(result, FusionResult)
        assert result.code == '000001'
        assert result.total_cp == 80.0
        assert result.predicted_gain_5d == 8.0
        assert result.up_probability_5d == 0.7
        assert result.confidence == 0.75
        assert result.fused_score > 0  # 融合得分应该大于0

    def test_fuse_single_stock_with_only_gain_prediction(self):
        """测试融合单只股票（只有涨幅预测）"""
        stock = self._create_mock_stock('000001', total_cp=70.0)
        gain_pred = self._create_mock_gain_pred('000001', predicted_gain_5d=6.0, confidence=0.6)

        result = PredictionFusion.fuse(stock, gain_pred, None, 'balanced')

        assert result.code == '000001'
        assert result.predicted_gain_5d == 6.0
        assert result.up_probability_5d == 0.5  # 默认值
        assert result.confidence == 0.6

    def test_fuse_single_stock_with_only_prob_prediction(self):
        """测试融合单只股票（只有概率预测）"""
        stock = self._create_mock_stock('000001', total_cp=75.0)
        prob_pred = self._create_mock_prob_pred('000001', up_probability_5d=0.65, confidence=0.7)

        result = PredictionFusion.fuse(stock, None, prob_pred, 'balanced')

        assert result.code == '000001'
        assert result.predicted_gain_5d == 0  # 默认值
        assert result.up_probability_5d == 0.65

    def test_fuse_single_stock_with_no_predictions(self):
        """测试融合单只股票（无预测数据）"""
        stock = self._create_mock_stock('000001', total_cp=65.0)

        result = PredictionFusion.fuse(stock, None, None, 'balanced')

        assert result.code == '000001'
        assert result.total_cp == 65.0
        assert result.predicted_gain_5d == 0
        assert result.up_probability_5d == 0.5
        assert result.confidence == 0

    def test_fuse_batch_filters_low_probability(self):
        """测试批量融合（过滤低概率）"""
        stocks = [
            self._create_mock_stock('000001', total_cp=80.0),
            self._create_mock_stock('000002', total_cp=75.0),
        ]
        gain_predictions = {
            '000001': self._create_mock_gain_pred('000001', predicted_gain_5d=8.0),
            '000002': self._create_mock_gain_pred('000002', predicted_gain_5d=6.0),
        }
        prob_predictions = {
            # 000001 概率正常，000002 概率过低会被过滤
            '000001': self._create_mock_prob_pred('000001', up_probability_5d=0.7),
            '000002': self._create_mock_prob_pred('000002', up_probability_5d=0.3),  # 低于0.5阈值
        }

        results = PredictionFusion.fuse_batch(stocks, gain_predictions, prob_predictions, 'balanced')

        # 000002 应该被过滤掉（概率低于0.5）
        assert len(results) == 1
        assert results[0].code == '000001'

    def test_fuse_batch_filters_high_risk(self):
        """测试批量融合（过滤高风险）"""
        stocks = [
            self._create_mock_stock('000001', total_cp=80.0),
        ]
        gain_predictions = {
            '000001': self._create_mock_gain_pred('000001', predicted_gain_5d=8.0),
        }
        prob_predictions = {
            '000001': self._create_mock_prob_pred('000001', up_probability_5d=0.7),
        }
        prob_predictions['000001'].risk_level = 'high'

        results = PredictionFusion.fuse_batch(stocks, gain_predictions, prob_predictions, 'balanced')

        # 高风险应该被过滤
        assert len(results) == 0

    def test_fuse_batch_sorted_by_fused_score(self):
        """测试批量融合结果按融合得分排序"""
        stocks = [
            self._create_mock_stock('000001', total_cp=60.0),
            self._create_mock_stock('000002', total_cp=80.0),
            self._create_mock_stock('000003', total_cp=70.0),
        ]
        gain_predictions = {
            '000001': self._create_mock_gain_pred('000001', predicted_gain_5d=3.0),
            '000002': self._create_mock_gain_pred('000002', predicted_gain_5d=10.0),
            '000003': self._create_mock_gain_pred('000003', predicted_gain_5d=6.0),
        }
        prob_predictions = {
            '000001': self._create_mock_prob_pred('000001', up_probability_5d=0.55),
            '000002': self._create_mock_prob_pred('000002', up_probability_5d=0.8),
            '000003': self._create_mock_prob_pred('000003', up_probability_5d=0.65),
        }

        results = PredictionFusion.fuse_batch(stocks, gain_predictions, prob_predictions, 'balanced')

        assert len(results) == 3
        # 验证排序
        assert results[0].fused_rank == 1
        assert results[1].fused_rank == 2
        assert results[2].fused_rank == 3
        # 验证得分递减
        assert results[0].fused_score >= results[1].fused_score
        assert results[1].fused_score >= results[2].fused_score

    def test_fuse_different_risk_preferences(self):
        """测试不同风险偏好配置"""
        stock = self._create_mock_stock('000001', total_cp=80.0)
        gain_pred = self._create_mock_gain_pred('000001', predicted_gain_5d=10.0, confidence=0.8)
        prob_pred = self._create_mock_prob_pred('000001', up_probability_5d=0.75, confidence=0.8)

        result_conservative = PredictionFusion.fuse(stock, gain_pred, prob_pred, 'conservative')
        result_balanced = PredictionFusion.fuse(stock, gain_pred, prob_pred, 'balanced')
        result_aggressive = PredictionFusion.fuse(stock, gain_pred, prob_pred, 'aggressive')

        # 保守型融合得分应该最高（战力评分权重更大：cp=0.5 vs gain=0.4 vs prob=0.3）
        # 权重配置: conservative={'cp': 0.5, 'gain': 0.3, 'prob': 0.2}
        #           balanced={'cp': 0.4, 'gain': 0.35, 'prob': 0.25}
        #           aggressive={'cp': 0.3, 'gain': 0.4, 'prob': 0.3}
        assert result_conservative.fused_score >= result_balanced.fused_score
        assert result_balanced.fused_score >= result_aggressive.fused_score

    def test_to_dict(self):
        """测试转换为字典格式"""
        stock = self._create_mock_stock('000001', total_cp=75.0)
        gain_pred = self._create_mock_gain_pred('000001', predicted_gain_5d=5.0, confidence=0.7)
        prob_pred = self._create_mock_prob_pred('000001', up_probability_5d=0.65, confidence=0.7)

        result = PredictionFusion.fuse(stock, gain_pred, prob_pred, 'balanced')
        result_dict = PredictionFusion.to_dict(result)

        assert isinstance(result_dict, dict)
        assert result_dict['code'] == '000001'
        assert result_dict['total_cp'] == 75.0
        assert result_dict['predicted_gain_5d'] == 5.0
        assert result_dict['up_probability_5d'] == 0.65
        assert 'fused_score' in result_dict
        assert 'score_breakdown' in result_dict

    def test_get_risk_level_from_stock(self):
        """测试从战力数据推断风险等级"""
        # 高风险
        stock_high = self._create_mock_stock('000001', risk_score=80)
        assert PredictionFusion._get_risk_level(stock_high) == 'high'

        # 中风险
        stock_medium = self._create_mock_stock('000001', risk_score=60)
        assert PredictionFusion._get_risk_level(stock_medium) == 'medium'

        # 低风险
        stock_low = self._create_mock_stock('000001', risk_score=40)
        assert PredictionFusion._get_risk_level(stock_low) == 'low'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
