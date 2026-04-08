"""
数据获取器 - TradeSnake Data Fetcher
====================================
多数据源 + 缓存 + 智能选择 + 重试机制
"""

import os
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)

import akshare as ak
import requests
import pandas as pd
import re
import time
import json
import hashlib
import threading
import baostock as bs
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import OrderedDict

# ==================== 常量配置 ====================
MAX_RETRIES = 3
RETRY_DELAY = 1
CACHE_DIR = "/home/ailearn/projects/TradeSnake/data"
CACHE_EXPIRE_MINUTES = 5

# ==================== 内存缓存（LRU）====================

class MemoryCache:
    """线程安全的内存LRU缓存"""

    def __init__(self, maxsize: int = 128, ttl_seconds: int = 60):
        self._cache = OrderedDict()
        self._timestamps = {}
        self._maxsize = maxsize
        self._ttl = ttl_seconds
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[any]:
        with self._lock:
            if key not in self._cache:
                return None
            if time.time() - self._timestamps[key] > self._ttl:
                del self._cache[key]
                del self._timestamps[key]
                return None
            self._cache.move_to_end(key)
            return self._cache[key]

    def set(self, key: str, value: any):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            else:
                if len(self._cache) >= self._maxsize:
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                    del self._timestamps[oldest]
            self._cache[key] = value
            self._timestamps[key] = time.time()

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()


_memory_cache = MemoryCache(maxsize=256, ttl_seconds=30)


# ==================== 工具函数 ====================

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def get_cache_path(cache_type: str) -> str:
    ensure_dir(CACHE_DIR)
    return os.path.join(CACHE_DIR, f"{cache_type}_cache.json")


def read_cache(cache_type: str) -> Optional[Dict]:
    mem_value = _memory_cache.get(cache_type)
    if mem_value is not None:
        return mem_value

    cache_file = get_cache_path(cache_type)
    if not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        expire_time = datetime.fromisoformat(cache.get('expire_at', '2000-01-01'))
        if datetime.now() > expire_time:
            return None
        data = cache.get('data')
        if data is not None:
            _memory_cache.set(cache_type, data)
        return data
    except Exception as e:
        print(f"读取缓存失败 {cache_type}: {e}")
        return None


def write_cache(cache_type: str, data: Dict, expire_minutes: int = CACHE_EXPIRE_MINUTES):
    _memory_cache.set(cache_type, data)
    cache_file = get_cache_path(cache_type)
    try:
        cache = {
            'data': data,
            'expire_at': (datetime.now() + timedelta(minutes=expire_minutes)).isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        print(f"缓存写入失败: {e}")


def md5_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:8]


# ==================== 股票列表获取 ====================

class StockListFetcher:
    """股票列表获取器"""

    def __init__(self):
        self._cache = None

    def get_stock_list(self, force_refresh: bool = False) -> pd.DataFrame:
        if self._cache is not None and not force_refresh:
            return self._cache

        if not force_refresh:
            cached = read_cache('stock_list')
            if cached is not None:
                self._cache = pd.DataFrame(cached)
                return self._cache

        try:
            df = ak.stock_info_a_code_name()
            self._cache = df
            write_cache('stock_list', df.to_dict('records'), expire_minutes=60 * 24)
            return df
        except Exception as e:
            print(f"获取股票列表失败: {e}")
            cached = read_cache('stock_list')
            if cached is not None:
                self._cache = pd.DataFrame(cached)
                return self._cache
            return pd.DataFrame()

    def get_market_cap_leaders(self, limit: int = 50) -> List[str]:
        try:
            cached = read_cache('top_volume')
            if cached:
                return cached[:limit]

            df = ak.stock_zh_a_spot_em()
            if df is not None and len(df) > 0:
                if '成交额' in df.columns:
                    df = df.sort_values('成交额', ascending=False)
                    top_codes = df['代码'].head(limit).tolist()
                    write_cache('top_volume', top_codes, expire_minutes=60)
                    return top_codes
        except Exception as e:
            print(f"获取市值排名失败: {e}")
        return []


# ==================== 行情数据获取 ====================

class MarketDataFetcher:
    """行情数据获取器（支持多数据源）"""

    def __init__(self):
        self.stock_list_fetcher = StockListFetcher()
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def get_market_data(self, codes: List[str], use_cache: bool = True) -> List[Dict]:
        if not codes:
            return []

        cache_key = md5_hash(','.join(sorted(codes)))

        if use_cache:
            cached = read_cache(f'market_{cache_key}')
            if cached:
                return cached

        data = self._fetch_from_tencent(codes)
        if data:
            write_cache(f'market_{cache_key}', data, expire_minutes=CACHE_EXPIRE_MINUTES)
            return data

        data = self._fetch_from_sina(codes)
        if data:
            write_cache(f'market_{cache_key}', data, expire_minutes=CACHE_EXPIRE_MINUTES)
            return data

        return []

    def _fetch_from_tencent(self, codes: List[str]) -> List[Dict]:
        tencent_codes = []
        for code in codes:
            code = str(code).strip()
            if code.startswith(('sh', 'sz')):
                tencent_codes.append(code)
            elif code.startswith('6'):
                tencent_codes.append(f'sh{code}')
            else:
                tencent_codes.append(f'sz{code}')

        codes_str = ','.join(tencent_codes)
        url = f"https://qt.gtimg.cn/q={codes_str}"

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                r = self._session.get(url, timeout=10)
                r.encoding = 'gbk'
                return self._parse_tencent_data(r.text)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))

        print(f"  腾讯API获取失败: {last_error}")
        return []

    def _fetch_from_sina(self, codes: List[str]) -> List[Dict]:
        sina_codes = []
        for code in codes:
            code = str(code).strip()
            if code.startswith(('sh', 'sz')):
                sina_codes.append(code)
            elif code.startswith('6'):
                sina_codes.append(f'sh{code}')
            else:
                sina_codes.append(f'sz{code}')

        codes_str = ','.join(sina_codes)
        url = f"https://hq.sinajs.cn/list={codes_str}"

        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn'
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                r = requests.get(url, headers=headers, timeout=10)
                r.encoding = 'gbk'
                return self._parse_sina_data(r.text)
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))

        print(f"  新浪API获取失败: {last_error}")
        return []

    def _parse_tencent_data(self, data: str) -> List[Dict]:
        stocks = []
        lines = data.strip().split('\n')

        for line in lines:
            if not line.strip():
                continue

            match = re.search(r'v_(\w+)="(.+)"', line)
            if not match:
                continue

            code = match.group(1)
            fields = match.group(2).split('~')

            if len(fields) < 40:
                continue

            try:
                price = float(fields[3]) if fields[3] and fields[3] != '-' else 0
                yesterday = float(fields[4]) if fields[4] and fields[4] != '-' else 0
                change_pct = ((price - yesterday) / yesterday * 100) if yesterday > 0 else 0

                market_cap = 0
                if len(fields) > 44 and fields[44] and fields[44] != '-':
                    try:
                        market_cap = float(fields[44])
                    except Exception:
                        pass

                stocks.append({
                    'code': code,
                    'name': fields[1] if len(fields) > 1 else '',
                    'price': price,
                    'yesterday': yesterday,
                    'open': float(fields[5]) if fields[5] and fields[5] != '-' else 0,
                    'high': float(fields[33]) if len(fields) > 33 and fields[33] and fields[33] != '-' else 0,
                    'low': float(fields[34]) if len(fields) > 34 and fields[34] and fields[34] != '-' else 0,
                    'volume': int(fields[6]) if fields[6] and fields[6] != '-' else 0,
                    'amount': float(fields[37]) if len(fields) > 37 and fields[37] and fields[37] != '-' else 0,
                    'pe': float(fields[39]) if len(fields) > 39 and fields[39] and fields[39] != '-' else 0,
                    'pb': float(fields[46]) if len(fields) > 46 and fields[46] and fields[46] != '-' else 0,
                    'change_pct': round(change_pct, 2),
                    'market_cap': round(market_cap, 2),
                    'source': 'tencent'
                })
            except Exception:
                continue

        return stocks

    def _parse_sina_data(self, data: str) -> List[Dict]:
        stocks = []
        lines = data.strip().split('\n')

        for line in lines:
            if not line.strip():
                continue

            match = re.search(r'var hq_str_(\w+)="(.+)"', line)
            if not match:
                continue

            code = match.group(1)
            fields = match.group(2).split(',')

            if len(fields) < 32:
                continue

            try:
                price = float(fields[3]) if fields[3] and fields[3] != '-' else 0
                yesterday = float(fields[2]) if fields[2] and fields[2] != '-' else 0
                change_pct = ((price - yesterday) / yesterday * 100) if yesterday > 0 else 0

                stocks.append({
                    'code': code,
                    'name': fields[0] if fields[0] else '',
                    'price': price,
                    'yesterday': yesterday,
                    'open': float(fields[1]) if fields[1] and fields[1] != '-' else 0,
                    'high': float(fields[4]) if len(fields) > 4 and fields[4] and fields[4] != '-' else 0,
                    'low': float(fields[5]) if len(fields) > 5 and fields[5] and fields[5] != '-' else 0,
                    'volume': int(float(fields[8])) if len(fields) > 8 and fields[8] and fields[8] != '-' else 0,
                    'amount': float(fields[9]) if len(fields) > 9 and fields[9] and fields[9] != '-' else 0,
                    'pe': float(fields[39]) if len(fields) > 39 and fields[39] and fields[39] != '-' else 0,
                    'pb': 0,
                    'change_pct': round(change_pct, 2),
                    'market_cap': 0,
                    'source': 'sina'
                })
            except Exception:
                continue

        return stocks


# ==================== 财务数据获取 ====================

class FinancialDataFetcher:
    """财务数据获取器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://data.eastmoney.com/'
        })

    def get_financial_data(self, symbol: str, use_cache: bool = True) -> Dict:
        cache_key = f"fin_{symbol}"

        if use_cache:
            cached = read_cache(cache_key)
            if cached:
                return cached

        if symbol.startswith('6'):
            market = 'SH'
        else:
            market = 'SZ'

        em_data = self._fetch_from_eastmoney(symbol, market)
        bs_data = self._fetch_from_baostock(symbol)

        if em_data and bs_data:
            result = em_data.copy()
            if result.get('gross_margin', 0) == 0 and bs_data.get('gross_margin', 0) > 0:
                result['gross_margin'] = bs_data['gross_margin']
            if result.get('revenue', 0) == 0 and bs_data.get('revenue', 0) > 0:
                result['revenue'] = bs_data['revenue']
            if result.get('debt_ratio', 0) == 0 and bs_data.get('debt_ratio', 0) > 0:
                result['debt_ratio'] = bs_data['debt_ratio']
            if result.get('cashflow', 0) == 0 and bs_data.get('cashflow', 0) != 0:
                result['cashflow'] = bs_data['cashflow']
            if bs_data.get('dividend_per_share'):
                result['dividend_per_share'] = bs_data['dividend_per_share']
            result['source'] = 'eastmoney+baostock'
        elif em_data:
            result = em_data
        elif bs_data:
            result = bs_data
        else:
            result = None

        try:
            df_ak = ak.stock_financial_analysis_indicator(symbol=symbol, start_year='2023')
            if df_ak is not None and len(df_ak) > 0:
                latest_ak = df_ak.iloc[-1]
                if result is None:
                    result = {}
                current_ratio = latest_ak.get('流动比率', 0)
                if current_ratio is not None and str(current_ratio) != 'nan':
                    result['current_ratio'] = round(float(current_ratio), 2)
                interest_coverage = latest_ak.get('利息支付倍数', 0)
                if interest_coverage is not None and str(interest_coverage) != 'nan':
                    result['interest_coverage'] = round(float(interest_coverage), 2)
                deducted_net_profit = latest_ak.get('扣除非经常性损益后的净利润(元)', 0)
                if deducted_net_profit is not None and str(deducted_net_profit) != 'nan':
                    result['deducted_net_profit'] = round(float(deducted_net_profit) / 100000000, 2)
        except Exception as e:
            print(f"  akshare补充字段失败 {symbol}: {e}")

        if result:
            write_cache(cache_key, result, expire_minutes=60 * 24)
            return result

        return {
            'roe': 0, 'net_profit_growth': 0, 'revenue_growth': 0,
            'gross_margin': 0, 'revenue': 0, 'cashflow': 0, 'debt_ratio': 0,
            'current_ratio': 0, 'interest_coverage': 0, 'deducted_net_profit': 0,
            'dividend_yield': 0, 'turnover_rate': 0,
            'data_quality': 'low', 'source': 'none'
        }

    def _fetch_from_eastmoney(self, symbol: str, market: str) -> Optional[Dict]:
        url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        params = {
            "reportName": "RPT_LICO_FN_CPD",
            "columns": "WEIGHTAVG_ROE,YSTZ,SJLTZ",
            "filter": f"(SECUCODE=\"{symbol}.{market}\")",
            "pageNumber": 1,
            "pageSize": 1,
            "sortTypes": -1,
            "sortColumns": "REPORTDATE",
            "source": "DataCenter",
            "client": "PC"
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                r = self.session.get(url, params=params, timeout=10)
                result = r.json()

                if result.get('result') and result['result'].get('data'):
                    d = result['result']['data'][0]
                    return {
                        'roe': round(float(d.get('WEIGHTAVG_ROE', 0) or 0), 2),
                        'net_profit_growth': round(float(d.get('SJLTZ', 0) or 0), 2),
                        'revenue_growth': round(float(d.get('YSTZ', 0) or 0), 2),
                        'gross_margin': 0, 'revenue': 0, 'cashflow': 0, 'debt_ratio': 0,
                        'dividend_yield': 0, 'data_quality': 'high', 'source': 'eastmoney'
                    }
                return None
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))

        print(f"  东方财富财务API失败 {symbol}: {last_error}")
        return None

    def _fetch_from_baostock(self, symbol: str) -> Optional[Dict]:
        try:
            if symbol.startswith('6'):
                baostock_code = f'sh.{symbol}'
            else:
                baostock_code = f'sz.{symbol}'

            lg = bs.login()
            if lg.error_code != '0':
                bs.logout()
                return None

            result = {
                'roe': 0, 'net_profit_growth': 0, 'revenue_growth': 0,
                'gross_margin': 0, 'revenue': 0, 'cashflow': 0, 'debt_ratio': 0,
                'dividend_yield': 0, 'data_quality': 'low', 'source': 'baostock'
            }

            try:
                rs = bs.query_profit_data(code=baostock_code, year=2024, quarter=4)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        roe = row.get('roeAvg')
                        if roe is not None and str(roe) != '' and str(roe) != 'nan':
                            result['roe'] = round(float(roe) * 100, 2)
                        gp = row.get('gpMargin')
                        if gp is not None and str(gp) != '' and str(gp) != 'nan':
                            result['gross_margin'] = round(float(gp) * 100, 2)
                        mbrevenue = row.get('MBRevenue')
                        if mbrevenue is not None and str(mbrevenue) != '' and str(mbrevenue) != 'nan':
                            result['revenue'] = round(float(mbrevenue) / 100000000, 2)
            except Exception as e:
                print(f"  baostock盈利能力获取失败 {symbol}: {e}")

            try:
                rs = bs.query_growth_data(code=baostock_code, year=2024, quarter=4)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        yoyni = row.get('YOYNI')
                        if yoyni is not None and str(yoyni) != '' and str(yoyni) != 'nan':
                            result['net_profit_growth'] = round(float(yoyni) * 100, 2)
                        yoyor = row.get('YOYOR')
                        if yoyor is not None and str(yoyor) != '' and str(yoyor) != 'nan':
                            result['revenue_growth'] = round(float(yoyor) * 100, 2)
            except Exception as e:
                print(f"  baostock成长能力获取失败 {symbol}: {e}")

            try:
                rs = bs.query_balance_data(code=baostock_code, year=2024, quarter=4)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        asset_to_equity = row.get('assetToEquity')
                        if asset_to_equity is not None and str(asset_to_equity) != '' and str(asset_to_equity) != 'nan':
                            ate = float(asset_to_equity)
                            if ate > 0:
                                result['debt_ratio'] = round((1 - 1/ate) * 100, 2)
            except Exception as e:
                print(f"  baostock资产负债表获取失败 {symbol}: {e}")

            try:
                rs = bs.query_cash_flow_data(code=baostock_code, year=2024, quarter=4)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        cfo_to_np = row.get('CFOToNP')
                        cfo_ratio = None
                        if cfo_to_np is not None and str(cfo_to_np) != '' and str(cfo_to_np) != 'nan':
                            cfo_ratio = float(cfo_to_np)
                        elif cfo_to_np is not None and str(cfo_to_np) == '':
                            cfo_to_or = row.get('CFOToOR')
                            if cfo_to_or is not None and str(cfo_to_or) != '' and str(cfo_to_or) != 'nan':
                                cfo_ratio = float(cfo_to_or)
                        if cfo_ratio is not None and cfo_ratio > 0:
                            result['cashflow'] = 1
                        elif cfo_ratio is not None and cfo_ratio < 0:
                            result['cashflow'] = -1
            except Exception as e:
                print(f"  baostock现金流获取失败 {symbol}: {e}")

            try:
                rs = bs.query_dividend_data(code=baostock_code, year=2024)
                if rs.error_code == '0':
                    data = rs.get_data()
                    if len(data) > 0:
                        row = data.iloc[-1]
                        dividend_ps = row.get('dividCashPsBeforeTax')
                        if dividend_ps is not None and str(dividend_ps) != '' and str(dividend_ps) != 'nan':
                            result['dividend_per_share'] = round(float(dividend_ps), 2)
            except Exception as e:
                print(f"  baostock股息数据获取失败 {symbol}: {e}")

            bs.logout()

            if result['roe'] > 0 or result['net_profit_growth'] != 0:
                result['data_quality'] = 'medium'

            return result

        except Exception as e:
            try:
                bs.logout()
            except:
                pass
            print(f"  baostock获取财务数据失败 {symbol}: {e}")
            return None


# ==================== 主数据获取器 ====================

class StockDataFetcher:
    """综合股票数据获取器"""

    def __init__(self):
        self.market_fetcher = MarketDataFetcher()
        self.financial_fetcher = FinancialDataFetcher()
        self.stock_list_fetcher = StockListFetcher()
        self._industry_mapping = None  # 行业映射缓存

    def get_stock_list(self) -> pd.DataFrame:
        return self.stock_list_fetcher.get_stock_list()

    def _get_industry_mapping(self) -> Dict[str, str]:
        """获取股票行业映射（从Tushare） v18.2"""
        if self._industry_mapping is not None:
            return self._industry_mapping

        self._industry_mapping = {}

        # 尝试从Tushare获取
        try:
            from .providers.tushare import get_tushare_provider, TushareProvider
            provider = get_tushare_provider()
            if provider is None:
                # 直接实例化
                provider = TushareProvider()
            stock_list = provider.get_stock_list()
            if stock_list:
                for item in stock_list:
                    symbol = item.get('symbol', '')
                    industry = item.get('industry', '')
                    if symbol and industry:
                        self._industry_mapping[symbol] = industry
            else:
                raise ValueError('Empty stock list')
        except Exception as e:
            print(f"获取行业映射失败: {e}")

        # 如果Tushare不可用，尝试从缓存读取
        if not self._industry_mapping:
            try:
                cached = read_cache('stock_industry')
                if cached:
                    self._industry_mapping = {item['code']: item['industry'] for item in cached}
            except:
                pass

        return self._industry_mapping

    def _get_sector(self, code: str) -> str:
        """根据股票代码获取行业"""
        # 提取纯代码
        clean_code = code.upper().replace('SH', '').replace('SZ', '')

        mapping = self._get_industry_mapping()
        return mapping.get(clean_code, '')

    def get_market_data_tencent(self, codes: List[str]) -> List[Dict]:
        return self.market_fetcher.get_market_data(codes)

    def get_batch_market_data(self, limit: int = 300, prefer_top: bool = True, page: int = 0) -> List[Dict]:
        stock_df = self.stock_list_fetcher.get_stock_list()

        main_stocks = stock_df[
            stock_df['code'].str.startswith(('6', '0')) &
            ~stock_df['name'].str.contains('ST', na=False)
        ]

        if prefer_top and page == 0:
            top_codes = self.stock_list_fetcher.get_market_cap_leaders(limit * 2)
            if top_codes:
                available = main_stocks[main_stocks['code'].isin(top_codes)]
                if len(available) >= limit:
                    sample = available.head(limit)
                else:
                    remaining = main_stocks[~main_stocks['code'].isin(top_codes)]
                    needed = limit - len(available)
                    sample = pd.concat([available, remaining.head(needed)])
            else:
                sample = main_stocks.sample(n=min(limit, len(main_stocks)), random_state=42)
        else:
            seed = 42 + page * 17
            sample = main_stocks.sample(n=min(limit, len(main_stocks)), random_state=seed)

        all_data = []
        batch_size = 50
        failed_batches = 0

        for i in range(0, len(sample), batch_size):
            batch = sample.iloc[i:i+batch_size]
            codes = batch['code'].tolist()
            try:
                market_data = self.market_fetcher.get_market_data(codes)
                if market_data:
                    all_data.extend(market_data)
                else:
                    failed_batches += 1
            except Exception as e:
                failed_batches += 1
            time.sleep(0.05)

        if failed_batches > 0 and len(all_data) == 0:
            print(f"  警告: 所有批次获取失败，共 {failed_batches} 个批次")

        return all_data

    def get_full_stock_data(self, limit: int = 100, prefer_top: bool = True, page: int = 0) -> List[Dict]:
        """获取完整股票数据（市场+财务+行业） v18.2"""
        market_data = self.get_batch_market_data(limit, prefer_top, page=page)

        full_data = []
        success_count = 0
        fail_count = 0

        # 预加载行业映射
        self._get_industry_mapping()

        for mkt in market_data:
            code = mkt.get('code', '')
            if not code:
                continue

            if code.startswith('sh'):
                symbol = code[2:]
            elif code.startswith('sz'):
                symbol = code[2:]
            else:
                continue

            fin = self.financial_fetcher.get_financial_data(symbol)

            price = mkt.get('price', 0)
            dividend_per_share = fin.get('dividend_per_share', 0)
            dividend_yield = 0
            if price > 0 and dividend_per_share > 0:
                dividend_yield = round(dividend_per_share / price * 100, 2)

            data = {
                'code': code,
                'name': mkt.get('name', ''),
                'price': price,
                'yesterday': mkt.get('yesterday', 0),
                'open': mkt.get('open', 0),
                'high': mkt.get('high', 0),
                'low': mkt.get('low', 0),
                'volume': mkt.get('volume', 0),
                'amount': mkt.get('amount', 0),
                'pe': mkt.get('pe', 0),
                'pb': mkt.get('pb', 0),
                'change_pct': mkt.get('change_pct', 0),
                'market_cap': mkt.get('market_cap', 0),
                'roe': fin.get('roe', 0),
                'net_profit_growth': fin.get('net_profit_growth', 0),
                'revenue_growth': fin.get('revenue_growth', 0),
                'gross_margin': fin.get('gross_margin', 0),
                'revenue': fin.get('revenue', 0),
                'cashflow': fin.get('cashflow', 0),
                'debt_ratio': fin.get('debt_ratio', 0),
                'dividend_yield': dividend_yield,
                'data_quality': fin.get('data_quality', 'low'),
                'data_source': mkt.get('source', 'unknown'),
                'sector': self._get_sector(symbol),  # 行业 v18.2
            }

            full_data.append(data)

            if fin.get('data_quality') in ('high', 'medium'):
                success_count += 1
            else:
                fail_count += 1

            time.sleep(0.1)

        if full_data:
            total = success_count + fail_count
            quality_rate = success_count / total * 100 if total > 0 else 0
            print(f"数据获取完成: 共{total}只, 高质量{success_count}只({quality_rate:.1f}%), 低质量{fail_count}只")

        return full_data


# ==================== 便捷函数 ====================

_global_fetcher = None
_global_fetcher_lock = threading.Lock()


def get_stock_data_api(limit: int = 100, page: int = 0) -> List[Dict]:
    global _global_fetcher
    if _global_fetcher is None:
        with _global_fetcher_lock:
            if _global_fetcher is None:
                _global_fetcher = StockDataFetcher()
    return _global_fetcher.get_full_stock_data(limit, page=page)


def get_single_stock_data(code: str) -> Optional[Dict]:
    """获取单只股票的完整数据 v18.2"""
    fetcher = StockDataFetcher()

    clean_code = code.upper().strip()
    if clean_code.startswith('SH'):
        clean_code = clean_code[2:]
    elif clean_code.startswith('SZ'):
        clean_code = clean_code[2:]

    if clean_code.startswith('6'):
        tencent_code = f'sh{clean_code}'
    else:
        tencent_code = f'sz{clean_code}'

    market_fetcher = MarketDataFetcher()
    market_data = market_fetcher.get_market_data([clean_code], use_cache=False)
    if not market_data:
        return None

    mkt = market_data[0]

    financial_fetcher = FinancialDataFetcher()
    fin = financial_fetcher.get_financial_data(clean_code, use_cache=False)

    price = mkt.get('price', 0)
    dividend_per_share = fin.get('dividend_per_share', 0)
    dividend_yield = 0
    if price > 0 and dividend_per_share > 0:
        dividend_yield = round(dividend_per_share / price * 100, 2)

    return {
        'code': tencent_code,
        'name': mkt.get('name', ''),
        'price': price,
        'open': mkt.get('open', 0),
        'yesterday': mkt.get('yesterday', 0),
        'high': mkt.get('high', 0),
        'low': mkt.get('low', 0),
        'volume': mkt.get('volume', 0),
        'amount': mkt.get('amount', 0),
        'pe': mkt.get('pe', 0),
        'pb': mkt.get('pb', 0),
        'change_pct': mkt.get('change_pct', 0),
        'market_cap': mkt.get('market_cap', 0),
        'roe': fin.get('roe', 0),
        'net_profit_growth': fin.get('net_profit_growth', 0),
        'revenue_growth': fin.get('revenue_growth', 0),
        'gross_margin': fin.get('gross_margin', 0),
        'revenue': fin.get('revenue', 0),
        'cashflow': fin.get('cashflow', 0),
        'debt_ratio': fin.get('debt_ratio', 0),
        'dividend_yield': dividend_yield,
        'data_quality': fin.get('data_quality', 'low'),
        'current_ratio': fin.get('current_ratio', 0),
        'interest_coverage': fin.get('interest_coverage', 0),
        'deducted_net_profit': fin.get('deducted_net_profit', 0),
        'sector': fetcher._get_sector(clean_code),  # 行业 v18.2
    }


# ==================== Tushare K线同步 ====================

def sync_klines_from_tushare(codes: List[str] = None, days: int = 365) -> Dict:
    """
    从Tushare同步K线数据到DuckDB

    Args:
        codes: 股票代码列表，默认全部
        days: 同步天数

    Returns:
        Dict: 同步结果统计
    """
    try:
        from .providers.tushare import get_tushare_provider
        from .duckdb_store import get_duckdb_store, KlineRecord
    except ImportError:
        return {'success': 0, 'failed': 0, 'error': '模块不可用'}

    provider = get_tushare_provider()
    if provider is None:
        return {'success': 0, 'failed': 0, 'error': 'Tushare不可用'}

    store = get_duckdb_store()
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

    # 获取股票列表
    if codes is None:
        stock_list = provider.get_stock_list()
        codes = [s['symbol'] for s in stock_list[:100]]  # 默认前100只

    success_count = 0
    failed_count = 0

    for code in codes:
        try:
            klines = provider.get_daily_kline(code, start_date, end_date)
            if not klines:
                failed_count += 1
                continue

            records = []
            for k in klines:
                records.append(KlineRecord(
                    code=code,
                    trade_date=k.get('trade_date', ''),
                    open=k.get('open', 0),
                    high=k.get('high', 0),
                    low=k.get('low', 0),
                    close=k.get('close', 0),
                    volume=k.get('volume', 0),
                    amount=k.get('amount', 0),
                    change_pct=k.get('change_pct', 0),
                    adj_close=k.get('close', 0)
                ))

            if records:
                store.insert_daily_klines_batch(records)
                success_count += 1

            time.sleep(0.06)  # 避免超过Tushare限制

        except Exception as e:
            failed_count += 1
            print(f"同步K线失败 {code}: {e}")

    return {
        'success': success_count,
        'failed': failed_count,
        'total': len(codes)
    }


def get_klines_from_duckdb(code: str, days: int = 30) -> List[Dict]:
    """
    从DuckDB获取K线数据

    Args:
        code: 股票代码
        days: 天数

    Returns:
        List[Dict]: K线数据列表
    """
    try:
        from .duckdb_store import get_duckdb_store
    except ImportError:
        return []

    store = get_duckdb_store()
    result = store.get_klines(code, limit=days)
    if result.success:
        return result.data.to_dict('records') if hasattr(result.data, 'to_dict') else []
    return []

