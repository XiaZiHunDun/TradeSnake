# 核心池问题追踪

> 记录核心池流程中发现的问题及其状态

---

## 一、待解决问题

### P3: 部分股票 total_cp 未计算

**描述**: SQLite `stocks` 表中有 1536 只股票（44.8%）的 `total_cp = 0`，未参与战力计算。

**影响**:
- 这些股票不会出现在战力榜中
- 不影响核心池战力计算（核心池约200只股票）

**解决方案**:
- 检查 `background_refresh_task` 是否覆盖所有股票
- 核心池股票应定期刷新

**状态**: 待调查

---

### P2: adj_factor 数据不完整

**描述**: DuckDB `daily_kline` 表的 `adj_factor` 部分缺失。

**当前状态** (2026-04-17 晚):
- 总行数: 2,398,525
- 有效复权因子 (≠1.0): 585,770 行 ✅ (24.42%)
- 无需调整 (=1.0): 1,812,755 行 ✅ (75.58%)
- 缺失 (IS NULL): 0 行 ✅

**数据来源**:
- `ExRightFactorFiller` 从 Tushare `pro.adj_factor` API 获取数据
- 存储在 SQLite `ex_right_factor` 表
- 回填到 DuckDB `daily_kline`

**修复方法**:
```python
# 使用 DuckDB SQLite 扩展直接 JOIN 回填
duckdb_conn.execute('''
    UPDATE daily_kline
    SET adj_factor = ROUND(sf.factor, 6)
    FROM sqlite_db.ex_right_factor sf
    WHERE sf.adj_type = 'qfq'
      AND sf.symbol = daily_kline.code
      AND CAST(SUBSTR(sf.trade_date, 1, 4) || ... AS DATE) = daily_kline.trade_date
      AND daily_kline.adj_factor IS NULL
      AND sf.factor < 10000
''')
```

**遗留问题**:
- 3 只股票的 3 行因 SQLite 无对应日期或 factor>10000 而设为 1.0
- 4,065 行 SQLite factor>=10000 无法存储 (DECIMAL(10,6) 上限)

**状态**: ✅ 已修复 (v19.9.6)

---

### P2: DuckDB minute_kline 数据量有限

**描述**: DuckDB `minute_kline` 表仅保留约4天数据（2026-04-08 到 2026-04-13），设计目标是保留14天。

**影响**:
- 分钟级实时因子计算受限
- 盘中MA5/MA15变化率可能不准确
- 不影响日线战力计算

**解决方案**:
- 数据源持续补充分钟K线数据
- 或调整 `cleanup.py` 中的保留策略

**状态**: 待解决

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

### ✅ P1: prediction_store 预测数据不新鲜 (v19.9.6)

**描述**: prediction_store 只保存了约1000只股票的预测，且最新日期为2026-04-14，不够新鲜。

**影响**:
- 融合推荐时无法获取最新预测数据
- 融合得分可能不准确

**修复**:
- 批量预测生成，覆盖5053只股票（97.3%，5194只有K线数据）
- 使用INSERT OR REPLACE保留历史数据
- 141只股票因K线不足5根无法生成预测

**状态**: ✅ 已修复 (2026-04-20)

---

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

**状态**: ✅ 已修复 (2026-04-20) - 366行已填充

---

### ✅ P2: roe > 0 阻止负ROE股票保存 (v19.9.6)

**描述**: `fetcher.py` 中 `if roe > 0:` 阻止了亏损公司（负ROE）的财务数据保存。

**修复**:
- 改为 `if roe != 0:` 允许负ROE公司有财务数据

**状态**: ✅ 已修复 (2026-04-20)

---

### ✅ P2: adj_close = 0 未计算 (v19.9.6)

**描述**: DuckDB `daily_kline` 表中部分 `adj_factor != 1.0` 的行 `adj_close = 0`。

**修复**:
```sql
UPDATE daily_kline SET adj_close = close * adj_factor
WHERE adj_factor != 1.0 AND adj_close = 0
```

**状态**: ✅ 已修复 (2026-04-20) - 3,578行已更新

### ✅ P1: prediction_store 代码格式不一致 (v19.9.5)

**描述**: `prediction_store` 中部分代码带 `sh/sz` 前缀，与 DuckDB/SQLite stocks 表不一致，导致融合推荐时查不到预测数据。

**影响**:
- 100 只股票的预测数据无法被匹配
- 融合推荐时这些股票会退化为默认值

**修复**:
- 在 `record_gain_predictions()` 和 `record_probability_predictions()` 中添加代码标准化
- 在 `get_gain_predictions()` 和 `get_probability_predictions()` 中添加代码标准化
- 已修复历史数据：100 条带前缀记录已更正

**修复文件**:
- `data_manager/prediction_store.py`: 添加 `_normalize_code()` 函数，应用于所有读写接口

---

### ✅ P1: DuckDB 代码格式不一致 (v19.9.5)

**描述**: DuckDB `daily_kline` 表中 90 只股票代码带 `sh/sz` 前缀，与标准格式不一致。

**影响**:
- 部分股票历史数据重复（同一股票既有 `sz002501` 又有 `002501`）
- 代码查询可能匹配失败

**修复**:
- 删除重复的带前缀记录（保留标准格式）
- 共删除 42,141 条重复记录

**状态**: ✅ 已修复

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
