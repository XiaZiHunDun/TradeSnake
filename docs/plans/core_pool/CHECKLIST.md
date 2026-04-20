# 核心池流程检查清单

> 每次进行核心池相关修改后，使用此清单验证流程完整性。

---

## 一、数据流验证

### 1.1 stock_selector → data_manager

- [ ] `selector.initialize()` 正确接收 `stock_list`, `market_data`, `financial_data`
- [ ] `get_analysable_codes()` 返回 core + active 集合
- [ ] `in_hs300`, `in_zz500`, `in_zz1000` 指数标志正确设置
- [ ] `volume_rank` 正确计算

### 1.2 data_manager → cp_engine

- [ ] `get_stock_data_api()` 返回完整字段
- [ ] `_normalize_code()` 正确处理 `sh/sz/.SH/.SZ` 前后缀
- [ ] `create_stock_from_raw()` 创建 `StockCP` 无异常
- [ ] `cp_engine.add_stock()` 成功添加

### 1.3 cp_engine → recommender

- [ ] `cp_engine.stocks` 包含所有核心池股票
- [ ] `calculate_all()` 正确计算各维度分数
- [ ] `total_cp` 在 0-100 范围内

### 1.4 recommender → API

- [ ] `/api/cp/recommend?fusion=true` 返回融合字段
- [ ] `kelly_position`, `predicted_gain_5d`, `up_probability_5d` 等字段存在

---

## 二、数据存储验证

### 2.1 DuckDB

```bash
# 验证日K线数据
python -c "
from backend.data_manager.duckdb_store import get_duckdb_store
d = get_duckdb_store()
r = d.get_klines('000001', limit=1)
print('000001 klines:', r.success, r.row_count)
"

# 验证分钟K线数据
python -c "
from backend.data_manager.duckdb_store import get_duckdb_store
d = get_duckdb_store()
r = d.get_minute_klines('000001', limit=1)
print('000001 minute_klines:', r.success, r.row_count)
"
```

- [ ] `daily_kline` 有数据（~2.4M 行）
- [ ] `minute_kline` 有数据（~2.4M 行）
- [ ] 代码格式为 6 位无前缀

### 2.2 SQLite

```bash
# 验证 stocks 表
python -c "
from backend.simulator.database import get_db
db = get_db()
s = db.get_stock('000001')
print('000001 stock:', s)
"
```

- [ ] `stocks` 表有核心池股票数据
- [ ] `cp_history` 表有历史战力记录
- [ ] `prediction_store` 有预测数据（收盘后）

---

## 三、模块逻辑验证

### 3.1 cp_engine

```python
# 验证战力计算
from backend.engine.cp_engine import create_stock_from_raw
stock = create_stock_from_raw(
    code='000001', name='平安银行',
    price=12.0, pe=5.0, roe=10.0,
    net_profit_growth=15.0, revenue_growth=8.0,
    change_pct=1.0, pb=0.8
)
print(f'total_cp: {stock.total_cp}')
assert 0 <= stock.total_cp <= 100
```

### 3.2 recommender

```python
# 验证预测融合
from backend.recommender.fusion import PredictionFusion
codes = ['000001', '600000']
gain_preds, prob_preds = PredictionFusion.get_latest_predictions(codes)
print(f'gain_preds: {len(gain_preds)}, prob_preds: {len(prob_preds)}')
```

---

## 四、API 验证

```bash
# 验证战力榜
curl -s "http://localhost:8001/api/cp/top?limit=5" | python -m json.tool

# 验证融合推荐
curl -s "http://localhost:8001/api/cp/recommend?fusion=true&limit=5" | python -m json.tool
```

- [ ] `/api/cp/top` 返回战力榜
- [ ] `/api/cp/recommend?fusion=true` 返回带融合字段的推荐
- [ ] 响应中包含 `predicted_gain_5d`, `up_probability_5d`, `fused_score`

---

## 五、测试验证

```bash
# 运行核心池相关测试
python -m pytest backend/tests/test_cp_engine.py -v
python -m pytest backend/tests/test_prediction_engines.py -v
python -m pytest backend/tests/test_recommender.py -v
```

- [ ] `test_cp_engine.py` 全部通过
- [ ] `test_prediction_engines.py` 全部通过
- [ ] `test_recommender.py` 全部通过

---

## 六、后台任务验证

```bash
# 检查后台刷新任务日志
# 应该在后台看到类似输出:
# [后台] 核心池 150 只, 活跃池 300 只, 待刷新 50 只
# [后台] 获取到 1500 只股票数据
# [后台] 最终加载: 200 只
# [后台] 刷新完成，当前 450 只股票
```

- [ ] 核心池定时刷新（每5分钟）
- [ ] 活跃池定时刷新（每30分钟）
- [ ] 收盘后战力计算和预测保存

---

## 七、问题修复记录

### 本次修复记录

| 日期 | 问题 | 修复文件 | 行号 |
|------|------|----------|------|
| 2026-04-17 | `/api/cp/recommend` 未使用预测融合 | `router.py` | 181-245 |
| 2026-04-17 | `SingleStockResponse` 缺少融合字段 | `schemas.py` | 135-143 |
| 2026-04-17 | `_normalize_code` 未处理 `.SH/.SZ` 后缀 | `main.py` | 257-267 |
| 2026-04-17 | `PredictionFusion` 只查询 1 天预测 | `fusion.py` | 251,267 |
| 2026-04-17 | `BacktestCompatibilityLayer` SQLite fallback | `backtest.py` | 748-758 |
| 2026-04-17 | DuckDB `get_klines` 异常未记录 | `duckdb_store.py` | 373-374 |
| 2026-04-17 | prediction_store 代码格式不一致 | `prediction_store.py` | 22-31, 162, 208, 241, 275 |
| 2026-04-17 | DuckDB 代码格式不一致 | `duckdb_store.py` | - |
| 2026-04-17 | prediction_store 预测数据不新鲜 | 手动批量预测 | - |
| 2026-04-17 | adj_factor 数据不完整 | DuckDB + SQLite JOIN | ✅ 已修复：585,770 有效, 1,812,755=1.0, 0 NULL |
| 2026-04-20 | roe > 0 阻止负ROE股票保存 | `fetcher.py` | `if roe > 0:` → `if roe != 0:` |
| 2026-04-20 | adj_close = 0 未计算 | DuckDB UPDATE | 3,578 行已修复 |
| 2026-04-20 | DuckDB trade_cal 为空 | Tushare填充 | 366行已填充 |
| 2026-04-20 | prediction_store 覆盖率低 | 批量预测生成 | 5053/5194只 (97.3%) |
| 2026-04-20 | SQLite stocks表有148条sh/sz前缀重复 | DELETE WHERE code LIKE 'sh%' | 148条已删除 |
| 2026-04-20 | DuckDB日K线缺少4月14-17日数据 | KlineFiller.fill_all批量补充 | +13,071行 |

---

## 八、检查频率

| 检查类型 | 频率 | 执行人 |
|----------|------|--------|
| 数据流验证 | 每次修改后 | 开发者 |
| 数据存储验证 | 每周 | 运维 |
| API 验证 | 每周 | 测试 |
| 测试验证 | 每次CI | CI系统 |
