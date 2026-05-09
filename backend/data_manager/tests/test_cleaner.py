"""
DataCleaner 单元测试
"""

import pytest

from backend.data_manager.cleaner import DataCleaner, clean_data


class TestDataCleaner:
    """DataCleaner 测试类"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.cleaner = DataCleaner()

    def test_clean_realtime_data(self):
        """测试实时行情清洗"""
        raw_data = {
            'code': '000001',
            'date': '2024-01-01',
            'close': 10.5,
            'volume': 1000000,
            'pe': 15.0,
            'pb': 1.5,
        }

        cleaned, report = self.cleaner.clean(raw_data, 'realtime')
        assert cleaned is not None
        assert report is not None
        assert 'total' in report
        assert 'level' in report

    def test_clean_financial_data(self):
        """测试财务数据清洗"""
        raw_data = {
            'code': '000001',
            'report_date': '2024-03-31',
            'roe': 12.5,
            'net_profit': 100000000,
            'revenue': 500000000,
            'growth': 15.0,
        }

        cleaned, report = self.cleaner.clean(raw_data, 'financial')
        assert cleaned is not None
        assert report is not None

    def test_clean_empty_data(self):
        """测试空数据处理"""
        result, report = self.cleaner.clean({}, 'realtime')
        assert result is not None

    def test_normalize_format(self):
        """测试格式标准化"""
        data = {'date': '2024-01-01', 'code': '000001'}
        result = self.cleaner._normalize_format(data)
        assert result is not None


class TestCleanData:
    """clean_data函数测试"""

    def test_clean_data_function(self):
        """测试便捷函数"""
        raw_data = {
            'code': '000001',
            'date': '2024-01-01',
            'close': 10.5,
            'volume': 1000000,
        }

        cleaned, report = clean_data(raw_data, 'realtime')
        assert cleaned is not None
        assert report is not None


class TestDataQualityReport:
    """数据质量报告测试"""

    def test_quality_report_structure(self):
        """测试质量报告结构"""
        raw_data = {
            'code': '000001',
            'close': 10.5,
            'volume': 1000000,
            'open': 10.2,
            'high': 10.8,
            'low': 10.1,
        }

        cleaner = DataCleaner()
        _, report = cleaner.clean(raw_data, 'realtime')

        assert 'total' in report
        assert 'level' in report
        assert 'dimensions' in report
        assert 'completeness' in report['dimensions']
        assert 'accuracy' in report['dimensions']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
