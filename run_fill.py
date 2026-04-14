#!/usr/bin/env python
import sys
sys.stdout = sys.stderr  # Force unbuffered

print('Step 1: ExRightFactorFiller', flush=True)
from backend.data_manager.filler import ExRightFactorFiller
f = ExRightFactorFiller()
r = f.fill_all(limit=200)
print(f'ExRightFactor: {r.success} success, {r.failed} failed', flush=True)

print('Step 2: KlineFiller', flush=True)
from backend.data_manager.filler import KlineFiller
f = KlineFiller()
r = f.fill_all(limit=100, days_back=730)
print(f'Kline: {r.success} success, {r.failed} failed', flush=True)

print('Step 3: MinuteKlineFiller', flush=True)
from backend.data_manager.filler import MinuteKlineFiller
f = MinuteKlineFiller()
r = f.fill_all(limit=200, days_back=2)
print(f'MinuteKline: {r.success} success, {r.failed} failed, {r.total_records} records', flush=True)

print('Step 4: FinancialHistoryFiller', flush=True)
from backend.data_manager.filler import FinancialHistoryFiller
f = FinancialHistoryFiller()
r = f.fill_all(limit=50)
print(f'FinancialHistory: {r.success} success, {r.failed} failed', flush=True)

print('Step 5: CleanupScheduler', flush=True)
from backend.data_manager.cleanup import CleanupScheduler
cs = CleanupScheduler()
cs.run()
print('Cleanup done', flush=True)

print('Step 6: Restarting uvicorn', flush=True)
import subprocess
subprocess.run('nohup conda run -n tradesnake python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 > /tmp/uvicorn.log 2>&1 &', shell=True)
import time
time.sleep(3)
result = subprocess.run('curl -s http://localhost:8001/health', shell=True, capture_output=True, text=True)
print(f'Health: {result.stdout}', flush=True)
print('ALL DONE', flush=True)