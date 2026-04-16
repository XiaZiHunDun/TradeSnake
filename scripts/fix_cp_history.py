#!/usr/bin/env python3
import sqlite3
import os
from datetime import date

os.chdir('/home/ailearn/projects/TradeSnake')

today = date.today().strftime('%Y-%m-%d')
print(f'Saving full cp_history for {today}...')

conn = sqlite3.connect('data/tradesnake.db')
cur = conn.cursor()
cur.execute('''
    SELECT code, name, price, total_cp, growth_score, value_score, quality_score,
           momentum_score, risk_score
    FROM stocks WHERE total_cp > 0 ORDER BY total_cp DESC
''')
stocks = []
for row in cur.fetchall():
    stocks.append({
        'code': row[0], 'name': row[1], 'price': row[2], 'total_cp': row[3],
        'growth_score': row[4], 'value_score': row[5], 'quality_score': row[6],
        'momentum_score': row[7], 'risk_score': row[8],
    })
conn.close()
print(f'Total: {len(stocks)} stocks')

hist_conn = sqlite3.connect('data/tradesnake_cp_history.db')
hist_cur = hist_conn.cursor()
hist_cur.execute('DELETE FROM cp_history WHERE recorded_at = ?', (today,))
stocks.sort(key=lambda x: x['total_cp'], reverse=True)
for rank, s in enumerate(stocks, 1):
    hist_cur.execute('''
        INSERT INTO cp_history (code, name, price, total_cp, growth_score, value_score,
                               quality_score, momentum_score, risk_score, rank, recorded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (s['code'], s['name'], s['price'], s['total_cp'], s['growth_score'],
          s['value_score'], s['quality_score'], s['momentum_score'],
          s['risk_score'], rank, today))
hist_conn.commit()
hist_cur.execute('SELECT COUNT(*) FROM cp_history WHERE recorded_at = ?', (today,))
print(f'Verified: {hist_cur.fetchone()[0]} records for {today}')
hist_conn.close()
