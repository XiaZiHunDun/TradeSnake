"""
战力历史记录 - TradeSnake History
简单的历史战力记录功能
"""

import json
import os
from datetime import datetime
from typing import List, Dict

HISTORY_DIR = "/home/ailearn/projects/TradeSnake/data"
HISTORY_FILE = os.path.join(HISTORY_DIR, "cp_history.json")

def ensure_dir():
    """确保数据目录存在"""
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)

def save_history(stocks: List[Dict], date: str = None):
    """保存当日战力数据到历史记录"""
    ensure_dir()

    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    history = load_history()

    # 只保留最近30天的数据
    history[date] = {
        "stocks": {s["code"]: s for s in stocks},
        "saved_at": datetime.now().isoformat()
    }

    # 清理旧数据
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
    """加载最近N天的历史数据"""
    if not os.path.exists(HISTORY_FILE):
        return {}

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            history = json.load(f)

        # 只返回最近N天
        dates = sorted(history.keys(), reverse=True)[:days]
        return {d: history[d] for d in dates}
    except Exception as e:
        print(f"加载历史记录失败: {e}")
        return {}

def get_stock_history(code: str, days: int = 7) -> List[Dict]:
    """获取指定股票的历史战力"""
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

def get_cp_changes(days: int = 7) -> List[Dict]:
    """获取战力变化显著的股票"""
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

    # 按变化排序
    changes.sort(key=lambda x: x["change"], reverse=True)
    return changes


def get_historical_rankings(days: int = 30, limit: int = 10) -> List[Dict]:
    """获取历史TOP10榜单（每日冠军）"""
    history = load_history(days)
    if not history:
        return []

    rankings = []
    for date in sorted(history.keys(), reverse=True):
        stocks = history[date]["stocks"]
        # 按战力排序取TOP10
        sorted_stocks = sorted(stocks.values(), key=lambda x: x.get("total_cp", 0), reverse=True)[:limit]
        rankings.append({
            "date": date,
            "top10": [{
                "code": s.get("code"),
                "name": s.get("name"),
                "total_cp": s.get("total_cp", 0)
            } for s in sorted_stocks]
        })

    return rankings


def get_ranking_changes(days: int = 30) -> List[Dict]:
    """获取榜单排名变化（哪些股票新晋/跌出TOP10）"""
    history = load_history(days)
    if len(history) < 2:
        return []

    dates = sorted(history.keys())
    latest_stocks = history[dates[-1]]["stocks"]
    oldest_stocks = history[dates[0]]["stocks"]

    # 获取最新TOP10
    latest_top10 = set(s.get("code") for s in sorted(latest_stocks.values(), key=lambda x: x.get("total_cp", 0), reverse=True)[:10])
    # 获取最初TOP10
    oldest_top10 = set(s.get("code") for s in sorted(oldest_stocks.values(), key=lambda x: x.get("total_cp", 0), reverse=True)[:10])

    # 新晋TOP10
    new_entrants = latest_top10 - oldest_top10
    # 跌出TOP10
    drop_outs = oldest_top10 - latest_top10

    result = []
    for code in new_entrants:
        stock = latest_stocks.get(code, {})
        result.append({
            "code": code,
            "name": stock.get("name", ""),
            "type": "new",
            "total_cp": stock.get("total_cp", 0)
        })

    for code in drop_outs:
        stock = oldest_stocks.get(code, {})
        result.append({
            "code": code,
            "name": stock.get("name", ""),
            "type": "drop",
            "total_cp": stock.get("total_cp", 0)
        })

    return result
