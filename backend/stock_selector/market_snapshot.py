"""
将 data_manager 拉取的全市场行情行，转换为 StockSelector / Rebalancer 所需的 market_data。

说明：当前产品范围仅考虑主板行情抽样（见 StockDataFetcher.get_batch_market_data），
与池内主板标的一致；非主板标的由上层股票列表/排除规则处理，不在此路径补行情。

market_data[code] 约定字段与 stock_selector、rebalancer 一致：
- daily_volume_20d: 近20日日均成交额（万元）
- volume_rank: 在当次 batch 内按流动性排序的名次（1 最活跃）
- turnover_rate: 换手率（%），无则 0
- volume_below_threshold_days: 连续低于观察池门槛的交易日数（无 K 线序列时为 0）
- momentum_streak: 连续强势日数（当前未算，默认 0）
- in_hs300 / in_zz500 / in_zz1000: 指数成分（由调用方传入）
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def normalize_stock_code(raw: str) -> str:
    raw = str(raw or "").strip()
    if raw.startswith("sh") or raw.startswith("sz"):
        return raw[2:]
    return raw


def build_market_data_from_fetcher_rows(
    rows: List[Dict[str, Any]],
    index_flags_by_code: Optional[Dict[str, Dict[str, bool]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Args:
        rows: `get_stock_data_api` 返回的列表项（含 code, amount 等）
        index_flags_by_code: 可选，{ "600000": {"in_hs300": True, ...}, ... }

    Returns:
        { "600000": { "daily_volume_20d": ..., "volume_rank": ... }, ... }
    """
    index_flags_by_code = index_flags_by_code or {}
    if not rows:
        return {}

    codes: List[str] = []
    for r in rows:
        c = normalize_stock_code(r.get("code", ""))
        if c:
            codes.append(c)

    avg_yuan_by_code: Dict[str, float] = {}
    try:
        from backend.data_manager.duckdb_store import get_duckdb_store

        avg_yuan_by_code = get_duckdb_store().get_avg_daily_amount_20d_bulk(codes)
    except Exception as e:
        logger.debug("DuckDB 批量日均成交额不可用，退回当日成交额近似: %s", e)

    scored: List[tuple] = []
    for r in rows:
        c = normalize_stock_code(r.get("code", ""))
        if not c:
            continue
        amt_yuan = float(r.get("amount") or 0)
        avg_yuan = float(avg_yuan_by_code.get(c, 0) or 0)
        if avg_yuan > 0:
            daily_vol_wan = avg_yuan / 10000.0
            rank_metric = avg_yuan
        else:
            daily_vol_wan = amt_yuan / 10000.0
            rank_metric = amt_yuan
        flags = index_flags_by_code.get(c, {})
        scored.append((c, daily_vol_wan, rank_metric, float(r.get("turnover_rate") or 0), flags))

    scored.sort(key=lambda x: x[2], reverse=True)
    rank_by_code = {t[0]: i + 1 for i, t in enumerate(scored)}

    out: Dict[str, Dict[str, Any]] = {}
    for c, daily_vol_wan, _rm, turnover_rate, flags in scored:
        # 连续低于门槛日数需日级序列，此处保持 0，避免误判降级
        below_days = 0

        out[c] = {
            "daily_volume_20d": daily_vol_wan,
            "turnover_rate": turnover_rate,
            "volume_rank": rank_by_code.get(c, 999),
            "volume_below_threshold_days": below_days,
            "momentum_streak": 0,
            "in_hs300": bool(flags.get("in_hs300")),
            "in_zz500": bool(flags.get("in_zz500")),
            "in_zz1000": bool(flags.get("in_zz1000")),
        }
    return out


def merge_market_data_for_stock_list(
    stock_codes: List[str],
    market_data: Dict[str, Dict[str, Any]],
    index_flags_by_code: Optional[Dict[str, Dict[str, bool]]] = None,
) -> Dict[str, Dict[str, Any]]:
    """确保股票列表中的每只代码在 market_data 中均有条目（缺失则用保守默认值）。"""
    index_flags_by_code = index_flags_by_code or {}
    merged = dict(market_data)
    for raw in stock_codes:
        c = normalize_stock_code(raw)
        if not c or c in merged:
            continue
        flags = index_flags_by_code.get(c, {})
        merged[c] = {
            "daily_volume_20d": 0.0,
            "turnover_rate": 0.0,
            "volume_rank": 999,
            "volume_below_threshold_days": 0,
            "momentum_streak": 0,
            "in_hs300": bool(flags.get("in_hs300")),
            "in_zz500": bool(flags.get("in_zz500")),
            "in_zz1000": bool(flags.get("in_zz1000")),
        }
    return merged
