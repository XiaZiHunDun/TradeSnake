# 核心池问题追踪

> 记录核心池流程中发现的问题及其状态

---

## 一、待解决问题

### P2: adj_factor 全为 1.0

**描述**: DuckDB `daily_kline` 表中所有 `adj_factor` 字段值均为 1.0，未正确存储复权因子。

**影响**:
- 复权价格计算不准确
- 不影响核心池战力计算（战力计算不使用复权价格）
- 仅影响需要精确复权价格的场景

**解决方案**:
```python
# 调用 backfill_adj_factor() 方法回填
from backend.data_manager.duckdb_store import get_duckdb_store
duckdb = get_duckdb_store()
result = duckdb.backfill_adj_factor()
print(result)
```

**状态**: 方案已实现，待手动执行

---

### P2: DuckDB minute_kline 数据量有限

**描述**: DuckDB `minute_kline` 表仅保留约5天数据（2.4M行），设计目标是保留14天。

**影响**:
- 分钟级实时因子计算受限
- 盘中MA5/MA15变化率可能不准确
- 不影响日线战力计算

**解决方案**:
- 数据源持续补充分钟K线数据
- 或调整 `cleanup.py` 中的保留策略

**状态**: 数据补充中

---

### P3: StockCP 部分字段未填充

**描述**: 以下 `StockCP` 字段在正常刷新流程中为 0:
- `avg_daily_amount_20d`
- `turnover_rate`
- `volatility_20d`
- `real_time_score`
- `current_ratio`, `interest_coverage`, `deducted_net_profit`

**影响**:
- 这些字段暂未用于战力计算（战力计算只依赖基础行情和财务数据）
- `real_time_score` 用于盘中实时排名，但当前由 `market_snapshot` 单独计算

**解决方案**:
- 如需使用这些字段，需在 `background_refresh_task` 中补充获取逻辑
- 或在 `create_stock_from_raw()` 调用时传入

**状态**: 暂不影响核心流程

---

## 二、已解决问题

### ✅ P1: `/api/cp/recommend` 未使用预测融合 (v19.9.5)

**描述**: API 只使用纯战力排序，未调用融合逻辑。

**修复**:
- 添加 `fusion` 参数 (`GET /api/cp/recommend?fusion=true`)
- `StockCPData` 和 `SingleStockResponse` 添加融合字段

**修复文件**:
- `models/schemas.py`: 添加 `kelly_position`, `predicted_gain_5d`, `up_probability_5d`, `prediction_confidence`, `fused_score`
- `api/router.py`: 添加 `fusion=True` 参数和融合逻辑

---

### ✅ P1: `SingleStockResponse` 缺少融合字段 (v19.9.5)

**描述**: 融合推荐返回的响应类型缺少融合相关字段。

**修复**:
- 在 `SingleStockResponse` 添加融合字段

---

### ✅ P2: `_normalize_code` 未处理 `.SH/.SZ` 后缀 (v19.9.5)

**描述**: Tushare 格式如 `000001.SH` 传入时后缀未去除。

**修复**:
```python
def _normalize_code(raw_code: str) -> str:
    code = raw_code
    if code.startswith('sh'):
        code = code[2:]
    elif code.startswith('sz'):
        code = code[2:]
    if '.' in code:  # 处理 .SH/.SZ 后缀
        code = code.split('.')[0]
    return code
```

---

### ✅ P2: `PredictionFusion` 只查询 1 天预测 (v19.9.5)

**描述**: 如果收盘后预测任务未运行，今天没有预测数据，融合会退化为默认值。

**修复**:
```python
# 旧代码
gain_list = store.get_gain_predictions(code, days=1)

# 新代码
gain_list = store.get_gain_predictions(code, days=7)
```

---

### ✅ P2: `BacktestCompatibilityLayer` SQLite fallback (v19.9.5)

**描述**: `get_stock_price_at_date()` 使用了未初始化的 `self.db`。

**修复**:
- 移除无效的 SQLite fallback
- DuckDB 是唯一数据源

---

### ✅ P2: DuckDB `get_klines` 异常未记录 (v19.9.5)

**描述**: DuckDB 查询异常被静默忽略。

**修复**:
```python
except Exception as e:
    logger.warning(f"get_klines 查询失败 code={code}: {e}")
    return QueryResult(success=False, error=str(e))
```

---

### ✅ P2: DuckDB trade_cal 表为空 (v19.9.4)

**描述**: `trade_cal` 表无数据，导致依赖交易日历的功能可能异常。

**修复**:
- 在 `TradeCalendarFiller` 中实现懒加载
- 如果表为空，自动从 Tushare 获取

---

## 三、架构建议

### 建议: Pool 状态持久化

**当前状态**: `PoolManager` 完全在内存中，重启后根据市场数据重新划分。

**问题**: 如果 Tushare/akshare 数据临时不可用，池划分可能与之前不同。

**建议**: 将池状态定期保存到 SQLite，重启时优先读取持久化状态。

---

### 建议: adj_factor 集成到数据管道

**当前状态**: `adj_factor` 需要手动调用 `backfill_adj_factor()` 回填。

**建议**: 在每日数据同步流程中自动获取并存储复权因子。

---

## 四、优先级说明

| 优先级 | 说明 | 响应时间 |
|--------|------|----------|
| P1 | 阻断性问题，影响核心功能 | 立即修复 |
| P2 | 重要问题，影响数据准确性 | 尽快修复 |
| P3 | 优化建议，不影响当前功能 | 规划修复 |
