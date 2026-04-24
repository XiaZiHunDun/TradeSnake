# 夜间数据增强系统设计

> 日期：2026-04-24
> 版本：v1.0

## 1. 目标

建立一个夜间持续运行的数据增强系统，实现：
1. **历史缺口补充** - 回溯3年（2023-04至今）日K线数据
2. **扩大覆盖范围** - 获取 A股指数、ETF、沪深股通标的 的行情数据
3. **增强预测精度** - 扩展分钟K线覆盖
4. **多源数据校验** - 交叉验证价格、财务、复权因子数据

## 2. 架构概览

```
nightly_data/
├── nightly_master.py          # 主调度脚本 (crontab 触发)
├── tasks/
│   ├── fill_history_klines.py # 历史K线回填 (2023-04 至今)
│   ├── fill_index_etf.py      # 指数/ETF 数据获取
│   ├── validate_data.py       # 多源交叉验证
│   └── update_predictions.py  # 预测数据更新
├── state/
│   └── nightly_state.db       # SQLite 进度状态表
└── logs/
    └── nightly_{date}.log     # 运行日志
```

## 3. 任务设计

### 3.1 历史K线回填 (`fill_history_klines.py`)

**目标**：回填 2023-04-01 至今的日K线数据

**逻辑**：
1. 读取 `kline_fill_status` 表，找出现在有数据的最大日期
2. 从起点开始，每天向前回补
3. 使用 `KlineFiller.fill_all()` 获取全市场数据
4. 完成后更新进度到 `nightly_state.db`

**进度跟踪**：
```sql
CREATE TABLE kline_fill_state (
    id INTEGER PRIMARY KEY,
    target VARCHAR(20),       -- 'index'/'stock'/'etf'
    last_date VARCHAR(10),    -- 上次完成日期 '2023-04-01'
    last_code VARCHAR(10),    -- 上次完成代码（断点用）
    updated_at TEXT
);
```

### 3.2 指数/ETF 数据获取 (`fill_index_etf.py`)

**目标**：获取以下品种的日K线数据

| 类型 | 品种 | 数据源 |
|------|------|--------|
| A股指数 | 上证指数(000001)、深证成指(399001)、创业板指(399006)、科创50(000688) 等 | Tushare `pro.index_daily` |
| ETF | 沪深300ETF(510300)、中证500ETF(510500)、上证50ETF(510050) 等 | Tushare `pro.fund_daily` |
| 沪深股通 | 沪股通(000001)、深股通(399001) 覆盖标的 | Tushare `hsconst` |

**逻辑**：
1. 维护指数和ETF代码列表（可配置）
2. 使用 `KlineFiller.fill_index()` 填充指数数据
3. 使用 `KlineFiller.fill_etf()` 填充ETF数据
4. 更新股通标的列表

### 3.3 多源数据校验 (`validate_data.py`)

**目标**：从多个数据源获取同一数据，检测不一致

**校验规则**：

| 数据类型 | 规则 | 阈值 |
|----------|------|------|
| 日K线价格 | Tushare vs AkShare 收盘价差异 | >1% 标记 |
| 复权因子 | adj_factor 与计算的复权收盘价对比 | >0.1% 标记 |
| 财务数据 | 东方财富 vs Tushare 营收差异 | >5% 标记 |
| 股票状态 | 检查停牌、退市标识变更 | 即时告警 |

**输出**：
- `validation_report_{date}.json` - 不一致数据列表
- 数据库标记不一致数据（用于后续修复）

### 3.4 预测数据更新 (`update_predictions.py`)

**目标**：为所有有数据的股票更新预测

**逻辑**：
1. 读取 DuckDB 中有K线的股票列表
2. 批量调用 `gain_predictor` 和 `probability_predictor`
3. 保存到 `prediction_store` (SQLite)
4. 只更新有60天以上K线数据的股票

## 4. 运行机制

### 4.1 主调度 (`nightly_master.py`)

```python
# crontab 设置：每天凌晨 00:30 开始
0 30 * * * /home/ailearn/miniconda3/envs/tradesnake/bin/python nightly_data/nightly_master.py

# 主流程
def run():
    check_time_window()  # 只在 00:30 - 06:00 运行

    tasks = [
        ('klines', fill_history_klines),
        ('index_etf', fill_index_etf),
        ('validate', validate_data),
        ('predictions', update_predictions),
    ]

    for task_id, task_func in tasks:
        if is_task_done_today(task_id):
            log(f"{task_id} already done today, skip")
            continue
        try:
            task_func()
            mark_done(task_id)
        except Exception as e:
            log_error(f"{task_id} failed: {e}")
            # 继续下一个任务，不阻塞
```

### 4.2 断点续传

每个任务执行过程中，每处理完一批数据（如100只股票或10个交易日）就更新进度：
```sql
UPDATE kline_fill_state SET last_date=?, last_code=?, updated_at=? WHERE target=?
```

如果任务中断，下次运行从 `last_date` 继续。

### 4.3 时间窗口保护

```python
def check_time_window():
    now = datetime.now()
    # 只在 00:30 - 06:00 运行
    if now.hour < 0 or now.hour >= 6:
        sys.exit(0)  # 正常退出，不报警
```

## 5. 状态管理

### 5.1 状态表结构

```sql
-- 任务进度状态
CREATE TABLE task_state (
    task_id VARCHAR(20) PRIMARY KEY,
    last_run DATE,
    status VARCHAR(10),  -- 'running'/'completed'/'failed'
    last_date VARCHAR(10),  -- 断点日期
    last_code VARCHAR(10),  -- 断点代码
    error_msg TEXT
);

-- 数据校验结果
CREATE TABLE validation_results (
    id INTEGER PRIMARY KEY,
    check_date DATE,
    data_type VARCHAR(20),  -- 'price'/'adj_factor'/'financial'
    code VARCHAR(10),
    source1 VARCHAR(20),
    source2 VARCHAR(20),
    diff_percent FLOAT,
    created_at TEXT
);
```

### 5.2 日志策略

- 每天一个日志文件：`logs/nightly_2026-04-24.log`
- 日志格式：`[2026-04-24 02:15:30] [klines] Processing 000001.SZ, date 2023-04-01`
- 保留最近30天日志

## 6. 数据源接口

### 6.1 Tushare 接口

| 接口 | 用途 | 积分消耗 |
|------|------|----------|
| `pro.daily` | 日K线 | 5/次 |
| `pro.index_daily` | 指数日K | 5/次 |
| `pro.fund_daily` | ETF日K | 5/次 |
| `pro.adj_factor` | 复权因子 | 1/只 |
| `pro.hsconst` | 沪深股通成分 | 5/次 |
| `pro.income` | 利润表 | 300/次 |
| `pro.balancesheet` | 资产负债表 | 300/次 |

### 6.2 AkShare 接口

| 接口 | 用途 |
|------|------|
| `stock_zh_a_hist` | A股历史K线 |
| `fund_etf_hist_sina` | ETF分钟/日K线 |
| `index_zh_a_hist` | 指数历史K线 |

## 7. 错误处理

| 场景 | 处理方式 |
|------|----------|
| Tushare 积分不足 | 降级为AkShare，跳过Tushare接口 |
| 单只股票数据异常 | 记录到 `error_stock_list`，继续下一只 |
| 网络超时 | 重试3次，间隔5秒 |
| DuckDB 锁定 | 等待10秒重试 |
| 任务超时（>5小时） | 记录断点，正常退出 |

## 8. 部署步骤

1. 创建目录结构
2. 创建 `nightly_state.db` 状态表
3. 配置 crontab 定时任务
4. 首次运行手动测试

## 9. 预期效果

- **3年日K线**：约 750 个交易日 × 5000 只股票 = 375万行数据
- **指数/ETF**：约 20 只指数 + 50 只ETF = 70 只品种
- **多源验证**：每天校验约 1000 只股票的关键数据
- **预测更新**：覆盖全市场约 5000 只股票

预计完成时间：首夜约 4-6 小时，之后每晚增量运行约 1-2 小时。