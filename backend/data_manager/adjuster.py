"""
复权因子管理器 - Adjustment Factor Manager
=========================================
职责：获取和管理股票复权因子，支持前复权/后复权价格计算

功能：
1. 从Tushare/Akshare获取复权因子
2. 存储和管理除权事件
3. 提供前复权/后复权价格计算

复权方式：
- 前复权：以当前价为基准调整历史价，保持价格序列连续
- 后复权：以上市首日价为基准调整后续价，体现累计收益
- 不复权：原始数据
"""

import sqlite3
import pandas as pd
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass


# ==================== 路径配置 ====================

DATA_DIR = Path("/home/ailearn/projects/TradeSnake/data")
DB_PATH = DATA_DIR / "tradesnake.db"


# ==================== 数据类 ====================

@dataclass
class AdjustmentFactor:
    """复权因子"""
    symbol: str
    trade_date: date
    adj_type: str  # 'qfq' (前复权) or 'hfq' (后复权)
    factor: float  # 复权因子

    def __str__(self):
        return f"{self.symbol} {self.trade_date} {self.adj_type}: {self.factor}"


@dataclass
class ExRightEvent:
    """除权事件"""
    symbol: str
    ex_date: date
    ex_type: str  # 'bonus', 'rights', 'split', 'dividend'
    bonus_ratio: float = 0.0  # 送转股比例
    rights_price: float = 0.0  # 配股价
    dividend: float = 0.0  # 每股派息


# ==================== 复权因子管理器 ====================

class AdjustmentManager:
    """
    复权因子管理器

    负责：
    1. 获取复权因子数据
    2. 存储除权事件
    3. 计算复权价格
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._ensure_table()

    def _ensure_table(self):
        """确保除权事件表存在"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ex_right_factor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                adj_type TEXT NOT NULL,
                factor REAL NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(symbol, trade_date, adj_type)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ex_right_symbol_date
            ON ex_right_factor(symbol, trade_date)
        """)

        conn.commit()
        conn.close()

    def get_factor(self, symbol: str, trade_date: str, adj_type: str = 'qfq') -> Optional[float]:
        """
        获取指定日期的复权因子

        Args:
            symbol: 股票代码 (如 '000001')
            trade_date: 交易日期 (如 '2024-01-01')
            adj_type: 复权类型 ('qfq' 前复权, 'hfq' 后复权)

        Returns:
            复权因子，如果不存在返回None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT factor FROM ex_right_factor
            WHERE symbol = ? AND trade_date = ? AND adj_type = ?
        """, (symbol, trade_date, adj_type))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def get_latest_factor(self, symbol: str, adj_type: str = 'qfq') -> Optional[float]:
        """
        获取最新的复权因子

        Args:
            symbol: 股票代码
            adj_type: 复权类型

        Returns:
            最新复权因子
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT factor FROM ex_right_factor
            WHERE symbol = ? AND adj_type = ?
            ORDER BY trade_date DESC
            LIMIT 1
        """, (symbol, adj_type))

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def save_factor(self, symbol: str, trade_date: str, adj_type: str, factor: float):
        """
        保存复权因子

        Args:
            symbol: 股票代码
            trade_date: 交易日期
            adj_type: 复权类型
            factor: 复权因子
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO ex_right_factor
            (symbol, trade_date, adj_type, factor, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (symbol, trade_date, adj_type, factor, datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def save_factors(self, factors: List[Dict]):
        """
        批量保存复权因子

        Args:
            factors: 复权因子列表，每项包含 symbol, trade_date, adj_type, factor
        """
        if not factors:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        data = [
            (
                f['symbol'],
                f['trade_date'],
                f['adj_type'],
                f['factor'],
                datetime.now().isoformat()
            )
            for f in factors
        ]

        cursor.executemany("""
            INSERT OR REPLACE INTO ex_right_factor
            (symbol, trade_date, adj_type, factor, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, data)

        conn.commit()
        conn.close()

    def calculate_adjusted_price(
        self,
        raw_price: float,
        current_factor: float,
        historical_factor: float
    ) -> float:
        """
        计算复权价格

        公式: 复权价格 = 原始价格 × (当前因子 / 历史因子)

        Args:
            raw_price: 不复权价格
            current_factor: 当前复权因子
            historical_factor: 历史复权因子

        Returns:
            复权价格
        """
        if current_factor is None or historical_factor is None:
            return raw_price
        if current_factor == 0 or historical_factor == 0:
            return raw_price
        return raw_price * (current_factor / historical_factor)

    def get_adjusted_price(
        self,
        symbol: str,
        trade_date: str,
        raw_price: float,
        adj_type: str = 'qfq'
    ) -> float:
        """
        获取复权价格

        Args:
            symbol: 股票代码
            trade_date: 交易日期
            raw_price: 不复权价格
            adj_type: 复权类型

        Returns:
            复权价格
        """
        # 获取历史因子
        hist_factor = self.get_factor(symbol, trade_date, adj_type)
        if hist_factor is None:
            return raw_price

        # 获取当前因子
        curr_factor = self.get_latest_factor(symbol, adj_type)
        if curr_factor is None:
            return raw_price

        return self.calculate_adjusted_price(raw_price, curr_factor, hist_factor)

    def adjust_price_series(
        self,
        prices: List[Dict],
        adj_type: str = 'qfq'
    ) -> List[Dict]:
        """
        调整价格序列（用于K线数据）

        Args:
            prices: 价格列表，每项包含 code, date, close 等
            adj_type: 复权类型

        Returns:
            调整后的价格列表
        """
        if not prices:
            return []

        result = []
        for p in prices:
            code = p.get('code') or p.get('symbol')
            date_str = p.get('date') or p.get('trade_date')

            if not code or not date_str:
                result.append(p)
                continue

            # 获取当前因子
            curr_factor = self.get_latest_factor(code, adj_type)
            if curr_factor is None:
                result.append(p)
                continue

            # 获取历史因子
            hist_factor = self.get_factor(code, date_str, adj_type)
            if hist_factor is None:
                result.append(p)
                continue

            # 调整价格字段
            adjusted = p.copy()
            for field in ['open', 'high', 'low', 'close']:
                if field in p and p[field] is not None:
                    adjusted[field] = self.calculate_adjusted_price(
                        p[field], curr_factor, hist_factor
                    )

            result.append(adjusted)

        return result

    def fetch_from_tushare(self, codes: List[str] = None) -> int:
        """
        从Tushare获取复权因子

        需要先安装tushare并设置token

        Args:
            codes: 股票代码列表，None表示获取所有

        Returns:
            获取的记录数
        """
        try:
            import tushare as ts
        except ImportError:
            print("Tushare未安装，跳过获取")
            return 0

        try:
            pro = ts.pro_api()
        except Exception as e:
            print(f"Tushare API初始化失败: {e}")
            return 0

        factors = []

        # 获取单只股票的复权因子
        stock_codes = codes or self._get_all_codes()

        for code in stock_codes[:100]:  # 限制数量，避免积分消耗过快
            try:
                # 转换代码格式
                ts_code = self._convert_to_ts_code(code)

                # 获取前复权因子
                df = pro.adj_factor(ts_code=ts_code, trade_date='')
                if df is not None and len(df) > 0:
                    for _, row in df.iterrows():
                        factors.append({
                            'symbol': code,
                            'trade_date': row['trade_date'],
                            'adj_type': 'qfq',
                            'factor': row['adj_factor']
                        })

            except Exception as e:
                print(f"获取 {code} 复权因子失败: {e}")
                continue

        if factors:
            self.save_factors(factors)

        return len(factors)

    def fetch_from_akshare(self, codes: List[str] = None) -> int:
        """
        从Akshare获取复权因子

        Args:
            codes: 股票代码列表

        Returns:
            获取的记录数
        """
        try:
            import akshare as ak
        except ImportError:
            print("Akshare未安装，跳过获取")
            return 0

        factors = []

        stock_codes = codes or self._get_all_codes()

        for code in stock_codes[:100]:
            try:
                df = ak.stock_zh_a_daily_basis(symbol=code, adjust="qfq")
                if df is not None and len(df) > 0:
                    # 取第一天的因子作为基准
                    first_factor = df.iloc[0]['factor'] if 'factor' in df.columns else 1.0
                    factors.append({
                        'symbol': code,
                        'trade_date': df.iloc[0]['date'] if 'date' in df.columns else str(date.today()),
                        'adj_type': 'qfq',
                        'factor': first_factor
                    })
            except Exception as e:
                print(f"获取 {code} 复权因子失败: {e}")
                continue

        if factors:
            self.save_factors(factors)

        return len(factors)

    def _get_all_codes(self) -> List[str]:
        """获取所有股票代码"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT code FROM stocks LIMIT 500")
        codes = [row[0] for row in cursor.fetchall()]

        conn.close()
        return codes

    def _convert_to_ts_code(self, code: str) -> str:
        """转换代码为Tushare格式"""
        code = code.strip().zfill(6)
        suffix = '.SH' if code.startswith('6') else '.SZ'
        return f"{code}{suffix}"

    def get_stats(self) -> Dict:
        """获取统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM ex_right_factor")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT symbol) FROM ex_right_factor")
        symbols = cursor.fetchone()[0]

        cursor.execute("SELECT MAX(trade_date) FROM ex_right_factor WHERE adj_type = 'qfq'")
        latest = cursor.fetchone()[0]

        conn.close()

        return {
            'total_factors': total,
            'total_symbols': symbols,
            'latest_update': latest,
        }


# ==================== 全局单例 ====================

_adjuster = None


def get_adjuster() -> AdjustmentManager:
    """获取复权因子管理器单例"""
    global _adjuster
    if _adjuster is None:
        _adjuster = AdjustmentManager()
    return _adjuster


# ==================== 便捷函数 ====================

def get_adjusted_price(symbol: str, trade_date: str, raw_price: float, adj_type: str = 'qfq') -> float:
    """获取复权价格"""
    return get_adjuster().get_adjusted_price(symbol, trade_date, raw_price, adj_type)


def adjust_price_series(prices: List[Dict], adj_type: str = 'qfq') -> List[Dict]:
    """批量调整价格序列"""
    return get_adjuster().adjust_price_series(prices, adj_type)
