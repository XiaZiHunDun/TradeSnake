#!/usr/bin/env python
"""
自动交易脚本 - 完整版
"""
import sys
import os
sys.path.insert(0, '/home/ailearn/projects/TradeSnake')

import time
import sqlite3
from datetime import datetime, date

os.chdir('/home/ailearn/projects/TradeSnake')

# ==================== 配置 ====================
MAX_HOLDINGS = 3
PER_STOCK_AMOUNT = 3000
MIN_CASH = 2000
RECOMMEND_LIMIT = 10
# ====================

def is_trading_day():
    return date.today().weekday() < 5

def is_trading_hours():
    now = datetime.now()
    m = now.hour * 60 + now.minute
    return (9*60+30 <= m <= 11*60+30) or (13*60 <= m <= 15*60)

def get_price_map():
    conn = sqlite3.connect('data/tradesnake.db')
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

def get_top_stocks(category='value', limit=10):
    conn = sqlite3.connect('data/tradesnake.db')
    cursor = conn.cursor()
    if category == 'value':
        order_by = 'h.total_cp DESC'
    elif category == 'growth':
        order_by = 'h.growth_score DESC'
    else:
        order_by = 'h.total_cp DESC'
    cursor.execute(f"""
        SELECT h.code, h.name, h.total_cp, h.growth_score, h.value_score,
               h.quality_score, h.risk_score
        FROM cp_history h
        WHERE h.total_cp > 0
        ORDER BY {order_by}
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

def get_account_simple():
    """快速获取账户信息（不实时查询市值）"""
    from backend.simulator.database import get_db
    db = get_db()
    acct = db.get_account()
    holdings = db.get_holdings()

    # 计算持仓市值（使用数据库中的价格，不走网络）
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

    # 获取CP数据
    conn = sqlite3.connect('data/tradesnake.db')
    cursor = conn.cursor()
    cursor.execute('SELECT code, total_cp FROM cp_history')
    cp_map = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()

    # 标准化CP映射
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
    from backend.simulator.trader import Trader
    trader = Trader()
    result = trader.buy(code, quantity)
    if result.get('success'):
        print(f"  ✅ 买入: {code} {name} x{quantity} @ ¥{price:.2f} = ¥{quantity*price:.0f}")
        return True
    else:
        print(f"  ❌ 失败: {code} {name} - {result.get('error', '未知错误')}")
        return False

def run_trading_cycle():
    now = datetime.now()
    trading = is_trading_hours()

    print(f"\n{'='*60}")
    print(f"⏰ {now.strftime('%Y-%m-%d %H:%M:%S')} 交易周期 | 交易:{'✅' if trading else '❌'}")
    print(f"{'='*60}")

    # 账户（快速版）
    acct = get_account_simple()
    print(f"\n💰 账户: 现金¥{acct['cash']:.2f} | 市值¥{acct['total_market_value']:.2f} | 总资产¥{acct['total_assets']:.2f} | 收益率{acct['profit_rate']:.2f}%")
    print(f"   持仓: {acct['holdings_count']} 只")

    # 持仓
    holdings = get_holdings_with_cp()
    if holdings:
        for h in holdings:
            print(f"   {h['code']} {h['name']}: {h['quantity']}股@¥{h['price']:.2f} (CP={h['total_cp']:.1f})")

    # 推荐
    recs = get_top_stocks('value', RECOMMEND_LIMIT)
    print(f"\n📈 推荐 (TOP {len(recs)}):")
    for i, s in enumerate(recs[:5]):
        print(f"   {i+1}. {s['code']} {s['name']}: CP={s['total_cp']:.1f} ¥{s['price']:.2f}")

    if not trading:
        print(f"\n⏸️ 非交易时间")
        return

    # 交易
    holding_codes = [h.get('code') for h in holdings]
    to_buy = [r for r in recs if r['code'] not in holding_codes]

    if acct['cash'] >= MIN_CASH and to_buy:
        available = acct['cash'] - MIN_CASH
        max_buy = min(len(to_buy), MAX_HOLDINGS - len(holdings), int(available / PER_STOCK_AMOUNT))

        if max_buy > 0:
            per = min(PER_STOCK_AMOUNT, available / max_buy)
            print(f"\n🛒 买入 {max_buy} 只，每只约¥{per:.0f}:")

            for stock in to_buy[:max_buy]:
                if acct['cash'] < 1000:  # 至少需要1000现金
                    break
                price = stock['price'] if stock['price'] > 0 else 10
                # 计算可买的整手数量（基于实际现金）
                max_shares = int(acct['cash'] / price)  # 可买的股数
                quantity = (max_shares // 100) * 100  # 向下取整到整手
                if quantity >= 100:
                    cost = quantity * price
                    if execute_buy(stock['code'], stock['name'], quantity, price):
                        acct['cash'] -= cost
                        acct['total_market_value'] += cost

    print(f"\n📊 最终: 现金¥{acct['cash']:.2f} | 市值¥{acct['total_market_value']:.2f} | 总资产¥{acct['total_assets']:.2f}")
    print(f"{'='*60}\n")

def main():
    now = datetime.now()
    print(f"""
╔═══════════════════════════════════════════════╗
║   TradeSnake 自动交易监控系统                    ║
║   启动: {now.strftime('%Y-%m-%d %H:%M:%S')}                        ║
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
            time.sleep(60)

if __name__ == "__main__":
    main()
