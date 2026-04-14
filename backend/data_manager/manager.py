"""
数据管理器 - Data Manager (单一数据入口)
==========================================
所有数据访问的唯一入口，统一管理数据获取、缓存、验证和存储。

核心职责：
1. 单一数据入口 - 所有数据获取都通过此类
2. 智能路由 - 根据数据类型选择合适的Provider
3. 统一缓存 - 整合所有缓存系统
4. 数据验证 - 写入前验证，读取时评分
5. 质量追踪 - 数据血缘和质量评分

数据分类:
- realtime: 实时行情 (5分钟TTL)
- financial: 财务数据 (24小时TTL)
- daily: 每日行情 (1天TTL)
- history: 历史数据 (永久)
- static: 静态数据 (7天TTL)
"""

import os
import json
import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import OrderedDict

logger = logging.getLogger(__name__)

# 导入现有模块
from .cache import CacheManager, get_cache_manager, DataValidator, DataQualityScorer, TTL_CONFIG
from .fetcher import (
    StockDataFetcher, MarketDataFetcher, FinancialDataFetcher, StockListFetcher,
    IndexDataFetcher,
    get_stock_data_api as fetcher_get_stock_data_api,
    get_single_stock_data as fetcher_get_single_stock_data
)
from .batcher import AsyncBatcher, get_batcher, BatchResult

# 导入Tushare Provider (如果存在)
try:
    from .providers.tushare import TushareProvider, get_tushare_provider
    TUSHARE_AVAILABLE = True
except ImportError:
    try:
        from backend.data_manager.providers.tushare import TushareProvider, get_tushare_provider
        TUSHARE_AVAILABLE = True
    except ImportError:
        TUSHARE_AVAILABLE = False
        TushareProvider = None
        get_tushare_provider = None

# ==================== 路径配置 ====================

DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 常量 ====================

DATA_CATEGORIES = {
    'realtime': {'ttl': 300, 'storage': 'memory+disk'},      # 5分钟
    'financial': {'ttl': 86400, 'storage': 'memory+disk'},   # 24小时
    'daily': {'ttl': 86400, 'storage': 'disk'},              # 1天
    'history': {'ttl': -1, 'storage': 'sqlite'},            # 永久
    'static': {'ttl': 604800, 'storage': 'memory+disk'},     # 7天
}

# 数据类别映射
CATEGORY_MAP = {
    'stock_list': 'static',
    'realtime': 'realtime',
    'financial': 'financial',
    'market': 'realtime',
    'daily': 'daily',
    'price': 'history',
    'cp_history': 'history',
}


def get_category(cache_type: str) -> str:
    """获取数据类型对应的数据类别"""
    return CATEGORY_MAP.get(cache_type, 'realtime')


# ==================== 统一缓存条目 ====================

class UnifiedCacheEntry:
    """统一缓存条目"""

    def __init__(self, data: Any, category: str, updated_at: str = None):
        self.data = data
        self.category = category
        self.updated_at = updated_at or datetime.now().isoformat()
        self.hit_count = 0
        self.last_access = time.time()
        self.source = None  # 数据来源标记

    def access(self):
        self.hit_count += 1
        self.last_access = time.time()

    def is_expired(self) -> bool:
        ttl = DATA_CATEGORIES.get(self.category, {}).get('ttl', 300)
        if ttl < 0:
            return False
        try:
            updated = datetime.fromisoformat(self.updated_at)
            age = (datetime.now() - updated).total_seconds()
            return age > ttl
        except:
            return True

    def to_dict(self) -> Dict:
        return {
            'data': self.data,
            'category': self.category,
            'updated_at': self.updated_at,
            'hit_count': self.hit_count,
            'source': self.source
        }


# ==================== 统一缓存管理器 ====================

class UnifiedCache:
    """统一缓存管理器（内存LRU + 磁盘持久化）"""

    def __init__(self, max_size: int = 500, hot_ttl: int = 3600):
        self.max_size = max_size
        self.hot_ttl = hot_ttl

        self._memory: OrderedDict[str, UnifiedCacheEntry] = OrderedDict()
        self._lock = threading.RLock()

        self._stats = {
            'hit': 0, 'miss': 0,
            'memory_hit': 0, 'disk_hit': 0,
        }

    def _make_key(self, cache_type: str, code: str = None) -> str:
        """生成统一的缓存key"""
        if code:
            return f"{cache_type}:{code}"
        return cache_type

    def get(self, cache_type: str, code: str = None) -> Optional[Any]:
        """获取缓存"""
        key = self._make_key(cache_type, code)
        category = get_category(cache_type)

        # 1. 先查内存缓存
        with self._lock:
            if key in self._memory:
                entry = self._memory[key]
                if not entry.is_expired():
                    entry.access()
                    self._memory.move_to_end(key)
                    self._stats['hit'] += 1
                    self._stats['memory_hit'] += 1
                    return entry.data
                else:
                    del self._memory[key]

        # 2. 查磁盘缓存
        disk_data = self._read_from_disk(cache_type, code)
        if disk_data is not None:
            # 重新加入内存缓存
            entry = UnifiedCacheEntry(disk_data, category)
            entry.source = 'disk'
            self._set_memory(key, entry)
            self._stats['hit'] += 1
            self._stats['disk_hit'] += 1
            return disk_data

        self._stats['miss'] += 1
        return None

    def _set_memory(self, key: str, entry: UnifiedCacheEntry):
        """加入内存缓存"""
        with self._lock:
            if key in self._memory:
                self._memory.move_to_end(key)
            else:
                if len(self._memory) >= self.max_size:
                    self._memory.popitem(last=False)
            self._memory[key] = entry

    def set(self, cache_type: str, data: Any, code: str = None, source: str = None):
        """写入缓存"""
        key = self._make_key(cache_type, code)
        category = get_category(cache_type)

        entry = UnifiedCacheEntry(data, category)
        entry.source = source or 'unknown'

        # 写入内存
        self._set_memory(key, entry)

        # 写入磁盘
        self._write_to_disk(cache_type, code, data, category)

    def _get_disk_path(self, cache_type: str, code: str = None) -> Path:
        """获取磁盘缓存路径"""
        if code:
            return DATA_DIR / f"{cache_type}_{code}.json"
        return DATA_DIR / f"{cache_type}.json"

    def _read_from_disk(self, cache_type: str, code: str = None) -> Optional[Any]:
        """从磁盘读取缓存"""
        path = self._get_disk_path(cache_type, code)
        if not path.exists():
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                cache = json.load(f)

            data = cache.get('data')
            if data is None:
                return None

            # 检查TTL
            updated_at = cache.get('updated_at', '')
            if updated_at:
                try:
                    updated = datetime.fromisoformat(updated_at)
                    category = get_category(cache_type)
                    ttl = DATA_CATEGORIES.get(category, {}).get('ttl', 300)
                    if ttl > 0 and (datetime.now() - updated).total_seconds() > ttl:
                        return None
                except:
                    pass

            return data
        except Exception as e:
            print(f"磁盘缓存读取失败 {path}: {e}")
            return None

    def _write_to_disk(self, cache_type: str, code: str, data: Any, category: str):
        """
        写入磁盘缓存（原子写入）

        实现：先写临时文件，成功后rename到目标文件
        好处：写入过程中崩溃不会损坏原文件
        """
        import tempfile
        import os

        path = self._get_disk_path(cache_type, code)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            cache = {
                'data': data,
                'category': category,
                'updated_at': datetime.now().isoformat(),
                'version': '2.0'
            }

            # 1. 先写临时文件
            fd, temp_path = tempfile.mkstemp(
                suffix='.json',
                prefix='cache_',
                dir=str(path.parent)
            )
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())  # 确保写入磁盘

                # 2. 原子重命名（覆盖原文件）
                os.replace(temp_path, path)
            except:
                # 写入失败，删除临时文件
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

        except Exception as e:
            print(f"磁盘缓存写入失败 {path}: {e}")

    def get_stats(self) -> Dict:
        """获取缓存统计"""
        total = self._stats['hit'] + self._stats['miss']
        hit_rate = self._stats['hit'] / total * 100 if total > 0 else 0
        return {
            **self._stats,
            'total': total,
            'hit_rate': round(hit_rate, 2),
            'memory_size': len(self._memory)
        }

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._memory.clear()


# ==================== 数据管理器 ====================

class DataManager:
    """
    数据管理器 - 单一数据入口

    所有数据访问都通过此类，确保：
    1. 数据获取路由到正确的Provider
    2. 缓存统一管理
    3. 数据验证和质量评分
    4. 数据一致性
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 统一缓存
        self._cache = UnifiedCache()

        # 数据验证器
        self._validator = DataValidator()

        # 质量评分器
        self._quality_scorer = DataQualityScorer()

        # Provider实例
        self._stock_fetcher = StockDataFetcher()
        self._market_fetcher = MarketDataFetcher()
        self._financial_fetcher = FinancialDataFetcher()
        self._stock_list_fetcher = StockListFetcher()
        self._index_fetcher = IndexDataFetcher()

        # Tushare Provider (如果可用)
        self._tushare = None
        if TUSHARE_AVAILABLE and get_tushare_provider:
            try:
                self._tushare = get_tushare_provider()
            except:
                pass

        # 统计信息
        self._stats = {
            'provider_calls': {},  # 各provider调用次数
            'cache_stats': {},
        }

        print(f"数据管理器初始化完成 (Tushare: {'可用' if self._tushare else '不可用'})")

    # ==================== 公共接口 ====================

    def get_stock_data(self, limit: int = 200) -> List[Dict]:
        """
        获取完整股票数据（行情+财务+战力）

        Returns:
            List[Dict]: 股票数据列表
        """
        return fetcher_get_stock_data_api(limit=limit)

    def get_single_stock(self, code: str) -> Optional[Dict]:
        """
        获取单只股票数据

        Args:
            code: 股票代码

        Returns:
            Dict: 股票数据
        """
        return fetcher_get_single_stock_data(code)

    def update_single_stock(self, code: str) -> bool:
        """
        更新单只股票数据（强制刷新）

        用于 UpdateScheduler 的差异化池更新策略。

        Args:
            code: 股票代码

        Returns:
            bool: 是否更新成功
        """
        try:
            # 1. 使缓存失效
            self.invalidate('realtime', code)
            self.invalidate('financial', code)

            # 2. 获取最新数据（不使用缓存）
            stock_data = fetcher_get_single_stock_data(code)
            if stock_data is None:
                logger.warning(f"更新股票 {code} 失败：获取数据为空")
                return False

            # 3. 获取财务数据（不使用缓存）
            financial_data = self._financial_fetcher.get_financial_data(code, use_cache=False)
            if financial_data:
                # 验证并缓存财务数据
                validated, warnings = self._validator.validate(financial_data)
                if warnings:
                    validated['_warnings'] = warnings
                quality = self._quality_scorer.calculate_quality_score(validated)
                validated['_quality'] = quality
                self._cache.set('financial', validated, code, source='financial_fetcher')

            # 4. 更新市场数据缓存
            market_data = self._market_fetcher.get_market_data([code], use_cache=False)
            if market_data:
                cache_key = f"market_{hash((code,))}"
                self._cache.set('market', market_data[0] if market_data else {}, code, source='market_fetcher')

            logger.debug(f"更新股票 {code} 成功")
            return True

        except Exception as e:
            logger.error(f"更新股票 {code} 失败: {e}")
            return False

    def get_market_data(self, codes: List[str], use_cache: bool = True) -> List[Dict]:
        """
        获取实时行情

        Args:
            codes: 股票代码列表
            use_cache: 是否使用缓存

        Returns:
            List[Dict]: 行情数据列表
        """
        cache_key = f"market_{hash(tuple(sorted(codes)))}"

        if use_cache:
            cached = self._cache.get('market', cache_key)
            if cached:
                return cached

        # 使用MarketDataFetcher获取
        data = self._market_fetcher.get_market_data(codes, use_cache=False)

        if use_cache and data:
            self._cache.set('market', data, cache_key, source='market_fetcher')

        return data

    def get_financial_data(self, code: str, use_cache: bool = True) -> Optional[Dict]:
        """
        获取财务数据（带验证和质量评分）

        Args:
            code: 股票代码
            use_cache: 是否使用缓存

        Returns:
            Dict: 财务数据（已验证）
        """
        cache_key = f"fin_{code}"

        if use_cache:
            cached = self._cache.get('financial', code)
            if cached:
                return cached

        # 获取数据
        data = self._financial_fetcher.get_financial_data(code, use_cache=False)

        if data is None:
            return None

        # 验证数据
        validated, warnings = self._validator.validate(data)
        if warnings:
            validated['_warnings'] = warnings

        # 质量评分
        quality = self._quality_scorer.calculate_quality_score(validated)
        validated['_quality'] = quality

        # 缓存
        if use_cache:
            self._cache.set('financial', validated, code, source='financial_fetcher')

        return validated

    def get_stock_list(self, use_cache: bool = True, force_refresh: bool = False) -> List[Dict]:
        """
        获取股票列表

        Args:
            use_cache: 是否使用缓存
            force_refresh: 是否强制刷新

        Returns:
            List[Dict]: 股票列表
        """
        if use_cache and not force_refresh:
            cached = self._cache.get('stock_list')
            if cached:
                return cached

        data = self._stock_list_fetcher.get_stock_list(force_refresh=force_refresh)

        if data is not None and len(data) > 0:
            records = data.to_dict('records') if hasattr(data, 'to_dict') else data
            self._cache.set('stock_list', records, source='stock_list_fetcher')
            return records

        return []

    def get_index_constituents(self, use_cache: bool = True, force_refresh: bool = False) -> Dict[str, List[Dict]]:
        """
        获取三大指数成分股

        Args:
            use_cache: 是否使用缓存
            force_refresh: 是否强制刷新

        Returns:
            {
                "hs300": [{"code": "600000", "name": "浦发银行"}, ...],
                "zz500": [...],
                "zz1000": [...],
            }
        """
        cache_key = "index_constituents"
        if use_cache and not force_refresh:
            cached = self._cache.get('static', cache_key)
            if cached:
                return cached

        data = self._index_fetcher.get_index_constituents(force_refresh=force_refresh)

        if data:
            self._cache.set('static', cache_key, data)
            return data

        return {}

    def get_tushare_data(self, code: str, data_type: str = 'daily', start_date: str = None, end_date: str = None) -> Optional[Dict]:
        """
        获取Tushare数据

        Args:
            code: 股票代码 (如 '000001' 或 '000001.SZ')
            data_type: 数据类型 ('daily', 'weekly', 'monthly', 'financial')
            start_date: 开始日期 (YYYYMMDD格式)
            end_date: 结束日期 (YYYYMMDD格式)

        Returns:
            Dict: Tushare数据
        """
        if not self._tushare:
            return None

        cache_key = f"ts_{data_type}_{code}"

        cached = self._cache.get('tushare', cache_key)
        if cached:
            return cached

        # 设置默认日期范围
        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

        if data_type == 'daily':
            klines = self._tushare.get_daily_kline(code, start_date, end_date)
            data = {'klines': klines, 'count': len(klines)}
        elif data_type == 'weekly':
            klines = self._tushare.get_weekly_kline(code, start_date, end_date)
            data = {'klines': klines, 'count': len(klines)}
        elif data_type == 'monthly':
            klines = self._tushare.get_monthly_kline(code, start_date, end_date)
            data = {'klines': klines, 'count': len(klines)}
        elif data_type == 'financial':
            data = self._tushare.get_financial_data(code)
        else:
            data = None

        if data:
            self._cache.set('tushare', data, cache_key, source='tushare')

        return data

    def get_history_price(self, code: str, days: int = 30) -> List[Dict]:
        """
        获取历史价格数据

        Args:
            code: 股票代码
            days: 天数

        Returns:
            List[Dict]: 历史价格数据
        """
        cache_key = f"price_{code}_{days}"

        cached = self._cache.get('history', cache_key)
        if cached:
            return cached

        # 计算日期范围
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days * 2)).strftime('%Y%m%d')

        # 优先使用Tushare
        if self._tushare:
            try:
                klines = self._tushare.get_daily_kline(code, start_date, end_date)
                if klines:
                    data = klines[-days:]  # 取最后days条
                    self._cache.set('history', data, cache_key, source='tushare')
                    return data
            except Exception as e:
                print(f"Tushare获取历史价格失败 {code}: {e}")

        # 备选：从JSON文件读取
        price_file = DATA_DIR / f"price_{code}.json"
        if price_file.exists():
            try:
                with open(price_file, 'r', encoding='utf-8') as f:
                    data = json.load(f).get('data', [])
                    if data:
                        self._cache.set('history', data, cache_key, source='file')
                        return data[-days:]
            except Exception as e:
                print(f"读取价格文件失败 {code}: {e}")

        return []

    def _convert_to_ts_code(self, code: str) -> str:
        """转换代码为Tushare格式"""
        code = code.strip().upper()
        if code.startswith(('SH', 'SZ')):
            code = code[2:]
        suffix = '.SH' if code.startswith('6') else '.SZ'
        return f"{code}{suffix}"

    def sync_klines_to_duckdb(self, codes: List[str] = None, days: int = 365) -> Dict:
        """
        从Tushare同步K线数据到DuckDB

        Args:
            codes: 股票代码列表，默认全部
            days: 同步天数

        Returns:
            Dict: 同步结果统计
        """
        try:
            from .duckdb_store import get_duckdb_store, KlineRecord
        except ImportError:
            return {'success': 0, 'failed': 0, 'error': 'DuckDB不可用'}

        if not self._tushare:
            return {'success': 0, 'failed': 0, 'error': 'Tushare不可用'}

        store = get_duckdb_store()
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 获取股票列表
        if codes is None:
            stock_list = self._tushare.get_stock_list()
            codes = [s['symbol'] for s in stock_list[:100]]  # 默认前100只

        success_count = 0
        failed_count = 0

        for code in codes:
            try:
                klines = self._tushare.get_daily_kline(code, start_date, end_date)
                if not klines:
                    failed_count += 1
                    continue

                records = []
                for k in klines:
                    records.append(KlineRecord(
                        code=code,
                        trade_date=k.get('trade_date', ''),
                        open=k.get('open', 0),
                        high=k.get('high', 0),
                        low=k.get('low', 0),
                        close=k.get('close', 0),
                        volume=k.get('volume', 0),
                        amount=k.get('amount', 0),
                        change_pct=k.get('change_pct', 0),
                        adj_close=k.get('close', 0)
                    ))

                if records:
                    store.insert_daily_klines_batch(records)
                    success_count += 1

                time.sleep(0.06)  # 避免超过限制

            except Exception as e:
                failed_count += 1
                print(f"同步K线失败 {code}: {e}")

        return {
            'success': success_count,
            'failed': failed_count,
            'total': len(codes)
        }

    # ==================== 批量操作 ====================

    def batch_get_financial(
        self,
        codes: List[str],
        use_cache: bool = True,
        concurrency: int = None
    ) -> BatchResult:
        """
        批量获取财务数据（并发）

        Args:
            codes: 股票代码列表
            use_cache: 是否使用缓存
            concurrency: 并发数，默认30

        Returns:
            BatchResult: 包含 success_count, failed_count, total_time, results, errors
        """
        batcher = get_batcher()

        # 创建包装函数，绑定 use_cache
        def fetch_one(code: str):
            return self.get_financial_data(code, use_cache=use_cache)

        return batcher.batch_get_financial(
            codes=codes,
            fetch_func=fetch_one,
            concurrency=concurrency
        )

    def batch_get_market(
        self,
        codes: List[str],
        use_cache: bool = True,
        concurrency: int = None
    ) -> Tuple[List[Dict], Dict[str, str]]:
        """
        批量获取行情数据（分批并发）

        Args:
            codes: 股票代码列表
            use_cache: 是否使用缓存
            concurrency: 并发批数，默认3

        Returns:
            (all_results, errors)
        """
        if not codes:
            return [], {}

        batcher = get_batcher()

        # 包装函数
        def fetch_batch(batch_codes: List[str]):
            return self.get_market_data(batch_codes, use_cache=use_cache)

        return batcher.batch_get_market(
            codes=codes,
            fetch_func=fetch_batch,
            batch_size=50,
            concurrency=concurrency
        )

    def batch_get_financial_sync(self, codes: List[str], use_cache: bool = True) -> Dict[str, Dict]:
        """
        批量获取财务数据（同步版本，兼容旧接口）

        Args:
            codes: 股票代码列表
            use_cache: 是否使用缓存

        Returns:
            Dict[str, Dict]: {code: data}
        """
        result = self.batch_get_financial(codes, use_cache=use_cache)
        return result.results

    def batch_get_market_sync(self, codes: List[str], use_cache: bool = True) -> List[Dict]:
        """
        批量获取行情数据（同步版本，兼容旧接口）

        Args:
            codes: 股票代码列表
            use_cache: 是否使用缓存

        Returns:
            List[Dict]: 行情数据列表
        """
        results, errors = self.batch_get_market(codes, use_cache=use_cache)
        return results

    # ==================== 缓存管理 ====================

    def invalidate(self, cache_type: str, code: str = None):
        """使缓存失效"""
        key = f"{cache_type}:{code}" if code else cache_type
        with self._cache._lock:
            self._cache._memory.pop(key, None)

        # 删除磁盘缓存
        if code:
            path = DATA_DIR / f"{cache_type}_{code}.json"
        else:
            path = DATA_DIR / f"{cache_type}.json"

        if path.exists():
            path.unlink()

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        return self._cache.get_stats()

    def get_data_quality(self, code: str) -> Dict:
        """获取数据质量评分"""
        return self._quality_scorer.get_data_quality('financial', code)

    # ==================== 数据验证 ====================

    def validate_data(self, data: Dict) -> Tuple[Dict, List[str]]:
        """验证数据"""
        return self._validator.validate(data)

    def calculate_quality_score(self, data: Dict) -> Dict:
        """计算质量评分"""
        return self._quality_scorer.calculate_quality_score(data)


# ==================== 全局单例 ====================

_data_manager = None


def get_data_manager() -> DataManager:
    """获取数据管理器单例"""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager


# ==================== 便捷函数 ====================

def get_stock_data_api(limit: int = 200) -> List[Dict]:
    """获取完整股票数据（兼容旧接口）"""
    return get_data_manager().get_stock_data(limit=limit)


def get_single_stock_data(code: str) -> Optional[Dict]:
    """获取单只股票数据（兼容旧接口）"""
    return get_data_manager().get_single_stock(code)


def get_market_data(codes: List[str], use_cache: bool = True) -> List[Dict]:
    """获取行情数据"""
    return get_data_manager().get_market_data(codes, use_cache=use_cache)


def get_financial_data(code: str, use_cache: bool = True) -> Optional[Dict]:
    """获取财务数据"""
    return get_data_manager().get_financial_data(code, use_cache=use_cache)


def get_stock_list(use_cache: bool = True, force_refresh: bool = False) -> List[Dict]:
    """获取股票列表"""
    return get_data_manager().get_stock_list(use_cache=use_cache, force_refresh=force_refresh)


def get_tushare_data(ts_code: str, data_type: str = 'complete') -> Optional[Dict]:
    """获取Tushare数据"""
    return get_data_manager().get_tushare_data(ts_code, data_type=data_type)
