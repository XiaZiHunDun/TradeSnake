#!/usr/bin/env python3
"""
Fix today's cp_history by fetching current CP from DuckDB and combining with saved CP scores
"""
import sqlite3
import duckdb
import os
from datetime import date, timedelta

os.chdir('/home/ailearn/projects/TradeSnake')

today = date.today().strftime('%Y-%m-%d')
yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
print(f'Fixing cp_history for {today}...')

# Get DuckDB stock data (has the current CP calculations)
dconn = duckdb.connect('data/historical.duckdb', read_only=True)

# Get all stock codes from DuckDB
duckdb_codes = {r[0] for r in dconn.execute('SELECT DISTINCT code FROM daily_kline').fetchall()}
print(f'DuckDB stocks: {len(duckdb_codes)}')

dconn.close()

# Get CP scores from cp_history (most recent available data)
hist_conn = sqlite3.connect('data/tradesnake_cp_history.db')
hist_cur = hist_conn.cursor()

# Dynamically find the most recent cp_history date
hist_cur.execute("SELECT recorded_at FROM cp_history ORDER BY recorded_at DESC LIMIT 1")
latest_row = hist_cur.fetchone()
if not latest_row:
    print("Error: No cp_history data found")
    hist_conn.close()
    exit(1)
latest_cp_date = latest_row[0]
print(f"Using cp_history from: {latest_cp_date}")

# Get most recent full cp data
hist_cur.execute('''
    SELECT code, name, price, total_cp, growth_score, value_score,
           quality_score, momentum_score, risk_score
    FROM cp_history WHERE recorded_at = ?
''', (latest_cp_date,))
yesterday_cp = {}
for row in hist_cur.fetchall():
    yesterday_cp[row[0]] = {
        'name': row[1],
        'price': row[2],
        'total_cp': row[3],
        'growth_score': row[4],
        'value_score': row[5],
        'quality_score': row[6],
        'momentum_score': row[7],
        'risk_score': row[8],
    }

hist_conn.close()
print(f'Yesterday CP data: {len(yesterday_cp)} stocks')

# Get current DuckDB prices
dconn = duckdb.connect('data/historical.duckdb', read_only=True)

# Get latest prices
price_query = '''
SELECT code, close FROM daily_kline dk1
WHERE trade_date = (SELECT MAX(trade_date) FROM daily_kline dk2 WHERE dk2.code = dk1.code)
'''
price_rows = dconn.execute(price_query).fetchall()
current_prices = {r[0]: float(r[1]) for r in price_rows if r[1] is not None}
print(f'Current prices: {len(current_prices)}')

dconn.close()

# Build stock list from yesterday's CP + current prices
stocks = []
for code, data in yesterday_cp.items():
    norm_code = code[2:] if code.startswith('sh') or code.startswith('sz') else code
    price = current_prices.get(norm_code, data['price'])

    stocks.append({
        'code': code,
        'name': data['name'],
        'price': price,
        'total_cp': data['total_cp'],
        'growth_score': data['growth_score'],
        'value_score': data['value_score'],
        'quality_score': data['quality_score'],
        'momentum_score': data['momentum_score'],
        'risk_score': data['risk_score'],
    })

print(f'Total stocks to save: {len(stocks)}')

# Save to cp_history
hist_conn = sqlite3.connect('data/tradesnake_cp_history.db')
hist_cur = hist_conn.cursor()

# Delete today's existing records
hist_cur.execute('DELETE FROM cp_history WHERE recorded_at = ?', (today,))

# Sort by CP descending
stocks.sort(key=lambda x: x['total_cp'], reverse=True)

# Insert
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
count = hist_cur.fetchone()[0]
print(f'Saved {count} records for {today}')

# Verify top 5
hist_cur.execute('''
    SELECT code, name, total_cp FROM cp_history
    WHERE recorded_at = ?
    ORDER BY total_cp DESC LIMIT 5
''', (today,))
print('TOP 5:')
for row in hist_cur.fetchall():
    print(f'  {row[0]} {row[1]}: {row[2]}')

hist_conn.close()
