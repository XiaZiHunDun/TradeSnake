"""
战力历史记录 - History Module v19.7
=====================================

存储策略：
- 主存储：data_manager/cp_history_store.py（SQLite WAL模式）
- 缓存：内存LRU（减少SQLite查询压力）

迁移记录：
- v19.7: cp_history 迁移到 data_manager 统一管理
  原：simulator/database.py
  新：data_manager/cp_history_store.py

设计文档：docs/plans/DATA_LIFECYCLE_MANAGEMENT.md
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from functools import lru_cache

# 尝试导入 CPHistoryStore（如果可用）
try:
    from backend.data_manager.cp_history_store import get_cp_history_store, CPHistoryStore
    _HAS_CP_STORE = True
except ImportError:
    get_cp_history_store = None  # type: ignore
    CPHistoryStore = None  # type: ignore
    _HAS_CP_STORE = False

# JSON文件路径（仅用于兼容旧数据和迁移）
from backend.config import HISTORY_DIR, HISTORY_FILE


def ensure_dir():
    """确保数据目录存在"""
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)


# ==================== SQLite存储（v19.7由data_manager管理） ====================

def _get_cp_store() -> Optional[CPHistoryStore]:
    """获取CPHistoryStore实例"""
    if not _HAS_CP_STORE:
        return None
    try:
        return get_cp_history_store()
    except Exception:
        return None


def save_history(stocks: List[Dict], date: str = None) -> bool:
    """保存当日战力数据到历史记录

    Args:
        stocks: 股票战力列表
        date: 日期，默认为当天

    Returns:
        保存是否成功
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    # 使用 data_manager 的 CPHistoryStore
    store = _get_cp_store()
    if store is not None:
        try:
            store.record_cp_history(stocks, date)
            return True
        except Exception as e:
            print(f"CPHistoryStore保存历史记录失败: {e}")

    # 降级到JSON存储
    return _save_history_json(stocks, date)


def _save_history_json(stocks: List[Dict], date: str = None) -> bool:
    """JSON文件存储（兼容旧版本）"""
    ensure_dir()

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    history = load_history()

    history[date] = {
        "stocks": {s["code"]: s for s in stocks},
        "saved_at": datetime.now().isoformat()
    }

    dates = sorted(history.keys(), reverse=True)
    if len(dates) > 30:
        for old_date in dates[30:]:
            del history[old_date]

    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存历史记录失败: {e}")
        return False


def load_history(days: int = 7) -> Dict:
    """加载最近N天的历史数据 v18.2

    优先从SQLite加载，SQLite不可用时从JSON加载
    """
    # 优先使用SQLite
    store = _get_cp_store()
    if store is not None:
        try:
            return _load_history_sqlite(days)
        except Exception as e:
            print(f"SQLite加载历史记录失败，降级到JSON: {e}")

    # 降级到JSON存储
    return _load_history_json(days)


def _load_history_sqlite(days: int = 7) -> Dict:
    """从CPHistoryStore加载历史数据"""
    store = _get_cp_store()
    if store is None:
        return {}

    result = {}

    # 获取所有有历史的代码
    all_codes = store.get_all_codes()

    # 获取最近N天的日期
    conn = store._get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT recorded_at FROM cp_history
        ORDER BY recorded_at DESC
        LIMIT ?
    """, (days,))
    date_rows = cursor.fetchall()
    conn.close()

    dates = [row['recorded_at'] for row in date_rows] if date_rows else []

    for date in dates:
        stocks_data = store.get_cp_history_by_date(date)

        stocks = {}
        for row in stocks_data:
            code = row['code']
            stocks[code] = {
                "code": code,
                "name": row['name'],
                "total_cp": row['total_cp'],
                "growth_score": row['growth_score'],
                "value_score": row['value_score'],
                "quality_score": row['quality_score'],
                "momentum_score": row['momentum_score'],
                "risk_score": row['risk_score'],
                "rank": row['rank'],
            }

        result[date] = {
            "stocks": stocks,
            "saved_at": date
        }

    return result


def _load_history_json(days: int = 7) -> Dict:
    """从JSON文件加载历史数据（兼容旧版本）"""
    if not os.path.exists(HISTORY_FILE):
        return {}

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)

        dates = sorted(history.keys(), reverse=True)[:days]
        return {d: history[d] for d in dates}
    except Exception as e:
        print(f"加载历史记录失败: {e}")
        return {}


def get_stock_history(code: str, days: int = 7) -> List[Dict]:
    """获取指定股票的历史战力 v18.2"""
    history = load_history(days)
    result = []

    for date in sorted(history.keys()):
        date_data = history.get(date, {})
        stocks_data = date_data.get("stocks", {})
        stock = stocks_data.get(code)
        if stock:
            result.append({
                "date": date,
                "total_cp": stock.get("total_cp", 0),
                "growth_score": stock.get("growth_score", 0),
                "value_score": stock.get("value_score", 0),
                "quality_score": stock.get("quality_score", 0),
                "momentum_score": stock.get("momentum_score", 0),
            })

    return result


def calc_momentum_nd(code: str, days: int = 5) -> float:
    """计算N日动量（战力变化值） v18.2"""
    history = load_history(days)
    if len(history) < 2:
        return 0

    dates = sorted(history.keys())
    if len(dates) < days:
        return 0

    oldest_cp = history[dates[0]]["stocks"].get(code, {}).get("total_cp", 0)
    newest_cp = history[dates[-1]]["stocks"].get(code, {}).get("total_cp", 0)

    if oldest_cp == 0:
        return 0

    return newest_cp - oldest_cp


def get_momentum_3d(code: str) -> float:
    """计算3日动量"""
    return calc_momentum_nd(code, 3)


def get_momentum_5d(code: str) -> float:
    """计算5日动量"""
    return calc_momentum_nd(code, 5)


def get_cp_changes(days: int = 7) -> List[Dict]:
    """获取战力变化显著的股票 v18.2"""
    history = load_history(days)
    if len(history) < 2:
        return []

    dates = sorted(history.keys())
    old_data = history[dates[0]]["stocks"]
    new_data = history[dates[-1]]["stocks"]

    changes = []
    for code in new_data:
        if code in old_data:
            old_cp = old_data[code].get("total_cp", 0)
            new_cp = new_data[code].get("total_cp", 0)
            if old_cp > 0:
                change = new_cp - old_cp
                changes.append({
                    "code": code,
                    "name": new_data[code].get("name", ""),
                    "old_cp": old_cp,
                    "new_cp": new_cp,
                    "change": change,
                    "change_pct": (change / old_cp * 100) if old_cp > 0 else 0
                })

    changes.sort(key=lambda x: x["change"], reverse=True)
    return changes


def get_historical_rankings(days: int = 30, limit: int = 10) -> List[Dict]:
    """获取历史TOP10榜单（每日冠军） v18.2"""
    history = load_history(days)
    if not history:
        return []

    rankings = []
    for date in sorted(history.keys(), reverse=True):
        stocks = history[date]["stocks"]
        sorted_stocks = sorted(stocks.values(), key=lambda x: x.get("total_cp", 0), reverse=True)[:limit]
        rankings.append({
            "date": date,
            "top10": [{"code": s.get("code"), "name": s.get("name"), "total_cp": s.get("total_cp", 0)} for s in sorted_stocks]
        })

    return rankings


def get_ranking_changes(days: int = 30) -> List[Dict]:
    """获取榜单排名变化（哪些股票新晋/跌出TOP10） v18.2"""
    history = load_history(days)
    if len(history) < 2:
        return []

    dates = sorted(history.keys())
    latest_stocks = history[dates[-1]]["stocks"]
    oldest_stocks = history[dates[0]]["stocks"]

    latest_top10 = set(s.get("code") for s in sorted(latest_stocks.values(), key=lambda x: x.get("total_cp", 0), reverse=True)[:10])
    oldest_top10 = set(s.get("code") for s in sorted(oldest_stocks.values(), key=lambda x: x.get("total_cp", 0), reverse=True)[:10])

    new_entrants = latest_top10 - oldest_top10
    drop_outs = oldest_top10 - latest_top10

    result = []
    for code in new_entrants:
        stock = latest_stocks.get(code, {})
        result.append({"code": code, "name": stock.get("name", ""), "type": "new", "total_cp": stock.get("total_cp", 0)})

    for code in drop_outs:
        stock = oldest_stocks.get(code, {})
        result.append({"code": code, "name": stock.get("name", ""), "type": "drop", "total_cp": stock.get("total_cp", 0)})

    return result


# ==================== 迁移工具 ====================

def migrate_json_to_sqlite() -> Dict:
    """将JSON历史数据迁移到SQLite

    Returns:
        迁移结果统计
    """
    if not os.path.exists(HISTORY_FILE):
        return {"success": True, "message": "No JSON file found", "records": 0}

    store = _get_cp_store()
    if store is None:
        return {"success": False, "error": "Database not available"}

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)

        total = 0
        for date, data in history.items():
            stocks = list(data.get("stocks", {}).values())
            store.record_cp_history(stocks, date)
            total += len(stocks)

        return {"success": True, "records": total, "dates": len(history)}
    except Exception as e:
        return {"success": False, "error": str(e)}
