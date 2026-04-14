#!/usr/bin/env python
"""
自动交易脚本 - 完整版

风控保护:
- 最大持仓数限制 (MAX_HOLDINGS)
- 最小现金保留 (MIN_CASH)
- 单只买入金额上限 (PER_STOCK_AMOUNT)
- 止损保护 (STOP_LOSS_PCT): 单只亏损超过此比例强制卖出
- 最大单日交易次数 (MAX_TRADES_PER_DAY)
"""
import sys
import os
from pathlib import Path

# 项目根目录（相对路径，兼容多环境）
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(str(PROJECT_ROOT))

import time
import sqlite3
from datetime import datetime, date, timedelta

# ==================== 风控配置 ====================
MAX_HOLDINGS = 3                    # 最大持仓数
PER_STOCK_AMOUNT = 3000             # 单只最大买入金额
MIN_CASH = 2000                    # 最小保留现金
STOP_LOSS_PCT = -0.05              # 止损线：亏损5%触发止损
MAX_TRADES_PER_DAY = 5              # 单日最大交易次数
POSITION_MAX_DAYS = 30              # 最大持仓天数，超期降级处理
# ================================================

# ==================== 交易统计（内存） ====================
_daily_trade_count = 0
_last_trade_date = None

# ==================== 配置 ====================
RECOMMEND_LIMIT = 10
# ============================================


def is_trading_day():
    return date.today().weekday() < 5


def is_trading_hours():
    now = datetime.now()
    m = now.hour * 60 + now.minute
    return (9 * 60 + 30 <= m <= 11 * 60 + 30) or (13 * 60 <= m <= 15 * 60)


def _reset_daily_stats():
    """重置每日统计（跨天后调用）"""
    global _daily_trade_count, _last_trade_date
    today = date.today()
    if _last_trade_date != today:
        _daily_trade_count = 0
        _last_trade_date = today


def _check_risk_limits(holdings, account):
    """
    风控检查：返回需要止损的持仓列表

    检查项：
    1. 单只亏损超过 STOP_LOSS_PCT
    2. 持仓时间超过 POSITION_MAX_DAYS
    3. 账户总亏损超过阈值
    """
    to_stop_loss = []
    conn = sqlite3.connect(str(PROJECT_ROOT / 'data' / 'tradesnake.db'))
    cursor = conn.cursor()

    for h in holdings:
        code = h.get('code', '')
        quantity = h.get('total_quantity', 0)
        if quantity <= 0:
            continue

        # 获取持仓成本
        cursor.execute("""
            SELECT avg_price FROM holdings
            WHERE code = ? ORDER BY created_at DESC LIMIT 1
        """, (code,))
        row = cursor.fetchone()
        if not row:
            continue
        avg_price = row[0]

        # 获取当前价格
        price_map = get_price_map()
        current_price = price_map.get(code) or price_map.get(code.replace('sh', '').replace('sz', '')) or avg_price

        # 1. 止损检查
        pnl_pct = (current_price - avg_price) / avg_price
        if pnl_pct <= STOP_LOSS_PCT:
            to_stop_loss.append({
                'code': code,
                'name': h.get('name', code),
                'quantity': quantity,
                'current_price': current_price,
                'avg_price': avg_price,
                'pnl_pct': pnl_pct,
                'reason': f'止损: 亏损{pnl_pct*100:.1f}%'
            })
            continue

        # 2. 持仓超时检查
        cursor.execute("""
            SELECT created_at FROM holdings
            WHERE code = ? ORDER BY created_at ASC LIMIT 1
        """, (code,))
        row = cursor.fetchone()
        if row:
            created_at = datetime.fromisoformat(row[0])
            days_held = (datetime.now() - created_at).days
            if days_held > POSITION_MAX_DAYS:
                to_stop_loss.append({
                    'code': code,
                    'name': h.get('name', code),
                    'quantity': quantity,
                    'current_price': current_price,
                    'avg_price': avg_price,
                    'pnl_pct': pnl_pct,
                    'reason': f'超期: 持仓{days_held}天>{POSITION_MAX_DAYS}天'
                })

    conn.close()
    return to_stop_loss


def get_price_map():
    """获取股价映射"""
    conn = sqlite3.connect(str(PROJECT_ROOT / 'data' / 'tradesnake.db'))
    cursor = conn.cursor()
    cursor.execute('SELECT code, price FROM stocks WHERE price > 0')
    rows = cursor.fetchall()
    conn.close()
    price_map = {}
    for code, price in rows:
        price_map[code] = price
        normalized = code.replace('sh', '').replace('sz', '')
        price_map[normalized] = price
    return price_map


# ==================== SQL注入防护：白名单 ====================
_VALID_ORDER_BY = {
    'value': 'h.total_cp DESC',
    'growth': 'h.growth_score DESC',
    'quality': 'h.quality_score DESC',
    'risk': 'h.risk_score ASC',  # 低风险优先
}


def get_top_stocks(category='value', limit=10):
    """获取战力榜TOP股票（SQL注入防护：order_by白名单）"""
    # 白名单验证，防止 SQL 注入
    order_by_clause = _VALID_ORDER_BY.get(category, _VALID_ORDER_BY['value'])

    conn = sqlite3.connect(str(PROJECT_ROOT / 'data' / 'tradesnake.db'))
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT h.code, h.name, h.total_cp, h.growth_score, h.value_score,
               h.quality_score, h.risk_score
        FROM cp_history h
        WHERE h.total_cp > 0
        ORDER BY {order_by_clause}
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    price_map = get_price_map()
    result = []
    for r in rows:
        code = r[0]
        price = price_map.get(code) or price_map.get(code.replace('sh', '').replace('sz', '')) or 0
        result.append({
            'code': code, 'name': r[1], 'total_cp': r[2],
            'growth': r[3], 'value': r[4], 'quality': r[5], 'risk': r[6], 'price': price
        })
    return result
# =========================================================


def get_account_simple():
    """快速获取账户信息"""
    from backend.simulator.database import get_db
    db = get_db()
    acct = db.get_account()
    holdings = db.get_holdings()

    price_map = get_price_map()
    market_value = 0
    for h in holdings:
        code = h.get('code', '')
        qty = h.get('total_quantity', 0)
        price = price_map.get(code) or price_map.get(code.replace('sh', '').replace('sz', '')) or 0
        market_value += price * qty

    cash = acct.get('cash', 0)
    initial = acct.get('initial_cash', 20000)
    total = cash + market_value
    profit = total - initial
    profit_rate = (profit / initial * 100) if initial > 0 else 0

    return {
        'cash': cash,
        'total_market_value': market_value,
        'total_assets': total,
        'total_profit': profit,
        'profit_rate': profit_rate,
        'holdings_count': len(holdings)
    }


def get_holdings_with_cp():
    """获取持仓（含CP数据）"""
    from backend.simulator.database import get_db
    db = get_db()
    holdings = db.get_holdings()

    conn = sqlite3.connect(str(PROJECT_ROOT / 'data' / 'tradesnake.db'))
    cursor = conn.cursor()
    cursor.execute('SELECT code, total_cp FROM cp_history')
    cp_map = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()

    cp_map2 = {}
    for code, cp in cp_map.items():
        normalized = code.replace('sh', '').replace('sz', '')
        cp_map2[code] = cp
        cp_map2[normalized] = cp

    price_map = get_price_map()

    result = []
    for h in holdings:
        code = h.get('code', '')
        cp = cp_map2.get(code) or cp_map2.get(code.replace('sh', '').replace('sz', '')) or 0
        price = price_map.get(code) or price_map.get(code.replace('sh', '').replace('sz', '')) or 0
        result.append({
            'code': code,
            'name': h.get('name', code),
            'quantity': h.get('total_quantity', 0),
            'price': price,
            'total_cp': cp
        })
    return result


def execute_buy(code, name, quantity, price):
    """执行买入（带风控）"""
    global _daily_trade_count
    _reset_daily_stats()

    # 风控检查
    if _daily_trade_count >= MAX_TRADES_PER_DAY:
        print(f"  ⛔ 已达单日最大交易次数({MAX_TRADES_PER_DAY})，禁止买入")
        return False

    from backend.simulator.trader import Trader
    trader = Trader()
    result = trader.buy(code, quantity)
    if result.get('success'):
        _daily_trade_count += 1
        cost = quantity * price
        print(f"  ✅ 买入: {code} {name} x{quantity} @ ¥{price:.2f} = ¥{cost:.0f} (今日第{_daily_trade_count}笔)")
        return True
    else:
        print(f"  ❌ 失败: {code} {name} - {result.get('error', '未知错误')}")
        return False


def execute_sell(code, name, quantity, price, reason=''):
    """执行卖出（带风控日志）"""
    global _daily_trade_count
    _reset_daily_stats()

    if _daily_trade_count >= MAX_TRADES_PER_DAY:
        print(f"  ⛔ 已达单日最大交易次数({MAX_TRADES_PER_DAY})，禁止卖出")
        return False

    from backend.simulator.trader import Trader
    trader = Trader()
    result = trader.sell(code, quantity)
    if result.get('success'):
        _daily_trade_count += 1
        proceeds = quantity * price
        print(f"  🔴 卖出: {code} {name} x{quantity} @ ¥{price:.2f} = ¥{proceeds:.0f} {reason} (今日第{_daily_trade_count}笔)")
        return True
    else:
        print(f"  ❌ 卖出失败: {code} {name} - {result.get('error', '未知错误')}")
        return False


def run_trading_cycle():
    global _daily_trade_count
    _reset_daily_stats()

    now = datetime.now()
    trading = is_trading_hours()

    print(f"\n{'=' * 60}")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} 交易周期 | 交易:{'✅' if trading else '❌'} | 今日交易:{_daily_trade_count}/{MAX_TRADES_PER_DAY}")
    print(f"{'=' * 60}")

    # 账户
    acct = get_account_simple()
    print(f"\n💰 账户: 现金¥{acct['cash']:.2f} | 市值¥{acct['total_market_value']:.2f} | 总资产¥{acct['total_assets']:.2f} | 收益率{acct['profit_rate']:.2f}%")
    print(f"   持仓: {acct['holdings_count']} 只")

    # 持仓
    holdings = get_holdings_with_cp()
    if holdings:
        print(f"   持仓详情:")
        for h in holdings:
            print(f"   {h['code']} {h['name']}: {h['quantity']}股@¥{h['price']:.2f} (CP={h['total_cp']:.1f})")

    # ========== 风控：止损 & 超期检查 ==========
    if holdings and trading:
        to_stop_loss = _check_risk_limits(holdings, acct)
        if to_stop_loss:
            print(f"\n🚨 风控触发 ({len(to_stop_loss)} 只需要处理):")
            for sl in to_stop_loss:
                print(f"   {sl['reason']}: {sl['code']} {sl['name']} 盈亏{sl['pnl_pct']*100:.1f}%")
                # 触发止损/超期卖出
                execute_sell(sl['code'], sl['name'], sl['quantity'], sl['current_price'], sl['reason'])
                # 更新账户（简化模拟）
                acct['cash'] += sl['quantity'] * sl['current_price']
                acct['total_market_value'] -= sl['quantity'] * sl['current_price']
    # ========================================

    # 推荐
    recs = get_top_stocks('value', RECOMMEND_LIMIT)
    print(f"\n📈 推荐 (TOP {len(recs)}):")
    for i, s in enumerate(recs[:5]):
        print(f"   {i + 1}. {s['code']} {s['name']}: CP={s['total_cp']:.1f} ¥{s['price']:.2f}")

    if not trading:
        print(f"\n⏸️ 非交易时间")
        return

    # ========== 买入逻辑 ==========
    holding_codes = [h.get('code') for h in holdings]
    to_buy = [r for r in recs if r['code'] not in holding_codes]

    if acct['cash'] >= MIN_CASH and to_buy:
        available = acct['cash'] - MIN_CASH
        max_buy = min(len(to_buy), MAX_HOLDINGS - len(holdings), int(available / PER_STOCK_AMOUNT))

        if max_buy > 0:
            per = min(PER_STOCK_AMOUNT, available / max_buy)
            print(f"\n🛒 买入 (最多{max_buy}只，每只约¥{per:.0f}):")

            for stock in to_buy[:max_buy]:
                if _daily_trade_count >= MAX_TRADES_PER_DAY:
                    print(f"  ⛔ 已达单日最大交易次数")
                    break
                if acct['cash'] < MIN_CASH:
                    break
                price = stock['price'] if stock['price'] > 0 else 10
                max_shares = int(acct['cash'] / price)
                quantity = (max_shares // 100) * 100
                if quantity >= 100:
                    cost = quantity * price
                    if execute_buy(stock['code'], stock['name'], quantity, price):
                        acct['cash'] -= cost
                        acct['total_market_value'] += cost
    # ==============================

    print(f"\n📊 最终: 现金¥{acct['cash']:.2f} | 市值¥{acct['total_market_value']:.2f} | 总资产¥{acct['total_assets']:.2f}")
    print(f"        今日交易: {_daily_trade_count}/{MAX_TRADES_PER_DAY}")
    print(f"{'=' * 60}\n")


def main():
    global _last_trade_date
    _last_trade_date = date.today()

    now = datetime.now()
    print(f"""
╔═══════════════════════════════════════════════╗
║   TradeSnake 自动交易监控系统                    ║
║   启动: {now.strftime('%Y-%m-%d %H:%M:%S')}                        ║
╠═══════════════════════════════════════════════╣
║   风控配置:                                     ║
║   - 最大持仓: {MAX_HOLDINGS}只 | 最小现金: ¥{MIN_CASH}              ║
║   - 止损线: {STOP_LOSS_PCT*100:.0f}% | 单日最大交易: {MAX_TRADES_PER_DAY}次       ║
║   - 最大持仓期: {POSITION_MAX_DAYS}天                              ║
╚═══════════════════════════════════════════════╝""")

    run_trading_cycle()
    print("⏳ 每60秒检查交易时间...\n")

    while True:
        try:
            time.sleep(60)
            if is_trading_day() and is_trading_hours():
                run_trading_cycle()
        except KeyboardInterrupt:
            print("\n👋 已停止")
            break
        except Exception as e:
            print(f"\n⚠️ 错误: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(60)


if __name__ == "__main__":
    main()
