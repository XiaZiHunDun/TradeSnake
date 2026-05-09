# 统一缓存架构设计

> **日期**: 2026-05-07
> **状态**: 已批准

## 1. 背景

当前项目存在**三套独立的缓存系统**，缓存键格式不互通：

| 系统 | 类 | 存储路径格式 | 问题 |
|------|-----|-------------|------|
| CacheManager | HotColdCache | `DATA_DIR/{type}_{code}.json` | 旧格式 |
| DataManager | UnifiedCache | `DATA_DIR/{type}/{code}.json` | 子目录结构 |
| Fetcher | MemoryCache | 内存 L1 | 无持久化 |

**核心问题**：
1. 同一数据可能被缓存两份，键格式不兼容
2. DataManager 创建了自己的 UnifiedCache，未复用 CacheManager
3. 数据更新后可能存在多个缓存副本，导致数据不一致

## 2. 目标

- **统一缓存层** - 所有数据访问通过 CacheManager
- **存储路径一致** - `DATA_DIR/{cache_type}/{code}.json`
- **DataManager 作为代理** - 内部使用 CacheManager，不自己创建缓存

## 3. 架构

```
外部调用（API、engine等）
     ↓
DataManager（统一入口）
     ↓
CacheManager（统一缓存层）
     ↓
Fetcher（数据源，缓存未命中时获取）
```

### 3.1 组件职责

| 组件 | 职责 |
|------|------|
| **DataManager** | 唯一数据入口，缓存读写代理，数据验证路由 |
| **CacheManager** | 统一缓存管理（HotColdCache），L2 持久化缓存 |
| **Fetcher** | 低层数据获取，L1 内存缓存（30秒 TTL） |

## 4. 缓存键格式

### 4.1 统一格式

```
缓存键：{cache_type}:{code}
存储路径：DATA_DIR/{cache_type}/{code}.json
```

### 4.2 CacheType 枚举

| cache_type | 说明 | TTL |
|-------------|------|-----|
| `stock_list` | 股票列表 | 7天 |
| `financial` | 财务数据 | 24小时 |
| `daily_basic` | 每日指标 | 24小时 |
| `moneyflow` | 资金流 | 24小时 |
| `trend` | 趋势数据 | 1小时 |
| `price_hist` | 历史价格 | 永不过期 |
| `realtime` | 实时行情 | 5分钟 |

### 4.3 旧格式迁移

**旧格式**：`DATA_DIR/{type}_{code}.json`

**策略**：自然过期淘汰，不强制迁移。新写入统一使用新格式。

## 5. 修改详情

### 5.1 CacheManager 变更

**文件**: `backend/data_manager/cache.py`

| 变更 | 说明 |
|------|------|
| `get_cache_path()` | 改为 `DATA_DIR/{cache_type}/{code}.json` 子目录结构 |
| `HotColdCache.clear()` | 新增方法，清空热缓存和所有磁盘缓存 |
| `HotColdCache.get_all_codes()` | 新增方法，获取某类型所有缓存的 code |
| `HotColdCache.get_stats()` | 添加 miss_rate 计算 |

### 5.2 DataManager 变更

**文件**: `backend/data_manager/manager.py`

| 变更 | 说明 |
|------|------|
| `__init__` 中 `self._cache` | 改为 `get_cache_manager().cache`，不复用 UnifiedCache |
| 删除 `UnifiedCache` 类引用 | 不再创建自己的缓存实例 |
| `get_cache_stats()` | 委托给 CacheManager |

### 5.3 Fetcher 变更

**文件**: `backend/data_manager/fetcher.py`

| 变更 | 说明 |
|------|------|
| 保留 MemoryCache | 作为 L1 内存缓存，30秒 TTL |
| `use_cache=False` 行为 | 改为绕过 L1，但仍然写入 CacheManager L2 |
| `get_cache_path()` | 移除自己的缓存路径逻辑，使用 CacheManager 的 |

## 6. API 设计

### 6.1 CacheManager 公开接口

```python
class CacheManager:
    @staticmethod
    def get_instance() -> CacheManager

    def get(self, cache_type: str, code: str = None, use_cache: bool = True) -> Optional[Any]
    def set(self, cache_type: str, data: Any, code: str = None, validate: bool = True) -> Dict
    def delete(self, cache_type: str, code: str = None) -> None
    def clear(self, cache_type: str = None) -> None
    def get_stats(self) -> Dict
    def get_all_codes(self, cache_type: str) -> List[str]

class HotColdCache:
    def get(self, cache_type: str, code: str = None) -> Optional[Any]
    def set(self, cache_type: str, data: Any, code: str = None) -> None
    def delete(self, cache_type: str, code: str = None) -> None
    def clear(self, cache_type: str = None) -> None
    def get_all_codes(self, cache_type: str) -> List[str]
    def get_stats(self) -> Dict
```

### 6.2 DataManager 公开接口（不变）

```python
def get_data_manager() -> DataManager
def get_stock_data(limit: int = 200) -> List[Dict]
def get_single_stock(code: str) -> Optional[Dict]
def get_market_data(codes: List[str], use_cache: bool = True) -> List[Dict]
def get_financial_data(code: str, use_cache: bool = True) -> Optional[Dict]
def get_stock_list(use_cache: bool = True, force_refresh: bool = False) -> List[Dict]
```

## 7. 数据流

### 7.1 数据获取流程

```
调用者 → DataManager.get_xxx()
    ↓
DataManager 检查 CacheManager L2
    ↓ (命中)
返回缓存数据
    ↓ (未命中)
调用 Fetcher 获取数据
    ↓
写入 CacheManager L2（同时更新 L1 MemoryCache）
    ↓
返回数据
```

### 7.2 缓存更新流程

```
force_refresh=True OR use_cache=False
    ↓
调用 Fetcher 获取新数据
    ↓
DataManager 验证数据
    ↓
写入 CacheManager L2
    ↓
清除 L1 MemoryCache（通过 use_cache=False 绕过）
```

## 8. 测试计划

| 测试 | 说明 |
|------|------|
| 缓存路径格式 | 验证新格式 `DATA_DIR/{type}/{code}.json` |
| 缓存命中/未命中 | 验证 get/set 正确 |
| DataManager 代理 | 验证 DataManager 正确使用 CacheManager |
| 缓存统计 | 验证 get_stats() 正确 |

## 9. 风险与回退

| 风险 | 缓解 |
|------|------|
| 旧缓存文件残留 | 自然过期淘汰，不影响新请求 |
| L1/L2 缓存不一致 | DataManager 统一管理写入，use_cache=False 只绕 L1 |

## 10. 实施顺序

1. 修改 `get_cache_path()` 为新格式
2. 给 HotColdCache 添加 `clear()` 和 `get_all_codes()`
3. 修改 DataManager 使用 CacheManager
4. 更新 Fetcher 的缓存路径逻辑
5. 验证测试通过