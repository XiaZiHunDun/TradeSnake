"""
预测结果数据存储模块

由 data_manager 统一管理预测结果数据：
- 存储：SQLite WAL 模式
- 生命周期：90天保留
- 清理：由 data_manager/cleanup.py 统一管理

设计文档：docs/plans/engine/gain_predictor/GAIN_PREDICTOR.md
设计文档：docs/plans/engine/probability_predictor/PROBABILITY_PREDICTOR.md
"""

import sqlite3
import threading
import json
import ast
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path


def _normalize_code(raw_code: str) -> str:
    """标准化股票代码为6位格式 (v19.9.5)"""
    code = raw_code
    if code.startswith('sh'):
        code = code[2:]
    elif code.startswith('sz'):
        code = code[2:]
    if '.' in code:
        code = code.split('.')[0]
    return code


def _tuple_to_str(tup: Tuple) -> str:
    """将tuple转换为字符串，用于数据库存储"""
    if tup is None:
        return None
    return '(' + ', '.join(str(float(x)) for x in tup) + ')'

def _str_to_tuple(s: str) -> Tuple:
    """将字符串转换回tuple"""
    if s is None or s == '':
        return None
    try:
        return ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return None


class PredictionStore:
    """预测结果数据存储"""

    _instance: Optional['PredictionStore'] = None
    _lock = threading.Lock()

    def __new__(cls, db_path: str = None):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return

        if db_path is None:
            from backend.config import PREDICTION_DB_PATH
            db_path = str(PREDICTION_DB_PATH)

        self.db_path = db_path
        self._write_lock = threading.Lock()
        self._ensure_db()
        self._initialized = True

    def _ensure_db(self):
        """确保数据库和表存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建涨幅预测表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gain_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                predicted_gain_3d REAL DEFAULT 0,
                predicted_gain_5d REAL DEFAULT 0,
                confidence REAL DEFAULT 0,
                confidence_interval_3d TEXT,
                confidence_interval_5d TEXT,
                features TEXT,
                model_version TEXT DEFAULT 'rule_v19.8',
                recorded_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建概率预测表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS probability_predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                up_probability_3d REAL DEFAULT 0,
                up_probability_5d REAL DEFAULT 0,
                confidence REAL DEFAULT 0,
                confidence_interval_3d TEXT,
                confidence_interval_5d TEXT,
                risk_level TEXT DEFAULT 'medium',
                features TEXT,
                model_version TEXT DEFAULT 'rule_v19.8',
                recorded_at TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # v19.9.9: 迁移旧表添加 confidence_interval 字段
        cursor.execute("PRAGMA table_info(probability_predictions)")
        existing_cols = [col[1] for col in cursor.fetchall()]
        if 'confidence_interval_3d' not in existing_cols:
            cursor.execute("ALTER TABLE probability_predictions ADD COLUMN confidence_interval_3d TEXT")
        if 'confidence_interval_5d' not in existing_cols:
            cursor.execute("ALTER TABLE probability_predictions ADD COLUMN confidence_interval_5d TEXT")

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gain_pred_date ON gain_predictions(recorded_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gain_pred_code ON gain_predictions(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gain_pred_date_code ON gain_predictions(recorded_at, code)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prob_pred_date ON probability_predictions(recorded_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prob_pred_code ON probability_predictions(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prob_pred_date_code ON probability_predictions(recorded_at, code)")

        # 启用 WAL 模式
        cursor.execute("PRAGMA journal_mode=WAL")

        conn.commit()
        conn.close()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_gain_predictions(self, predictions: List[Dict], date: str = None) -> int:
        """保存涨幅预测

        Args:
            predictions: 涨幅预测列表
            date: 日期，默认当天

        Returns:
            保存的股票数量
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM gain_predictions WHERE recorded_at = ?", (date,))

            for pred in predictions:
                features_json = json.dumps(pred.get('features', {})) if pred.get('features') else None
                # v19.9.5: 标准化代码格式
                code = _normalize_code(pred.get('code', ''))
                cursor.execute("""
                    INSERT INTO gain_predictions (
                        code, name, predicted_gain_3d, predicted_gain_5d,
                        confidence, confidence_interval_3d, confidence_interval_5d,
                        features, model_version, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    code,
                    pred.get('name'),
                    pred.get('predicted_gain_3d', 0),
                    pred.get('predicted_gain_5d', 0),
                    pred.get('confidence', 0),
                    _tuple_to_str(pred.get('confidence_interval_3d')) if pred.get('confidence_interval_3d') else None,
                    _tuple_to_str(pred.get('confidence_interval_5d')) if pred.get('confidence_interval_5d') else None,
                    features_json,
                    pred.get('model_version', 'rule_v19.8'),
                    date
                ))

            conn.commit()
            conn.close()
            return len(predictions)

    def record_probability_predictions(self, predictions: List[Dict], date: str = None) -> int:
        """保存概率预测

        Args:
            predictions: 概率预测列表
            date: 日期，默认当天

        Returns:
            保存的股票数量
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM probability_predictions WHERE recorded_at = ?", (date,))

            for pred in predictions:
                features_json = json.dumps(pred.get('features', {})) if pred.get('features') else None
                # v19.9.5: 标准化代码格式
                code = _normalize_code(pred.get('code', ''))
                # confidence_interval 使用 _tuple_to_str 格式，与 gain_predictions 保持一致
                ci_3d = _tuple_to_str(pred.get('confidence_interval_3d', (0.0, 1.0)))
                ci_5d = _tuple_to_str(pred.get('confidence_interval_5d', (0.0, 1.0)))
                cursor.execute("""
                    INSERT INTO probability_predictions (
                        code, name, up_probability_3d, up_probability_5d,
                        confidence, confidence_interval_3d, confidence_interval_5d,
                        risk_level, features, model_version, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    code,
                    pred.get('name'),
                    pred.get('up_probability_3d', 0),
                    pred.get('up_probability_5d', 0),
                    pred.get('confidence', 0),
                    ci_3d,
                    ci_5d,
                    pred.get('risk_level', 'medium'),
                    features_json,
                    pred.get('model_version', 'rule_v19.8'),
                    date
                ))

            conn.commit()
            conn.close()
            return len(predictions)

    def get_gain_predictions(self, code: str, days: int = 30) -> List[Dict]:
        """获取指定股票的历史涨幅预测

        Args:
            code: 股票代码
            days: 获取天数

        Returns:
            历史涨幅预测列表
        """
        # v19.9.5: 标准化代码格式
        code = _normalize_code(code)
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM gain_predictions WHERE code = ?
            ORDER BY recorded_at DESC LIMIT ?
        """, (code, days))

        result = []
        for row in cursor.fetchall():
            record = dict(row)
            if record.get('features'):
                record['features'] = json.loads(record['features'])
            if record.get('confidence_interval_3d'):
                record['confidence_interval_3d'] = _str_to_tuple(record['confidence_interval_3d'])
            if record.get('confidence_interval_5d'):
                record['confidence_interval_5d'] = _str_to_tuple(record['confidence_interval_5d'])
            result.append(record)

        conn.close()
        return result

    def get_probability_predictions(self, code: str, days: int = 30) -> List[Dict]:
        """获取指定股票的历史概率预测

        Args:
            code: 股票代码
            days: 获取天数

        Returns:
            历史概率预测列表
        """
        # v19.9.5: 标准化代码格式
        code = _normalize_code(code)
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM probability_predictions WHERE code = ?
            ORDER BY recorded_at DESC LIMIT ?
        """, (code, days))

        result = []
        for row in cursor.fetchall():
            record = dict(row)
            if record.get('features'):
                record['features'] = json.loads(record['features'])
            if record.get('confidence_interval_3d'):
                record['confidence_interval_3d'] = _str_to_tuple(record['confidence_interval_3d'])
            if record.get('confidence_interval_5d'):
                record['confidence_interval_5d'] = _str_to_tuple(record['confidence_interval_5d'])
            result.append(record)

        conn.close()
        return result

    def get_gain_predictions_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的涨幅预测

        Args:
            date: 日期 (YYYY-MM-DD)

        Returns:
            该日期的涨幅预测列表
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM gain_predictions WHERE recorded_at = ?
            ORDER BY predicted_gain_5d DESC
        """, (date,))

        result = []
        for row in cursor.fetchall():
            record = dict(row)
            if record.get('features'):
                record['features'] = json.loads(record['features'])
            if record.get('confidence_interval_3d'):
                record['confidence_interval_3d'] = _str_to_tuple(record['confidence_interval_3d'])
            if record.get('confidence_interval_5d'):
                record['confidence_interval_5d'] = _str_to_tuple(record['confidence_interval_5d'])
            result.append(record)

        conn.close()
        return result

    def get_probability_predictions_by_date(self, date: str) -> List[Dict]:
        """获取指定日期的概率预测

        Args:
            date: 日期 (YYYY-MM-DD)

        Returns:
            该日期的概率预测列表
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM probability_predictions WHERE recorded_at = ?
            ORDER BY up_probability_5d DESC
        """, (date,))

        result = []
        for row in cursor.fetchall():
            record = dict(row)
            if record.get('features'):
                record['features'] = json.loads(record['features'])
            if record.get('confidence_interval_3d'):
                record['confidence_interval_3d'] = _str_to_tuple(record['confidence_interval_3d'])
            if record.get('confidence_interval_5d'):
                record['confidence_interval_5d'] = _str_to_tuple(record['confidence_interval_5d'])
            result.append(record)

        conn.close()
        return result

    def get_all_codes(self) -> List[str]:
        """获取所有有预测历史的股票代码"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT code FROM gain_predictions")
        gain_codes = set(row['code'] for row in cursor.fetchall())

        cursor.execute("SELECT DISTINCT code FROM probability_predictions")
        prob_codes = set(row['code'] for row in cursor.fetchall())

        conn.close()
        return list(gain_codes | prob_codes)

    def delete_old_records(self, before_date: str) -> Dict[str, int]:
        """删除指定日期之前的记录

        Args:
            before_date: 日期 (YYYY-MM-DD)

        Returns:
            删除的记录数统计
        """
        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.cursor()

            cursor.execute("DELETE FROM gain_predictions WHERE recorded_at < ?", (before_date,))
            gain_deleted = cursor.rowcount

            cursor.execute("DELETE FROM probability_predictions WHERE recorded_at < ?", (before_date,))
            prob_deleted = cursor.rowcount

            conn.commit()
            conn.close()
            return {
                'gain_predictions': gain_deleted,
                'probability_predictions': prob_deleted
            }


# 全局实例
_store: Optional[PredictionStore] = None


def get_prediction_store() -> PredictionStore:
    """获取 PredictionStore 单例"""
    global _store
    if _store is None:
        _store = PredictionStore()
    return _store
