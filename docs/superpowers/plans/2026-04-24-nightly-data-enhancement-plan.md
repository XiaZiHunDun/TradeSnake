# 夜间数据增强系统实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立夜间持续运行的数据增强系统，实现历史K线回补、指数/ETF数据获取、多源数据校验、预测数据更新

**Architecture:** 采用模块化设计，4个独立任务脚本 + SQLite状态表，支持断点续传。主调度器通过 crontab 触发，各任务独立运行互不阻塞。

**Tech Stack:** Python 3.11, SQLite, DuckDB, Tushare/AkShare API

---

## 文件结构

```
backend/data_manager/
├── nightly_data/              # 新建目录
│   ├── __init__.py
│   ├── nightly_master.py     # 主调度脚本
│   ├── state_manager.py      # 状态管理（断点续传）
│   └── logger.py             # 日志工具
├── tasks/
│   ├── __init__.py
│   ├── fill_history_klines.py   # 历史K线回填
│   ├── fill_index_etf.py         # 指数/ETF获取
│   ├── validate_data.py          # 多源验证
│   └── update_predictions.py     # 预测更新
```

---

### Task 1: 创建状态管理模块

**Files:**
- Create: `backend/data_manager/nightly_data/state_manager.py`
- Create: `backend/data_manager/nightly_data/__init__.py`

- [ ] **Step 1: 创建目录和 __init__.py**

```bash
mkdir -p backend/data_manager/nightly_data/tasks
touch backend/data_manager/nightly_data/__init__.py
touch backend/data_manager/nightly_data/tasks/__init__.py
```

- [ ] **Step 2: 编写 state_manager.py**

```python
"""夜间数据任务状态管理器"""
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")
STATE_DB = DATA_DIR / "nightly_state.db"

class StateManager:
    """管理夜间任务的执行状态，支持断点续传"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.db_path = str(STATE_DB)
        self._ensure_tables()
        self._initialized = True

    def _ensure_tables(self):
        """创建状态表"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_state (
                    task_id VARCHAR(20) PRIMARY KEY,
                    last_run DATE,
                    status VARCHAR(10),
                    last_date VARCHAR(10),
                    last_code VARCHAR(10),
                    error_msg TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS validation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    check_date DATE,
                    data_type VARCHAR(20),
                    code VARCHAR(10),
                    source1 VARCHAR(20),
                    source2 VARCHAR(20),
                    diff_percent FLOAT,
                    created_at TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT * FROM task_state WHERE task_id = ?", (task_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'task_id': row[0],
                    'last_run': row[1],
                    'status': row[2],
                    'last_date': row[3],
                    'last_code': row[4],
                    'error_msg': row[5],
                    'updated_at': row[6]
                }
            return None
        finally:
            conn.close()

    def update_task_state(self, task_id: str, last_date: str = None,
                          last_code: str = None, status: str = 'running',
                          error_msg: str = None):
        """更新任务状态"""
        conn = sqlite3.connect(self.db_path)
        try:
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO task_state
                (task_id, last_run, status, last_date, last_code, error_msg, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, datetime.now().date().isoformat(), status,
                  last_date, last_code, error_msg, now))
            conn.commit()
        finally:
            conn.close()

    def is_task_done_today(self, task_id: str) -> bool:
        """检查任务是否已在今天完成"""
        state = self.get_task_state(task_id)
        if not state:
            return False
        if state['status'] != 'completed':
            return False
        if state['last_run']:
            return state['last_run'] == datetime.now().date().isoformat()
        return False

    def mark_task_done(self, task_id: str):
        """标记任务完成"""
        self.update_task_state(task_id, status='completed')

    def mark_task_failed(self, task_id: str, error: str):
        """标记任务失败"""
        self.update_task_state(task_id, status='failed', error_msg=error)

    def log_validation(self, data_type: str, code: str, source1: str,
                       source2: str, diff_percent: float):
        """记录验证结果"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO validation_results
                (check_date, data_type, code, source1, source2, diff_percent, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datetime.now().date().isoformat(), data_type, code,
                  source1, source2, diff_percent, datetime.now().isoformat()))
            conn.commit()
        finally:
            conn.close()
```

- [ ] **Step 3: 测试 state_manager**

```python
# 测试代码
from backend.data_manager.nightly_data.state_manager import StateManager

sm = StateManager()
sm.update_task_state('test_task', last_date='2023-04-01', last_code='600000', status='running')
state = sm.get_task_state('test_task')
print(state)  # 应显示 {'task_id': 'test_task', 'last_date': '2023-04-01', ...}
sm.mark_task_done('test_task')
```

- [ ] **Step 4: 提交**

```bash
git add backend/data_manager/nightly_data/state_manager.py backend/data_manager/nightly_data/__init__.py backend/data_manager/nightly_data/tasks/__init__.py
git commit -m "feat(nightly_data): add state_manager for task progress tracking"
```

---

### Task 2: 创建日志模块

**Files:**
- Create: `backend/data_manager/nightly_data/logger.py`

- [ ] **Step 1: 编写 logger.py**

```python
"""夜间数据任务日志工具"""
import logging
from datetime import datetime, date
from pathlib import Path
import os

LOG_DIR = Path("/home/ailearn/projects/TradeSnake/logs/nightly")
LOG_DIR.mkdir(parents=True, exist_ok=True)

def get_logger(task_name: str) -> logging.Logger:
    """获取指定任务的logger"""
    logger = logging.getLogger(f"nightly.{task_name}")

    # 避免重复添加handler
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 按日期创建日志文件
    log_file = LOG_DIR / f"nightly_{date.today().isoformat()}.log"

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def log_task_start(task_name: str, total: int = None):
    """记录任务开始"""
    logger = get_logger(task_name)
    msg = f"Task {task_name} started"
    if total:
        msg += f" (total: {total})"
    logger.info(msg)

def log_task_progress(task_name: str, current: int, total: int,
                      extra: str = ""):
    """记录任务进度"""
    logger = get_logger(task_name)
    pct = current / total * 100 if total else 0
    msg = f"Progress: {current}/{total} ({pct:.1f}%)"
    if extra:
        msg += f" - {extra}"
    logger.info(msg)

def log_task_complete(task_name: str, summary: str = ""):
    """记录任务完成"""
    logger = get_logger(task_name)
    msg = f"Task {task_name} completed"
    if summary:
        msg += f" - {summary}"
    logger.info(msg)

def log_task_error(task_name: str, error: str, extra: str = ""):
    """记录任务错误"""
    logger = get_logger(task_name)
    msg = f"Task {task_name} error: {error}"
    if extra:
        msg += f" - {extra}"
    logger.error(msg)
```

- [ ] **Step 2: 提交**

```bash
git add backend/data_manager/nightly_data/logger.py
git commit -m "feat(nightly_data): add logger module"
```

---

### Task 3: 创建历史K线回填任务

**Files:**
- Create: `backend/data_manager/nightly_data/tasks/fill_history_klines.py`
- Modify: `backend/data_manager/filler.py` (如需要添加 fill_index/fund 方法)

- [ ] **Step 1: 编写 fill_history_klines.py**

```python
"""历史K线回填任务

从2023-04-01开始，逐日回补全市场日K线数据
支持断点续传，中断后可从上次位置继续
"""
import sys
from pathlib import Path
from datetime import datetime, date, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.filler import KlineFiller
from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger, log_task_start, log_task_progress, log_task_complete, log_task_error

TASK_ID = 'fill_history_klines'
START_DATE = '2023-04-01'
DAILY_BATCH = 50  # 每天处理50只股票

def get_date_range(start_date_str: str, end_date_str: str):
    """生成日期范围"""
    start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    dates = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)
    return dates

def fill_history_klines():
    """执行历史K线回填任务"""
    logger = get_logger(TASK_ID)
    state_mgr = StateManager()

    # 检查时间窗口
    now = datetime.now()
    if now.hour < 0 or now.hour >= 6:
        logger.info("Outside time window (00:30-06:00), skip")
        return

    # 检查是否已完成
    if state_mgr.is_task_done_today(TASK_ID):
        logger.info(f"Task {TASK_ID} already completed today, skip")
        return

    log_task_start(TASK_ID)

    try:
        # 获取上次断点
        state = state_mgr.get_task_state(TASK_ID)
        last_date = state['last_date'] if state and state['last_date'] else START_DATE
        last_code = state.get('last_code') if state else None

        logger.info(f"Resuming from last_date={last_date}, last_code={last_code}")

        # 计算需要回填的日期范围
        today = date.today()
        dates_to_fill = get_date_range(last_date, today.strftime('%Y-%m-%d'))

        logger.info(f"Need to fill {len(dates_to_fill)} days of data")

        # 初始化KlineFiller
        filler = KlineFiller()

        total_dates = len(dates_to_fill)
        for idx, d in enumerate(dates_to_fill):
            try:
                date_str = d.strftime('%Y-%m-%d')
                logger.debug(f"Filling {date_str}")

                # 使用 fill_all 填充全市场数据
                result = filler.fill_all(target_date=date_str, limit=200)

                # 每完成一天更新进度
                state_mgr.update_task_state(TASK_ID, last_date=date_str, status='running')

                if (idx + 1) % 10 == 0:
                    log_task_progress(TASK_ID, idx + 1, total_dates, f"date={date_str}")

            except Exception as e:
                logger.warning(f"Failed to fill {d}: {e}")
                continue

        # 标记完成
        state_mgr.mark_task_done(TASK_ID)
        log_task_complete(TASK_ID, f"Filled {total_dates} days")

    except Exception as e:
        log_task_error(TASK_ID, str(e))
        state_mgr.mark_task_failed(TASK_ID, str(e))

if __name__ == '__main__':
    fill_history_klines()
```

- [ ] **Step 2: 提交**

```bash
git add backend/data_manager/nightly_data/tasks/fill_history_klines.py
git commit -m "feat(nightly_data): add fill_history_klines task"
```

---

### Task 4: 创建指数/ETF数据获取任务

**Files:**
- Create: `backend/data_manager/nightly_data/tasks/fill_index_etf.py`

- [ ] **Step 1: 编写 fill_index_etf.py**

```python
"""指数和ETF数据获取任务

获取A股主要指数和ETF的日K线数据
包括：上证指数、深证成指、创业板指、科创50、沪深300ETF、中证500ETF等
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.filler import KlineFiller
from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger, log_task_start, log_task_complete, log_task_error

TASK_ID = 'fill_index_etf'

# A股主要指数
INDEX_CODES = {
    '000001': '上证指数',
    '399001': '深证成指',
    '399006': '创业板指',
    '000688': '科创50',
    '000016': '上证50',
    '000300': '沪深300',
    '000905': '中证500',
    '000852': '中证1000',
}

# 主要ETF
ETF_CODES = {
    '510050': '上证50ETF',
    '510300': '沪深300ETF',
    '510500': '中证500ETF',
    '512000': '券商ETF',
    '512880': '证券ETF',
    '515000': '科技ETF',
    '159915': '创业板ETF',
    '159928': '中证500ETF',
}

def fill_index_etf():
    """执行指数/ETF数据获取任务"""
    logger = get_logger(TASK_ID)
    state_mgr = StateManager()

    if state_mgr.is_task_done_today(TASK_ID):
        logger.info(f"Task {TASK_ID} already completed today, skip")
        return

    log_task_start(TASK_ID, total=len(INDEX_CODES) + len(ETF_CODES))

    try:
        filler = KlineFiller()

        # 获取指数数据
        for code, name in INDEX_CODES.items():
            try:
                logger.debug(f"Filling index {code} ({name})")
                filler.fill_index(code, name)
                state_mgr.update_task_state(TASK_ID, last_code=code, status='running')
            except Exception as e:
                logger.warning(f"Failed to fill index {code}: {e}")

        # 获取ETF数据
        for code, name in ETF_CODES.items():
            try:
                logger.debug(f"Filling ETF {code} ({name})")
                filler.fill_etf(code, name)
                state_mgr.update_task_state(TASK_ID, last_code=code, status='running')
            except Exception as e:
                logger.warning(f"Failed to fill ETF {code}: {e}")

        state_mgr.mark_task_done(TASK_ID)
        log_task_complete(TASK_ID, f"Index: {len(INDEX_CODES)}, ETF: {len(ETF_CODES)}")

    except Exception as e:
        log_task_error(TASK_ID, str(e))
        state_mgr.mark_task_failed(TASK_ID, str(e))

if __name__ == '__main__':
    fill_index_etf()
```

- [ ] **Step 2: 检查 KlineFiller 是否有 fill_index/fill_etf 方法**

```bash
grep -n "def fill_index\|def fill_etf" backend/data_manager/filler.py
```

如果没有，需要添加：

```python
def fill_index(self, index_code: str, index_name: str = None) -> bool:
    """填充指数日K线数据"""
    # 使用 Tushare pro.index_daily 接口
    # ...

def fill_etf(self, fund_code: str, fund_name: str = None) -> bool:
    """填充ETF日K线数据"""
    # 使用 Tushare pro.fund_daily 接口
    # ...
```

- [ ] **Step 3: 提交**

```bash
git add backend/data_manager/nightly_data/tasks/fill_index_etf.py
git commit -m "feat(nightly_data): add fill_index_etf task"
```

---

### Task 5: 创建多源数据校验任务

**Files:**
- Create: `backend/data_manager/nightly_data/tasks/validate_data.py`

- [ ] **Step 1: 编写 validate_data.py**

```python
"""多源数据校验任务

从多个数据源获取同一数据，检测不一致并记录
校验：价格数据、复权因子、财务数据
"""
import sys
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger, log_task_start, log_task_complete, log_task_error

TASK_ID = 'validate_data'

# 验证阈值
PRICE_DIFF_THRESHOLD = 0.01  # 1%
ADJ_FACTOR_DIFF_THRESHOLD = 0.001  # 0.1%
FINANCIAL_DIFF_THRESHOLD = 0.05  # 5%

def get_stock_list(limit: int = 100):
    """获取待验证的股票列表"""
    from backend.data_manager.manager import get_data_manager
    dm = get_data_manager()
    return dm.get_stock_list()[:limit]

def validate_price(code: str, date_str: str, state_mgr: StateManager, logger) -> bool:
    """验证价格数据 - Tushare vs AkShare"""
    try:
        # Tushare 数据
        from backend.data_manager.providers.tushare import TushareProvider
        ts_provider = TushareProvider()

        # AkShare 数据
        import akshare as ak

        # 对比收盘价
        # ... (实现对比逻辑)

        return True
    except Exception as e:
        logger.debug(f"Price validation error for {code}: {e}")
        return False

def validate_adj_factor(code: str, state_mgr: StateManager, logger) -> bool:
    """验证复权因子"""
    try:
        from backend.data_manager.duckdb_store import get_duckdb_store
        from backend.data_manager.providers.tushare import TushareProvider

        store = get_duckdb_store()
        ts_provider = TushareProvider()

        # 从DuckDB获取 adj_factor
        # 从Tushare获取 adj_factor
        # 对比差异

        return True
    except Exception as e:
        logger.debug(f"Adj factor validation error for {code}: {e}")
        return False

def validate_financial(code: str, state_mgr: StateManager, logger) -> bool:
    """验证财务数据 - 东方财富 vs Tushare"""
    try:
        from backend.data_manager.fetcher import get_financial_data

        # 获取东方财富数据
        # 获取Tushare数据
        # 对比营收差异

        return True
    except Exception as e:
        logger.debug(f"Financial validation error for {code}: {e}")
        return False

def validate_data():
    """执行数据校验任务"""
    logger = get_logger(TASK_ID)
    state_mgr = StateManager()

    if state_mgr.is_task_done_today(TASK_ID):
        logger.info(f"Task {TASK_ID} already completed today, skip")
        return

    log_task_start(TASK_ID)

    try:
        stocks = get_stock_list(limit=100)
        validated_count = 0

        for code in stocks:
            try:
                # 价格验证
                validate_price(code, date.today().isoformat(), state_mgr, logger)

                # 复权因子验证
                validate_adj_factor(code, state_mgr, logger)

                # 财务数据验证
                validate_financial(code, state_mgr, logger)

                validated_count += 1

                if validated_count % 20 == 0:
                    logger.info(f"Validated {validated_count}/{len(stocks)}")

            except Exception as e:
                logger.warning(f"Validation failed for {code}: {e}")

        state_mgr.mark_task_done(TASK_ID)
        log_task_complete(TASK_ID, f"Validated {validated_count} stocks")

    except Exception as e:
        log_task_error(TASK_ID, str(e))
        state_mgr.mark_task_failed(TASK_ID, str(e))

if __name__ == '__main__':
    validate_data()
```

- [ ] **Step 2: 提交**

```bash
git add backend/data_manager/nightly_data/tasks/validate_data.py
git commit -m "feat(nightly_data): add validate_data task"
```

---

### Task 6: 创建预测数据更新任务

**Files:**
- Create: `backend/data_manager/nightly_data/tasks/update_predictions.py`

- [ ] **Step 1: 编写 update_predictions.py**

```python
"""预测数据更新任务

为所有有足够K线数据的股票更新预测
使用 gain_predictor 和 probability_predictor
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger, log_task_start, log_task_complete, log_task_error

TASK_ID = 'update_predictions'

def get_codes_with_enough_data(min_days: int = 60):
    """获取有足够K线数据的股票"""
    from backend.data_manager.duckdb_store import get_duckdb_store
    store = get_duckdb_store()

    try:
        result = store.query("""
            SELECT code, COUNT(*) as cnt
            FROM daily_kline
            GROUP BY code
            HAVING cnt >= ?
        """, [min_days])

        if result.success:
            return [row[0] for row in result.data.itertuples()]
        return []
    except Exception as e:
        logger = get_logger(TASK_ID)
        logger.error(f"Failed to get codes with enough data: {e}")
        return []

def update_predictions():
    """执行预测更新任务"""
    logger = get_logger(TASK_ID)
    state_mgr = StateManager()

    if state_mgr.is_task_done_today(TASK_ID):
        logger.info(f"Task {TASK_ID} already completed today, skip")
        return

    logger.info("Starting prediction update")

    try:
        codes = get_codes_with_enough_data(min_days=60)
        logger.info(f"Found {len(codes)} stocks with enough data")

        from backend.engine.gain_predictor.predictor import GainPredictor
        from backend.engine.probability_predictor.predictor import ProbabilityPredictor

        gain_pred = GainPredictor()
        prob_pred = ProbabilityPredictor()

        updated = 0
        for code in codes:
            try:
                gain_pred.predict(code)
                prob_pred.predict(code)
                updated += 1

                if updated % 100 == 0:
                    logger.info(f"Updated predictions for {updated}/{len(codes)}")

            except Exception as e:
                logger.debug(f"Failed to update predictions for {code}: {e}")

        state_mgr.mark_task_done(TASK_ID)
        log_task_complete(TASK_ID, f"Updated {updated} stocks")

    except Exception as e:
        log_task_error(TASK_ID, str(e))
        state_mgr.mark_task_failed(TASK_ID, str(e))

if __name__ == '__main__':
    update_predictions()
```

- [ ] **Step 2: 提交**

```bash
git add backend/data_manager/nightly_data/tasks/update_predictions.py
git commit -m "feat(nightly_data): add update_predictions task"
```

---

### Task 7: 创建主调度脚本

**Files:**
- Create: `backend/data_manager/nightly_data/nightly_master.py`

- [ ] **Step 1: 编写 nightly_master.py**

```python
#!/usr/bin/env python3
"""
夜间数据增强系统主调度脚本

通过 crontab 每天凌晨 00:30 触发:
0 30 * * * /home/ailearn/miniconda3/envs/tradesnake/bin/python backend/data_manager/nightly_data/nightly_master.py

各任务按顺序执行，支持断点续传
"""
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.data_manager.nightly_data.state_manager import StateManager
from backend.data_manager.nightly_data.logger import get_logger

# 导入各任务
from backend.data_manager.nightly_data.tasks.fill_history_klines import fill_history_klines
from backend.data_manager.nightly_data.tasks.fill_index_etf import fill_index_etf
from backend.data_manager.nightly_data.tasks.validate_data import validate_data
from backend.data_manager.nightly_data.tasks.update_predictions import update_predictions

TASKS = [
    ('fill_history_klines', fill_history_klines),
    ('fill_index_etf', fill_index_etf),
    ('validate_data', validate_data),
    ('update_predictions', update_predictions),
]

def check_time_window() -> bool:
    """检查是否在允许的时间窗口内 (00:30 - 06:00)"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute

    # 00:30 到 06:00
    if hour < 0 or hour >= 6:
        return False
    if hour == 0 and minute < 30:
        return False
    return True

def run():
    """主调度逻辑"""
    logger = get_logger('master')

    if not check_time_window():
        logger.info("Outside time window (00:30-06:00), exit gracefully")
        sys.exit(0)

    logger.info("=" * 50)
    logger.info("Nightly data enhancement started")
    logger.info("=" * 50)

    state_mgr = StateManager()

    for task_id, task_func in TASKS:
        logger.info(f"Starting task: {task_id}")

        try:
            task_func()
            logger.info(f"Task {task_id} completed")
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            # 继续执行下一个任务，不阻塞

    logger.info("=" * 50)
    logger.info("Nightly data enhancement finished")
    logger.info("=" * 50)

if __name__ == '__main__':
    run()
```

- [ ] **Step 2: 提交**

```bash
git add backend/data_manager/nightly_data/nightly_master.py
git commit -m "feat(nightly_data): add nightly_master scheduler"
```

---

### Task 8: 配置 crontab 定时任务

**Files:**
- Modify: crontab 配置

- [ ] **Step 1: 添加 crontab 配置**

```bash
# 每天凌晨 00:30 执行夜间数据任务
0 30 * * * cd /home/ailearn/projects/TradeSnake && /home/ailearn/miniconda3/envs/tradesnake/bin/python backend/data_manager/nightly_data/nightly_master.py >> /home/ailearn/projects/TradeSnake/logs/nightly/cron.log 2>&1

# 查看 crontab
crontab -l
```

- [ ] **Step 2: 创建日志目录**

```bash
mkdir -p /home/ailearn/projects/TradeSnake/logs/nightly
```

- [ ] **Step 3: 手动测试一次**

```bash
cd /home/ailearn/projects/TradeSnake
/home/ailearn/miniconda3/envs/tradesnake/bin/python backend/data_manager/nightly_data/nightly_master.py
```

---

### Task 9: 在 KlineFiller 中添加 fill_index 和 fill_etf 方法

**Files:**
- Modify: `backend/data_manager/filler.py`

- [ ] **Step 1: 检查 KlineFiller 类结构**

```bash
grep -n "class KlineFiller" backend/data_manager/filler.py
```

- [ ] **Step 2: 添加 fill_index 方法**

```python
def fill_index(self, index_code: str, index_name: str = None) -> bool:
    """填充指数日K线数据

    Args:
        index_code: 指数代码，如 '000001' (上证指数)
        index_name: 指数名称

    Returns:
        是否成功
    """
    try:
        from tushare import pro
        ts = pro

        df = ts.index_daily(
            ts_code=f"{index_code}.{index_code[0:2] == '000' and 'SH' or 'SZ'}",
            start_date='20100101',
            end_date=datetime.now().strftime('%Y%m%d')
        )

        # 转换为 K 线记录格式并保存到 DuckDB
        records = []
        for _, row in df.iterrows():
            records.append({
                'code': index_code,
                'trade_date': row['trade_date'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['vol'],
                'amount': row['amount'] if 'amount' in row else 0,
            })

        if records:
            from backend.data_manager.duckdb_store import get_duckdb_store
            store = get_duckdb_store()
            store.insert_daily_kline_batch(records)

        return True
    except Exception as e:
        logger.warning(f"fill_index {index_code} failed: {e}")
        return False
```

- [ ] **Step 3: 添加 fill_etf 方法**

```python
def fill_etf(self, fund_code: str, fund_name: str = None) -> bool:
    """填充ETF日K线数据

    Args:
        fund_code: ETF代码，如 '510300' (沪深300ETF)
        fund_name: ETF名称

    Returns:
        是否成功
    """
    try:
        from tushare import pro
        ts = pro

        # ETF 代码需要添加 .SH 或 .SZ 后缀
        suffix = '.SH' if fund_code.startswith('5') else '.SZ'

        df = ts.fund_daily(
            ts_code=f"{fund_code}{suffix}",
            start_date='20100101',
            end_date=datetime.now().strftime('%Y%m%d')
        )

        # 转换为 K 线记录格式并保存
        records = []
        for _, row in df.iterrows():
            records.append({
                'code': fund_code,
                'trade_date': row['trade_date'],
                'open': row['open'],
                'high': row['high'],
                'low': row['low'],
                'close': row['close'],
                'volume': row['vol'],
                'amount': row['amount'] if 'amount' in row else 0,
            })

        if records:
            from backend.data_manager.duckdb_store import get_duckdb_store
            store = get_duckdb_store()
            store.insert_daily_kline_batch(records)

        return True
    except Exception as e:
        logger.warning(f"fill_etf {fund_code} failed: {e}")
        return False
```

- [ ] **Step 4: 提交**

```bash
git add backend/data_manager/filler.py
git commit -m "feat(filler): add fill_index and fill_etf methods"
```

---

## 实现计划总结

| Task | 任务 | 预计时间 |
|------|------|---------|
| 1 | 创建状态管理模块 | 10分钟 |
| 2 | 创建日志模块 | 5分钟 |
| 3 | 创建历史K线回填任务 | 15分钟 |
| 4 | 创建指数/ETF任务 | 15分钟 |
| 5 | 创建多源验证任务 | 15分钟 |
| 6 | 创建预测更新任务 | 10分钟 |
| 7 | 创建主调度脚本 | 10分钟 |
| 8 | 配置 crontab | 5分钟 |
| 9 | 添加 fill_index/fill_etf | 20分钟 |

**总计约 1.5-2 小时**（不包括实际数据获取的网络等待时间）

---

Plan complete and saved to `docs/superpowers/plans/2026-04-24-nightly-data-enhancement-plan.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?