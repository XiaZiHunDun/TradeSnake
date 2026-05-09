"""测试统一缓存架构"""
import pytest
from backend.data_manager.cache import get_cache_path, HotColdCache, get_cache_manager
from backend.data_manager.manager import get_data_manager


def test_cache_path_format():
    """验证缓存路径格式为 DATA_DIR/{type}/{code}.json"""
    path = get_cache_path('financial', '000001')
    assert 'financial' in str(path)
    assert '000001' in str(path)
    # 应该是子目录结构
    parts = str(path).split('/')
    assert 'financial' in parts[-2:]  # 至少在路径中


def test_data_manager_uses_cache_manager():
    """验证 DataManager 使用 CacheManager"""
    dm = get_data_manager()
    cache = get_cache_manager().cache
    assert dm._cache is cache, "DataManager 应该使用 CacheManager 的缓存"


def test_hot_cold_cache_methods():
    """验证 HotColdCache 有 clear 和 get_all_codes"""
    cache = HotColdCache()
    assert hasattr(cache, 'clear')
    assert hasattr(cache, 'get_all_codes')
    assert callable(cache.clear)
    assert callable(cache.get_all_codes)