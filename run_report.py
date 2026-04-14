#!/usr/bin/env python
"""自动交易报告 - 单次运行"""
import sys
import os
sys.path.insert(0, '/home/ailearn/projects/TradeSnake')

import json
import sqlite3
from datetime import datetime, date

os.chdir('/home/ailearn/projects/TradeSnake')

def is_trading_day():
    return date.today().weekday() < 5

def is_trading_hours():
    now = datetime.now()
    m = now.hour * 60 + now.minute
    return (9*60+30 <= m <= 11*60+30) or (13*60 <= m <= 15*60)


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

    # 单独查询价格
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

def get_price_map():
    """获取所有股票价格映射"""
    conn = sqlite3.connect('data/tradesnake.db')
    cursor = conn.cursor()
    cursor.execute('SELECT code, price FROM stocks WHERE price > 0')
    rows = cursor.fetchall()
    conn.close()

    price_map = {}
    for code, price in rows:
        price_map[code] = price
        # 也存去掉前缀的版本
        normalized = code.replace('sh', '').replace('sz', '')
        price_map[normalized] = price
    return price_map

def main():
    now = datetime.now()
    trading = is_trading_hours()

    print("=" * 60)
    print(f"TradeSnake 自动交易报告")
    print(f"时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"交易日: {'是' if is_trading_day() else '否'}")
    print(f"交易时间: {'是' if trading else '否'}")
    print("=" * 60)

    # 账户
    from backend.simulator.account import Account
    acct = Account().get_summary()
    print(f"\n账户状态:")
    print(f"  现金: ¥{acct.get('cash', 0):.2f}")
    print(f"  总资产: ¥{acct.get('total_assets', 0):.2f}")
    print(f"  收益率: {acct.get('profit_rate', 0):.2f}%")

    from backend.simulator.portfolio import Portfolio
    holdings = Portfolio().get_holdings()
    print(f"  持仓: {len(holdings)} 只")

    # 推荐
    recs = get_top_stocks('value', 10)
    print(f"\n推荐股票 (价值型 TOP {len(recs)}):")
    print(f"{'代码':<12} {'名称':<10} {'CP':<8} {'价值':<8} {'风险':<8} {'价格':<8}")
    print("-" * 60)
    for s in recs:
        print(f"{s['code']:<12} {s['name']:<10} {s['total_cp']:<8.1f} {s['value']:<8.1f} {s['risk']:<8.1f} ¥{s['price']:<8.2f}")

    if holdings:
        print(f"\n当前持仓 ({len(holdings)} 只):")
        for h in holdings[:5]:
            print(f"  {h.get('code')} {h.get('name')}: {h.get('quantity')}股")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
