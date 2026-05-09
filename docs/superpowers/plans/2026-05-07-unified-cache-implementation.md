# 统一缓存架构实现方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan.

**Goal:** 统一缓存层，所有数据访问通过 CacheManager，存储路径改为 `DATA_DIR/{cache_type}/{code}.json`

**Architecture:**
1. 修改 `get_cache_path()` 为子目录结构 `DATA_DIR/{type}/{code}.json`
2. 给 HotColdCache 添加 `clear()` 和 `get_all_codes()` 方法
3. 修改 DataManager 使用 CacheManager，不再创建自己的 UnifiedCache

---

## Task 1: 修改 get_cache_path() 为子目录结构

**Files:**
- Modify: `backend/data_manager/cache.py:79-83`

- [ ] **Step 1: 读取当前 get_cache_path 实现**

约 line 79-83，当前实现：
```python
def get_cache_path(cache_type: str, code: str = None) -> Path:
    """获取缓存文件路径"""
    if code:
        return DATA_DIR / f"{cache_type}_{code}.json"
    return DATA_DIR / f"{cache_type}.json"
```

- [ ] **Step 2: 修改为子目录结构**

```python
def get_cache_path(cache_type: str, code: str = None) -> Path:
    """获取缓存文件路径

    统一格式: DATA_DIR/{cache_type}/{code}.json
    无 code 时: DATA_DIR/{cache_type}.json
    """
    if code:
        return DATA_DIR / cache_type / f"{code}.json"
    return DATA_DIR / f"{cache_type}.json"
```

- [ ] **Step 3: 验证修改**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -c "
from backend.data_manager.cache import get_cache_path
print(get_cache_path('financial', '000001'))
print(get_cache_path('stock_list'))
"`

Expected: `DATA_DIR/financial/000001.json` 和 `DATA_DIR/stock_list.json`

---

## Task 2: 给 HotColdCache 添加 clear() 和 get_all_codes() 方法

**Files:**
- Modify: `backend/data_manager/cache.py:160-260`（HotColdCache 类）

- [ ] **Step 1: 在 HotColdCache 类末尾添加两个方法**

在 `_hot_cache` 相关的方法之后（约 line 259 后）添加：

```python
def clear(self, cache_type: str = None):
    """清空缓存

    Args:
        cache_type: 如果指定，只清空该类型；否则清空所有缓存
    """
    with self._hot_lock:
        if cache_type:
            # 只清空指定类型的热缓存
            keys_to_remove = [k for k in self._hot_cache if k.startswith(f"{cache_type}:")]
            for k in keys_to_remove:
                self._hot_cache.pop(k, None)
        else:
            self._hot_cache.clear()

def get_all_codes(self, cache_type: str) -> List[str]:
    """获取某类型所有缓存的 code

    Args:
        cache_type: 缓存类型

    Returns:
        code 列表
    """
    # 先从热缓存获取
    codes = set()
    with self._hot_lock:
        for key in self._hot_cache:
            if key.startswith(f"{cache_type}:"):
                parts = key.split(":")
                if len(parts) == 2:
                    codes.add(parts[1])

    # 再扫描磁盘缓存目录
    type_dir = DATA_DIR / cache_type
    if type_dir.exists():
        for f in type_dir.glob("*.json"):
            codes.add(f.stem)

    return sorted(list(codes))
```

- [ ] **Step 2: 验证 HotColdCache 方法**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -c "
from backend.data_manager.cache import HotColdCache
cache = HotColdCache()
print('clear 方法存在:', hasattr(cache, 'clear'))
print('get_all_codes 方法存在:', hasattr(cache, 'get_all_codes'))
print('OK')
"`

---

## Task 3: 修改 DataManager 使用 CacheManager

**Files:**
- Modify: `backend/data_manager/manager.py:305-360`（DataManager.__init__）

- [ ] **Step 1: 读取 DataManager.__init__**

约 line 327-360，找到：
```python
def __init__(self):
    if self._initialized:
        return
    self._initialized = True

    # 统一缓存
    self._cache = UnifiedCache()

    # 数据验证器
    self._validator = DataValidator()
    ...
```

- [ ] **Step 2: 修改为使用 CacheManager**

将 `self._cache = UnifiedCache()` 改为：
```python
# 使用统一的 CacheManager
self._cache = get_cache_manager().cache
```

- [ ] **Step 3: 删除 UnifiedCache 导入（如果存在）**

在文件顶部找到类似 `from .unified_cache import UnifiedCache` 的导入并删除（如果 `UnifiedCache` 不存在则跳过此步）

- [ ] **Step 4: 验证 DataManager 使用 CacheManager**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -c "
from backend.data_manager.manager import DataManager
dm = DataManager()
print('_cache 类型:', type(dm._cache).__name__)
print('OK - DataManager 使用 CacheManager')
"`

---

## Task 4: 更新 fetcher.py 的缓存路径逻辑

**Files:**
- Modify: `backend/data_manager/fetcher.py:88-90`

- [ ] **Step 1: 检查 fetcher.py 中的 get_cache_path**

约 line 88-90，有自己的 `get_cache_path`：
```python
def get_cache_path(cache_type: str) -> str:
    ensure_dir(CACHE_DIR)
    return os.path.join(CACHE_DIR, f"{cache_type}_cache.json")
```

- [ ] **Step 2: 修改为使用 cache.py 的 get_cache_path**

将 fetcher.py 中的 `get_cache_path` 函数删除或改为调用 cache.py 的版本：
```python
# 删除原函数，改为从 cache.py 导入
from backend.data_manager.cache import get_cache_path as cache_get_path
```

如果原函数被其他地方引用，保留函数但调用 cache_get_path。

- [ ] **Step 3: 验证 fetcher 导入**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -c "
from backend.data_manager.fetcher import StockDataFetcher
print('StockDataFetcher 导入 OK')
"`

---

## Task 5: 验证缓存架构统一

**Files:**
- Create: `backend/data_manager/tests/test_unified_cache.py`

- [ ] **Step 1: 编写验证测试**

```python
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
```

- [ ] **Step 2: 运行测试**

Run: `source ~/miniconda3/etc/profile.d/conda.sh && conda activate tradesnake && python -m pytest backend/data_manager/tests/test_unified_cache.py -v`

---

## 验证清单

- [ ] get_cache_path() 返回子目录结构路径
- [ ] HotColdCache.clear() 方法存在且可调用
- [ ] HotColdCache.get_all_codes() 方法存在且可调用
- [ ] DataManager._cache 是 CacheManager 的缓存实例
- [ ] fetcher.py 可以正常导入
- [ ] 所有测试通过