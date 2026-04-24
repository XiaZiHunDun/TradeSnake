"""
战力因子缓存模块 v18.2

提供因子级缓存，避免重复计算：
1. 原始分数缓存（growth_score, value_score 等）
2. 归一化参数缓存（用于批量计算一致性）
3. 技术指标缓存
4. LRU 淘汰策略

适用场景：
- 日内多次刷新时，避免重复计算
- 批量处理时保持归一化一致性
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np


@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any
    created_at: datetime
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


@dataclass
class StockFactorCache:
    """
    单只股票因子缓存 v18.2

    存储股票的各类因子计算结果，避免重复计算
    """
    code: str
    name: str = ''

    # 原始分数（未归一化）
    raw_growth_score: float = 0
    raw_value_score: float = 0
    raw_momentum_score: float = 0
    raw_quality_score: float = 0

    # 归一化分数
    norm_growth_score: float = 0
    norm_value_score: float = 0
    norm_momentum_score: float = 0
    norm_quality_score: float = 0

    # 风险相关
    risk_score: float = 0
    peg: float = 0

    # 技术指标
    technical_signal: str = 'neutral'
    rsi: float = 0
    macd_histogram: float = 0

    # 缓存元数据
    calculated_at: datetime = field(default_factory=datetime.now)
    cache_ttl_seconds: int = 300  # 默认5分钟缓存

    # 归一化参数（用于批量一致性）
    norm_params: Dict = field(default_factory=dict)

    def is_expired(self, ttl: int = None) -> bool:
        """检查缓存是否过期"""
        if ttl is None:
            ttl = self.cache_ttl_seconds
        return datetime.now() > self.calculated_at + timedelta(seconds=ttl)

    def to_dict(self) -> Dict:
        """转换为字典（字段名与 StockCP.to_dict() 一致）"""
        return {
            'code': self.code,
            'name': self.name,
            'growth_score': self.raw_growth_score,
            'value_score': self.raw_value_score,
            'momentum_score': self.raw_momentum_score,
            'quality_score': self.raw_quality_score,
            'norm_growth_score': self.norm_growth_score,
            'norm_value_score': self.norm_value_score,
            'norm_momentum_score': self.norm_momentum_score,
            'norm_quality_score': self.norm_quality_score,
            'risk_score': self.risk_score,
            'peg': self.peg,
            'technical_signal': self.technical_signal,
            'rsi': self.rsi,
            'macd_histogram': self.macd_histogram,
            'calculated_at': self.calculated_at.isoformat(),
            'is_expired': self.is_expired(),
        }


class FactorCache:
    """
    因子缓存管理器 v18.2

    特性：
    - LRU 淘汰策略
    - TTL 过期机制
    - 批量缓存一致性保证
    - 统计信息收集
    """

    # 默认缓存配置
    DEFAULT_TTL = 300  # 5分钟
    MAX_CACHE_SIZE = 500  # 最多缓存500只股票

    def __init__(self, max_size: int = None, default_ttl: int = None):
        """
        Args:
            max_size: 最大缓存条目数（默认500）
            default_ttl: 默认缓存时间（秒，默认300）
        """
        self.max_size = max_size or self.MAX_CACHE_SIZE
        self.default_ttl = default_ttl or self.DEFAULT_TTL
        self._cache: Dict[str, StockFactorCache] = {}
        self._access_order: List[str] = []  # LRU 追踪
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
        }

    def get(self, code: str) -> Optional[StockFactorCache]:
        """
        获取缓存的股票因子

        Args:
            code: 股票代码

        Returns:
            StockFactorCache 或 None（缓存不存在或已过期）
        """
        code_upper = code.upper()

        if code_upper not in self._cache:
            self._stats['misses'] += 1
            return None

        entry = self._cache[code_upper]

        if entry.is_expired(self.default_ttl):
            self._remove(code_upper)
            self._stats['misses'] += 1
            return None

        # LRU 更新
        self._update_access(code_upper)
        self._stats['hits'] += 1

        return entry

    def set(self, code: str, cache: StockFactorCache) -> None:
        """
        设置股票因子缓存

        Args:
            code: 股票代码
            cache: StockFactorCache 对象
        """
        code_upper = code.upper()

        # 检查容量，必要时淘汰
        if code_upper not in self._cache and len(self._cache) >= self.max_size:
            self._evict_lru()

        cache.code = code_upper
        self._cache[code_upper] = cache
        self._update_access(code_upper)

    def _update_access(self, code: str) -> None:
        """更新 LRU 访问顺序"""
        if code in self._access_order:
            self._access_order.remove(code)
        self._access_order.append(code)

    def _evict_lru(self) -> None:
        """淘汰最少使用的缓存条目"""
        if not self._access_order:
            return

        oldest = self._access_order.pop(0)
        if oldest in self._cache:
            del self._cache[oldest]
            self._stats['evictions'] += 1

    def _remove(self, code: str) -> None:
        """移除缓存条目"""
        if code in self._cache:
            del self._cache[code]
        if code in self._access_order:
            self._access_order.remove(code)

    def invalidate(self, code: str = None) -> None:
        """
        使缓存失效

        Args:
            code: 股票代码，如果为 None 则清空所有缓存
        """
        if code is None:
            self._cache.clear()
            self._access_order.clear()
        else:
            self._remove(code.upper())

    def get_batch(self, codes: List[str]) -> Tuple[List[StockFactorCache], List[str]]:
        """
        批量获取缓存

        Args:
            codes: 股票代码列表

        Returns:
            (缓存命中列表, 未命中代码列表)
        """
        cached = []
        missed = []

        for code in codes:
            entry = self.get(code)
            if entry is not None:
                cached.append(entry)
            else:
                missed.append(code)

        return cached, missed

    def get_stats(self) -> Dict:
        """获取缓存统计信息"""
        total = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total if total > 0 else 0

        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'hit_rate': round(hit_rate * 100, 2),
            'evictions': self._stats['evictions'],
        }

    def get_norm_params(self) -> Dict[str, Tuple[float, float]]:
        """
        获取当前缓存的归一化参数

        用于批量计算时保持归一化一致性

        Returns:
            {factor_name: (lower, upper), ...}
        """
        params = {}
        for factor in ['growth', 'value', 'momentum', 'quality']:
            raw_key = f'raw_{factor}_score'
            norm_key = f'norm_{factor}_score'

            values = []
            for entry in self._cache.values():
                if not entry.is_expired(self.default_ttl):
                    raw = getattr(entry, raw_key, None)
                    norm = getattr(entry, norm_key, None)
                    if raw is not None and norm is not None:
                        values.append((raw, norm))

            if len(values) >= 2:
                # 使用缓存数据计算线性变换参数
                raws = [v[0] for v in values]
                norms = [v[1] for v in values]
                # 简单线性回归获取映射
                min_raw, max_raw = min(raws), max(raws)
                min_norm, max_norm = min(norms), max(norms)
                params[factor] = (min_raw, max_raw, min_norm, max_norm)

        return params


# 全局缓存实例
_global_cache: Optional[FactorCache] = None


def get_factor_cache() -> FactorCache:
    """获取全局因子缓存实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = FactorCache()
    return _global_cache


def cache_stock_factors(stock: 'StockCP', ttl: int = None) -> None:
    """
    将股票因子缓存到全局缓存

    Args:
        stock: StockCP 对象
        ttl: 缓存时间（秒）
    """
    cache = get_factor_cache()

    entry = StockFactorCache(
        code=stock.code,
        name=stock.name,
        raw_growth_score=stock.growth_score,
        raw_value_score=stock.value_score,
        raw_momentum_score=stock.momentum_score,
        raw_quality_score=stock.quality_score,
        norm_growth_score=stock.growth_score,
        norm_value_score=stock.value_score,
        norm_momentum_score=stock.momentum_score,
        norm_quality_score=stock.quality_score,
        risk_score=stock.risk_score,
        peg=stock.peg,
        technical_signal=getattr(stock, 'technical_signal', {}).get('signal', 'neutral'),
        rsi=getattr(stock, 'technical_signal', {}).get('rsi', 0),
        macd_histogram=getattr(stock, 'technical_signal', {}).get('macd', {}).get('histogram', 0),
        cache_ttl_seconds=ttl or FactorCache.DEFAULT_TTL,
    )

    cache.set(stock.code, entry)


def get_cached_stock_factors(code: str) -> Optional[StockFactorCache]:
    """获取缓存的股票因子"""
    return get_factor_cache().get(code)


def invalidate_cache(code: str = None) -> None:
    """使缓存失效"""
    get_factor_cache().invalidate(code)
