"""
缓存管理 - TradeSnake Cache Manager
===================================
1. 统一缓存格式：{data, updated_at, version}
2. 增量更新：追踪哪些股票需要更新
3. 数据验证：异常值检测和处理
4. 冷热分离：内存缓存 + 磁盘持久化

Version: 2.0 (统一格式)
"""

import os
import json
import math
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import OrderedDict

# 路径配置
DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 缓存版本
CACHE_VERSION = "2.0"

# TTL配置（秒）
TTL_CONFIG = {
    "stock_list": 7 * 24 * 3600,
    "financial": 24 * 3600,
    "daily_basic": 24 * 3600,
    "moneyflow": 24 * 3600,
    "trend": 3600,
    "price_hist": -1,
    "realtime": 5 * 60,
}

# 数据验证规则
VALIDATION_RULES = {
    "roe": {"min": -500, "max": 500, "default": 0, "flag": "abnormal_roe"},
    "roe_dt": {"min": -500, "max": 500, "default": 0, "flag": "abnormal_roe"},
    "roe_yearly": {"min": -500, "max": 500, "default": 0, "flag": "abnormal_roe"},
    "net_profit_growth": {"min": -2000, "max": 10000, "default": 0, "flag": "abnormal_growth"},
    "revenue_growth": {"min": -100, "max": 500, "default": 0, "flag": "abnormal_growth"},
    "pe": {"min": -1000, "max": 10000, "default": None, "flag": "abnormal_pe"},
    "pe_ttm": {"min": -1000, "max": 10000, "default": None, "flag": "abnormal_pe"},
    "pb": {"min": 0, "max": 50, "default": None, "flag": "abnormal_pb"},
    "market_cap": {"min": 0, "max": 100000, "default": None, "flag": "abnormal_market_cap"},
    "circ_market_cap": {"min": 0, "max": 100000, "default": None, "flag": "abnormal_market_cap"},
    "gross_margin": {"min": -50, "max": 99, "default": 0, "flag": "abnormal_margin"},
    "netprofit_margin": {"min": -300, "max": 100, "default": 0, "flag": "abnormal_margin"},
    "debt_ratio": {"min": 0, "max": 100, "default": 0, "flag": "abnormal_debt"},
    "current_ratio": {"min": 0, "max": 50, "default": None, "flag": "abnormal_current_ratio"},
    "quick_ratio": {"min": 0, "max": 50, "default": None, "flag": "abnormal_quick_ratio"},
}


# ==================== 工具函数 ====================

def json_serializable(obj):
    """将对象转换为JSON可序列化格式"""
    if isinstance(obj, dict):
        return {k: json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [json_serializable(v) for v in obj]
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif obj is None:
        return None
    return obj


def get_cache_path(cache_type: str, code: str = None) -> Path:
    """获取缓存文件路径"""
    if code:
        return DATA_DIR / f"{cache_type}_{code}.json"
    return DATA_DIR / f"{cache_type}.json"


# ==================== 数据验证 ====================

class DataValidator:
    """数据验证器"""

    @staticmethod
    def validate(data: Dict, rules: Dict = VALIDATION_RULES) -> tuple[Dict, List[str]]:
        """验证数据并标记异常值"""
        validated = data.copy()
        warnings = []

        for field, rule in rules.items():
            if field not in validated:
                continue

            value = validated[field]
            if value is None:
                continue

            try:
                val = float(value)

                if val < rule["min"] or val > rule["max"]:
                    warnings.append(f"{field}={val} 超出范围 [{rule['min']}, {rule['max']}]")

                    if rule["default"] is not None:
                        validated[field] = rule["default"]

                    validated[f"_{rule['flag']}"] = True
                else:
                    validated.pop(f"_{rule['flag']}", None)

            except (ValueError, TypeError):
                pass

        return validated, warnings

    @staticmethod
    def validate_required(data: Dict) -> bool:
        """检查必需字段是否有有效值"""
        has_roe = data.get("roe", 0) != 0
        has_growth = data.get("net_profit_growth", 0) != 0
        return has_roe or has_growth


# ==================== 冷热数据缓存 ====================

class CacheEntry:
    """缓存条目"""

    def __init__(self, data: Any, updated_at: str, code: str = None):
        self.data = data
        self.updated_at = updated_at
        self.code = code
        self.hit_count = 0
        self.last_access = time.time()

    def access(self):
        """记录访问"""
        self.hit_count += 1
        self.last_access = time.time()

    def is_expired(self, ttl: int) -> bool:
        """检查是否过期"""
        if ttl < 0:
            return False
        try:
            updated = datetime.fromisoformat(self.updated_at)
            age = (datetime.now() - updated).total_seconds()
            return age > ttl
        except:
            return True


class HotColdCache:
    """冷热分离缓存"""

    def __init__(self, max_hot_size: int = 500, hot_ttl: int = 3600):
        self.max_hot_size = max_hot_size
        self.hot_ttl = hot_ttl

        self._hot_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hot_lock = threading.RLock()

        self._stats = {
            "hit": 0, "miss": 0, "hot_hit": 0, "cold_hit": 0,
        }

    def get(self, cache_type: str, code: str = None) -> Optional[Any]:
        """获取缓存"""
        key = f"{cache_type}:{code}"

        with self._hot_lock:
            if key in self._hot_cache:
                entry = self._hot_cache[key]
                if not entry.is_expired(self.hot_ttl):
                    entry.access()
                    self._hot_cache.move_to_end(key)
                    self._stats["hit"] += 1
                    self._stats["hot_hit"] += 1
                    return entry.data
                else:
                    del self._hot_cache[key]

        cache_file = get_cache_path(cache_type, code)
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)

                updated_at = cache.get('updated_at', '')
                data = cache.get('data')

                entry = CacheEntry(data, updated_at, code)
                if not entry.is_expired(TTL_CONFIG.get(cache_type, 3600)):
                    self._set_hot(key, entry)
                    self._stats["hit"] += 1
                    self._stats["cold_hit"] += 1
                    return data
            except Exception:
                pass

        self._stats["miss"] += 1
        return None

    def _set_hot(self, key: str, entry: CacheEntry):
        """加入热缓存"""
        with self._hot_lock:
            if key in self._hot_cache:
                self._hot_cache.move_to_end(key)
            else:
                if len(self._hot_cache) >= self.max_hot_size:
                    self._hot_cache.popitem(last=False)
                self._hot_cache[key] = entry

    def set(self, cache_type: str, data: Any, code: str = None):
        """写入缓存"""
        key = f"{cache_type}:{code}"
        updated_at = datetime.now().isoformat()

        cache_file = get_cache_path(cache_type, code)
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache = {
                'data': json_serializable(data),
                'updated_at': updated_at,
                'version': CACHE_VERSION,
                'cache_type': cache_type
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"缓存写入失败: {e}")

        entry = CacheEntry(data, updated_at, code)
        self._set_hot(key, entry)

    def delete(self, cache_type: str, code: str = None):
        """删除缓存"""
        key = f"{cache_type}:{code}"

        with self._hot_lock:
            self._hot_cache.pop(key, None)

        cache_file = get_cache_path(cache_type, code)
        if cache_file.exists():
            cache_file.unlink()

    def get_stats(self) -> Dict:
        """获取缓存统计"""
        total = self._stats["hit"] + self._stats["miss"]
        hit_rate = self._stats["hit"] / total * 100 if total > 0 else 0
        return {
            **self._stats,
            "total": total,
            "hit_rate": round(hit_rate, 2),
            "hot_size": len(self._hot_cache)
        }

    def clear_hot(self):
        """清空热缓存"""
        with self._hot_lock:
            self._hot_cache.clear()


_hot_cold_cache = HotColdCache()


# ==================== 统一缓存管理器 ====================

class CacheManager:
    """统一缓存管理器（单例）"""

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

        self.validator = DataValidator()
        self.cache = _hot_cold_cache

        print(f"缓存管理器初始化完成 (v{CACHE_VERSION})")

    def get(self, cache_type: str, code: str = None, use_cache: bool = True) -> Optional[Dict]:
        """获取缓存"""
        if not use_cache:
            return None
        return self.cache.get(cache_type, code)

    def set(self, cache_type: str, data: Dict, code: str = None, validate: bool = True) -> Dict:
        """写入缓存"""
        if validate:
            data, warnings = self.validator.validate(data)
            if warnings:
                data["_warnings"] = warnings

        self.cache.set(cache_type, data, code)
        return data

    def get_or_fetch(self, cache_type: str, code: str, fetch_func, ttl: int = None, validate: bool = True) -> Optional[Dict]:
        """获取缓存，不存在则获取并缓存"""
        cached = self.get(cache_type, code)
        if cached is not None:
            return cached

        data = fetch_func(code)
        if data is None:
            return None

        return self.set(cache_type, data, code, validate=validate)

    def is_valid(self, cache_type: str, code: str) -> bool:
        """检查缓存是否有效"""
        cache_file = get_cache_path(cache_type, code)
        if not cache_file.exists():
            return False

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)

            updated_at = cache.get('updated_at', '')
            if not updated_at:
                return False

            updated = datetime.fromisoformat(updated_at)
            age = (datetime.now() - updated).total_seconds()

            ttl = TTL_CONFIG.get(cache_type, 3600)
            if ttl < 0:
                return True

            return age <= ttl
        except:
            return False

    def get_cache_age(self, cache_type: str, code: str) -> Optional[float]:
        """获取缓存年龄（秒）"""
        cache_file = get_cache_path(cache_type, code)
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)

            updated_at = cache.get('updated_at', '')
            updated = datetime.fromisoformat(updated_at)
            return (datetime.now() - updated).total_seconds()
        except:
            return None

    def invalidate(self, cache_type: str, code: str = None):
        """使缓存失效"""
        if code:
            self.cache.delete(cache_type, code)
        else:
            for f in DATA_DIR.glob(f"{cache_type}_*.json"):
                f.unlink()

    def get_stale_stocks(self, cache_type: str, stock_pool: List[Dict], batch_size: int = 200) -> List[str]:
        """获取需要刷新的股票列表"""
        stale = []

        for stock in stock_pool:
            symbol = stock.get('symbol') or stock.get('code', '')
            if not symbol:
                continue

            if not self.is_valid(cache_type, symbol):
                stale.append(symbol)

            if len(stale) >= batch_size:
                break

        return stale

    def migrate_old_cache(self):
        """迁移旧格式缓存到新格式"""
        print("检查旧缓存格式...")

        migrated = 0
        removed = 0

        for fin_file in DATA_DIR.glob("fin_*.json"):
            code = fin_file.stem[4:]
            new_file = DATA_DIR / f"financial_{code}.json"

            if not new_file.exists():
                try:
                    with open(fin_file, 'r') as f:
                        old_cache = json.load(f)

                    old_data = old_cache.get('data', old_cache)
                    new_cache = {
                        'data': old_data,
                        'updated_at': old_cache.get('updated_at', datetime.now().isoformat()),
                        'version': CACHE_VERSION,
                        'cache_type': 'financial',
                        '_migrated': True
                    }

                    with open(new_file, 'w') as f:
                        json.dump(new_cache, f, ensure_ascii=False, indent=2)

                    migrated += 1
                except Exception as e:
                    print(f"迁移失败 {fin_file}: {e}")

        for fin_file in DATA_DIR.glob("fin_*.json"):
            fin_file.unlink()
            removed += 1

        print(f"缓存迁移完成: {migrated} 个迁移, {removed} 个旧缓存清理")

    def cleanup_invalid_cache(self):
        """清理无效缓存"""
        print("清理无效缓存...")

        removed = 0
        for cache_file in DATA_DIR.glob("financial_*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cache = json.load(f)

                data = cache.get('data', {})

                if not self.validator.validate_required(data):
                    cache_file.unlink()
                    removed += 1
            except:
                cache_file.unlink()
                removed += 1

        print(f"清理完成: {removed} 个无效缓存移除")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        stats = {
            "total_files": 0,
            "by_type": {},
            "size_mb": 0,
            "hot_cache": self.cache.get_stats(),
            "coverage": {}
        }

        for f in DATA_DIR.glob("*.json"):
            stats["total_files"] += 1
            stats["size_mb"] += f.stat().st_size / (1024 * 1024)

            name = f.stem
            if '_' in name:
                prefix = name.split('_')[0]
                stats["by_type"][prefix] = stats["by_type"].get(prefix, 0) + 1

        stats["size_mb"] = round(stats["size_mb"], 2)

        return stats


_cache_manager = None


def get_cache_manager() -> CacheManager:
    """获取缓存管理器单例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# ==================== 便捷函数 ====================

def read_cache(cache_type: str, code: str = None) -> Optional[Dict]:
    return get_cache_manager().get(cache_type, code)


def write_cache(cache_type: str, data: Dict, code: str = None):
    return get_cache_manager().set(cache_type, data, code)


def is_cache_valid(cache_type: str, code: str) -> bool:
    return get_cache_manager().is_valid(cache_type, code)


def get_cache_stats() -> Dict:
    return get_cache_manager().get_cache_stats()


def migrate_and_cleanup():
    cm = get_cache_manager()
    cm.migrate_old_cache()
    cm.cleanup_invalid_cache()


# ==================== 数据质量评分 ====================

class DataQualityScorer:
    """数据质量评分器"""

    REQUIRED_FIELDS = {
        'roe': 2, 'gross_margin': 1, 'net_profit_growth': 2,
        'revenue_growth': 1, 'pe': 1, 'pb': 1, 'cashflow': 1,
        'debt_ratio': 1, 'dividend_yield': 0.5,
    }

    @classmethod
    def calculate_quality_score(cls, data: Dict) -> Dict:
        if not data:
            return {'score': 0, 'level': 'low', 'missing_fields': [], 'coverage': 0}

        total_weight = sum(cls.REQUIRED_FIELDS.values())
        present_weight = 0
        missing_fields = []

        for field, weight in cls.REQUIRED_FIELDS.items():
            value = data.get(field)
            if value is not None and value != 0:
                present_weight += weight
            else:
                missing_fields.append(field)

        coverage = (present_weight / total_weight) * 100 if total_weight > 0 else 0
        base_score = coverage

        bonus = 0
        if data.get('source') == 'tushare':
            bonus = 10
        elif data.get('source') == 'eastmoney':
            bonus = 5

        warnings = data.get('_warnings', [])
        penalty = len(warnings) * 5

        final_score = max(0, min(100, base_score + bonus - penalty))

        if final_score >= 80:
            level = 'high'
        elif final_score >= 50:
            level = 'medium'
        else:
            level = 'low'

        return {
            'score': round(final_score, 1),
            'level': level,
            'missing_fields': missing_fields,
            'coverage': round(coverage, 1),
            'source': data.get('source', 'unknown')
        }

    @classmethod
    def get_data_quality(cls, cache_key: str, code: str) -> Dict:
        cm = get_cache_manager()
        data = cm.get(cache_key, code)
        if data:
            return cls.calculate_quality_score(data)
        return {'score': 0, 'level': 'low', 'missing_fields': [], 'coverage': 0}


def get_data_quality_summary() -> Dict:
    cm = get_cache_manager()
    stats = cm.get_cache_stats()

    fin_files = list(DATA_DIR.glob('financial_*.json'))[:100]
    quality_scores = []

    for f in fin_files:
        try:
            with open(f) as fp:
                data = json.load(fp).get('data', {})
            score = DataQualityScorer.calculate_quality_score(data)
            quality_scores.append(score['score'])
        except:
            pass

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

    stats['avg_data_quality'] = round(avg_quality, 1)
    return stats
