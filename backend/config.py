"""
TradeSnake 集中式路径配置
所有文件系统路径从此模块获取，支持环境变量覆盖。
"""
import os
from pathlib import Path

# 项目根目录：从 config.py 所在位置向上推导
# backend/config.py → backend/ → TradeSnake/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 数据根目录（支持 TRADESNAKE_DATA_DIR 环境变量覆盖）
DATA_DIR = Path(os.environ.get('TRADESNAKE_DATA_DIR', str(PROJECT_ROOT / 'data')))

# === 数据库路径 ===
SQLITE_PATH = DATA_DIR / 'tradesnake.db'
DUCKDB_PATH = DATA_DIR / 'historical.duckdb'
PREDICTION_DB_PATH = DATA_DIR / 'tradesnake_prediction.db'
CP_HISTORY_DB_PATH = DATA_DIR / 'tradesnake_cp_history.db'
NIGHTLY_STATE_DB_PATH = DATA_DIR / 'nightly_state.db'
BACKTEST_REPORTS_DB_PATH = DATA_DIR / 'backtest_reports.db'
SIMULATOR_DB_PATH = DATA_DIR / 'simulator.db'

# === 目录 ===
BACKUP_DIR = DATA_DIR / 'backup'
LOG_DIR = PROJECT_ROOT / 'logs' / 'nightly'
CACHE_DIR = DATA_DIR  # JSON 缓存文件在 data/ 下

# === CP 历史 JSON 回退 ===
HISTORY_DIR = DATA_DIR
HISTORY_FILE = HISTORY_DIR / 'cp_history.json'

# === API 状态文件 ===
REFRESH_STATE_FILE = DATA_DIR / '.refresh_state.json'
