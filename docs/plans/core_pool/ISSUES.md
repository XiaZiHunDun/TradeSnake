# 核心池问题追踪

> 记录核心池流程中发现的问题及其状态

---

## 一、待解决问题

### P3: 部分股票 total_cp 未计算

**描述**: SQLite `stocks` 表中有 1484 只股票（45.2%）的 `total_cp = 0`。

**调查结论** (2026-04-22):

| 类别 | 数量 | 原因 |
|------|------|------|
| revenue > 0 且 total_cp > 0 | 1508只 | ✅ 数据完整 |
| revenue = 0 且 total_cp > 0 | 293只 | ⚠️ revenue缺失，但PE/ROE正常 |
| **revenue = 0 且 total_cp = 0** | **1484只** | ❌ 历史遗留（updated_at 在 2026-04-17之前） |

**关键发现**：
- **战力榜前200只中，有55只 revenue = 0 但 total_cp > 0**（如格力电器000651、燕京啤酒000729等）
- 这55只股票的 revenue 数据在东方财富/baostock 缺失，但 PE/ROE 正常，战力分合理
- **核心池战力计算不受影响**

**根因**：东方财富/baostock 的 revenue 数据对部分股票不可用，导致 growth_score 为0

**状态**: ✅ 已优化（从 Tushare income API 获取 revenue 作为 fallback）

**优化实现** (2026-04-22):
- `tushare.py`: `get_fina_indicator_batch()` 添加 `revenue` 和 `revenue_yoy` 字段
- `fetcher.py`: `get_financial_data()` 添加 Tushare revenue fallback 逻辑
- 当 eastmoney/baostock 的 revenue 为 0 时，自动从 Tushare `income` API 补充

**验证**:
```python
# Tushare 直接获取 格力电器 revenue
provider.get_financial_data('000651')['revenue']  # = 1371.8 亿元
```

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

**解决方案** (v19.9.8):
- 在 `background_refresh_task` 收盘后（16:30+）添加 `MinuteKlineFiller` 调用
- 每天轮换填充核心池+活跃池的50只股票（约4天轮换完全部）
- 每只股票获取最近1天数据

**修复文件**:
- `backend/api/main.py`: RefreshState 类 + 收盘后分钟K线填充逻辑

**状态**: ✅ 已修复 (2026-04-22)

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

### ✅ P2: DuckDB日K线缺少4月14-17日数据 (v19.9.6)

**描述**: DuckDB `daily_kline` 表最新日期为2026-04-13，缺少4月14-17日的K线数据。

**影响**:
- 约4991只股票的近期K线数据缺失
- 战力计算可能使用过时数据

**修复**:
- 重置completed状态股票的last_date为20260413，触发缺口检测
- 运行KlineFiller.fill_all批量补充缺失数据

**修复结果** (2026-04-20):
- 4月14-17日K线: 1只 → 3149-3150只
- 总行数: 2,398,525 → 2,411,596 (+13,071)

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

---

### ✅ P2: SQLite stocks表有sh/sz前缀重复记录 (v19.9.6)

**描述**: SQLite stocks表有148条带sh/sz前缀的重复记录，导致核心池查询时找不到这些股票。

**影响**:
- 核心池300只股票中9只显示"无K线数据"
- 实际是代码格式不一致（sh603207 vs 603207）

**修复**:
```sql
DELETE FROM stocks WHERE code LIKE 'sh%' OR code LIKE 'sz%'
```

**状态**: ✅ 已修复 (2026-04-20) - 148条已删除，核心池300只全部有K线

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

### ✅ P3: `_merge_missing_days_to_gaps` 类型错误 (v19.9.7)

**描述**: `filler.py` 中 `_merge_missing_days_to_gaps` 期望 `datetime.date` 对象，但 `strptime()` 需要字符串参数，导致类型错误。

**影响**:
- 缺口检测在某些情况下会抛出异常，回退到简单检测
- 不影响核心功能（回退机制正常工作）

**修复**:
- 添加 `to_date()` 函数统一处理字符串和 `datetime.date` 对象
- 确保返回的 `gap_start` 和 `gap_end` 都是字符串格式

**修复文件**:
- `backend/data_manager/filler.py`: 775-819 行

**状态**: ✅ 已修复 (2026-04-20)

---

### ✅ P2: KlineFiller 不在自动更新流程中 (v19.9.7)

**描述**: KlineFiller 不会自动触发，需要手动调用。收盘后 `background_refresh_task` 只保存预测，不更新 K 线数据。

**影响**:
- 新交易日 K 线数据不会自动获取
- completed 股票的 last_date 不会更新

**修复**:
- 在 `background_refresh_task` 收盘后逻辑中添加 KlineFiller 调用
- 使用 `fill_incremental(days_back=7)` 增量填充
- 添加 `_refresh_state.last_kline_fill_date` 状态跟踪

**修复文件**:
- `backend/api/main.py`: RefreshState 类 + 488-499 行

**状态**: ✅ 已修复 (2026-04-20)

---

## 三、架构建议

### ✅ 已实现: Pool 状态持久化 (v19.9.9)

**功能**:
- `PoolStateStore` 类管理池状态持久化（SQLite）
- `PoolManager.save_state()` 每次 `refresh_pools` 后自动保存
- `PoolManager.load_state()` 启动时恢复池组成（如果24小时内）
- 表结构: `pool_state (pool_tier TEXT PRIMARY KEY, codes TEXT, updated_at TEXT)`

**实现文件**:
- `backend/data_manager/pool_state_store.py` - 持久化存储
- `backend/stock_selector/pool_manager.py` - save_state/load_state 方法
- `backend/api/main.py` - 集成到启动和再平衡流程

**状态**: ✅ 已实现 (2026-04-22)

---

### ✅ 已实现: adj_factor 集成到数据管道 (v19.9.9)

**功能**:
- 收盘后 (16:00+) 自动从 Tushare 获取 `adj_factor` 数据
- KlineFiller 完成后自动回填 `adj_factor` 到 DuckDB
- 使用 `RefreshState.last_adj_factor_fill_date` 避免重复填充

**实现位置**:
- `main.py`: 在 KlineFiller 流程中添加 `ExRightFactorFiller` 和 `backfill_adj_factor` 调用
- `RefreshState`: 添加 `last_adj_factor_fill_date` 状态跟踪

**流程**:
```
收盘后 (16:00+)
  → ExRightFactorFiller.fill_all()  # 从 Tushare 获取 adj_factor 到 SQLite
  → KlineFiller.fill_incremental()   # 填充 K 线
  → duckdb.backfill_adj_factor()     # 回填 adj_factor 到 DuckDB
```

**状态**: ✅ 已实现 (2026-04-22)

---

### ✅ Team模式审查: stock_selector 问题修复 (v19.9.9)

**审查时间**: 2026-04-23

| 优先级 | 问题 | 修复文件 | 状态 |
|--------|------|----------|------|
| P2 | save_state 未保存 whitelist/blacklist/probation_records | pool_state_store.py, pool_manager.py | ✅ 已修复 |
| P2 | load_state 未恢复 whitelist/blacklist/probation_records | pool_manager.py | ✅ 已修复 |
| P2 | on_financial_warning 接口类型不一致 | stock_selector.py | ✅ 已修复 |

---

### ✅ Team模式审查: 其他模块问题修复 (v19.9.9)

| 模块 | 问题 | 优先级 | 状态 |
|------|------|--------|------|
| probability_predictor | data_timestamp 引用错误 | P0 | ✅ 已修复 |
| models | risk_level 默认值不一致 | P1 | ✅ 已修复 |
| data_manager | query() 使用错误锁/连接 | P2 | ✅ 已修复 |
| api | /api/pool/stats _selector 未定义 | P0 | ✅ 已修复 |
| backtester | 过户费未区分沪深市场 | P1 | ✅ 已修复 |

---

## 四、优先级说明

| 优先级 | 说明 | 响应时间 |
|--------|------|----------|
| P1 | 阻断性问题，影响核心功能 | 立即修复 |
| P2 | 重要问题，影响数据准确性 | 尽快修复 |
| P3 | 优化建议，不影响当前功能 | 规划修复 |
